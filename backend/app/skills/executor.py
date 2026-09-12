"""工具执行器 — 把 AgentToolRef 转成 OpenAI function-calling 规格并执行

- 内部 Skill：tool_type=skill，按 skill.handler 路由到 app/skills/handlers.py
- MCP 工具：tool_type=mcp_tool，tool_ref 形如 "<server_id>:<tool_name>"

工具在 LLM 侧的名称需要唯一，MCP 工具统一加 `mcp<server_id>_` 前缀，避免跨服务重名。

来源编号：处理函数只知道自己那几条来源（文本里的 [N] 指 sources[N-1]），
执行器知道「当前已经有几条来源」，由它统一改写成全局编号 ——
回答正文里的 [来源N] 与来源面板里的第 N 条因此必然指向同一条。
"""

import json
import re
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Dict, Any, Optional, Tuple

from app.models.skill import Skill
from app.schemas.agent import AgentToolRef
from app.skills.registry import get_handler

_NAME_SAFE = re.compile(r"[^A-Za-z0-9_-]")


def _safe_name(raw: str) -> str:
    """OpenAI 工具名只允许 [A-Za-z0-9_-]，长度 ≤ 64"""
    name = _NAME_SAFE.sub("_", raw)[:60]
    return name


async def build_tool_specs(
    db: AsyncSession, tool_refs: List[AgentToolRef]
) -> Tuple[List[Dict[str, Any]], Dict[str, AgentToolRef]]:
    """构造 function-calling 工具规格 + 名称到引用的映射

    返回 (tool_specs, name_to_ref)。引用失效的（skill 已删 / mcp 服务已删）直接跳过。
    """
    specs: List[Dict[str, Any]] = []
    name_map: Dict[str, AgentToolRef] = {}

    # 内部 Skill
    skill_ids = [t.tool_ref_id for t in tool_refs if t.tool_type == "skill" and t.tool_ref_id]
    skills: Dict[int, Skill] = {}
    if skill_ids:
        rows = (await db.execute(select(Skill).where(Skill.id.in_(skill_ids)))).scalars().all()
        skills = {s.id: s for s in rows}

    for t in tool_refs:
        if t.tool_type != "skill" or not t.tool_ref_id:
            continue
        s = skills.get(t.tool_ref_id)
        if s is None or not s.is_active:
            continue
        try:
            params = json.loads(s.input_schema) if s.input_schema else {"type": "object", "properties": {}}
        except Exception:
            params = {"type": "object", "properties": {}}
        name = _safe_name(s.name)
        specs.append({
            "type": "function",
            "function": {
                "name": name,
                "description": (s.description or s.title)[:1000],
                "parameters": params,
            },
        })
        name_map[name] = t

    # MCP 工具
    mcp_refs = [t for t in tool_refs if t.tool_type == "mcp_tool" and t.tool_ref]
    if mcp_refs:
        from app.services import mcp_service

        for t in mcp_refs:
            server, tool = await mcp_service.resolve_mcp_tool(db, t.tool_ref)  # type: ignore[arg-type]
            if server is None or tool is None or not server.is_active:
                continue
            name = _safe_name(f"mcp{server.id}_{tool.name}")
            specs.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": (tool.description or tool.title or tool.name)[:1000],
                    "parameters": tool.input_schema or {"type": "object", "properties": {}},
                },
            })
            name_map[name] = t

    return specs, name_map


def normalize_tool_result(raw: Any) -> Tuple[str, List[Dict[str, Any]]]:
    """归一化处理函数返回值

    - 返回 str：只有给 LLM 看的文本（大多数工具，行为与从前完全一致）
    - 返回 (str, list)：文本 + 结构化来源（如联网搜索的网页）
    """
    if isinstance(raw, tuple) and len(raw) == 2:
        text, sources = raw
        return str(text), [s for s in (sources or []) if isinstance(s, dict)]
    return str(raw), []


def source_label(source: Dict[str, Any]) -> str:
    """来源清单里显示的标题"""
    return str(source.get("title") or source.get("filename") or source.get("url") or "来源")


_CITATION_MARKER = re.compile(r"\[(\d{1,2})\]")


