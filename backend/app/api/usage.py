"""用量统计 API — 仅管理员

- GET /api/admin/usage/overview：按时间范围汇总真实用量 + 按智能体明细
- GET /api/admin/usage/timeseries：按日/月/年的用量时间序列

两个接口的缺省区间都按 granularity 推导（见 usage_stats_service.resolve_range），
因此前端只需传粒度，不必自己复刻那套规则。
"""

from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_admin_user
from app.database import get_db
from app.models.user import User
from app.schemas.usage import UsageOverview, UsageTimeseries
from app.services import usage_stats_service

router = APIRouter(prefix="/api/admin/usage", tags=["用量统计"])

Granularity = Literal["day", "month", "year"]


def _resolve(
    start: Optional[date],
    end: Optional[date],
    granularity: Granularity,
) -> tuple:
    """补全起止日期并校验顺序（缺省区间的规则只在 usage_stats_service 一处定义）"""
    try:
        resolved_start, resolved_end = usage_stats_service.resolve_range(
            start, end, granularity
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if resolved_start > resolved_end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="起始日期不能晚于结束日期",
        )
    return resolved_start, resolved_end


@router.get("/overview", response_model=UsageOverview)
async def get_overview(
    granularity: Granularity = Query("day", description="缺省区间按该粒度推导"),
    start: Optional[date] = Query(None, description="起始日期（含），缺省按粒度推导"),
    end: Optional[date] = Query(None, description="结束日期（含），缺省为今天"),
    agent_id: Optional[int] = Query(None, description="限定到某个智能体；不传为全部"),
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """汇总时间范围内的真实用量（估算行与失败行不计入）"""
    resolved_start, resolved_end = _resolve(start, end, granularity)
    return await usage_stats_service.overview(
        db, resolved_start, resolved_end, agent_id=agent_id
    )


@router.get("/timeseries", response_model=UsageTimeseries)
async def get_timeseries(
    granularity: Granularity = Query("day", description="时间粒度"),
    start: Optional[date] = Query(None, description="起始日期（含），缺省按粒度推导"),
    end: Optional[date] = Query(None, description="结束日期（含），缺省为今天"),
    agent_id: Optional[int] = Query(None, description="限定到某个智能体；不传为全部"),
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """按日/月/年返回真实用量的时间序列（没有数据的时间桶补 0）"""
    resolved_start, resolved_end = _resolve(start, end, granularity)
    try:
        return await usage_stats_service.timeseries(
            db, resolved_start, resolved_end, granularity, agent_id=agent_id
        )
    except ValueError as e:
        # 跨度超出桶数上限：明确拒绝，不硬算
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
