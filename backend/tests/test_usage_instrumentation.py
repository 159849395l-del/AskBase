"""测试用量埋点接线 — 一次提问背后的每一类模型调用都进账

seam（已与用户约定）：假模型注入替换 chain 的模块级协作者，驱动**真实的编排函数**，
只在公开边界（SSE 事件 + 流水表）上断言。不联网、不连向量库、不碰开发数据库。
"""

import asyncio
from types import SimpleNamespace

import pytest
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, AIMessageChunk

from app.config import settings
from app.models.data_source import DataSource
from app.rag.chain import stream_rag_response
from app.rag.text2sql import run_sql_query
from app.services.usage_service import UsageContext


def _content(text):
    return AIMessageChunk(content=text, usage_metadata=None)


def _usage_chunk(prompt, completion):
    return AIMessageChunk(
        content="",
        usage_metadata={
            "input_tokens": prompt,
            "output_tokens": completion,
            "total_tokens": prompt + completion,
        },
    )


class FakeStreamingLLM:
    """主回答用的假流式客户端"""

    def __init__(self, chunks, model_name="fake-chat-model", error=None):
        self._chunks = chunks
        self.model_name = model_name
        self._error = error

    async def astream(self, messages):
        if self._error:
            raise self._error
        for chunk in self._chunks:
            yield chunk


class FakeInvokeLLM:
    """改写 / 压缩 / Text2SQL 用的假一次性客户端"""

    def __init__(self, content="改写后的问题", usage=(30, 5), model_name="fake-invoke-model"):
        self._content = content
        self._usage = usage
        self.model_name = model_name
        self.calls = 0

    async def ainvoke(self, messages):
        self.calls += 1
        return AIMessage(
            content=self._content,
            usage_metadata={
                "input_tokens": self._usage[0],
                "output_tokens": self._usage[1],
                "total_tokens": self._usage[0] + self._usage[1],
            },
        )


class FakeToolLLM:
    """工具轮用的假客户端：第 1 次 ainvoke 要求调工具，之后不再调"""

    def __init__(self, chunks, model_name="fake-tool-model"):
        self._chunks = chunks
        self.model_name = model_name
        self.ainvoke_calls = 0

    def bind_tools(self, specs):
        return self

    async def ainvoke(self, messages):
        self.ainvoke_calls += 1
        tool_calls = (
            [{"name": "get_current_time", "args": {}, "id": "call_1"}]
            if self.ainvoke_calls == 1
            else []
        )
        return AIMessage(
            content="",
            tool_calls=tool_calls,
            usage_metadata={"input_tokens": 40, "output_tokens": 4, "total_tokens": 44},
        )

    async def astream(self, messages):
        for chunk in self._chunks:
            yield chunk


def _types(rows):
    return sorted(r.call_type for r in rows)


