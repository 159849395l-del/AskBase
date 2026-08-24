"""测试查询改写模块 — 消息构建与系统提示词（rewrite_query 网络部分不单测）"""

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from app.config import settings
from app.rag.query_rewriter import build_rewrite_messages, REWRITE_SYSTEM_PROMPT


class TestBuildRewriteMessages:
    """改写消息构建 — build_rewrite_messages"""

    def test_消息角色顺序_系统_历史_当前问题(self):
        """场景：有聊天历史 → 系统提示在前，human/ai 交替，当前问题在最后"""
        history = [("human", "问题1"), ("ai", "回答1"), ("human", "问题2")]
        msgs = build_rewrite_messages("问题3", history)

        assert isinstance(msgs[0], SystemMessage)
        assert msgs[0].content == REWRITE_SYSTEM_PROMPT
        assert isinstance(msgs[1], HumanMessage)
        assert msgs[1].content == "问题1"
        assert isinstance(msgs[2], AIMessage)
        assert msgs[2].content == "回答1"
        assert isinstance(msgs[3], HumanMessage)
        assert msgs[3].content == "问题2"
        assert isinstance(msgs[4], HumanMessage)
        assert msgs[4].content == "问题3"

    def test_历史超过窗口_截断到最近窗口条(self):
        """场景：历史超过 CHAT_HISTORY_WINDOW → 只保留最近 N 条"""
        history = [
            item
            for i in range(15)
            for item in (("human", f"问题{i}"), ("ai", f"回答{i}"))
        ]
        msgs = build_rewrite_messages("新问题", history)

        expected = history[-settings.CHAT_HISTORY_WINDOW:]
        # 系统提示 + 窗口内历史 + 当前问题
        assert len(msgs) == 1 + len(expected) + 1
        assert [m.content for m in msgs[1:-1]] == [content for _, content in expected]
        assert msgs[-1].content == "新问题"

    def test_无历史_只含系统提示和当前问题(self):
        """场景：空聊天历史 → 仅系统提示 + 当前问题"""
        msgs = build_rewrite_messages("问题", [])

        assert len(msgs) == 2
        assert isinstance(msgs[0], SystemMessage)
        assert isinstance(msgs[1], HumanMessage)
        assert msgs[1].content == "问题"

    def test_历史为空None_不报错(self):
        """场景：chat_history 传 None → 按空处理"""
        msgs = build_rewrite_messages("问题", None)

        assert len(msgs) == 2
        assert msgs[-1].content == "问题"


class TestRewriteSystemPrompt:
    """改写系统提示词 — 规则完整性"""

    def test_包含指代省略改写规则(self):
        """场景：提示词要求仅在存在指代/省略时改写"""
        assert "指代或省略" in REWRITE_SYSTEM_PROMPT
        assert "完整自包含" in REWRITE_SYSTEM_PROMPT

    def test_包含原样输出与只输出问题规则(self):
        """场景：提示词要求无指代时原样输出，且只输出改写后的问题"""
        assert "原样输出" in REWRITE_SYSTEM_PROMPT
        assert "只输出改写后的问题" in REWRITE_SYSTEM_PROMPT
        assert "不要解释" in REWRITE_SYSTEM_PROMPT


class TestRewriteQueryFallback:
    """改写调用 — 异常回退（用 monkeypatch 触发异常，不联网）"""

    def test_LLM异常_回退返回原问题(self, monkeypatch):
        """场景：LLM 调用抛异常 → 返回原问题，不中断"""
        import asyncio
        import app.rag.query_rewriter as qr

        def fake_llm_raise(*args, **kwargs):
            raise RuntimeError("mock network error")

        monkeypatch.setattr("app.rag.chain.get_llm", fake_llm_raise)
        result = asyncio.run(qr.rewrite_query("原始问题", [("human", "之前的问题")]))

        assert result == "原始问题"
