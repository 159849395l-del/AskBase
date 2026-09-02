"""
MCP 服务管理 API — 仅管理员可访问
- CRUD：/api/mcp-servers
- 工具发现：POST /api/mcp-servers/{id}/discover
- 缓存工具列表：GET /api/mcp-servers/{id}/tools
- 测试调用：POST /api/mcp-servers/{id}/tools/{tool_name}/call
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.database import get_db
from app.models.user import User
from app.core.dependencies import get_current_user, get_admin_user
from app.schemas.mcp_server import (
    MCPServerCreate,
    MCPServerUpdate,
    MCPServerItem,
    MCPServerDetail,
    MCPToolItem,
    MCPToolCallRequest,
    MCPToolCallResponse,
    DiscoverResponse,
)
from app.schemas.auth import MessageResponse
from app.services import mcp_service

router = APIRouter(prefix="/api/mcp-servers", tags=["AI 智能工具"])


@router.get("", response_model=List[MCPServerItem])
async def list_servers(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """MCP 服务列表（管理员看全部；普通用户只看启用）"""
    items = await mcp_service.list_servers(db)
    if current_user.role != "admin":
        items = [i for i in items if i.is_active]
    return items


@router.post("", response_model=MCPServerDetail, status_code=status.HTTP_201_CREATED)
async def create_server(
    body: MCPServerCreate,
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """新建 MCP 服务（仅管理员）"""
    return await mcp_service.create_server(db, body)


@router.get("/{server_id}", response_model=MCPServerDetail)
async def get_server(
    server_id: int,
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """MCP 服务详情（仅管理员，含命令与环境变量）"""
    return await mcp_service.get_server_detail(db, server_id)


@router.put("/{server_id}", response_model=MCPServerDetail)
async def update_server(
    server_id: int,
    body: MCPServerUpdate,
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """更新 MCP 服务（仅管理员）"""
    return await mcp_service.update_server(db, server_id, body)


@router.delete("/{server_id}", response_model=MessageResponse)
async def delete_server(
    server_id: int,
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """删除 MCP 服务（仅管理员）"""
    await mcp_service.delete_server(db, server_id)
    return MessageResponse(message="MCP 服务已删除")


@router.post("/{server_id}/discover", response_model=DiscoverResponse)
async def discover_tools(
    server_id: int,
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """连接 MCP 服务并拉取工具列表（tools/list），结果缓存（仅管理员）"""
    return await mcp_service.discover_tools(db, server_id)


@router.get("/{server_id}/tools", response_model=List[MCPToolItem])
async def list_cached_tools(
    server_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """读取缓存的工具列表（不连接服务）"""
    return await mcp_service.load_cached_tools(db, server_id)


@router.post("/{server_id}/tools/{tool_name}/call", response_model=MCPToolCallResponse)
async def call_tool(
    server_id: int,
    tool_name: str,
    body: MCPToolCallRequest,
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """测试调用 MCP 工具（仅管理员）"""
    from fastapi import HTTPException

    try:
        result = await mcp_service.call_tool(db, server_id, tool_name, body.arguments)
        return MCPToolCallResponse(success=True, result=result)
    except HTTPException as e:
        return MCPToolCallResponse(success=False, message=str(e.detail))
    except Exception as e:
        return MCPToolCallResponse(success=False, message=str(e)[:500])
