"""工具执行器 — 把 AgentToolRef 转成 OpenAI function-calling 规格并执行

- 内部 Skill：tool_type=skill，按 skill.handler 路由到 app/skills/handlers.py
- MCP 工具：tool_type=mcp_tool，tool_ref 形如 "<server_id>:<tool_name>"

工具在 LLM 侧的名称需要唯一，MCP 工具统一加 `mcp<server_id>_` 前缀，避免跨服务重名。
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


async def execute_tool_call(
    db: AsyncSession, ref: AgentToolRef, arguments: Dict[str, Any],
    kb_ids: Optional[List[int]] = None,
) -> str:
    """执行单个工具调用，返回给 LLM 看的文本结果"""
    if ref.tool_type == "skill":
        result = await db.execute(select(Skill).where(Skill.id == ref.tool_ref_id))
        s = result.scalar_one_or_none()
        if s is None:
            return "工具不存在或已被删除"
        handler = get_handler(s.handler or s.name)
        if handler is None:
            return "该工具没有可执行的处理函数"
        try:
            return str(await handler(arguments or {}))
        except Exception as e:
            return f"工具执行失败：{str(e)[:500]}"

    if ref.tool_type == "mcp_tool" and ref.tool_ref:
        from app.services import mcp_service

        try:
            server_id_str, tool_name = ref.tool_ref.split(":", 1)
            server_id = int(server_id_str)
        except (ValueError, IndexError):
            return "MCP 工具引用格式错误"
        try:
            return await mcp_service.call_tool(db, server_id, tool_name, arguments or {})
        except Exception as e:
            detail = getattr(e, "detail", None) or str(e)
            return f"MCP 工具调用失败：{str(detail)[:500]}"

    return "未知工具类型"


async def run_tool_calls(
    db: AsyncSession, tool_calls: List[Dict[str, Any]], name_map: Dict[str, AgentToolRef],
    kb_ids: Optional[List[int]] = None,
) -> List[Dict[str, Any]]:
    """批量执行 tool_calls，返回可直接作为 ToolMessage 的结果列表

    每项形如 {"tool_call_id": ..., "name": ..., "content": ...}
    """
    results = []
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
            content = f"未找到名为 {name} 的工具"
        else:
            content = await execute_tool_call(db, ref, args, kb_ids=kb_ids)
        results.append({
            "tool_call_id": call.get("id") or name,
            "name": name,
            "content": content,
        })
    return results
