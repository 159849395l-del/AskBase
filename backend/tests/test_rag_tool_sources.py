"""测试 RAG 链路把工具来源并入「统一编号」的来源列表

seam（与用户约定）：假模型注入替换 chain 的模块级协作者，驱动**真实的编排函数**
跑完一个回合，只在公开边界（SSE 事件 + 给模型看的上下文）上断言。
不联网、不连向量库、不碰开发数据库。
"""

import asyncio

import pytest
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, AIMessageChunk

from app.rag.chain import stream_rag_response
from app.schemas.agent import AgentToolRef


WEB_SOURCE = {
    "kind": "web",
    "title": "国务院通知",
    "url": "https://a.example/1",
    "filename": "国务院通知",
    "chunk_text": "通知正文",
}


class FakeToolLLM:
    """第一轮要求调用工具，之后直接作答；同时记录模型实际看到的 messages"""

    def __init__(self, answer="春节放假 9 天 [来源2]。", rounds=1):
        self.model_name = "fake-tool-model"
        self.answer = answer
        self.rounds = rounds
        self.ainvoke_rounds = 0
        self.seen_messages: list = []

    def bind_tools(self, specs):
        return self

    async def ainvoke(self, messages):
        self.seen_messages.append(messages)
        if self.ainvoke_rounds < self.rounds:
            self.ainvoke_rounds += 1
            return AIMessage(
                content="",
                tool_calls=[
                    {"name": "web_search", "args": {"query": "春节"}, "id": "call_1", "type": "tool_call"}
                ],
            )
        return AIMessage(content="", tool_calls=[])

    async def astream(self, messages):
        self.seen_messages.append(messages)
        yield AIMessageChunk(content=self.answer, usage_metadata=None)


def _async(value):
    return value


def _patch_llm(monkeypatch, llm):
    async def _resolve(model_id=None, streaming=True, stream_usage=None):
        return llm

    monkeypatch.setattr("app.rag.chain.resolve_llm", _resolve)


def _patch_retrieval(monkeypatch, docs):
    async def fake_retrieve(*args, **kwargs):
        return docs

    monkeypatch.setattr("app.rag.chain.retrieve_with_scores", fake_retrieve)


def _patch_tool_executor(monkeypatch, captured, sources, offsets=None):
    async def fake_build_specs(db, tool_refs):
        return [{"type": "function", "function": {"name": "web_search"}}], {"web_search": "ref"}

    async def fake_run_tool_calls(db, tool_calls, name_map, kb_ids=None, source_offset=0):
        captured["source_offset"] = source_offset
        if offsets is not None:
            offsets.append(source_offset)
        return [
            {
                "tool_call_id": c.get("id", "call_1"),
                "name": c.get("name", "web_search"),
                "content": "工具结果文本",
                "sources": list(sources),
            }
            for c in tool_calls
        ]

    monkeypatch.setattr("app.skills.executor.build_tool_specs", fake_build_specs)
    monkeypatch.setattr("app.skills.executor.run_tool_calls", fake_run_tool_calls)


def _run(monkeypatch, docs=(), tool_sources=(), captured=None, offsets=None, rounds=1):
    """驱动一次完整问答，返回 (events, llm, captured)"""
    captured = captured if captured is not None else {}
    _patch_retrieval(monkeypatch, list(docs))
    _patch_tool_executor(monkeypatch, captured, tool_sources, offsets=offsets)
    llm = FakeToolLLM(rounds=rounds)
    _patch_llm(monkeypatch, llm)

    async def _collect():
        return [
            event
            async for event in stream_rag_response(
                "2026年春节放假安排",
                [],
                kb_ids=None,
                tools=[AgentToolRef(tool_type="skill", tool_ref_id=1, enabled=True)],
            )
        ]

    return asyncio.run(_collect()), llm, captured


def _sources_of(events):
    return [e for e in events if e["type"] == "sources"][0]["sources"]