class TestInternalCallsAreMetered:
    """一次提问背后的改写 / 压缩 / 工具轮 / Text2SQL 都要各留一条记录"""

    def test_查询改写_留下rewrite记录(self, usage_db, read_rows, monkeypatch):
        """场景：开启改写且有历史 → 改写那次调用进账，类型为 rewrite"""
        monkeypatch.setattr(settings, "QUERY_REWRITE_ENABLED", True)
        _patch_retrieval(monkeypatch)
        rewriter = FakeInvokeLLM(content="退货政策是什么（改写）", usage=(30, 5))
        monkeypatch.setattr("app.rag.chain.get_llm", lambda *a, **k: rewriter)
        monkeypatch.setattr("app.rag.chain.resolve_llm", _resolve(FakeStreamingLLM([_content("答"), _usage_chunk(10, 2)])))

        _run(history=[("human", "之前问过什么"), ("ai", "之前答过什么")])

        rows = read_rows(usage_db)
        assert _types(rows) == ["chat", "rewrite"]
        rewrite = [r for r in rows if r.call_type == "rewrite"][0]
        assert (rewrite.prompt_tokens, rewrite.completion_tokens, rewrite.total_tokens) == (30, 5, 35)
        assert rewrite.is_estimated is False
        assert rewrite.model_name == "fake-invoke-model"

    def test_上下文压缩_留下compress记录(self, usage_db, read_rows, monkeypatch):
        """场景：历史超过压缩阈值 → 压缩那次调用进账，类型为 compress"""
        # 显式关掉改写：本用例只关心压缩，且不能依赖 .env 的取值
        monkeypatch.setattr(settings, "QUERY_REWRITE_ENABLED", False)
        _clear_summary_cache()
        _patch_retrieval(monkeypatch)
        compressor = FakeInvokeLLM(content="历史摘要", usage=(60, 8))
        monkeypatch.setattr("app.rag.chain.get_llm", lambda *a, **k: compressor)
        monkeypatch.setattr("app.rag.chain.resolve_llm", _resolve(FakeStreamingLLM([_content("答"), _usage_chunk(10, 2)])))
        long_history = [(("human" if i % 2 == 0 else "ai"), f"内容{i}") for i in range(8)]

        _run(history=long_history, conv_id=1, last_msg_id=99)

        rows = read_rows(usage_db)
        assert _types(rows) == ["chat", "compress"]
        compress = [r for r in rows if r.call_type == "compress"][0]
        assert compress.total_tokens == 68

    def test_压缩缓存命中_不产生新记录(self, usage_db, read_rows, monkeypatch):
        """场景：同一会话同一最近消息再次提问 → 摘要复用，不再调用模型、不再记录"""
        monkeypatch.setattr(settings, "QUERY_REWRITE_ENABLED", False)
        _clear_summary_cache()
        _patch_retrieval(monkeypatch)
        compressor = FakeInvokeLLM(content="历史摘要", usage=(60, 8))
        monkeypatch.setattr("app.rag.chain.get_llm", lambda *a, **k: compressor)
        monkeypatch.setattr("app.rag.chain.resolve_llm", _resolve(FakeStreamingLLM([_content("答"), _usage_chunk(10, 2)])))
        long_history = [(("human" if i % 2 == 0 else "ai"), f"内容{i}") for i in range(8)]

        _run(history=long_history, conv_id=7, last_msg_id=100)
        _run(history=long_history, conv_id=7, last_msg_id=100)

        rows = read_rows(usage_db)
        assert compressor.calls == 1
        assert _types(rows) == ["chat", "chat", "compress"]

    def test_工具轮_留下tool记录(self, usage_db, read_rows, monkeypatch):
        """场景：挂了工具且模型要求调用 → 工具轮的模型调用进账，类型为 tool"""
        _patch_retrieval(monkeypatch)
        monkeypatch.setattr("app.database.async_session_factory", usage_db)
        llm = FakeToolLLM([_content("答"), _usage_chunk(10, 2)])
        monkeypatch.setattr("app.rag.chain.resolve_llm", _resolve(llm))
        _patch_tool_executor(monkeypatch)

        _run(tools=[_tool_ref()])

        rows = read_rows(usage_db)
        assert set(_types(rows)) == {"chat", "tool"}
        tool_rows = [r for r in rows if r.call_type == "tool"]
        assert tool_rows, "工具轮应至少产生一条 tool 记录"
        assert all(r.total_tokens == 44 and r.is_estimated is False for r in tool_rows)

    def test_Text2SQL_留下text2sql记录(self, usage_db, read_rows, monkeypatch):
        """场景：绑定数据库型知识库 → SQL 生成那次调用进账，类型为 text2sql"""
        _insert_data_source(usage_db)
        sql_llm = FakeInvokeLLM(content="NO_RELEVANT_TABLE", usage=(80, 6))
        monkeypatch.setattr("app.rag.text2sql.get_llm", lambda *a, **k: sql_llm)

        async def fake_load_schema(db, kb):
            return "表 t_article(id, title)"

        monkeypatch.setattr("app.rag.text2sql.load_schema", fake_load_schema)
        kb = SimpleNamespace(data_source_id=1, database_name="demo")

        async def _call():
            async with usage_db() as db:
                return await run_sql_query(db, kb, "有多少篇文章", "", usage_ctx=UsageContext(agent_id=3))

        asyncio.run(_call())

        row = read_rows(usage_db)[0]
        assert row.call_type == "text2sql"
        assert row.total_tokens == 86
        assert row.agent_id == 3


