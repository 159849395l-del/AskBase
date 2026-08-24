"""AggregatorAgent — 统计结果，决定终态"""
import json
import time
from datetime import datetime
from sqlalchemy import select, func
from app.crawler.models import CrawlTask, CrawlResult, UrlQueueItem, AgentLog, TaskStatus, get_crawler_session_factory
from app.crawler.utils import safe_json
from app.crawler.sse_publisher import publish_agent_log


async def execute_aggregating(task_id: int) -> TaskStatus:
    start_ms = int(time.time() * 1000)
    factory = get_crawler_session_factory()
    async with factory() as db:
        log = AgentLog(task_id=task_id, agent="AGGREGATOR", stage="summary", status="RUNNING", started_at=datetime.now())
        db.add(log)
        task = await db.get(CrawlTask, task_id)
        if not task: return TaskStatus.FAILED
        valid = (await db.scalar(select(func.count()).select_from(CrawlResult).where(CrawlResult.task_id==task_id, CrawlResult.status=="VALID"))) or 0
        invalid = (await db.scalar(select(func.count()).select_from(CrawlResult).where(CrawlResult.task_id==task_id, CrawlResult.status=="INVALID"))) or 0
        duplicate = (await db.scalar(select(func.count()).select_from(CrawlResult).where(CrawlResult.task_id==task_id, CrawlResult.status=="DUPLICATE"))) or 0
        fetch_failed = (await db.scalar(select(func.count()).select_from(UrlQueueItem).where(UrlQueueItem.task_id==task_id, UrlQueueItem.status=="FAILED"))) or 0
        stats = safe_json(task.stats_json) or {}
        stats["valid"] = valid; stats["invalid"] = invalid
        task.stats_json = stats; await db.flush(); await db.commit()
        if valid > 0:
            terminal = TaskStatus.PARTIAL if (fetch_failed > 0 or invalid > 0) else TaskStatus.COMPLETED
        else:
            terminal = TaskStatus.FAILED
        log2 = AgentLog(task_id=task_id, agent="AGGREGATOR", stage="summary", status="SUCCESS", duration_ms=int(time.time()*1000-start_ms), started_at=datetime.now(), finished_at=datetime.now())
        db.add(log2)
        await db.commit()
        await publish_agent_log(task_id, "AGGREGATOR", "SUCCESS", "summary", 0)
        print(f"[Aggregator] Task {task_id}: valid={valid} invalid={invalid} dup={duplicate} failed={fetch_failed} -> {terminal.value}")
        return terminal
