"""CrawlerAgent — 并发爬取 URL 队列"""
import asyncio
import time
from datetime import datetime
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from app.crawler.models import CrawlTask, UrlQueueItem, CrawlPage, AgentLog, TaskStatus, get_crawler_session_factory
from app.crawler.engine.fetcher import StaticHttpFetcher, PlaywrightFetcher, CrawlerRouter, FetchedPage
from app.crawler.engine.html_cleaner import HtmlCleaner
from app.crawler.engine.rate_limiter import RateLimiter
from app.crawler.engine.robots_policy import RobotsPolicy
from app.crawler.utils import normalize, is_same_domain, is_static_asset, url_hash, safe_json
from app.crawler.sse_publisher import publish_agent_log, publish_stage_progress, publish_url_progress
from app.crawler.config import CRAWLER_CONCURRENCY, CRAWLER_MAX_RETRIES


async def execute_crawling(task_id: int):
    start_ms = int(time.time() * 1000)
    factory = get_crawler_session_factory()

    async with factory() as db:
        log = AgentLog(task_id=task_id, agent="CRAWLER", stage="fetch", status="RUNNING", started_at=datetime.now())
        db.add(log)
        await db.flush()

    fetcher = StaticHttpFetcher()
    playwright = PlaywrightFetcher()
    cleaner = HtmlCleaner()
    rate_limiter = RateLimiter()
    robots = RobotsPolicy()
    semaphore = asyncio.Semaphore(CRAWLER_CONCURRENCY)
    fetched_ok = 0; failed = 0; total = 0

    while True:
        async with factory() as db:
            task = await db.get(CrawlTask, task_id)
            if not task or task.status != TaskStatus.CRAWLING.value:
                break
            batch = (await db.execute(select(UrlQueueItem).where(UrlQueueItem.task_id == task_id, UrlQueueItem.status == "PENDING").order_by(UrlQueueItem.id.asc()).limit(CRAWLER_CONCURRENCY))).scalars().all()
            if not batch:
                break

        tasks_l = [_crawl_one(task_id, item, fetcher, playwright, cleaner, rate_limiter, robots, semaphore) for item in batch]
        results = await asyncio.gather(*tasks_l, return_exceptions=True)
        for r in results:
            if isinstance(r, Exception):
                import traceback
                traceback.print_exception(type(r), r, r.__traceback__)
                failed += 1
            elif r:
                ok, _ = r
                if ok: fetched_ok += 1
                else: failed += 1
            total += 1
        await publish_stage_progress(task_id, "crawl", total, -1)

    async with factory() as db:
        task = await db.get(CrawlTask, task_id)
        if task:
            stats = safe_json(task.stats_json) or {}
            stats.update({"crawled": total, "fetched_ok": fetched_ok, "failed": failed})
            task.stats_json = stats
            await db.flush()
            await db.commit()
        log2 = AgentLog(task_id=task_id, agent="CRAWLER", stage="fetch", status="SUCCESS", duration_ms=int(time.time()*1000-start_ms), started_at=datetime.now(), finished_at=datetime.now())
        db.add(log2)
        await db.commit()
        await publish_agent_log(task_id, "CRAWLER", "SUCCESS", "fetch", 0)
        print(f"[Crawler] Task {task_id} crawled {total} urls, {fetched_ok} ok, {failed} failed")
    return None


