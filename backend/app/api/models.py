"""
大模型库管理 API — 仅管理员可增删改，登录用户可读启用列表
- CRUD：/api/models
- 连通测试：POST /api/models/{id}/test（用已存配置）
- 设为默认：POST /api/models/{id}/set-default
- 厂商选项：GET /api/models/providers
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.database import get_db
from app.models.user import User
from app.core.dependencies import get_current_user, get_admin_user
from app.schemas.llm_model import (
    LLMModelCreate,
    LLMModelUpdate,
    LLMModelItem,
    ModelTestResponse,
    ProviderOption,
    PROVIDER_OPTIONS,
)
from app.schemas.auth import MessageResponse
from app.services import llm_model_service

router = APIRouter(prefix="/api/models", tags=["大模型库"])


@router.get("/providers", response_model=List[ProviderOption])
async def list_providers(
    current_user: User = Depends(get_current_user),
):
    """厂商下拉选项（含默认 endpoint，前端选中后自动填充接口地址）"""
    return [ProviderOption(**p) for p in PROVIDER_OPTIONS]


@router.get("", response_model=List[LLMModelItem])
async def list_models(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """模型列表（管理员看全部；普通用户只看启用）"""
    only_active = current_user.role != "admin"
    return await llm_model_service.list_models(db, only_active=only_active)


@router.post("", response_model=LLMModelItem, status_code=status.HTTP_201_CREATED)
async def create_model(
    body: LLMModelCreate,
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """新建模型（仅管理员）"""
    return await llm_model_service.create_model(db, body)


@router.get("/{model_id}", response_model=LLMModelItem)
async def get_model(
    model_id: int,
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """模型详情（仅管理员；不含密钥）"""
    m = await llm_model_service.get_model(db, model_id)
    return LLMModelItem.model_validate(m)


@router.put("/{model_id}", response_model=LLMModelItem)
async def update_model(
    model_id: int,
    body: LLMModelUpdate,
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """更新模型（仅管理员）"""
    return await llm_model_service.update_model(db, model_id, body)


@router.delete("/{model_id}", response_model=MessageResponse)
async def delete_model(
    model_id: int,
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """删除模型（仅管理员；引用它的智能体自动改为系统默认）"""
    await llm_model_service.delete_model(db, model_id)
    return MessageResponse(message="模型已删除")


@router.post("/{model_id}/test", response_model=ModelTestResponse)
async def test_model(
    model_id: int,
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """用已保存的模型配置测试连通（仅管理员）"""
    return await llm_model_service.test_saved_model(db, model_id)


@router.post("/{model_id}/set-default", response_model=LLMModelItem)
async def set_default_model(
    model_id: int,
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """设为系统默认模型（仅管理员）"""
    return await llm_model_service.set_default_model(db, model_id)
