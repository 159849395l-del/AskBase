"""爬虫编排器 — 状态机驱动的多 Agent 流水线"""
import asyncio
import logging
from datetime import datetime
from typing import Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.crawler.models import CrawlTask, TaskStatus, get_crawler_session_factory
from app.crawler.engine.planner import execute_planning
from app.crawler.engine.discovery import execute_discovery
from app.crawler.engine.crawler import execute_crawling
from app.crawler.engine.extractor import execute_extracting
from app.crawler.engine.verifier import execute_verifying
from app.crawler.engine.aggregator import execute_aggregating
from app.crawler.sse_publisher import publish_status, publish_error

logger = logging.getLogger(__name__)

STATEMACHINE = {
    TaskStatus.PENDING: TaskStatus.PLANNING,
    TaskStatus.PLANNING: TaskStatus.DISCOVERING,
    TaskStatus.DISCOVERING: TaskStatus.CRAWLING,
    TaskStatus.CRAWLING: TaskStatus.EXTRACTING,
    TaskStatus.EXTRACTING: TaskStatus.VERIFYING,
    TaskStatus.VERIFYING: TaskStatus.AGGREGATING,
    TaskStatus.AGGREGATING: TaskStatus.COMPLETED,
}

EXECUTORS = {
    TaskStatus.PLANNING: execute_planning,
    TaskStatus.DISCOVERING: execute_discovery,
    TaskStatus.CRAWLING: execute_crawling,
    TaskStatus.EXTRACTING: execute_extracting,
    TaskStatus.VERIFYING: execute_verifying,
    TaskStatus.AGGREGATING: execute_aggregating,
}


async def submit_task(task_id: int):
    try:
        await _run_pipeline(task_id)
    except Exception as e:
        logger.error(f"Pipeline failed for task {task_id}: {e}")
        async with get_crawler_session_factory()() as db:
            task = await db.get(CrawlTask, task_id)
            if task:
                task.status = TaskStatus.FAILED.value
                task.error_message = str(e)[:500]
                task.finished_at = datetime.now()
                await db.commit()
        await publish_error(task_id, str(e))


async def _run_pipeline(task_id: int):
    while True:
        task = await _wait_for_task(task_id)
        if task is None:
            return
        current = TaskStatus(task.status)
        if current.is_terminal():
            return
        next_status = STATEMACHINE.get(current)
        if next_status is None:
            return
        executor = EXECUTORS.get(current)
        override = None
        if executor:
            try:
                if current == TaskStatus.AGGREGATING:
                    override = await executor(task_id)
                else:
                    await executor(task_id)
            except Exception as e:
                logger.error(f"Agent failed for task {task_id} at {current.value}: {e}")
                await _fail(task_id, current, str(e))
                return
        if not await _advance(task_id, current, override if override else next_status):
            return


async def _wait_for_task(task_id: int, retries: int = 20, delay: float = 0.3) -> Optional[CrawlTask]:
    for _ in range(retries):
        async with get_crawler_session_factory()() as db:
            task = await db.get(CrawlTask, task_id)
            if task is not None:
                return task
        await asyncio.sleep(delay)
    return None


async def _advance(task_id: int, from_status: TaskStatus, to_status: TaskStatus) -> bool:
    async with get_crawler_session_factory()() as db:
        task = await db.get(CrawlTask, task_id)
        if task is None:
            return False
        current = TaskStatus(task.status)
        if current != from_status:
            return False
        _assert_transition(from_status, to_status)
        task.status = to_status.value
        if task.started_at is None:
            task.started_at = datetime.now()
        if to_status.is_terminal():
            task.finished_at = datetime.now()
        await db.commit()
    await publish_status(task_id, to_status.value, from_status.value)
    logger.info(f"Task {task_id} status: {from_status.value} -> {to_status.value}")
    return True


async def _fail(task_id: int, from_status: TaskStatus, error: str):
    async with get_crawler_session_factory()() as db:
        task = await db.get(CrawlTask, task_id)
        if task:
            task.status = TaskStatus.FAILED.value
            task.error_message = error[:500]
            task.finished_at = datetime.now()
            await db.commit()
    await publish_status(task_id, TaskStatus.FAILED.value, from_status.value)
    await publish_error(task_id, error)


def _assert_transition(from_status: TaskStatus, to_status: TaskStatus):
    expected = STATEMACHINE.get(from_status)
    if expected and to_status != expected:
        if from_status == TaskStatus.AGGREGATING and to_status in (TaskStatus.COMPLETED, TaskStatus.PARTIAL, TaskStatus.FAILED):
            return
        raise ValueError(f"\u975e\u6cd5\u72b6\u6001\u8f6c\u6362: {from_status.value} -> {to_status.value}")
