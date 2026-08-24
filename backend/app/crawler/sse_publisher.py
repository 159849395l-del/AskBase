"""
爬虫 SSE 事件发布 — 对接前端的实时进度推送
"""
import json
import asyncio
from typing import Dict, Optional

_subscribers: Dict[int, list] = {}


def subscribe(task_id: int) -> asyncio.Queue:
    queue: asyncio.Queue = asyncio.Queue()
    _subscribers.setdefault(task_id, []).append(queue)
    return queue


def unsubscribe(task_id: int, queue: asyncio.Queue):
    subs = _subscribers.get(task_id, [])
    if queue in subs:
        subs.remove(queue)
    if not subs:
        _subscribers.pop(task_id, None)


async def publish_event(task_id: int, event_type: str, data: dict):
    subs = _subscribers.get(task_id, [])
    if not subs:
        return
    payload = f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
    for q in list(subs):
        try:
            await q.put(payload)
        except Exception:
            pass


async def publish_status(task_id: int, status: str, prev: Optional[str] = None):
    await publish_event(task_id, "TASK_STATUS", {"taskId": task_id, "status": status, "prev": prev})

async def publish_error(task_id: int, error: str):
    await publish_event(task_id, "TASK_ERROR", {"taskId": task_id, "error": error})

async def publish_agent_log(task_id: int, agent: str, status: str, stage: str, tokens: int):
    await publish_event(task_id, "AGENT_LOG", {"taskId": task_id, "agent": agent, "status": status, "stage": stage, "tokens": tokens})

async def publish_url_progress(task_id: int, url: str, status: str, crawl_mode: Optional[str], fetch_time_ms: int):
    await publish_event(task_id, "URL_PROGRESS", {"taskId": task_id, "url": url, "status": status, "crawlMode": crawl_mode, "fetchTimeMs": fetch_time_ms})

async def publish_stage_progress(task_id: int, stage: str, current: int, total: int):
    await publish_event(task_id, "STAGE_PROGRESS", {"taskId": task_id, "stage": stage, "current": current, "total": total})

async def publish_result_new(task_id: int, result_id: int, summary: str):
    await publish_event(task_id, "RESULT_NEW", {"taskId": task_id, "resultId": result_id, "summary": summary})