class TestWholeRequestMetering:
    """一次提问的全部内部调用要同时进账（工单第 1 条）"""

    def test_一次提问_五类调用各自进账(self, usage_db, read_rows, monkeypatch):
        """场景：带历史 + 挂工具 + 绑定数据库型知识库 → chat/tool/rewrite/compress/text2sql 齐全"""
        monkeypatch.setattr("app.database.async_session_factory", usage_db)
        monkeypatch.setattr(settings, "QUERY_REWRITE_ENABLED", True)
        _clear_summary_cache()
        _insert_database_kb(usage_db)

        monkeypatch.setattr("app.rag.chain.resolve_llm", _resolve(FakeToolLLM([_content("答"), _usage_chunk(10, 2)])))
        monkeypatch.setattr("app.rag.chain.get_llm", lambda *a, **k: FakeInvokeLLM(content="改写或摘要"))
        monkeypatch.setattr("app.rag.text2sql.get_llm", lambda *a, **k: FakeInvokeLLM(content="NO_RELEVANT_TABLE"))
        monkeypatch.setattr("app.rag.text2sql.load_schema", _fake_schema)
        _patch_retrieval(monkeypatch)
        _patch_tool_executor(monkeypatch)

        long_history = [(("human" if i % 2 == 0 else "ai"), f"内容{i}") for i in range(8)]

        _run(history=long_history, conv_id=11, last_msg_id=200, tools=[_tool_ref()], kb_ids=[1])

        rows = read_rows(usage_db)
        assert set(_types(rows)) == {"chat", "tool", "rewrite", "compress", "text2sql"}
        # 每一类都带上了同一次请求的归属
        assert all(r.agent_id == 7 and r.agent_name == "客服助手" for r in rows)
        assert all(r.is_estimated is False for r in rows)
        # 一次提问只对应一条主回答记录
        assert _types(rows).count("chat") == 1


class TestExcludedCalls:
    """无结果短路、失败调用：都不进报表，但失败要留痕"""

    def test_无结果但已发生改写_不记问答但改写照实记账(self, usage_db, read_rows, monkeypatch):
        """场景：检索无结果 → 不产生主回答记录、不计入问答次数；

        但为这次提问**已经发生**的改写调用真的花了钱，必须照实记账：
        否则「总消费 = 端点确认的真实消耗」这条原则就被破坏了。
        """
        monkeypatch.setattr(settings, "QUERY_REWRITE_ENABLED", True)
        _patch_empty_retrieval(monkeypatch)
        rewriter = FakeInvokeLLM(content="改写后的问题", usage=(12, 3))
        monkeypatch.setattr("app.rag.chain.get_llm", lambda *a, **k: rewriter)

        events = _run(history=[("human", "之前"), ("ai", "之前")])

        assert [e["type"] for e in events] == ["no_results", "token", "done"]
        rows = read_rows(usage_db)
        assert [r.call_type for r in rows] == ["rewrite"]
        assert rows[0].total_tokens == 15

    def test_检索无结果_不产生任何记录(self, usage_db, read_rows, monkeypatch):
        """场景：知识库没有命中且没挂工具 → 短路返回，一次模型都没调"""
        async def empty_retrieve(*args, **kwargs):
            return []

        monkeypatch.setattr("app.rag.chain.retrieve_with_scores", empty_retrieve)

        events = _run()

        assert [e["type"] for e in events] == ["no_results", "token", "done"]
        assert read_rows(usage_db) == []

    def test_主回答失败_落error行且异常上抛(self, usage_db, read_rows, monkeypatch):
        """场景：主回答调用失败 → 记一条 error 行（报表会过滤），异常照常抛出"""
        _patch_retrieval(monkeypatch)
        boom = FakeStreamingLLM([], error=RuntimeError("connection reset by peer"))
        monkeypatch.setattr("app.rag.chain.resolve_llm", _resolve(boom))

        with pytest.raises(RuntimeError):
            _run()

        row = read_rows(usage_db)[0]
        assert row.status == "error"
        assert row.call_type == "chat"

    def test_改写失败_落error行且不影响回答(self, usage_db, read_rows, monkeypatch):
        """场景：改写调用失败 → 记 error 行并回退原问题，回答照常完成"""
        monkeypatch.setattr(settings, "QUERY_REWRITE_ENABLED", True)
        _patch_retrieval(monkeypatch)

        class BoomLLM:
            model_name = "fake-invoke-model"

            async def ainvoke(self, messages):
                raise RuntimeError("rewrite down")

        monkeypatch.setattr("app.rag.chain.get_llm", lambda *a, **k: BoomLLM())
        monkeypatch.setattr("app.rag.chain.resolve_llm", _resolve(FakeStreamingLLM([_content("答"), _usage_chunk(10, 2)])))

        events = _run(history=[("human", "之前"), ("ai", "之前")])

        assert "".join(e["content"] for e in events if e["type"] == "token") == "答"
        rows = read_rows(usage_db)
        assert "error" in [r.status for r in rows]
        assert [r.call_type for r in rows if r.status == "error"] == ["rewrite"]


