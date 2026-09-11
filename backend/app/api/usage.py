"""用量统计 API — 仅管理员

- GET /api/admin/usage/overview：按时间范围汇总真实用量
"""

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_admin_user
from app.database import get_db
from app.models.user import User
from app.schemas.usage import UsageOverview
from app.services import usage_stats_service

router = APIRouter(prefix="/api/admin/usage", tags=["用量统计"])

DEFAULT_RANGE_DAYS = 30


@router.get("/overview", response_model=UsageOverview)
async def get_overview(
    start: Optional[date] = Query(None, description="起始日期（含），缺省为近 30 天前"),
    end: Optional[date] = Query(None, description="结束日期（含），缺省为今天"),
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """汇总时间范围内的真实用量（估算行与失败行不计入）"""
    resolved_end = end or date.today()
    resolved_start = start or (resolved_end - timedelta(days=DEFAULT_RANGE_DAYS - 1))
    if resolved_start > resolved_end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="起始日期不能晚于结束日期",
        )
    return await usage_stats_service.overview(db, resolved_start, resolved_end)
