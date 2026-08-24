"""
知识库管理 API — 仅管理员可访问
CRUD：/api/knowledge-bases
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.user import User
from app.core.dependencies import get_admin_user
from app.schemas.knowledge_base import (
    KnowledgeBaseCreate,
    KnowledgeBaseUpdate,
    KnowledgeBaseItem,
)
from app.schemas.auth import MessageResponse
from app.services import knowledge_base_service

router = APIRouter(prefix="/api/knowledge-bases", tags=["知识库"])


@router.get("", response_model=list[KnowledgeBaseItem])
async def list_knowledge_bases(
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """知识库列表（仅管理员；含子资源计数）"""
    return await knowledge_base_service.list_knowledge_bases(db)


@router.post("", response_model=KnowledgeBaseItem, status_code=status.HTTP_201_CREATED)
async def create_knowledge_base(
    body: KnowledgeBaseCreate,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """新建知识库（仅管理员；B 类自动同步表结构）"""
    return await knowledge_base_service.create_knowledge_base(db, body, created_by=current_user.id)


@router.get("/{kb_id}", response_model=KnowledgeBaseItem)
async def get_knowledge_base(
    kb_id: int,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """知识库详情"""
    kb = await knowledge_base_service.get_knowledge_base(db, kb_id)
    return await knowledge_base_service._enrich_item(db, kb)


@router.put("/{kb_id}", response_model=KnowledgeBaseItem)
async def update_knowledge_base(
    kb_id: int,
    body: KnowledgeBaseUpdate,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """更新知识库"""
    return await knowledge_base_service.update_knowledge_base(db, kb_id, body)


@router.delete("/{kb_id}", response_model=MessageResponse)
async def delete_knowledge_base(
    kb_id: int,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """删除知识库"""
    await knowledge_base_service.delete_knowledge_base(db, kb_id)
    return MessageResponse(message="知识库已删除")
