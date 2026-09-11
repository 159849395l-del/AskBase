"""测试用量统计的汇总口径 — 只认端点确认的真实成功用量

seam：统计服务的公开查询入口 + 临时文件库
"""

import asyncio
from datetime import date

from app.models.llm_usage import LLMUsageLog
from app.services.usage_stats_service import overview


def _row(**overrides):
    base = dict(
        model_name="deepseek-chat",
        call_type="chat",
        prompt_tokens=100,
        completion_tokens=20,
        total_tokens=120,
        is_estimated=False,
        status="success",
        created_at="2026-09-11T10:00:00",
    )
    base.update(overrides)
    return LLMUsageLog(**base)


def _insert(factory, *rows):
    async def _run():
        async with factory() as db:
            for r in rows:
                db.add(r)
            await db.commit()

    asyncio.run(_run())


def _overview(factory, start, end):
    async def _run():
        async with factory() as db:
            return await overview(db, start, end)

    return asyncio.run(_run())


class TestOverviewTotals:
    """汇总口径：估算行与失败行不进入任何数字"""

    def test_只统计真实成功的调用(self, usage_db):
        """场景：范围内混入估算行与失败行 → 只累加真实成功的那条"""
        _insert(
            usage_db,
            _row(),
            _row(is_estimated=True, prompt_tokens=50, completion_tokens=10, total_tokens=60),
            _row(status="error", prompt_tokens=0, completion_tokens=0, total_tokens=0),
            _row(created_at="2026-09-20T10:00:00", total_tokens=999),
        )

        result = _overview(usage_db, date(2026, 9, 1), date(2026, 9, 15))

        assert result.totals.llm_calls == 1
        assert result.totals.prompt_tokens == 100
        assert result.totals.completion_tokens == 20
        assert result.totals.total_tokens == 120

    def test_时间范围含首尾两日(self, usage_db):
        """场景：起点当天 00:00 与终点当天 23:59 都算在内，次日 00:00 排除"""
        _insert(
            usage_db,
            _row(created_at="2026-09-01T00:00:00", total_tokens=1),
            _row(created_at="2026-09-15T23:59:59", total_tokens=2),
            _row(created_at="2026-09-16T00:00:00", total_tokens=999),
        )

        result = _overview(usage_db, date(2026, 9, 1), date(2026, 9, 15))

        assert result.totals.llm_calls == 2
        assert result.totals.total_tokens == 3

    def test_范围内没有数据_返回全零(self, usage_db):
        """场景：空区间 → 各计数为 0，而不是 null"""
        result = _overview(usage_db, date(2026, 1, 1), date(2026, 1, 31))

        assert result.totals.llm_calls == 0
        assert result.totals.prompt_tokens == 0
        assert result.totals.completion_tokens == 0
        assert result.totals.total_tokens == 0
        assert result.start == "2026-01-01"
        assert result.end == "2026-01-31"
