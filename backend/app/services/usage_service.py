"""LLM 用量采集 — 旁路写入，任何故障都不得打断问答

设计要点：
- 真实用量优先取自 LangChain 消息对象上的 usage_metadata（端点什么形态都能解析）
- 端点未返回用量时按字符估算，并打上 is_estimated 标记（估算值不进统计）
- 写入使用独立短会话，与问答请求的事务解耦；异常一律吞掉，只在日志留痕
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from app.database import async_session_factory
from app.models.llm_usage import LLMUsageLog


@dataclass(frozen=True)
class TokenUsage:
    """一次调用的 token 用量（端点确认的真实值）"""

    prompt: int
    completion: int
    total: int


@dataclass
class UsageContext:
    """一次请求的身份，随调用链传递；模型信息由各调用点单独给出"""

    agent_id: Optional[int] = None
    agent_name: Optional[str] = None
    user_id: Optional[int] = None
    conversation_id: Optional[int] = None


def estimate_tokens(text: str) -> int:
    """按字符估算 token：CJK 一字约 1 token，其余 4 字符约 1 token；空串为 0。

    只在端点未返回用量的极少数情况（流被中断/超时）兜底，
    估算结果不进入任何统计数字。
    """
    if not text:
        return 0
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    other = len(text) - cjk
    return max(cjk + (other + 3) // 4, 1)


def read_usage(message) -> Optional[TokenUsage]:
    """读 LangChain 消息对象上的真实用量；端点没给就返回 None"""
    meta = getattr(message, "usage_metadata", None)
    if not meta:
        return None
    prompt = int(meta.get("input_tokens") or 0)
    completion = int(meta.get("output_tokens") or 0)
    total = int(meta.get("total_tokens") or 0) or (prompt + completion)
    if prompt <= 0 and completion <= 0 and total <= 0:
        return None
    return TokenUsage(prompt=prompt, completion=completion, total=total)


async def record_call(
    ctx: Optional[UsageContext],
    *,
    call_type: str,
    model_name: str,
    model_id: Optional[int] = None,
    usage: Optional[TokenUsage] = None,
    response=None,
    input_text: str = "",
    output_text: str = "",
    duration_ms: Optional[int] = None,
    error: Optional[str] = None,
) -> None:
    """记录一次模型调用。

    usage 显式给定时优先（流式路径自己累计），否则从 response 上读；
    两者都没有则按 input_text/output_text 估算并打上估算标记。
    error 非空时记为失败行（token 记 0）。

    **绝不抛异常**：采集是旁路，不能成为问答的单点故障。
    """
    try:
        ctx = ctx or UsageContext()
        resolved = usage if usage is not None else (
            read_usage(response) if response is not None else None
        )

        if error is not None:
            prompt = completion = total = 0
            status, estimated = "error", False
        elif resolved is not None:
            prompt, completion, total = resolved.prompt, resolved.completion, resolved.total
            status, estimated = "success", False
        else:
            prompt = estimate_tokens(input_text)
            completion = estimate_tokens(output_text)
            total = prompt + completion
            status, estimated = "success", True

        row = LLMUsageLog(
            agent_id=ctx.agent_id,
            agent_name=ctx.agent_name,
            user_id=ctx.user_id,
            conversation_id=ctx.conversation_id,
            model_id=model_id,
            model_name=model_name or "",
            call_type=call_type,
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=total,
            is_estimated=estimated,
            duration_ms=duration_ms,
            status=status,
            error_message=(error or "")[:500] or None,
            created_at=datetime.now().isoformat(),
        )
        async with async_session_factory() as db:
            db.add(row)
            await db.commit()
    except Exception as e:  # noqa: BLE001 — 采集失败绝不影响问答
        print(f"[usage] 用量记录失败(已忽略): {e}")
