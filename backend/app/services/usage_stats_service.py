"""用量统计 — 汇总查询

口径（见 CONTEXT.md）：
- 只统计端点确认的真实用量：失败行、估算行一律排除
- 时间范围按本地时间的日界划分；created_at 是 ISO 字符串，可直接字典序比较
"""

from datetime import date, datetime, time as dtime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_usage import LLMUsageLog
from app.schemas.usage import UsageExcluded, UsageOverview, UsageTotals


def _range_bounds(start: date, end: date) -> tuple:
    """返回 [起, 止) 的 ISO 字符串边界（含首尾两日的完整一天）"""
    lo = datetime.combine(start, dtime.min).isoformat()
    hi = datetime.combine(end + timedelta(days=1), dtime.min).isoformat()
    return lo, hi


def _range_filter(lo: str, hi: str) -> list:
    """时间范围条件（created_at 是 ISO 字符串，可直接字典序比较）"""
    return [
        LLMUsageLog.created_at >= lo,
        LLMUsageLog.created_at < hi,
    ]


def _real_usage_filter(lo: str, hi: str) -> list:
    """报表的统一过滤条件：成功 + 非估算 + 落在范围内"""
    return [
        LLMUsageLog.status == "success",
        LLMUsageLog.is_estimated == False,  # noqa: E712
        *_range_filter(lo, hi),
    ]


async def overview(db: AsyncSession, start: date, end: date) -> UsageOverview:
    """汇总时间范围内的真实用量（估算行与失败行不计入）"""
    lo, hi = _range_bounds(start, end)
    real = _real_usage_filter(lo, hi)

    row = (
        await db.execute(
            select(
                func.count().label("llm_calls"),
                func.coalesce(func.sum(LLMUsageLog.prompt_tokens), 0).label("prompt_tokens"),
                func.coalesce(func.sum(LLMUsageLog.completion_tokens), 0).label("completion_tokens"),
                func.coalesce(func.sum(LLMUsageLog.total_tokens), 0).label("total_tokens"),
            ).where(*real)
        )
    ).one()

    # 问答次数：只数主回答调用。一次提问在内部可能触发多次模型调用，
    # 因此它天然小于等于模型调用次数（见 CONTEXT.md 的两个词条）。
    requests = (
        await db.execute(
            select(func.count()).where(*real, LLMUsageLog.call_type == "chat")
        )
    ).scalar_one()

    # 估算行不进任何合计，但要让页面知道「有多少没算进来」：
    # 否则端点哪天不再返回用量时，报表会静默变成 0 而看不出原因。
    estimated = (
        await db.execute(
            select(func.count()).where(
                LLMUsageLog.is_estimated == True,  # noqa: E712
                *_range_filter(lo, hi),
            )
        )
    ).scalar_one()

    return UsageOverview(
        start=start.isoformat(),
        end=end.isoformat(),
        totals=UsageTotals(
            requests=int(requests or 0),
            llm_calls=int(row.llm_calls or 0),
            prompt_tokens=int(row.prompt_tokens or 0),
            completion_tokens=int(row.completion_tokens or 0),
            total_tokens=int(row.total_tokens or 0),
        ),
        excluded=UsageExcluded(estimated_calls=int(estimated or 0)),
    )