# ---------- 辅助 ----------

def _resolve(llm):
    async def _fake_resolve(model_id=None, streaming=True, stream_usage=None):
        return llm

    return _fake_resolve


def _run(history=None, ctx=None, conv_id=None, last_msg_id=None, tools=None, kb_ids=None):
    async def _collect():
        return [
            event
            async for event in stream_rag_response(
                "退货政策是什么",
                history or [],
                kb_ids=kb_ids,
                usage_ctx=ctx or UsageContext(agent_id=7, agent_name="客服助手"),
                conv_id=conv_id,
                last_msg_id=last_msg_id,
                tools=tools,
            )
        ]

    return asyncio.run(_collect())


def _patch_retrieval(monkeypatch):
    async def fake_retrieve(*args, **kwargs):
        return [(Document(page_content="退货需在 7 天内申请", metadata={"filename": "policy.md"}), 0.9)]

    monkeypatch.setattr("app.rag.chain.retrieve_with_scores", fake_retrieve)


def _clear_summary_cache():
    import app.rag.context_compressor as cc

    cc._summary_cache.clear()


def _tool_ref():
    from app.schemas.agent import AgentToolRef

    return AgentToolRef(tool_type="skill", tool_ref_id=1, enabled=True)


def _patch_tool_executor(monkeypatch):
    async def fake_build_specs(db, tool_refs):
        return [{"type": "function", "function": {"name": "get_current_time"}}], {"get_current_time": "get_current_time"}

    async def fake_run_tool_calls(db, tool_calls, name_map, kb_ids=None, source_offset=0):
        return [
            {
                "tool_call_id": c.get("id", "call_1"),
                "name": c.get("name", "get_current_time"),
                "content": "2026-09-11 19:00:00",
                "sources": [],
            }
            for c in tool_calls
        ]

    monkeypatch.setattr("app.skills.executor.build_tool_specs", fake_build_specs)
    monkeypatch.setattr("app.skills.executor.run_tool_calls", fake_run_tool_calls)


def _patch_empty_retrieval(monkeypatch):
    async def empty_retrieve(*args, **kwargs):
        return []

    monkeypatch.setattr("app.rag.chain.retrieve_with_scores", empty_retrieve)


async def _fake_schema(db, kb):
    return "表 t_article(id, title, content)"


def _insert_database_kb(factory):
    """插入一个数据库型知识库（B 类），让检索链走 Text-to-SQL 分支"""
    from app.models.knowledge_base import KnowledgeBase

    async def _run_insert():
        async with factory() as db:
            db.add(DataSource(id=1, name="冒烟数据源", type="mysql", host="127.0.0.1",
                              port=3306, database="demo", username="u"))
            db.add(KnowledgeBase(id=1, name="冒烟库", type="database",
                                 data_source_id=1, database_name="demo", created_by=1))
            await db.commit()

    asyncio.run(_run_insert())


def _insert_data_source(factory):
    async def _run_insert():
        async with factory() as db:
            db.add(DataSource(id=1, name="冒烟数据源", type="mysql", host="127.0.0.1",
                              port=3306, database="demo", username="u"))
            await db.commit()

    asyncio.run(_run_insert())
