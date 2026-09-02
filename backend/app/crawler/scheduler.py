"""
定时爬取调度器 — 周期性扫描启用的 CrawlSchedule，到点自动开启新一轮爬取

- 每 TICK_SECONDS 秒扫描一次数据库（进程内单实例，uvicorn --reload 只有一个 worker 会跑 lifespan）。
- 触发语义：schedule 关联任务必须处于终态（上一轮已结束）才会开启新一轮，
  否则跳过本轮、等下一个周期，避免与正在运行的状态机冲突。
- 执行时刻对齐 daily run_time：last_run_at 之后的下一个 run_time（间隔 interval_days 天）<= now 即触发。
  从未执行过则以调度创建时刻为前界，不会误把当天尚未到点的时刻判成错过。
- 触发后立刻把 last_run_at 置为当前时间并落库，防止同周期重复触发（也天然防多进程双跑）。
"""

import asyncio
import logging
from datetime import datetime, time as dtime, timedelta

from sqlalchemy import delete, select

from app.crawler.models import (
    AgentLog,
    CrawlPage,
    CrawlResult,
    CrawlSchedule,
    CrawlTask,
    TaskStatus,
    UrlQueueItem,
    get_crawler_session_factory,
)
from app.crawler.utils import normalize_run_time

logger = logging.getLogger(__name__)

TICK_SECONDS = 20
DEFAULT_RUN_TIME = "02:00:00"


def parse_run_time(run_time_value) -> dtime:
    """解析 run_time（兼容 timedelta / str / time），失败回退 02:00:00"""
    try:
        text = normalize_run_time(run_time_value)
        hh, mm, ss = text.split(":")
        return dtime(int(hh), int(mm), int(ss))
    except Exception:
        return dtime(2, 0, 0)


def next_run_after(run_time_str: str, interval_days: int, after: datetime) -> datetime:
    """返回 after 之后第一个计划执行时刻

    候选 = after 所在日的 run_time；若该时刻已不晚于 after，则顺延 interval_days 天。
    interval_days <= 0 按 1 处理。
    """
    rt = parse_run_time(run_time_str)
    candidate = datetime.combine(after.date(), rt)
    if candidate <= after:
        candidate += timedelta(days=max(1, interval_days or 1))
    return candidate


async def _dispatch_due() -> None:
    """找出所有到点的 schedule 并触发新一轮爬取"""
    now = datetime.now()
    factory = get_crawler_session_factory()

    async with factory() as db:
        rows = (
            await db.execute(select(CrawlSchedule).where(CrawlSchedule.enabled == True))  # noqa: E712
        ).scalars().all()

        for sched in rows:
            try:
                # 前界 = 上次实际执行时刻；从未执行过则从调度创建时刻起算，
                # 保证今天尚未到点的 run_time 不会被"昨天已错过"误判
                after = sched.last_run_at or sched.created_at or now
                next_at = next_run_after(sched.run_time, sched.interval_days, after)
                if next_at > now:
                    continue  # 未到点

                task = await db.get(CrawlTask, sched.task_id)
                if task is None:
                    logger.warning("[Schedule] task %s 不存在，跳过", sched.task_id)
                    continue
                if not TaskStatus(task.status).is_terminal():
                    # 上一轮还在跑：跳过本轮，等下一个周期再判断
                    continue

                # —— 到点：重置任务数据（与手动 restart 语义一致）后开启新一轮 ——
                await db.execute(delete(UrlQueueItem).where(UrlQueueItem.task_id == task.id))
                await db.execute(delete(CrawlPage).where(CrawlPage.task_id == task.id))
                await db.execute(delete(CrawlResult).where(CrawlResult.task_id == task.id))
                await db.execute(delete(AgentLog).where(AgentLog.task_id == task.id))
                task.status = TaskStatus.PENDING.value
                task.error_message = None
                task.started_at = None
                task.finished_at = None
                task.stats_json = None
                task.schema_json = None
                task.plan_json = None

                sched.last_run_at = now
                sched.last_status = "RUNNING"
                sched.last_detail = f"定时触发：{now:%Y-%m-%d %H:%M:%S}"
                await db.commit()

                from app.crawler.engine.orchestrator import submit_task

                asyncio.create_task(submit_task(task.id))
                logger.info(
                    "[Schedule] 已触发任务 %s（%s），下次计划从 %s 起算",
                    task.id, task.title, sched.last_run_at,
                )
            except Exception:
                logger.exception("[Schedule] 处理 schedule %s 失败", getattr(sched, "id", "?"))


async def scheduler_loop() -> None:
    """调度主循环：启动后常驻，直到进程关闭"""
    logger.info("[Schedule] 定时调度器已启动（每 %s 秒扫描一次）", TICK_SECONDS)
    while True:
        try:
            await _dispatch_due()
        except Exception:
            logger.exception("[Schedule] 扫描周期异常，继续下一轮")
        await asyncio.sleep(TICK_SECONDS)
