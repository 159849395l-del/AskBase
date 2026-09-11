"""测试用量时间序列 — 分桶、补零、默认区间与跨度上限

seam：统计服务的公开查询入口 + 临时文件库；分桶/补零/默认区间是纯函数，直接断言。
"""

import asyncio
from datetime import date, timedelta

import pytest

from app.models.llm_usage import LLMUsageLog
from app.services.usage_stats_service import (
    MAX_BUCKETS,
    iter_buckets,
    resolve_range,
    timeseries,
)

from tests.test_usage_stats import _insert, _row


def _series(factory, start, end, granularity):
    async def _run():
        async with factory() as db:
            return await timeseries(db, start, end, granularity)

    return asyncio.run(_run())


class TestIterBuckets:
    """时间桶序列：含首尾、跨月跨年闰年都正确"""

    def test_单日范围(self):
        """场景：起止同一天 → 只一个桶"""
        assert iter_buckets(date(2026, 9, 11), date(2026, 9, 11), "day") == ["2026-09-11"]

    def test_跨月(self):
        """场景：跨自然月 → 逐日连续"""
        assert iter_buckets(date(2026, 1, 30), date(2026, 2, 2), "day") == [
            "2026-01-30", "2026-01-31", "2026-02-01", "2026-02-02",
        ]

    def test_跨年(self):
        """场景：跨自然年 → 逐日连续"""
        assert iter_buckets(date(2025, 12, 30), date(2026, 1, 2), "day") == [
            "2025-12-30", "2025-12-31", "2026-01-01", "2026-01-02",
        ]

    def test_闰年二月(self):
        """场景：2024 是闰年 → 出现 02-29"""
        assert iter_buckets(date(2024, 2, 28), date(2024, 3, 1), "day") == [
            "2024-02-28", "2024-02-29", "2024-03-01",
        ]

    def test_月粒度_跨年连续(self):
        """场景：月粒度跨年 → 含首尾所在月"""
        assert iter_buckets(date(2025, 11, 15), date(2026, 2, 3), "month") == [
            "2025-11", "2025-12", "2026-01", "2026-02",
        ]

    def test_年粒度(self):
        """场景：年粒度 → 含首尾所在年"""
        assert iter_buckets(date(2024, 5, 1), date(2026, 2, 1), "year") == [
            "2024", "2025", "2026",
        ]

    def test_超过桶数上限_抛错(self):
        """场景：按日查十年 → 桶数远超上限，直接拒绝而不是硬算"""
        with pytest.raises(ValueError):
            iter_buckets(date(2016, 1, 1), date(2026, 1, 1), "day")

    def test_恰好上限_允许(self):
        """场景：桶数正好等于上限 → 允许"""
        start = date(2026, 1, 1)
        end = start + timedelta(days=MAX_BUCKETS - 1)
        assert len(iter_buckets(start, end, "day")) == MAX_BUCKETS


class TestTimeseriesEndpoint:
    """端点契约：跨度超上限映射成 400 + 明确文案"""

    def test_跨度超上限_返回400且带明确文案(self):
        """场景：按日查十年 → 在触库之前就被拒绝，并给出可操作的建议"""
        from fastapi import HTTPException

        from app.api.usage import get_timeseries

        async def _call():
            await get_timeseries(
                granularity="day",
                start=date(2016, 1, 1),
                end=date(2026, 1, 1),
                admin_user=None,
                db=None,  # 超限在访问数据库之前就抛出
            )

        with pytest.raises(HTTPException) as exc:
            asyncio.run(_call())

        assert exc.value.status_code == 400
        assert "时间跨度过大" in exc.value.detail
        assert "粒度" in exc.value.detail


class TestResolveRange:
    """默认区间：日近 30 天、月近 12 个月、年近 5 年"""

    def test_日粒度_近30天(self):
        """场景：只给粒度 → 默认近 30 天（含今天）"""
        start, end = resolve_range(None, None, "day", today=date(2026, 9, 11))
        assert (start, end) == (date(2026, 8, 13), date(2026, 9, 11))

    def test_月粒度_近12个月(self):
        """场景：月粒度 → 从 11 个月前的 1 号到今天所在月"""
        start, end = resolve_range(None, None, "month", today=date(2026, 9, 11))
        assert start == date(2025, 10, 1)
        assert end == date(2026, 9, 11)

    def test_年粒度_近5年(self):
        """场景：年粒度 → 从 4 年前的 1 月 1 日起"""
        start, end = resolve_range(None, None, "year", today=date(2026, 9, 11))
        assert start == date(2022, 1, 1)
        assert end == date(2026, 9, 11)

    def test_显式区间_原样保留(self):
        """场景：用户自选起止 → 不被默认值覆盖"""
        start, end = resolve_range(date(2026, 1, 5), date(2026, 2, 6), "day",
                                   today=date(2026, 9, 11))
        assert (start, end) == (date(2026, 1, 5), date(2026, 2, 6))

    def test_只给结束_起点按粒度推导(self):
        """场景：只给 end → start 以该 end 为基准推导"""
        start, end = resolve_range(None, date(2026, 3, 10), "day", today=date(2026, 9, 11))
        assert (start, end) == (date(2026, 2, 9), date(2026, 3, 10))


