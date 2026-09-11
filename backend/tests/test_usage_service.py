"""测试用量采集 — 真实用量 / 估算兜底 / 写库失败三条分支

seam：用量采集模块的公开入口 + 临时文件库（不联网、不碰开发数据库）
"""

import asyncio

from langchain_core.messages import AIMessage

from app.services.usage_service import UsageContext, estimate_tokens, record_call


class TestEstimateTokens:
    """字符估算 — 仅在端点未返回用量时使用"""

    def test_空串_返回零(self):
        """场景：空文本 → 0"""
        assert estimate_tokens("") == 0

    def test_纯中文_一字一token(self):
        """场景：4 个汉字 → 4"""
        assert estimate_tokens("你好世界") == 4

    def test_纯英文_四字符一token(self):
        """场景：8 个 ASCII 字符 → 2"""
        assert estimate_tokens("abcdefgh") == 2

    def test_极短非空文本_至少为一(self):
        """场景：单个字符 → 不为 0（避免"有调用却零消耗"）"""
        assert estimate_tokens("a") == 1


class TestRecordCall:
    """采集入口 — 落库内容正确，且绝不向外抛异常"""

    def test_端点返回用量_按真实值落库(self, usage_db, read_rows):
        """场景：响应带 usage → 落一条真实用量记录，身份与模型都记全"""
        ctx = UsageContext(agent_id=7, agent_name="客服助手", user_id=1, conversation_id=3)
        resp = AIMessage(
            content="答",
            usage_metadata={"input_tokens": 120, "output_tokens": 30, "total_tokens": 150},
        )

        asyncio.run(
            record_call(ctx, call_type="chat", model_name="deepseek-chat", response=resp)
        )

        rows = read_rows(usage_db)
        assert len(rows) == 1
        row = rows[0]
        assert (row.prompt_tokens, row.completion_tokens, row.total_tokens) == (120, 30, 150)
        assert row.is_estimated is False
        assert row.status == "success"
        assert (row.agent_id, row.agent_name) == (7, "客服助手")
        assert (row.user_id, row.conversation_id) == (1, 3)
        assert row.model_name == "deepseek-chat"
        assert row.call_type == "chat"
        assert row.created_at

    def test_端点未返回用量_标记估算且总量自洽(self, usage_db, read_rows):
        """场景：响应无 usage → 按字符估算并打标，token 不出现负数或零总量"""
        ctx = UsageContext(agent_id=1, agent_name="助手")

        asyncio.run(
            record_call(
                ctx,
                call_type="chat",
                model_name="deepseek-chat",
                response=AIMessage(content="答"),
                input_text="请介绍一下退货政策的具体流程",
                output_text="退货流程分为三步……",
            )
        )

        row = read_rows(usage_db)[0]
        assert row.is_estimated is True
        assert row.total_tokens > 0
        assert row.total_tokens == row.prompt_tokens + row.completion_tokens

    def test_调用失败_记为失败行且token为零(self, usage_db, read_rows):
        """场景：调用本身失败 → 落一条 error 行（报表会过滤掉它）"""
        asyncio.run(
            record_call(
                UsageContext(agent_id=1, agent_name="助手"),
                call_type="chat",
                model_name="deepseek-chat",
                error="connection reset by peer",
            )
        )

        row = read_rows(usage_db)[0]
        assert row.status == "error"
        assert row.total_tokens == 0
        assert row.error_message == "connection reset by peer"

    def test_写库异常_不外抛(self, usage_db, read_rows, monkeypatch):
        """场景：会话工厂直接抛异常 → 静默返回，问答主链路不受影响"""

        class BoomFactory:
            def __call__(self):
                raise RuntimeError("db down")

        monkeypatch.setattr("app.services.usage_service.async_session_factory", BoomFactory())

        # 不抛异常即为通过
        asyncio.run(
            record_call(
                UsageContext(),
                call_type="chat",
                model_name="m",
                input_text="x",
                output_text="y",
            )
        )
        assert read_rows(usage_db) == []