async def _crawl_one(task_id, item, fetcher, playwright, cleaner, rate_limiter, robots, semaphore) -> tuple:
    async with semaphore:
        url = item.url
        await rate_limiter.acquire(url)
        page = await fetcher.fetch(url)
        crawl_mode = "STATIC"
        async with get_crawler_session_factory()() as db:
            task = await db.get(CrawlTask, task_id)
            plan_hint = None
            if task and task.plan_json:
                try:
                    plan = safe_json(task.plan_json)
                    plan_hint = (plan or {}).get("crawl_mode_hint")
                except Exception:
                    pass

        router_mode = CrawlerRouter.decide(url, plan_hint, page)
        static_len = 0
        if not page.ok:
            # 静态抓取失败（403 / 超时 / 空壳）也尝试 JS 渲染兜底
            router_mode = "JS_RENDER"
        elif page.html:
            # 静态成功但内容近乎空壳（JS 渲染站点常见）：无视 planner hint，按实际内容判断
            pre = cleaner.clean(page.html, url)
            static_len = len(pre.clean_text)
            if static_len < 80:
                router_mode = "JS_RENDER"
        if router_mode == "JS_RENDER" and await playwright.is_available():
            rendered = await playwright.fetch(url)
            if rendered.ok and rendered.html:
                if not page.ok:
                    page = rendered; crawl_mode = "JS_RENDER"
                else:
                    js_len = len(cleaner.clean(rendered.html, url).clean_text)
                    if js_len > static_len:
                        page = rendered; crawl_mode = "JS_RENDER"

        async with get_crawler_session_factory()() as db:
            now = datetime.now(); ok = page.ok and page.html is not None
            task = await db.get(CrawlTask, task_id)
            if ok:
                cleaned = cleaner.clean(page.html, url)
                pr = CrawlPage(task_id=task_id, url_queue_id=item.id, url=url, final_url=page.final_url, http_status=page.http_status, content_type=page.content_type, rendered_html=page.html, clean_text=cleaned.clean_text or "", charset=page.charset, crawl_mode=crawl_mode, fetch_time_ms=page.fetch_time_ms, fetched_at=now)
                db.add(pr); await db.flush(); await db.refresh(pr)
                qi = await db.get(UrlQueueItem, item.id)
                if qi:
                    qi.status = "SUCCESS"
                    qi.crawl_mode = crawl_mode
                    qi.http_status = page.http_status
                    qi.page_id = pr.id
                    qi.last_attempt_at = now
                    qi.error_message = None
                if item.depth < (task.max_depth if task else 3):
                    # 发现的新链接与外层提交同一事务，确保落库（原实现在 commit 后才调用导致深度链接丢失）
                    await _discover_links(db, task_id, url, item.depth + 1, cleaned.links, task.max_pages if task else 100)
                await db.commit()
                await publish_url_progress(task_id, url, "SUCCESS", crawl_mode, page.fetch_time_ms)
                return True, item.id
            else:
                qi = await db.get(UrlQueueItem, item.id)
                if qi and qi.retry_count < CRAWLER_MAX_RETRIES:
                    # 失败重试：重置为 PENDING，下一轮循环会再次抓取
                    qi.retry_count += 1
                    qi.status = "PENDING"
                    qi.error_message = page.error_message or f"http {page.http_status}"
                    qi.crawl_mode = crawl_mode
                    qi.http_status = page.http_status
                    qi.last_attempt_at = now
                    await db.commit()
                    return False, item.id
                if qi:
                    qi.status = "FAILED"
                    qi.error_message = page.error_message or f"http {page.http_status}"
                    qi.crawl_mode = crawl_mode
                    qi.http_status = page.http_status
                    qi.last_attempt_at = now
                await db.commit()
                await publish_url_progress(task_id, url, "FAILED", crawl_mode, page.fetch_time_ms)
                return False, item.id


async def _discover_links(db, task_id, base_url, depth, links, max_pages):
    for link in links:
        count = await db.scalar(select(func.count()).select_from(UrlQueueItem).where(UrlQueueItem.task_id == task_id))
        if count and count >= max_pages: return
        target = normalize(link.url)
        if is_static_asset(target) or target == base_url: continue
        if not is_same_domain(base_url, target): continue
        h = url_hash(task_id, target)
        exists = await db.scalar(select(func.count()).select_from(UrlQueueItem).where(UrlQueueItem.task_id == task_id, UrlQueueItem.url_hash == h))
        if exists and exists > 0: continue
        db.add(UrlQueueItem(task_id=task_id, url=target, url_hash=h, depth=depth, source="DISCOVERY", status="PENDING", retry_count=0))
        try:
            # flush 让唯一索引立即生效，重复链接冲突时仅回滚到 savepoint，不影响整个事务
            async with db.begin_nested():
                await db.flush()
        except IntegrityError:
            pass
