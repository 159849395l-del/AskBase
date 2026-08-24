"""
数据源管理 API — 仅管理员可访问
- CRUD：/api/data-sources
- 连通测试：POST /api/data-sources/test-connection（不落库）/ {id}/test-connection（用已存配置）
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.user import User
from app.core.dependencies import get_admin_user
from app.schemas.data_source import (
    DataSourceCreate,
    DataSourceUpdate,
    DataSourceItem,
    TestConnectionRequest,
    TestConnectionResponse,
)
from app.schemas.auth import MessageResponse
from app.services import data_source_service

router = APIRouter(prefix="/api/data-sources", tags=["数据源管理"])


@router.get("", response_model=list[DataSourceItem])
async def list_data_sources(
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """数据源列表（仅管理员）"""
    return await data_source_service.list_data_sources(db)


@router.post("", response_model=DataSourceItem, status_code=status.HTTP_201_CREATED)
async def create_data_source(
    body: DataSourceCreate,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """新建数据源（仅管理员）"""
    return await data_source_service.create_data_source(db, body)


@router.get("/{ds_id}", response_model=DataSourceItem)
async def get_data_source(
    ds_id: int,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """数据源详情（仅管理员）"""
    ds = await data_source_service.get_data_source(db, ds_id)
    return DataSourceItem.model_validate(ds)


@router.put("/{ds_id}", response_model=DataSourceItem)
async def update_data_source(
    ds_id: int,
    body: DataSourceUpdate,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """更新数据源（仅管理员）"""
    return await data_source_service.update_data_source(db, ds_id, body)


@router.delete("/{ds_id}", response_model=MessageResponse)
async def delete_data_source(
    ds_id: int,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """删除数据源（仅管理员；被知识库引用时拒绝）"""
    await data_source_service.delete_data_source(db, ds_id)
    return MessageResponse(message="数据源已删除")


@router.post("/test-connection", response_model=TestConnectionResponse)
async def test_connection(
    body: TestConnectionRequest,
    current_user: User = Depends(get_admin_user),
):
    """用传入的连接信息测试连通（不落库）"""
    return await data_source_service.test_connection(
        host=body.host,
        port=body.port,
        database=body.database,
        username=body.username,
        password=body.password or "",
    )


@router.post("/{ds_id}/test-connection", response_model=TestConnectionResponse)
async def test_saved_connection(
    ds_id: int,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """用已保存的数据源配置测试连通"""
    return await data_source_service.test_saved_connection(db, ds_id)
