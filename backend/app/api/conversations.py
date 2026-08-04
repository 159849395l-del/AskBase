"""
会话 API — 会话 CRUD
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.user import User
from app.core.dependencies import get_current_user
from app.services.conversation_service import (
    list_conversations,
    create_conversation,
    get_conversation_detail,
    delete_conversation,
    update_conversation_title,
)
from app.schemas.conversation import (
    ConversationCreate,
    ConversationUpdate,
    ConversationListResponse,
    ConversationDetail,
    ConversationItem,
)
from app.schemas.auth import MessageResponse

router = APIRouter(prefix="/api/conversations", tags=["会话"])


@router.get("", response_model=ConversationListResponse)
async def list_convs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的会话列表"""
    items, total = await list_conversations(db, current_user, page, page_size)
    return ConversationListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=ConversationItem, status_code=201)
async def create_conv(
    body: ConversationCreate = ConversationCreate(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """新建会话"""
    conv = await create_conversation(db, current_user, body.title)
    return ConversationItem(
        id=conv.id,
        title=conv.title,
        is_active=conv.is_active,
        message_count=0,
        last_message_preview=None,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
    )


@router.get("/{conv_id}", response_model=ConversationDetail)
async def get_conv(
    conv_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取会话详情（含所有消息）"""
    return await get_conversation_detail(db, conv_id, current_user)


@router.delete("/{conv_id}", response_model=MessageResponse)
async def delete_conv(
    conv_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除会话"""
    await delete_conversation(db, conv_id, current_user)
    return MessageResponse(message="会话已删除")


@router.patch("/{conv_id}", response_model=ConversationItem)
async def update_conv(
    conv_id: int,
    body: ConversationUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """修改会话标题"""
    conv = await update_conversation_title(db, conv_id, current_user, body.title)
    return ConversationItem(
        id=conv.id,
        title=conv.title,
        is_active=conv.is_active,
        message_count=0,
        last_message_preview=None,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
    )
