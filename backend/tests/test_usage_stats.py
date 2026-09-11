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


def _insert_agent(factory, agent_id: int, name: str):
    """插一个真实智能体（外键未启用，created_by 不需要真有对应用户）"""
    from app.models.agent import Agent

    async def _run():
        async with factory() as db:
            db.add(Agent(id=agent_id, name=name, created_by=1))
            await db.commit()

    asyncio.run(_run())


def _delete_agent(factory, agent_id: int):
    from sqlalchemy import delete as sa_delete

    from app.models.agent import Agent

    async def _run():
        async with factory() as db:
            await db.execute(sa_delete(Agent).where(Agent.id == agent_id))
            await db.commit()

    asyncio.run(_run())


def _insert(factory, *rows):
    async def _run():
        async with factory() as db:
            for r in rows:
                db.add(r)
            await db.commit()

    asyncio.run(_run())


class TestPerAgentBreakdown:
    """按智能体聚合：排序、名称快照、无归属分组"""

    def test_按总token降序(self, usage_db):
        """场景：两个智能体用量不同 → 最贵的排最前"""
        _insert(
            usage_db,
            _row(agent_id=1, agent_name="便宜助手", total_tokens=100,
                 prompt_tokens=80, completion_tokens=20),
            _row(agent_id=2, agent_name="昂贵助手", total_tokens=300,
                 prompt_tokens=200, completion_tokens=100),
        )

        result = _overview(usage_db, date(2026, 9, 1), date(2026, 9, 15))

        assert [r.agent_name for r in result.agents] == ["昂贵助手", "便宜助手"]
        assert result.agents[0].total_tokens == 300
        assert result.agents[0].agent_id == 2

    def test_改名后仍归到同一行_显示最新名称(self, usage_db):
        """场景：同一智能体先后留下两个名称快照 → 合并成一行，名称取最近一次"""
        _insert(
            usage_db,
            _row(agent_id=1, agent_name="旧名", created_at="2026-09-02T10:00:00",
                 total_tokens=50, prompt_tokens=40, completion_tokens=10),
            _row(agent_id=1, agent_name="新名", created_at="2026-09-03T10:00:00",
                 total_tokens=70, prompt_tokens=60, completion_tokens=10),
        )

        result = _overview(usage_db, date(2026, 9, 1), date(2026, 9, 15))

        assert len(result.agents) == 1
        assert result.agents[0].agent_name == "新名"
        assert result.agents[0].total_tokens == 120
        assert result.agents[0].llm_calls == 2

    def test_智能体被删除后_历史仍可读(self, usage_db):
        """场景：先建智能体、留下用量，再把它删掉 → 报表仍按名称快照显示"""
        _insert_agent(usage_db, agent_id=99, name="将被删除的智能体")
        _insert(usage_db, _row(agent_id=99, agent_name="将被删除的智能体", total_tokens=42))
        _delete_agent(usage_db, agent_id=99)

        result = _overview(usage_db, date(2026, 9, 1), date(2026, 9, 15))

        assert result.agents[0].agent_name == "将被删除的智能体"
        assert result.agents[0].agent_id == 99
        assert result.agents[0].total_tokens == 42

    def test_最新一条快照名称为空_退回最近的非空名称(self, usage_db):
        """场景：智能体被删后，绑定它的会话仍会写出名称为空的流水

        若最新一条恰好为空，不能因此丢掉历史名称。
        """
        _insert(
            usage_db,
            _row(agent_id=99, agent_name="历史名称", created_at="2026-09-02T10:00:00"),
            _row(agent_id=99, agent_name=None, created_at="2026-09-05T10:00:00"),
        )

        result = _overview(usage_db, date(2026, 9, 1), date(2026, 9, 15))

        assert result.agents[0].agent_name == "历史名称"

    def test_无归属记录_归入未绑定智能体(self, usage_db):
        """场景：智能体配置测试等无归属调用 → 单独一行「未绑定智能体」"""
        _insert(usage_db, _row(agent_id=None, agent_name=None, total_tokens=11))

        result = _overview(usage_db, date(2026, 9, 1), date(2026, 9, 15))

        assert len(result.agents) == 1
        assert result.agents[0].agent_id is None
        assert result.agents[0].agent_name == "未绑定智能体"
        assert result.agents[0].total_tokens == 11

    def test_用量相同时_未绑定排在真实智能体之后(self, usage_db):
        """场景：两者 token 相同 → NULL 不应压过真实智能体（SQLite 升序会把 NULL 排最前）"""
        _insert(
            usage_db,
            _row(agent_id=None, agent_name=None, total_tokens=100,
                 prompt_tokens=80, completion_tokens=20),
            _row(agent_id=5, agent_name="真实智能体", total_tokens=100,
                 prompt_tokens=80, completion_tokens=20),
        )

        result = _overview(usage_db, date(2026, 9, 1), date(2026, 9, 15))

        assert [r.agent_name for r in result.agents] == ["真实智能体", "未绑定智能体"]

    def test_最近调用时间_取该智能体最新一次(self, usage_db):
        """场景：同一智能体两次调用 → 最近调用时间取较晚的那次"""
        _insert(
            usage_db,
            _row(agent_id=1, agent_name="A", created_at="2026-09-02T09:00:00"),
            _row(agent_id=1, agent_name="A", created_at="2026-09-05T18:30:00"),
        )

        result = _overview(usage_db, date(2026, 9, 1), date(2026, 9, 15))

        assert result.agents[0].last_called_at == "2026-09-05T18:30:00"


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

    def test_双计数_问答次数只数主回答(self, usage_db):
        """场景：范围内含工具轮/改写/Text2SQL → 问答次数只数主回答，模型调用次数数全部"""
        _insert(
            usage_db,
            _row(call_type="chat"),
            _row(call_type="tool"),
            _row(call_type="rewrite"),
            _row(call_type="text2sql"),
        )

        result = _overview(usage_db, date(2026, 9, 1), date(2026, 9, 15))

        assert result.totals.requests == 1
        assert result.totals.llm_calls == 4

    def test_估算行只进排除计数_不进任何合计(self, usage_db):
        """场景：范围内有两条估算调用 → 只体现在 excluded，token 合计不受影响"""
        _insert(
            usage_db,
            _row(),
            _row(is_estimated=True, prompt_tokens=50, completion_tokens=10, total_tokens=60),
            _row(is_estimated=True, prompt_tokens=70, completion_tokens=20, total_tokens=90),
        )

        result = _overview(usage_db, date(2026, 9, 1), date(2026, 9, 15))

        assert result.totals.llm_calls == 1
        assert result.totals.requests == 1
        assert result.totals.total_tokens == 120
        assert result.excluded.estimated_calls == 2

    def test_失败行_既不计入合计也不计入排除计数(self, usage_db):
        """场景：失败调用单独留痕，但不属于「估算被排除」，也不进任何数字"""
        _insert(usage_db, _row(), _row(status="error"))

        result = _overview(usage_db, date(2026, 9, 1), date(2026, 9, 15))

        assert result.totals.llm_calls == 1
        assert result.excluded.estimated_calls == 0

    def test_明细各列与汇总自洽(self, usage_db):
        """场景：三行分属两个智能体与一个无归属 → 明细逐列相加等于汇总"""
        _insert(
            usage_db,
            _row(agent_id=1, agent_name="A"),
            _row(agent_id=2, agent_name="B", call_type="tool", total_tokens=30,
                 prompt_tokens=20, completion_tokens=10),
            _row(agent_id=None, agent_name=None),
        )

        result = _overview(usage_db, date(2026, 9, 1), date(2026, 9, 15))

        assert sum(r.llm_calls for r in result.agents) == result.totals.llm_calls
        assert sum(r.total_tokens for r in result.agents) == result.totals.total_tokens
        assert sum(r.requests for r in result.agents) == result.totals.requests

    def test_范围内没有数据_返回全零(self, usage_db):
        """场景：空区间 → 各计数为 0，而不是 null"""
        result = _overview(usage_db, date(2026, 1, 1), date(2026, 1, 31))

        assert result.totals.llm_calls == 0
        assert result.totals.prompt_tokens == 0
        assert result.totals.completion_tokens == 0
        assert result.totals.total_tokens == 0
        assert result.start == "2026-01-01"
        assert result.end == "2026-01-31"
