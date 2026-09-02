"""测试上下文压缩模块 — 阈值 / 摘要产出 / 缓存命中 / 异常降级（不联网）"""

import asyncio
from unittest.mock import MagicMock

import app.rag.context_compressor as cc
from app.config import settings


def _make_messages(n):
    """构造 n 条 (role, content) 历史，奇偶交替 human/ai"""
    return [("human" if i % 2 == 0 else "ai", f"内容{i}") for i in range(n)]


class FakeLLM:
    """可注入的假 LLM：ainvoke 返回固定摘要文本"""

    def __init__(self, summary="用户想查订单；已确认表orders；未决：物流状态。"):
        self._summary = summary

    async def ainvoke(self, messages):
        return MagicMock(content=self._summary)


class TestCompressThreshold:
    """未达阈值时不压缩，行为等价于原滑动窗口"""

    def test_未超阈值_不压缩(self):
        msgs = _make_messages(3)  # 3 <= 阈值4
        summary, recent = asyncio.run(cc.compress_history(msgs))
        assert summary is None
        assert recent == msgs

    def test_恰好阈值_不压缩(self):
        msgs = _make_messages(4)  # 等于阈值，不压缩
        summary, recent = asyncio.run(cc.compress_history(msgs))
        assert summary is None
        assert recent == msgs


class TestCompressSummary:
    """超阈值时产出摘要，且保留近期原文高保真；缓存命中避免重算"""

    def test_超阈值_产出摘要且近期原文保留(self, monkeypatch):
        cc._summary_cache.clear()
        msgs = _make_messages(6)  # earlier=2, recent=4
        monkeypatch.setattr("app.rag.chain.get_llm", lambda: FakeLLM())
        summary, recent = asyncio.run(
            cc.compress_history(msgs, conv_id=1, last_msg_id=5)
        )
        assert summary is not None
        assert "订单" in summary
        assert recent == msgs[-settings.CONTEXT_RECENT_TURNS:]

    def test_缓存命中_复用摘要不重算(self, monkeypatch):
        cc._summary_cache.clear()
        msgs = _make_messages(6)
        calls = {"n": 0}

        class CountingLLM(FakeLLM):
            async def ainvoke(self, messages):
                calls["n"] += 1
                return await super().ainvoke(messages)

        monkeypatch.setattr("app.rag.chain.get_llm", lambda: CountingLLM())
        asyncio.run(cc.compress_history(msgs, conv_id=2, last_msg_id=9))
        asyncio.run(cc.compress_history(msgs, conv_id=2, last_msg_id=9))  # 同键
        assert calls["n"] == 1  # 仅首次真正调用 LLM

    def test_摘要为空_降级(self, monkeypatch):
        cc._summary_cache.clear()
        msgs = _make_messages(6)
        monkeypatch.setattr("app.rag.chain.get_llm", lambda: FakeLLM(summary="无"))
        summary, recent = asyncio.run(cc.compress_history(msgs))
        assert summary is None
        assert recent == msgs


class TestCompressFallback:
    """LLM 调用异常时静默降级，退回原滑动窗口，不中断主链路"""

    def test_LLM异常_降级返回原消息(self, monkeypatch):
        def fake_raise(*args, **kwargs):
            raise RuntimeError("mock network error")

        monkeypatch.setattr("app.rag.chain.get_llm", fake_raise)
        msgs = _make_messages(6)
        summary, recent = asyncio.run(cc.compress_history(msgs))
        assert summary is None
        assert recent == msgs
