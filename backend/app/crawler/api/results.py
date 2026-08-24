"""
爬取结果 API
"""
import json
import csv
import io
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.crawler.models import CrawlResult, CrawlPage, CrawlTask, get_crawler_db
from app.crawler.utils import safe_json
from app.core.dependencies import get_admin_user
from app.models.user import User

router = APIRouter(prefix="/api/crawler/tasks", tags=["爬取结果"])


def _result_data(r: CrawlResult):
    """兼容历史双重 JSON 编码的 data_json"""
    return safe_json(r.data_json, default={})


def _result_to_dict(r: CrawlResult) -> dict:
    return {
        "id": r.id,
        "taskId": r.task_id,
        "url": r.url,
        "pageId": r.page_id,
        "data": _result_data(r),
        "recordHash": r.record_hash,
        "status": r.status,
        "sourceUrl": r.source_url,
        "extractedAt": r.extracted_at.isoformat() if r.extracted_at else None,
        "createdAt": r.created_at.isoformat(),
    }


@router.get("/{task_id}/results")
async def list_results(
    task_id: int, page: int = Query(0, ge=0), size: int = Query(20, ge=1, le=200),
    status: Optional[str] = None, keyword: Optional[str] = None,
    db: AsyncSession = Depends(get_crawler_db), admin: User = Depends(get_admin_user),
):
    q = select(CrawlResult).where(CrawlResult.task_id == task_id)
    if status:
        q = q.where(CrawlResult.status == status)
    if keyword:
        q = q.where(CrawlResult.data_json.like(f"%{keyword}%"))
    q = q.order_by(CrawlResult.id.asc())
    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    q = q.offset(page * size).limit(size)
    rows = (await db.execute(q)).scalars().all()
    return {"items": [_result_to_dict(r) for r in rows], "total": total or 0, "page": page, "size": size}


@router.get("/{task_id}/results/{result_id}")
async def get_result_detail(
    task_id: int, result_id: int,
    db: AsyncSession = Depends(get_crawler_db), admin: User = Depends(get_admin_user),
):
    result = await db.get(CrawlResult, result_id)
    if not result or result.task_id != task_id:
        raise HTTPException(404, detail="结果不存在")
    detail = _result_to_dict(result)
    if result.page_id:
        page = await db.get(CrawlPage, result.page_id)
        detail["pageText"] = page.clean_text[:5000] if page and page.clean_text else None
    else:
        detail["pageText"] = None
    return detail


@router.get("/{task_id}/export")
async def export_results(
    task_id: int, format: str = Query("csv", regex="^(csv|json)$"),
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_crawler_db), admin: User = Depends(get_admin_user),
):
    q = select(CrawlResult).where(
        CrawlResult.task_id == task_id, CrawlResult.status == (status or "VALID"),
    ).order_by(CrawlResult.id.asc())
    rows = (await db.execute(q)).scalars().all()
    items = [_result_data(r) for r in rows]
    if format == "json":
        content = json.dumps(items, ensure_ascii=False, indent=2)
        media_type = "application/json"
        filename = f"task-{task_id}.json"
    else:
        output = io.StringIO()
        if items:
            w = csv.DictWriter(output, fieldnames=items[0].keys())
            w.writeheader()
            w.writerows(items)
        content = "\ufeff" + output.getvalue()
        media_type = "text/csv"
        filename = f"task-{task_id}.csv"
    return StreamingResponse(
        iter([content]), media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
