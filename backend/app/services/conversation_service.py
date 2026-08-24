"""
会话服务 — 会话 CRUD 和消息管理
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status
from typing import Optional, Tuple, List
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.schemas.conversation import ConversationItem, ConversationDetail
from app.schemas.chat import MessageItem, SourceItem
import json


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
        sources = None
        if msg.sources:
            try:
                sources = [SourceItem(**s) for s in json.loads(msg.sources)]
            except (json.JSONDecodeError, TypeError):
                sources = None
        messages.append(MessageItem(
            id=msg.id,
            conversation_id=msg.conversation_id,
            role=msg.role,
            content=msg.content,
            sources=sources,
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