class TestTimeseriesPoints:
    """时间序列：无数据的桶补 0，曲线连续；口径与总览一致"""

    def test_无数据的桶补零且连续(self, usage_db):
        """场景：只有中间一天有数据 → 两端补 0，长度等于桶数"""
        _insert(usage_db, _row(created_at="2026-09-11T10:00:00", total_tokens=120))

        result = _series(usage_db, date(2026, 9, 9), date(2026, 9, 13), "day")

        assert [p.bucket for p in result.points] == [
            "2026-09-09", "2026-09-10", "2026-09-11", "2026-09-12", "2026-09-13",
        ]
        assert [p.total_tokens for p in result.points] == [0, 0, 120, 0, 0]
        assert [p.llm_calls for p in result.points] == [0, 0, 1, 0, 0]

    def test_按月分桶聚合(self, usage_db):
        """场景：跨月数据 → 同月相加，落在各自月桶"""
        _insert(
            usage_db,
            _row(created_at="2026-08-05T10:00:00", total_tokens=10),
            _row(created_at="2026-08-20T10:00:00", total_tokens=20),
            _row(created_at="2026-09-01T10:00:00", total_tokens=5),
        )

        result = _series(usage_db, date(2026, 8, 1), date(2026, 9, 30), "month")

        assert [p.bucket for p in result.points] == ["2026-08", "2026-09"]
        assert [p.total_tokens for p in result.points] == [30, 5]

    def test_按年分桶聚合(self, usage_db):
        """场景：跨年数据 → 落在各自年桶"""
        _insert(
            usage_db,
            _row(created_at="2025-06-01T10:00:00", total_tokens=7),
            _row(created_at="2026-06-01T10:00:00", total_tokens=9),
        )

        result = _series(usage_db, date(2025, 1, 1), date(2026, 12, 31), "year")

        assert [p.bucket for p in result.points] == ["2025", "2026"]
        assert [p.total_tokens for p in result.points] == [7, 9]

    def test_口径与总览一致_估算与失败行不进序列(self, usage_db):
        """场景：混入估算行与失败行 → 序列只认真实成功用量"""
        _insert(
            usage_db,
            _row(created_at="2026-09-11T10:00:00", total_tokens=120),
            _row(created_at="2026-09-11T11:00:00", is_estimated=True, total_tokens=60),
            _row(created_at="2026-09-11T12:00:00", status="error", total_tokens=0),
        )

        result = _series(usage_db, date(2026, 9, 11), date(2026, 9, 11), "day")

        point = result.points[0]
        assert point.llm_calls == 1
        assert point.total_tokens == 120

    def test_区分问答次数与模型调用次数(self, usage_db):
        """场景：同一天既有主回答又有工具轮 → 两个计数分别累加"""
        _insert(
            usage_db,
            _row(call_type="chat", created_at="2026-09-11T10:00:00"),
            _row(call_type="tool", created_at="2026-09-11T10:01:00"),
            _row(call_type="rewrite", created_at="2026-09-11T10:02:00"),
        )

        result = _series(usage_db, date(2026, 9, 11), date(2026, 9, 11), "day")

        assert result.points[0].requests == 1
        assert result.points[0].llm_calls == 3

    def test_输入输出分别累计(self, usage_db):
        """场景：token 折线要区分输入与输出 → 两个字段各自求和"""
        _insert(
            usage_db,
            _row(created_at="2026-09-11T10:00:00", prompt_tokens=80, completion_tokens=20,
                 total_tokens=100),
            _row(created_at="2026-09-11T11:00:00", prompt_tokens=30, completion_tokens=10,
                 total_tokens=40),
        )

        result = _series(usage_db, date(2026, 9, 11), date(2026, 9, 11), "day")

        assert result.points[0].prompt_tokens == 110
        assert result.points[0].completion_tokens == 30

    def test_空区间_全部补零(self, usage_db):
        """场景：范围内一条数据都没有 → 返回补齐的零序列，而不是空数组"""
        result = _series(usage_db, date(2026, 1, 1), date(2026, 1, 3), "day")

        assert len(result.points) == 3
        assert all(p.total_tokens == 0 and p.llm_calls == 0 for p in result.points)
        assert result.granularity == "day"
        assert result.start == "2026-01-01"
        assert result.end == "2026-01-03"
