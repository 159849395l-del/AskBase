"""用量统计 — 汇总查询

口径（见 CONTEXT.md）：
- 只统计端点确认的真实用量：失败行、估算行一律排除
- 时间范围按本地时间的日界划分；created_at 是 ISO 字符串，可直接字典序比较
"""

from datetime import date, datetime, time as dtime, timedelta
from typing import Literal, Optional

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_usage import LLMUsageLog
from app.schemas.usage import (
    UsageAgentRow,
    UsageExcluded,
    UsageOverview,
    UsagePoint,
    UsageTimeseries,
    UsageTotals,
)

# 没有智能体归属的用量（如智能体配置测试）在报表里单独成行
UNBOUND_AGENT_NAME = "未绑定智能体"

# 时间粒度，以及各粒度对应的 ISO 前缀长度（created_at 是 ISO 字符串，可直接截取）
Granularity = Literal["day", "month", "year"]
GRANULARITIES: tuple = ("day", "month", "year")
_KEY_LEN = {"day": 10, "month": 7, "year": 4}

# 各粒度的默认区间长度
DEFAULT_RANGE_DAYS = 30
DEFAULT_RANGE_MONTHS = 12
DEFAULT_RANGE_YEARS = 5

# 单次查询允许的最大时间桶数：按日查十年应被拒绝，而不是硬算
MAX_BUCKETS = 400


def _range_bounds(start: date, end: date) -> tuple:
    """返回 [起, 止) 的 ISO 字符串边界（含首尾两日的完整一天）"""
    lo = datetime.combine(start, dtime.min).isoformat()
    hi = datetime.combine(end + timedelta(days=1), dtime.min).isoformat()
    return lo, hi


def _sum_of(column):
    """求和并兜底为 0（空区间时聚合结果是 NULL）"""
    return func.coalesce(func.sum(column), 0)


def _chat_requests_col():
    """问答次数：只数主回答调用（见 CONTEXT.md 的两个词条）"""
    return func.sum(case((LLMUsageLog.call_type == "chat", 1), else_=0))


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


def bucket_of(iso_time: str, granularity: str) -> str:
    """把一条记录的本地时间截成它所属的时间桶"""
    return iso_time[: _KEY_LEN[granularity]]


def _ensure_granularity(granularity: str) -> None:
    """粒度是报表的对外契约，非法值统一在这里拒绝"""
    if granularity not in GRANULARITIES:
        raise ValueError(f"未知的时间粒度：{granularity}")


def _bucket_count(start: date, end: date, granularity: Granularity) -> int:
    if granularity == "day":
        return (end - start).days + 1
    if granularity == "month":
        return (end.year * 12 + end.month) - (start.year * 12 + start.month) + 1
    return end.year - start.year + 1


def iter_buckets(start: date, end: date, granularity: Granularity) -> list:
    """含首尾的时间桶序列；跨度超出上限时抛 ValueError"""
    _ensure_granularity(granularity)
    count = _bucket_count(start, end, granularity)
    if count > MAX_BUCKETS:
        raise ValueError(
            f"时间跨度过大：{count} 个时间桶超过上限 {MAX_BUCKETS}，"
            "请缩小范围或改用更粗的粒度"
        )

    if granularity == "day":
        return [(start + timedelta(days=i)).isoformat() for i in range(count)]
    if granularity == "month":
        base = start.year * 12 + (start.month - 1)
        return [f"{(base + i) // 12:04d}-{(base + i) % 12 + 1:02d}" for i in range(count)]
    return [str(start.year + i) for i in range(count)]