def renumber_citations(text: str, own_source_count: int, offset: int) -> str:
    """把工具文本里指向自己来源的 [N] 改写成全局编号 [来源offset+N]

    只改写落在 1..own_source_count 内的编号：正文里的 [2024]、[9] 不是引用标记，不能误伤。
    代价是「网页正文里恰好写成 [1]~[N] 的脚注」也会被改写 —— 换来的是外部服务
    自带的编号一定能被换掉，这个取舍写进了 ADR-0002。
    """

    def _sub(match: re.Match) -> str:
        n = int(match.group(1))
        return f"[来源{offset + n}]" if 1 <= n <= own_source_count else match.group(0)

    return _CITATION_MARKER.sub(_sub, text)


def source_list_block(sources: List[Dict[str, Any]], offset: int) -> str:
    """给模型看的来源清单：全局编号 + 标题 + 链接（模型据此在正文里引用）"""
    lines = ["【可引用的来源】"]
    for i, s in enumerate(sources, 1):
        lines.append(f"[来源{offset + i}: {source_label(s)}]")
        if s.get("url"):
            lines.append(f"    {s['url']}")
    return "\n".join(lines)


def apply_source_offset(text: str, sources: List[Dict[str, Any]], offset: int) -> str:
    """把工具结果改写成与来源面板同一套编号，并在末尾附上可引用清单"""
    if not sources:
        return text
    numbered = renumber_citations(text, len(sources), offset)
    return numbered + "\n\n" + source_list_block(sources, offset)


async def execute_tool_call(
    db: AsyncSession, ref: AgentToolRef, arguments: Dict[str, Any],
    kb_ids: Optional[List[int]] = None,
) -> Tuple[str, List[Dict[str, Any]]]:
    """执行单个工具调用，返回 (给 LLM 看的文本, 结构化来源列表)"""
    if ref.tool_type == "skill":
        result = await db.execute(select(Skill).where(Skill.id == ref.tool_ref_id))
        s = result.scalar_one_or_none()
        if s is None:
            return "工具不存在或已被删除", []
        handler = get_handler(s.handler or s.name)
        if handler is None:
            return "该工具没有可执行的处理函数", []
        try:
            return normalize_tool_result(await handler(arguments or {}))
        except Exception as e:
            return f"工具执行失败：{str(e)[:500]}", []

    if ref.tool_type == "mcp_tool" and ref.tool_ref:
        from app.services import mcp_service

        try:
            server_id_str, tool_name = ref.tool_ref.split(":", 1)
            server_id = int(server_id_str)
        except (ValueError, IndexError):
            return "MCP 工具引用格式错误", []
        try:
            # MCP 由外部服务返回纯文本，拿不到结构化来源 —— 不编造来源条目
            return await mcp_service.call_tool(db, server_id, tool_name, arguments or {}), []
        except Exception as e:
            detail = getattr(e, "detail", None) or str(e)
            return f"MCP 工具调用失败：{str(detail)[:500]}", []

    return "未知工具类型", []


async def run_tool_calls(
    db: AsyncSession, tool_calls: List[Dict[str, Any]], name_map: Dict[str, AgentToolRef],
    kb_ids: Optional[List[int]] = None, source_offset: int = 0,
) -> List[Dict[str, Any]]:
    """批量执行 tool_calls，返回可直接作为 ToolMessage 的结果列表

    每项形如 {"tool_call_id": ..., "name": ..., "content": ..., "sources": [...]}。
    source_offset 是**已有的来源条数**（如知识库来源）：工具带出的网页来源接着
    它往下编号，正文里的 [来源N] 与来源面板第 N 条因此是同一条。
    """
    results = []
    offset = source_offset
    for call in tool_calls:
        # 兼容两种 tool_call 形态：
        #   OpenAI 原始格式: {"function": {"name", "arguments"(JSON字符串)}}
        #   LangChain 解析后: {"name", "args"(dict), "id", "type"}
        fn = call.get("function") or {}
        name = fn.get("name") or call.get("name") or ""
        raw_args = fn.get("arguments")
        if raw_args is None:
            raw_args = call.get("args")
        if isinstance(raw_args, str):
            try:
                args = json.loads(raw_args)
            except Exception:
                args = {}
        else:
            args = raw_args or {}
        ref = name_map.get(name)
        if ref is None:
            content, sources = f"未找到名为 {name} 的工具", []
        else:
            content, sources = await execute_tool_call(db, ref, args, kb_ids=kb_ids)
        results.append({
            "tool_call_id": call.get("id") or name,
            "name": name,
            "content": apply_source_offset(content, sources, offset),
            "sources": sources,
        })
        offset += len(sources)
    return results
