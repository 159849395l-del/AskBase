"""用量统计 — 汇总查询

口径（见 CONTEXT.md）：
- 只统计端点确认的真实用量：失败行、估算行一律排除
- 时间范围按本地时间的日界划分；created_at 是 ISO 字符串，可直接字典序比较
"""

from datetime import date, datetime, time as dtime, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_usage import LLMUsageLog
from app.schemas.usage import UsageAgentRow, UsageExcluded, UsageOverview, UsageTotals

# 没有智能体归属的用量（如智能体配置测试）在报表里单独成行
UNBOUND_AGENT_NAME = "未绑定智能体"


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