def resolve_range(
    start: Optional[date],
    end: Optional[date],
    granularity: Granularity,
    today: Optional[date] = None,
) -> tuple:
    """把可选的起止补成完整区间；缺省值按粒度给（日近 30 天 / 月近 12 个月 / 年近 5 年）"""
    _ensure_granularity(granularity)
    resolved_end = end or today or date.today()
    if start is not None:
        return start, resolved_end

    if granularity == "day":
        return resolved_end - timedelta(days=DEFAULT_RANGE_DAYS - 1), resolved_end
    if granularity == "month":
        base = resolved_end.year * 12 + (resolved_end.month - 1) - (DEFAULT_RANGE_MONTHS - 1)
        return date(base // 12, base % 12 + 1, 1), resolved_end
    return date(resolved_end.year - (DEFAULT_RANGE_YEARS - 1), 1, 1), resolved_end


async def timeseries(
    db: AsyncSession,
    start: date,
    end: date,
    granularity: str,
) -> UsageTimeseries:
    """按粒度返回时间序列；没有数据的时间桶补 0，保证曲线连续"""
    buckets = iter_buckets(start, end, granularity)  # 顺带校验粒度与跨度上限
    lo, hi = _range_bounds(start, end)
    bucket_col = func.substr(LLMUsageLog.created_at, 1, _KEY_LEN[granularity])

    rows = (
        await db.execute(
            select(
                bucket_col.label("bucket"),
                func.count().label("llm_calls"),
                _chat_requests_col().label("requests"),
                _sum_of(LLMUsageLog.prompt_tokens).label("prompt_tokens"),
                _sum_of(LLMUsageLog.completion_tokens).label("completion_tokens"),
                _sum_of(LLMUsageLog.total_tokens).label("total_tokens"),
            )
            .where(*_real_usage_filter(lo, hi))
            .group_by(bucket_col)
        )
    ).all()
    by_bucket = {r.bucket: r for r in rows}

    points = []
    for bucket in buckets:
        r = by_bucket.get(bucket)
        points.append(
            UsagePoint(
                bucket=bucket,
                requests=int(r.requests or 0) if r else 0,
                llm_calls=int(r.llm_calls or 0) if r else 0,
                prompt_tokens=int(r.prompt_tokens or 0) if r else 0,
                completion_tokens=int(r.completion_tokens or 0) if r else 0,
                total_tokens=int(r.total_tokens or 0) if r else 0,
            )
        )

    return UsageTimeseries(
        granularity=granularity,
        start=start.isoformat(),
        end=end.isoformat(),
        points=points,
    )


async def overview(db: AsyncSession, start: date, end: date) -> UsageOverview:
    """汇总时间范围内的真实用量（估算行与失败行不计入）"""
    lo, hi = _range_bounds(start, end)
    real = _real_usage_filter(lo, hi)

    row = (
        await db.execute(
            select(
                func.count().label("llm_calls"),
                # 问答次数天然小于等于模型调用次数：一次提问内部可能触发多次调用
                _chat_requests_col().label("requests"),
                _sum_of(LLMUsageLog.prompt_tokens).label("prompt_tokens"),
                _sum_of(LLMUsageLog.completion_tokens).label("completion_tokens"),
                _sum_of(LLMUsageLog.total_tokens).label("total_tokens"),
            ).where(*real)
        )
    ).one()

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
            requests=int(row.requests or 0),
            llm_calls=int(row.llm_calls or 0),
            prompt_tokens=int(row.prompt_tokens or 0),
            completion_tokens=int(row.completion_tokens or 0),
            total_tokens=int(row.total_tokens or 0),
        ),
        excluded=UsageExcluded(estimated_calls=int(estimated or 0)),
        agents=await _per_agent(db, lo, hi),
    )


def _display_name(agent_id, agent_name) -> str:
    """报表里显示的智能体名：无归属单独命名，缺快照时退回 id"""
    if agent_id is None:
        return UNBOUND_AGENT_NAME
    return agent_name or f"智能体 #{agent_id}"


async def _latest_names(db: AsyncSession, lo: str, hi: str) -> dict:
    """每个智能体在区间内**最近一条带名称的**快照

    取快照而不是回查 agents 表：改名后历史仍归到同一行并显示新名，
    智能体被删除后历史仍可读（见 ADR-0001）。

    只认非空名称：智能体被删除后，绑定它的会话仍可能写出 agent_name 为空的流水；
    若最新一条恰好是空的，不能因此丢掉历史名称。
    """
    ranked = (
        select(
            LLMUsageLog.agent_id.label("agent_id"),
            LLMUsageLog.agent_name.label("agent_name"),
            func.row_number()
            .over(
                partition_by=LLMUsageLog.agent_id,
                order_by=LLMUsageLog.created_at.desc(),
            )
            .label("rn"),
        )
        .where(*_real_usage_filter(lo, hi), LLMUsageLog.agent_name.is_not(None))
        .subquery()
    )
    rows = await db.execute(
        select(ranked.c.agent_id, ranked.c.agent_name).where(ranked.c.rn == 1)
    )
    return {agent_id: name for agent_id, name in rows.all()}


async def _per_agent(db: AsyncSession, lo: str, hi: str) -> list:
    """按智能体聚合，按总 token 降序"""
    total_tokens = _sum_of(LLMUsageLog.total_tokens)

    rows = (
        await db.execute(
            select(
                LLMUsageLog.agent_id.label("agent_id"),
                func.count().label("llm_calls"),
                _chat_requests_col().label("requests"),
                _sum_of(LLMUsageLog.prompt_tokens).label("prompt_tokens"),
                _sum_of(LLMUsageLog.completion_tokens).label("completion_tokens"),
                total_tokens.label("total_tokens"),
                func.max(LLMUsageLog.created_at).label("last_called_at"),
            )
            .where(*_real_usage_filter(lo, hi))
            .group_by(LLMUsageLog.agent_id)
            # 用量相同时把「未绑定智能体」排在真实智能体之后
            # （SQLite 升序会把 NULL 排在最前，所以要显式把它压到最后）
            .order_by(
                total_tokens.desc(),
                LLMUsageLog.agent_id.is_(None),
                LLMUsageLog.agent_id.asc(),
            )
        )
    ).all()

    names = await _latest_names(db, lo, hi)
    return [
        UsageAgentRow(
            agent_id=r.agent_id,
            agent_name=_display_name(r.agent_id, names.get(r.agent_id)),
            requests=int(r.requests or 0),
            llm_calls=int(r.llm_calls or 0),
            prompt_tokens=int(r.prompt_tokens or 0),
            completion_tokens=int(r.completion_tokens or 0),
            total_tokens=int(r.total_tokens or 0),
            last_called_at=r.last_called_at,
        )
        for r in rows
    ]
