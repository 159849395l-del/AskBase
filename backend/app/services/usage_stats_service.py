"""用量统计 — 汇总查询

口径（见 CONTEXT.md）：
- 只统计端点确认的真实用量：失败行、估算行一律排除
- 时间范围按本地时间的日界划分；created_at 是 ISO 字符串，可直接字典序比较
"""

from datetime import date, datetime, time as dtime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_usage import LLMUsageLog
from app.schemas.usage import UsageOverview, UsageTotals


def _range_bounds(start: date, end: date) -> tuple:
    """返回 [起, 止) 的 ISO 字符串边界（含首尾两日的完整一天）"""
    lo = datetime.combine(start, dtime.min).isoformat()
    hi = datetime.combine(end + timedelta(days=1), dtime.min).isoformat()
    return lo, hi


def _real_usage_filter(lo: str, hi: str) -> list:
    """报表的统一过滤条件：成功 + 非估算 + 落在范围内"""
    return [
        LLMUsageLog.status == "success",
        LLMUsageLog.is_estimated == False,  # noqa: E712
        LLMUsageLog.created_at >= lo,
        LLMUsageLog.created_at < hi,
    ]


async def overview(db: AsyncSession, start: date, end: date) -> UsageOverview:
    """汇总时间范围内的真实用量（估算行与失败行不计入）"""
    lo, hi = _range_bounds(start, end)
    row = (
        await db.execute(
            select(
                func.count().label("llm_calls"),
                func.coalesce(func.sum(LLMUsageLog.prompt_tokens), 0).label("prompt_tokens"),
                func.coalesce(func.sum(LLMUsageLog.completion_tokens), 0).label("completion_tokens"),
                func.coalesce(func.sum(LLMUsageLog.total_tokens), 0).label("total_tokens"),
            ).where(*_real_usage_filter(lo, hi))
        )
    ).one()

    return UsageOverview(
        start=start.isoformat(),
        end=end.isoformat(),
        totals=UsageTotals(
            llm_calls=int(row.llm_calls or 0),
            prompt_tokens=int(row.prompt_tokens or 0),
            completion_tokens=int(row.completion_tokens or 0),
            total_tokens=int(row.total_tokens or 0),
        ),
    )
