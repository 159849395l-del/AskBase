"""测试工具调用随助手消息落库、并能原样读回

seam：temp_db 夹具（临时文件 SQLite，建全部表）真实读写 messages 表。
刷新页面后「这次回答调用了哪些工具、网页来源是什么」必须还在。
"""

import asyncio
import json
from types import SimpleNamespace

from app.models.conversation import Conversation
from app.models.message import Message
from app.services.conversation_service import (
    get_conversation_detail,
    save_assistant_message,
)


WEB_SOURCE = {
    "kind": "web",
    "title": "国务院通知",
    "url": "https://a.example/1",
    "filename": "国务院通知",
    "chunk_text": "通知正文",
    "snippet": "通知正文",
    "published": "2025-11-04T00:00:00.000Z",
}

TOOL_CALLS = [
    {"name": "web_search", "content": "【可引用的来源】…"},
    {"name": "get_current_time", "content": "2026-09-12 10:00:00"},
]


def _seed_conversation(factory, user_id=1):
    async def _go():
        async with factory() as db:
            conv = Conversation(user_id=user_id, title="春节放假")
            db.add(conv)
            await db.commit()
            await db.refresh(conv)
            return conv.id

    return asyncio.run(_go())


def _detail(factory, conv_id, user_id=1):
    async def _go():
        async with factory() as db:
            return await get_conversation_detail(
                db, conv_id, SimpleNamespace(id=user_id, role="user")
            )

    return asyncio.run(_go())


def _read_message(factory, conv_id):
    from sqlalchemy import select

    async def _go():
        async with factory() as db:
            return (
                await db.execute(select(Message).where(Message.conversation_id == conv_id))
            ).scalars().one()

    return asyncio.run(_go())


def _save(factory, conv_id, **kwargs):
    async def _go():
        return await save_assistant_message(conv_id, **kwargs)

    return asyncio.run(_go())


class TestSaveAndRead:
    """落库 → 读回，用户可见的东西一个都不能丢"""

    def test_工具调用与来源一起落库(self, temp_db):
        """场景：回答带工具调用与网页来源 → 详情接口原样返回"""
        conv_id = _seed_conversation(temp_db)

        msg_id = _save(
            temp_db,
            conv_id,
            content="春节放假 9 天 [来源1]。",
            sources=[WEB_SOURCE],
            token_count=128,
            tool_calls=TOOL_CALLS,
        )

        assert msg_id > 0
        msg = _detail(temp_db, conv_id).messages[0]
        assert msg.content == "春节放假 9 天 [来源1]。"
        assert msg.token_count == 128
        assert [t.name for t in msg.tool_calls] == ["web_search", "get_current_time"]
        assert msg.tool_calls[0].content.startswith("【可引用的来源】")
        assert msg.sources[0].url == "https://a.example/1"
        assert msg.sources[0].kind == "web"
        assert msg.sources[0].title == "国务院通知"

    def test_没有工具调用时字段为None(self, temp_db):
        """场景：普通回答（没调工具）→ tool_calls 为 None，不是空数组冒充"""
        conv_id = _seed_conversation(temp_db)

        _save(temp_db, conv_id, content="直接回答", sources=[])

        assert _detail(temp_db, conv_id).messages[0].tool_calls is None

    def test_落库的是JSON字符串(self, temp_db):
        """场景：库里存的就是 JSON 文本（与 sources 同一套做法）"""
        conv_id = _seed_conversation(temp_db)

        _save(temp_db, conv_id, content="答", tool_calls=TOOL_CALLS)

        raw = _read_message(temp_db, conv_id).tool_calls
        assert json.loads(raw)[0]["name"] == "web_search"


class TestLegacyAndBrokenData:
    """历史数据与脏数据都不能让会话页打不开"""

    def test_历史消息没有tool_calls列_读回为None(self, temp_db):
        """场景：升级前落的消息 tool_calls 为 NULL → 正常返回 None"""
        conv_id = _seed_conversation(temp_db)

        async def _go():
            async with temp_db() as db:
                db.add(Message(conversation_id=conv_id, role="assistant", content="老回答"))
                await db.commit()

        asyncio.run(_go())

        assert _detail(temp_db, conv_id).messages[0].tool_calls is None

    def test_工具调用JSON损坏_降级为None(self, temp_db):
        """场景：列里是坏 JSON → 不让整个会话详情 500"""
        conv_id = _seed_conversation(temp_db)

        async def _go():
            async with temp_db() as db:
                db.add(Message(
                    conversation_id=conv_id, role="assistant", content="答",
                    tool_calls="{不是合法 json",
                ))
                await db.commit()

        asyncio.run(_go())

        assert _detail(temp_db, conv_id).messages[0].tool_calls is None

    def test_历史的向量来源仍然可读(self, temp_db):
        """场景：老格式来源（没有 kind/title/url）→ 依旧解析得出来"""
        conv_id = _seed_conversation(temp_db)

        async def _go():
            async with temp_db() as db:
                db.add(Message(
                    conversation_id=conv_id, role="assistant", content="答",
                    sources=json.dumps([{
                        "filename": "policy.md", "chunk_text": "退货需在 7 天内",
                        "similarity_score": 0.9, "chunk_index": 0, "score_type": "vector",
                    }], ensure_ascii=False),
                ))
                await db.commit()

        asyncio.run(_go())

        src = _detail(temp_db, conv_id).messages[0].sources[0]
        assert src.filename == "policy.md"
        assert src.similarity_score == 0.9
