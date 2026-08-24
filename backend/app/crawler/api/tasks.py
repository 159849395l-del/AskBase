"""
爬虫任务管理 API
"""
import json
import asyncio
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status, Header
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.crawler.models import (
    CrawlTask, UrlQueueItem, CrawlPage, CrawlResult, AgentLog,
    TaskStatus, get_crawler_session_factory
)
from app.crawler.engine.orchestrator import submit_task as orchestrator_submit
from app.crawler.sse_publisher import subscribe, unsubscribe
from app.crawler.utils import safe_json
from app.core.dependencies import get_admin_user, get_admin_user_with_token
from app.crawler.models import get_crawler_db
from app.models.user import User

router = APIRouter(prefix="/api/crawler/tasks", tags=["爬虫任务"])


class TaskCreateRequest(BaseModel):
    title: Optional[str] = None
    description: str
    seed_urls: List[str] = []
    max_pages: int = 100
    max_depth: int = 3
    same_domain_only: bool = True


def _task_to_dict(t: CrawlTask) -> dict:
    schema = safe_json(t.schema_json, default={})
    plan = safe_json(t.plan_json, default={})
    stats = safe_json(t.stats_json, default={})
    return {
        "id": t.id,
        "taskNo": t.task_no,
        "title": t.title,
        "description": t.description,
        "seedUrls": (t.seed_urls or "").split(",") if t.seed_urls else [],
        "maxPages": t.max_pages,
        "maxDepth": t.max_depth,
        "sameDomainOnly": t.same_domain_only,
        "status": t.status,
        "schema": schema,
        "plan": plan,
        "stats": stats or {},
        "errorMessage": t.error_message,
        "startedAt": t.started_at.isoformat() if t.started_at else None,
        "finishedAt": t.finished_at.isoformat() if t.finished_at else None,
        "createdAt": t.created_at.isoformat(),
        "updatedAt": t.updated_at.isoformat(),
    }


@router.post("", status_code=201)
async def create_task(
    body: TaskCreateRequest,
    db: AsyncSession = Depends(get_crawler_db),
    admin: User = Depends(get_admin_user),
):
    count = await db.scalar(select(func.count()).select_from(CrawlTask))
    task_no = f"T{datetime.now().strftime('%y%m%d')}-{(count or 0) + 1}"
    task = CrawlTask(
        task_no=task_no,
        title=body.title or f"任务 {task_no}",
        description=body.description,
        seed_urls=",".join(body.seed_urls) if body.seed_urls else None,
        max_pages=body.max_pages,
        max_depth=body.max_depth,
        same_domain_only=body.same_domain_only,
        status=TaskStatus.PENDING.value,
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)
    return _task_to_dict(task)


@router.get("")
async def list_tasks(
    page: int = Query(0, ge=0),
    size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    keyword: Optional[str] = None,
    db: AsyncSession = Depends(get_crawler_db),
    admin: User = Depends(get_admin_user),
):
    q = select(CrawlTask).order_by(CrawlTask.id.desc())
    if status:
        q = q.where(CrawlTask.status == status)
    if keyword:
        q = q.where(CrawlTask.title.like(f"%{keyword}%") | CrawlTask.description.like(f"%{keyword}%"))
    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    q = q.offset(page * size).limit(size)
    rows = (await db.execute(q)).scalars().all()
    return {"items": [_task_to_dict(t) for t in rows], "total": total or 0, "page": page, "size": size}


@router.get("/{task_id}")
async def get_task(task_id: int, db: AsyncSession = Depends(get_crawler_db), admin: User = Depends(get_admin_user)):
    task = await db.get(CrawlTask, task_id)
    if not task:
        raise HTTPException(404, detail="任务不存在")
    return _task_to_dict(task)


@router.delete("/{task_id}", status_code=204)
async def delete_task(task_id: int, db: AsyncSession = Depends(get_crawler_db), admin: User = Depends(get_admin_user)):
    task = await db.get(CrawlTask, task_id)
    if not task:
        raise HTTPException(404, detail="任务不存在")
    await db.execute(delete(UrlQueueItem).where(UrlQueueItem.task_id == task_id))
    await db.execute(delete(CrawlPage).where(CrawlPage.task_id == task_id))
    await db.execute(delete(CrawlResult).where(CrawlResult.task_id == task_id))
    await db.execute(delete(AgentLog).where(AgentLog.task_id == task_id))
    await db.delete(task)


@router.post("/{task_id}/submit")
async def submit_task(task_id: int, db: AsyncSession = Depends(get_crawler_db), admin: User = Depends(get_admin_user)):
    task = await db.get(CrawlTask, task_id)
    if not task:
        raise HTTPException(404, detail="任务不存在")
    asyncio.create_task(orchestrator_submit(task_id))
    return {"message": "任务已提交", "taskId": task_id}


@router.post("/{task_id}/restart")
async def restart_task(task_id: int, db: AsyncSession = Depends(get_crawler_db), admin: User = Depends(get_admin_user)):
    task = await db.get(CrawlTask, task_id)
    if not task:
        raise HTTPException(404, detail="任务不存在")
    task.status = TaskStatus.PENDING.value
    task.error_message = None
    task.started_at = None
    task.finished_at = None
    task.stats_json = None
    task.schema_json = None
    task.plan_json = None
    await db.execute(delete(UrlQueueItem).where(UrlQueueItem.task_id == task_id))
    await db.execute(delete(CrawlPage).where(CrawlPage.task_id == task_id))
    await db.execute(delete(CrawlResult).where(CrawlResult.task_id == task_id))
    await db.execute(delete(AgentLog).where(AgentLog.task_id == task_id))
    await db.flush()
    asyncio.create_task(orchestrator_submit(task_id))
    return _task_to_dict(task)


@router.post("/{task_id}/stop")
async def stop_task(task_id: int, db: AsyncSession = Depends(get_crawler_db), admin: User = Depends(get_admin_user)):
    task = await db.get(CrawlTask, task_id)
    if not task:
        raise HTTPException(404, detail="任务不存在")
    if TaskStatus(task.status).is_terminal():
        raise HTTPException(400, detail="任务已结束")
    task.status = TaskStatus.CANCELLED.value
    task.finished_at = datetime.now()
    await db.flush()
    return _task_to_dict(task)


@router.get("/{task_id}/events")
async def task_events(
    task_id: int,
    token: Optional[str] = Query(None, description="JWT token (for EventSource)"),
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_crawler_db),
    admin: User = Depends(get_admin_user_with_token),
):
    task = await db.get(CrawlTask, task_id)
    if not task:
        raise HTTPException(404, detail="任务不存在")
    queue = subscribe(task_id)

    async def event_stream():
        try:
            yield f"event: TASK_STATUS\ndata: {json.dumps({'taskId': task_id, 'status': task.status, 'prev': None})}\n\n"
            while True:
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=30)
                    yield payload
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            unsubscribe(task_id, queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
