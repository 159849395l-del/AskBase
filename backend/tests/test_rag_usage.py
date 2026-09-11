"""测试 RAG 链路的用量埋点 — 一次提问落一条主回答用量记录

seam（已与用户约定）：用假模型注入替换 chain 的模块级协作者，
驱动**真实的编排函数**跑完一个回合，只在公开边界（SSE 事件 + 流水表）上断言。
不联网、不连向量库、不碰开发数据库。
"""

import asyncio

import pytest
from langchain_core.documents import Document
from langchain_core.messages import AIMessageChunk

from app.rag.chain import stream_rag_response
from app.services.usage_service import UsageContext


class FakeStreamingLLM:
    """鸭子类型的假流式客户端：astream 依次吐出给定 chunk，并记录被调用次数"""

    def __init__(self, chunks, model_name="fake-chat-model", fail_times=0, error=None):
        self._chunks = chunks
        self.model_name = model_name
        self._fail_times = fail_times
        self._error = error
        self.calls = 0

    async def astream(self, messages):
        self.calls += 1
        if self.calls <= self._fail_times:
            raise self._error
        for chunk in self._chunks:
            yield chunk


def _content(text):
    return AIMessageChunk(content=text, usage_metadata=None)


def _usage_chunk(prompt, completion, content=""):
    return AIMessageChunk(
        content=content,
        usage_metadata={
            "input_tokens": prompt,
            "output_tokens": completion,
            "total_tokens": prompt + completion,
        },
    )


def _run(history=None, ctx=None, call_type="chat"):
    """驱动一次完整问答，返回 SSE 事件列表"""

    async def _collect():
        return [
            event
            async for event in stream_rag_response(
                "退货政策是什么",
                history or [],
                kb_ids=None,
                usage_ctx=ctx,
                usage_call_type=call_type,
            )
        ]

    return asyncio.run(_collect())


def _patch_retrieval(monkeypatch):
    """让检索命中一篇文档，避免走「无结果」短路"""

    async def fake_retrieve(*args, **kwargs):
        return [(Document(page_content="退货需在 7 天内申请", metadata={"filename": "policy.md"}), 0.9)]

    monkeypatch.setattr("app.rag.chain.retrieve_with_scores", fake_retrieve)


class TestStreamUsageCapture:
    """流式用量的两种形态都要能拿到真实值"""

    def test_用量挂在最后一个内容块_DeepSeek形态(self, usage_db, read_rows, monkeypatch):
        """场景：用量附加在最后一个内容块上（choices 非空）→ 仍能取到"""
        _patch_retrieval(monkeypatch)
        llm = FakeStreamingLLM([_content("退货"), _content("需在7天内"), _usage_chunk(120, 30)])
        monkeypatch.setattr("app.rag.chain.resolve_llm", lambda *a, **k: _async(llm))
        ctx = UsageContext(agent_id=7, agent_name="客服助手", user_id=1, conversation_id=3)

        events = _run(ctx=ctx)

        assert "".join(e["content"] for e in events if e["type"] == "token") == "退货需在7天内"
        rows = read_rows(usage_db)
        assert len(rows) == 1
        row = rows[0]
        assert (row.prompt_tokens, row.completion_tokens, row.total_tokens) == (120, 30, 150)
        assert row.is_estimated is False
        assert row.call_type == "chat"
        assert row.model_name == "fake-chat-model"
        assert (row.agent_id, row.agent_name, row.user_id, row.conversation_id) == (7, "客服助手", 1, 3)

    def test_用量是独立的空内容块_OpenAI与百炼形态(self, usage_db, read_rows, monkeypatch):
        """场景：用量单独成一个空 choices 块 → 同样能取到"""
        _patch_retrieval(monkeypatch)
        llm = FakeStreamingLLM([_content("答案"), _usage_chunk(200, 50)])
        monkeypatch.setattr("app.rag.chain.resolve_llm", lambda *a, **k: _async(llm))

        events = _run()

        assert "".join(e["content"] for e in events if e["type"] == "token") == "答案"
        row = read_rows(usage_db)[0]
        assert (row.prompt_tokens, row.completion_tokens) == (200, 50)
        assert row.is_estimated is False

    def test_端点不返回用量_标记估算(self, usage_db, read_rows, monkeypatch):
        """场景：整条流都没有 usage → 记录标记为估算（不进入统计）"""
        _patch_retrieval(monkeypatch)
        llm = FakeStreamingLLM([_content("没有用量的回答")])
        monkeypatch.setattr("app.rag.chain.resolve_llm", lambda *a, **k: _async(llm))

        events = _run()

        assert "".join(e["content"] for e in events if e["type"] == "token") == "没有用量的回答"
        row = read_rows(usage_db)[0]
        assert row.is_estimated is True
        assert row.total_tokens > 0

    def test_自定义调用类型_按传入值落库(self, usage_db, read_rows, monkeypatch):
        """场景：智能体测试端点复用同一编排 → 类型记为 agent_test，不冒充用户问答"""
        _patch_retrieval(monkeypatch)
        llm = FakeStreamingLLM([_content("答"), _usage_chunk(10, 5)])
        monkeypatch.setattr("app.rag.chain.resolve_llm", lambda *a, **k: _async(llm))

        _run(call_type="agent_test")

        row = read_rows(usage_db)[0]
        assert row.call_type == "agent_test"
        assert row.total_tokens == 15

    def test_done事件带回真实用量(self, usage_db, monkeypatch):
        """场景：done 事件携带真实用量 → 上层可据此存真实的 token 数"""
        _patch_retrieval(monkeypatch)
        llm = FakeStreamingLLM([_content("答"), _usage_chunk(10, 5)])
        monkeypatch.setattr("app.rag.chain.resolve_llm", lambda *a, **k: _async(llm))

        done = [e for e in _run() if e["type"] == "done"][0]

        assert (done["usage"].prompt, done["usage"].completion, done["usage"].total) == (10, 5, 15)

    def test_端点无用量时_done不编造数字(self, usage_db, monkeypatch):
        """场景：拿不到真实用量 → done 的 usage 为 None，不拿估算值冒充"""
        _patch_retrieval(monkeypatch)
        llm = FakeStreamingLLM([_content("答")])
        monkeypatch.setattr("app.rag.chain.resolve_llm", lambda *a, **k: _async(llm))

        done = [e for e in _run() if e["type"] == "done"][0]

        assert done["usage"] is None


