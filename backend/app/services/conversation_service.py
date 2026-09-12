"""
会话服务 — 会话 CRUD 和消息管理
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status
from typing import Optional, Tuple, List
from app.database import async_session_factory
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.schemas.conversation import ConversationItem, ConversationDetail
from app.schemas.chat import MessageItem, SourceItem, ToolCallItem
import json


def _load_items(raw: Optional[str], item_type):
    """把落库的 JSON 文本解析成列表项；坏数据降级为 None，不让会话详情接口 500

    sources 与 tool_calls 是同一套做法（JSON 文本列 → 列表），只有元素类型不同。
    """
    if not raw:
        return None
    try:
        return [item_type(**d) for d in json.loads(raw)]
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


async def save_assistant_message(
    conv_id: int,
    content: str,
    sources: Optional[list] = None,
    token_count: Optional[int] = None,
    tool_calls: Optional[list] = None,
) -> int:
    """在独立会话中落库助手消息（保证提交），返回消息 id

    用独立会话是刻意的：SSE 生成器跑在请求依赖之外，共用请求会话可能来不及提交。
    """
    async with async_session_factory() as db:
        msg = Message(
            conversation_id=conv_id,
            role="assistant",
            content=content,
            sources=json.dumps(sources or [], ensure_ascii=False),
            tool_calls=json.dumps(tool_calls, ensure_ascii=False) if tool_calls else None,
            token_count=token_count,
        )
        db.add(msg)
        await db.commit()
        await db.refresh(msg)
        return msg.id


async def list_conversations(
    db: AsyncSession,
    user: User,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[List[ConversationItem], int]:
    """获取用户会话列表（分页，按更新时间倒序）"""
    # 总数
    count_q = select(func.count()).select_from(Conversation).where(
        Conversation.user_id == user.id,
        Conversation.is_active == True,
    )
    total = (await db.execute(count_q)).scalar() or 0

    # 分页查询
    q = (
        select(Conversation)
        .where(Conversation.user_id == user.id, Conversation.is_active == True)
        .order_by(desc(Conversation.updated_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(q)
    conversations = result.scalars().all()

    items = []
    for conv in conversations:
        # 获取消息数量和最后一条消息
        msg_count_q = select(func.count()).select_from(Message).where(
            Message.conversation_id == conv.id
        )
        msg_count = (await db.execute(msg_count_q)).scalar() or 0

        last_msg_q = (
            select(Message)
            .where(Message.conversation_id == conv.id)
            .order_by(desc(Message.created_at))
            .limit(1)
        )
        last_msg_result = await db.execute(last_msg_q)
        last_msg = last_msg_result.scalar_one_or_none()

        items.append(ConversationItem(
            id=conv.id,
            title=conv.title,
            is_active=conv.is_active,
            agent_id=conv.agent_id,
            message_count=msg_count,
            last_message_preview=last_msg.content[:100] if last_msg else None,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
        ))

    return items, total


async def create_conversation(
    db: AsyncSession,
    user: User,
    title: Optional[str] = None,
    agent_id: Optional[int] = None,
) -> Conversation:
    """创建新会话（可选绑定智能体）"""
    conv = Conversation(
        user_id=user.id,
        title=title or "新对话",
        agent_id=agent_id,
    )
    db.add(conv)
    await db.flush()
    await db.refresh(conv)
    return conv


async def get_conversation_detail(
    db: AsyncSession,
    conv_id: int,
    user: User,
) -> ConversationDetail:
    """获取会话详情（含所有消息）"""
    q = (
        select(Conversation)
        .where(Conversation.id == conv_id)
        .options(selectinload(Conversation.messages))
    )
    result = await db.execute(q)
    conv = result.scalar_one_or_none()

    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    if conv.user_id != user.id and user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问此会话")

    messages = []
    for msg in conv.messages:
        messages.append(MessageItem(
            id=msg.id,
            conversation_id=msg.conversation_id,
            role=msg.role,
            content=msg.content,
            sources=_load_items(msg.sources, SourceItem),
            tool_calls=_load_items(msg.tool_calls, ToolCallItem),
            token_count=msg.token_count,
            created_at=msg.created_at,
        ))

    return ConversationDetail(
        id=conv.id,
        title=conv.title,
        is_active=conv.is_active,
        agent_id=conv.agent_id,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=messages,
    )


async def delete_conversation(db: AsyncSession, conv_id: int, user: User) -> None:
    """删除会话（软删除）"""
    q = select(Conversation).where(Conversation.id == conv_id)
    result = await db.execute(q)
    conv = result.scalar_one_or_none()

    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    if conv.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权删除此会话")

    conv.is_active = False
    db.add(conv)
    await db.flush()


async def update_conversation_title(db: AsyncSession, conv_id: int, user: User, title: str) -> Conversation:
    """修改会话标题"""
    q = select(Conversation).where(Conversation.id == conv_id)
    result = await db.execute(q)
    conv = result.scalar_one_or_none()

    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    if conv.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权修改此会话")

    conv.title = title
    db.add(conv)
    await db.flush()
    await db.refresh(conv)
    return conv