class TestToolSourcesInEvent:
    """工具带出的网页来源必须进入来源列表，且排在知识库来源之后"""

    def test_网页来源接在知识库来源后面(self, monkeypatch):
        """场景：1 条知识库来源 + 1 条网页来源 → 面板上是来源1、来源2"""
        doc = Document(page_content="春节放假安排", metadata={"filename": "policy.md"})
        events, _, captured = _run(monkeypatch, docs=[(doc, 0.9)], tool_sources=[WEB_SOURCE])

        sources = _sources_of(events)

        assert len(sources) == 2
        assert sources[0]["filename"] == "policy.md"
        assert sources[1]["url"] == "https://a.example/1"

    def test_执行器拿到的起始偏移等于已有来源数(self, monkeypatch):
        """场景：已有 1 条知识库来源 → 执行器要从来源2开始编号"""
        doc = Document(page_content="春节放假安排", metadata={"filename": "policy.md"})
        _, _, captured = _run(monkeypatch, docs=[(doc, 0.9)], tool_sources=[WEB_SOURCE])

        assert captured["source_offset"] == 1

    def test_没有知识库来源时从0开始(self, monkeypatch):
        """场景：只挂工具、检索为空 → 网页来源就是来源1"""
        _, _, captured = _run(monkeypatch, docs=[], tool_sources=[WEB_SOURCE])

        assert captured["source_offset"] == 0

    def test_工具事件只报工具名与结果(self, monkeypatch):
        """场景：工具过程要可见 → tool_call 事件带工具名与结果摘要（来源走 sources 事件）"""
        events, _, _ = _run(monkeypatch, docs=[], tool_sources=[WEB_SOURCE])

        tool_events = [e for e in events if e["type"] == "tool_call"]

        assert [e["name"] for e in tool_events] == ["web_search"]
        assert tool_events[0]["content"]
        assert "sources" not in tool_events[0]

    def test_多轮工具调用_编号接着上一轮往下排(self, monkeypatch):
        """场景：模型第一轮调工具、第二轮又调一次 → 第二轮的来源要接着第一轮编号

        每一轮都从「已有来源数」重新起算的话，第二轮会和第一轮撞车 ——
        那正是这份工单要消灭的错位。
        """
        doc = Document(page_content="春节放假安排", metadata={"filename": "policy.md"})
        offsets: list = []

        events, _, _ = _run(
            monkeypatch, docs=[(doc, 0.9)], tool_sources=[WEB_SOURCE],
            offsets=offsets, rounds=2,
        )

        assert offsets == [1, 2]
        # 来源列表：知识库1条 + 每轮各1条网页 → 共 3 条，第二轮那条排在最后
        assert [s.get("url") or s["filename"] for s in _sources_of(events)] == [
            "policy.md",
            "https://a.example/1",
            "https://a.example/1",
        ]

    def test_没有结构化来源的工具不产生来源条目(self, monkeypatch):
        """场景：取当前时间这类工具没有来源 → 面板不许冒出假的来源"""
        events, _, _ = _run(monkeypatch, docs=[], tool_sources=[])

        assert _sources_of(events) == []


class TestUnifiedNumberingAcrossContext:
    """SQL、文档、网页三种来源混在一起时，模型看到的编号要连续不撞车"""

    def test_三种来源编号连续(self, monkeypatch):
        """场景：SQL 查询 + 1 篇文档 + 1 条网页 → 来源1/2/3/4，模型上下文与之对齐"""
        doc = Document(page_content="春节放假安排", metadata={"filename": "policy.md"})

        async def fake_resolve_kbs(kb_ids):
            return None, object()  # 假装挂了一个数据库型知识库

        async def fake_run_sql(db, kb, question, system_prompt, usage_ctx=None):
            return {"sql": "SELECT 1", "result_text": "查询结果"}

        monkeypatch.setattr("app.rag.chain._resolve_kbs", fake_resolve_kbs)
        monkeypatch.setattr("app.rag.text2sql.run_sql_query", fake_run_sql)

        events, llm, captured = _run(
            monkeypatch, docs=[(doc, 0.9)], tool_sources=[WEB_SOURCE]
        )

        sources = _sources_of(events)
        system_content = llm.seen_messages[0][0].content

        assert [s["filename"] for s in sources] == [
            "生成查询",
            "数据库查询结果",
            "policy.md",
            "国务院通知",
        ]
        # 模型看到的编号必须与列表位置一一对应（来源N ↔ sources[N-1]）
        assert "[来源2: 数据库查询结果]" in system_content
        assert "[来源3: policy.md]" in system_content
        assert captured["source_offset"] == 3
