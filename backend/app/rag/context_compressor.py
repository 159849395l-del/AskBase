"""
上下文压缩模块 — 将较早的对话历史压缩为 ≤200 字中文摘要

零新依赖：复用 chain.get_llm()，通过函数内 import 避免与 chain.py 循环导入。
失败时静默降级（返回 (None, messages)），绝不中断主问答链路（与 query_rewriter 容错一致）。

设计：滑动窗口 + 超阈值摘要
- 最近 `keep_recent` 轮保持原文（高保真）
- 更早的历史若非空且总轮数 > 阈值，调 LLM 压成 ≤200 字摘要
- 原始消息仍全量存库，此处压缩只影响"喂给模型的内容"，不丢数据
"""

from app.config import settings


# 固定严格 prompt：要求保留用户核心诉求、关键结论、已确认表名/字段约束、未决问题
COMPRESS_SYSTEM_PROMPT = """你是一个对话历史压缩助手。请把下面多轮对话历史压缩成不超过200字的中文摘要，必须保留：
1. 用户的核心诉求
2. 已给出的关键结论/答案要点
3. 已确认的表名/字段/数据约束
4. 尚未解决的未决问题
只输出摘要正文，不要解释，不要使用列表以外的多余格式。若历史中无实质内容，仅输出"无"。"""


# 模块级缓存：key=(conv_id, last_msg_id) -> summary_text
# 仅作为避免每轮重复计算的优化；异常或缺失时不影响主链路。
# 受 CACHE_MAX_ENTRIES 思路约束，超出时简单淘汰前半（近似 LRU）。
_summary_cache: dict = {}


def _cache_key(conv_id, last_msg_id):
    return (conv_id, last_msg_id)


def _build_compress_messages(earlier_messages: list) -> list:
    """构造压缩用消息列表：系统提示 + 更早历史（纯函数，延迟 import 避免循环依赖）"""
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

    msgs = [SystemMessage(content=COMPRESS_SYSTEM_PROMPT)]
    for role, content in earlier_messages:
        if role == "human":
            msgs.append(HumanMessage(content=content))
        else:
            msgs.append(AIMessage(content=content))
    return msgs


async def compress_history(
    messages: list,
    keep_recent: int = None,
    conv_id=None,
    last_msg_id=None,
):
    """把 messages 分成「最近 keep_recent 轮」与「更早的」。

    返回 (summary_text_or_None, recent_raw_messages)：
    - 无更早消息 或 总轮数 <= 阈值 -> (None, messages)  # 不压缩，行为等价于原滑动窗口
    - 否则调 LLM 压成 ≤200 字摘要（带缓存；任何异常静默降级回原窗口）

    messages 格式与项目一致：[(role, content), ...]，role ∈ {"human", "ai"}。
    """
    if keep_recent is None:
        keep_recent = settings.CONTEXT_RECENT_TURNS

    if not messages:
        return (None, messages)

    total_turns = len(messages)
    # 阈值：历史轮数超过此值才压缩
    if total_turns <= settings.CONTEXT_COMPRESS_THRESHOLD_TURNS:
        return (None, messages)

    earlier = messages[:-keep_recent]
    recent = messages[-keep_recent:]
    if not earlier:
        return (None, messages)

    # 缓存命中：同一会话、同一最近消息（即"更早历史"未变）时复用摘要
    key = _cache_key(conv_id, last_msg_id)
    if key in _summary_cache:
        return (_summary_cache[key], recent)

    try:
        # 函数内 import，避免与 chain.py 循环导入
        from app.rag.chain import get_llm

        msgs = _build_compress_messages(earlier)
        response = await get_llm().ainvoke(msgs)
        summary = (response.content or "").strip()
        if not summary or summary == "无":
            # 视为无有效摘要，不压缩，退回原窗口
            return (None, messages)

        # 写入缓存并约束规模
        _summary_cache[key] = summary
        if len(_summary_cache) > settings.CACHE_MAX_ENTRIES:
            for k in list(_summary_cache)[: len(_summary_cache) // 2]:
                _summary_cache.pop(k, None)

        return (summary, recent)
    except Exception as e:
        print(f"[ContextCompress] 摘要异常，降级回原滑动窗口: {e}")
        return (None, messages)
