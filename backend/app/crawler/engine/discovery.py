"""UrlDiscoveryAgent — 种子 URL 入队 + 列表页链接发现"""
import json
import time
from datetime import datetime
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from app.crawler.models import CrawlTask, UrlQueueItem, AgentLog, TaskStatus, get_crawler_session_factory
from app.crawler.engine.fetcher import StaticHttpFetcher
from app.crawler.engine.html_cleaner import HtmlCleaner
from app.crawler.utils import normalize, is_same_domain, is_static_asset, url_hash, safe_json
from app.crawler.sse_publisher import publish_agent_log, publish_stage_progress


async def execute_discovery(task_id: int):
    factory = get_crawler_session_factory()
    async with factory() as db:
        task = await db.get(CrawlTask, task_id)
        if not task or task.status != TaskStatus.DISCOVERING.value:
            return None
        start_ms = int(time.time() * 1000)
        log = AgentLog(task_id=task_id, agent="DISCOVERY", stage="seed_check", status="RUNNING", started_at=datetime.now())
        db.add(log)
        seeds = _resolve_seeds(task)
        if not seeds:
            task.status = TaskStatus.FAILED.value
            task.error_message = "\u672a\u63d0\u4f9b\u79cd\u5b50 URL"
            task.finished_at = datetime.now()
            await db.flush()
            return None
        enqueued = 0
        fetcher = StaticHttpFetcher()
        cleaner = HtmlCleaner()
        for seed in seeds:
            if enqueued >= task.max_pages:
                break
            normalized = normalize(seed)
            if await _enqueue(db, task_id, normalized, 1, "SEED", task.max_pages):
                enqueued += 1
            try:
                page = await fetcher.fetch(normalized)
                if page.ok and page.html:
                    cleaned = cleaner.clean(page.html, normalized)
                    for link in cleaned.links:
                        if enqueued >= task.max_pages:
                            break
                        target = normalize(link.url)
                        if is_same_domain(normalized, target) and not is_static_asset(target) and target != normalized:
                            if await _enqueue(db, task_id, target, 2, "DISCOVERY", task.max_pages):
                                enqueued += 1
            except Exception:
                pass
        await db.flush()
        await db.commit()
        stats = safe_json(task.stats_json) or {}
        stats["discovered"] = enqueued
        task.stats_json = stats
        await db.flush()
        await db.commit()
        await publish_stage_progress(task_id, "discover", enqueued, enqueued)
        log2 = AgentLog(task_id=task_id, agent="DISCOVERY", stage="seed_check", status="SUCCESS", duration_ms=int(time.time()*1000-start_ms), started_at=datetime.now(), finished_at=datetime.now())
        db.add(log2)
        await db.commit()
        await publish_agent_log(task_id, "DISCOVERY", "SUCCESS", "seed_check", 0)
        print(f"[Discovery] Task {task_id} discovered {enqueued} urls")
        return None


def _resolve_seeds(task: CrawlTask) -> list:
    if task.seed_urls:
        seeds = [s.strip() for s in task.seed_urls.split(",") if s.strip()]
        if seeds:
            return seeds
    try:
        if task.plan_json:
            plan = safe_json(task.plan_json)
            if isinstance(plan, dict):
                return [s for s in plan.get("seed_hint", []) if isinstance(s, str) and s.startswith("http")]
    except Exception:
        pass
    return []


async def _enqueue(db, task_id: int, url: str, depth: int, source: str, max_pages: int) -> bool:
    h = url_hash(task_id, url)
    existing = await db.scalar(select(func.count()).select_from(UrlQueueItem).where(UrlQueueItem.task_id == task_id, UrlQueueItem.url_hash == h))
    if existing and existing > 0:
        return False
    count = await db.scalar(select(func.count()).select_from(UrlQueueItem).where(UrlQueueItem.task_id == task_id))
    if count and count >= max_pages:
        return False
    item = UrlQueueItem(task_id=task_id, url=url, url_hash=h, depth=depth, source=source, status="PENDING", retry_count=0)
    db.add(item)
    try:
        # flush 立即触发唯一索引检查，冲突时仅回滚到 savepoint
        async with db.begin_nested():
            await db.flush()
    except IntegrityError:
        return False
    return True