class TestStreamOptionsFallback:
    """端点拒绝用量参数时，去掉参数重试一次，问答必须完整"""

    def test_首次被拒_换掉参数后重试成功(self, usage_db, read_rows, monkeypatch):
        """场景：第一次调用报 stream_options 相关错误 → 重试一次并拿到完整回答"""
        _patch_retrieval(monkeypatch)
        rejected = FakeStreamingLLM(
            [], fail_times=1, error=RuntimeError("400 Unknown parameter: 'stream_options'")
        )
        healthy = FakeStreamingLLM([_content("重试后的回答"), _usage_chunk(11, 7)])

        async def fake_resolve(model_id=None, streaming=True, stream_usage=None):
            return healthy if stream_usage is False else rejected

        monkeypatch.setattr("app.rag.chain.resolve_llm", fake_resolve)

        events = _run()

        assert "".join(e["content"] for e in events if e["type"] == "token") == "重试后的回答"
        assert rejected.calls == 1
        assert healthy.calls == 1
        row = read_rows(usage_db)[0]
        assert row.total_tokens == 18
        assert row.is_estimated is False

    def test_重试后仍失败_异常向上抛(self, usage_db, monkeypatch):
        """场景：去掉参数后依然失败 → 不吞掉错误，交由上层处理"""
        _patch_retrieval(monkeypatch)

        async def always_reject(model_id=None, streaming=True, stream_usage=None):
            raise RuntimeError("400 Unknown parameter: 'stream_options'")

        monkeypatch.setattr("app.rag.chain.resolve_llm", always_reject)

        with pytest.raises(RuntimeError):
            _run()

    def test_与用量参数无关的错误_不重试(self, usage_db, monkeypatch):
        """场景：错误与用量参数无关 → 直接抛出，不做无谓重试"""
        _patch_retrieval(monkeypatch)
        broken = FakeStreamingLLM([], fail_times=99, error=RuntimeError("connection reset by peer"))

        async def fake_resolve(model_id=None, streaming=True, stream_usage=None):
            return broken

        monkeypatch.setattr("app.rag.chain.resolve_llm", fake_resolve)

        with pytest.raises(RuntimeError):
            _run()
        assert broken.calls == 1


async def _async(value):
    """把同步构造的假对象包成可 await 的返回值"""
    return value
