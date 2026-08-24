"""
定时爬取管理 API
"""
from datetime import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.crawler.models import CrawlTask, CrawlSchedule, get_crawler_db
from app.core.dependencies import get_admin_user
from app.models.user import User

router = APIRouter(prefix="/api/crawler/schedules", tags=["定时爬取"])


class ScheduleRequest(BaseModel):
    interval_days: int = 1
    run_time: str = "02:00:00"
    enabled: bool = True


def _schedule_to_dict(s: CrawlSchedule) -> dict:
    return {
        "id": s.id,
        "taskId": s.task_id,
        "intervalDays": s.interval_days,
        "runTime": str(s.run_time)[:8] if s.run_time else "02:00:00",
        "enabled": s.enabled,
        "lastRunAt": s.last_run_at.isoformat() if s.last_run_at else None,
        "lastStatus": s.last_status or "NONE",
        "lastDetail": s.last_detail,
        "createdAt": s.created_at.isoformat(),
        "updatedAt": s.updated_at.isoformat(),
    }


@router.get("/{task_id}")
async def get_schedule(task_id: int, db: AsyncSession = Depends(get_crawler_db), admin: User = Depends(get_admin_user)):
    s = (await db.execute(select(CrawlSchedule).where(CrawlSchedule.task_id == task_id))).scalar_one_or_none()
    return _schedule_to_dict(s) if s else None


@router.put("/{task_id}")
async def save_schedule(
    task_id: int, body: ScheduleRequest,
    db: AsyncSession = Depends(get_crawler_db), admin: User = Depends(get_admin_user),
):
    task = await db.get(CrawlTask, task_id)
    if not task:
        raise HTTPException(404, detail="任务不存在")
    s = (await db.execute(select(CrawlSchedule).where(CrawlSchedule.task_id == task_id))).scalar_one_or_none()
    if s is None:
        s = CrawlSchedule(task_id=task_id)
        db.add(s)
    s.interval_days = body.interval_days
    s.run_time = body.run_time
    s.enabled = body.enabled
    await db.flush()
    await db.refresh(s)
    return _schedule_to_dict(s)


@router.delete("/{task_id}", status_code=204)
async def delete_schedule(task_id: int, db: AsyncSession = Depends(get_crawler_db), admin: User = Depends(get_admin_user)):
    await db.execute(delete(CrawlSchedule).where(CrawlSchedule.task_id == task_id))
