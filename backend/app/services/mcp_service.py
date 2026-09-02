"""MCP 服务 — 连接外部 MCP server，发现工具并调用

- transport=stdio：后端按需启动子进程，一次调用完即关闭（避免长期僵尸进程）
- transport=sse：连接远端 HTTP 服务
- 依赖官方 `mcp` 包；未安装时所有操作返回明确错误，不影响其它模块
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional, Dict, Any, Tuple
from fastapi import HTTPException, status
import asyncio
import json

from app.models.mcp_server import MCPServer
from app.schemas.mcp_server import (
    MCPServerCreate,
    MCPServerUpdate,
    MCPServerItem,
    MCPServerDetail,
    MCPToolItem,
    DiscoverResponse,
)

MCP_NOT_INSTALLED = "未安装 mcp 依赖，请在 backend 环境执行：pip install mcp"


def _require_mcp():
    """导入 mcp SDK，未安装时抛 500 并给出安装提示"""
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        from mcp.client.sse import sse_client

        return ClientSession, StdioServerParameters, stdio_client, sse_client
    except ImportError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=MCP_NOT_INSTALLED) from e


# ---------- CRUD ----------


def _to_item(s: MCPServer) -> MCPServerItem:
    tool_count = 0
    if s.tools_cache:
        try:
            tool_count = len(json.loads(s.tools_cache))
        except Exception:
            tool_count = 0
    return MCPServerItem(
        id=s.id,
        name=s.name,
        description=s.description,
        transport=s.transport,
        is_active=s.is_active,
        tool_count=tool_count,
        tools_cached_at=s.tools_cached_at,
        last_error=s.last_error,
        created_at=s.created_at,
        updated_at=s.updated_at,
    )


def _to_detail(s: MCPServer) -> MCPServerDetail:
    item = _to_item(s)
    return MCPServerDetail(
        **item.model_dump(),
        command=s.command,
        args=s.args,
        env=s.env,
        url=s.url,
        tools_cache=s.tools_cache,
    )


async def list_servers(db: AsyncSession) -> List[MCPServerItem]:
    result = await db.execute(select(MCPServer).order_by(MCPServer.id.asc()))
    return [_to_item(s) for s in result.scalars().all()]


async def get_server(db: AsyncSession, server_id: int) -> MCPServer:
    result = await db.execute(select(MCPServer).where(MCPServer.id == server_id))
    s = result.scalar_one_or_none()
    if s is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="MCP 服务不存在")
    return s


async def get_server_detail(db: AsyncSession, server_id: int) -> MCPServerDetail:
    return _to_detail(await get_server(db, server_id))


async def create_server(db: AsyncSession, body: MCPServerCreate) -> MCPServerDetail:
    await _ensure_name_unique(db, body.name, exclude_id=None)
    s = MCPServer(
        name=body.name.strip(),
        description=body.description or "",
        transport=body.transport,
        command=body.command,
        args=_dump_json(body.args),
        env=_dump_json(body.env),
        url=body.url,
        is_active=body.is_active,
    )
    db.add(s)
    await db.flush()
    await db.refresh(s)
    return _to_detail(s)


async def update_server(
    db: AsyncSession, server_id: int, body: MCPServerUpdate
) -> MCPServerDetail:
    s = await get_server(db, server_id)
    data = body.model_dump(exclude_unset=True)
    if "name" in data and data["name"]:
        data["name"] = data["name"].strip()
        await _ensure_name_unique(db, data["name"], exclude_id=server_id)
    if "args" in data:
        data["args"] = _dump_json(data["args"])
    if "env" in data:
        data["env"] = _dump_json(data["env"])
    for k, v in data.items():
        setattr(s, k, v)
    await db.flush()
    await db.refresh(s)
    return _to_detail(s)


async def delete_server(db: AsyncSession, server_id: int) -> None:
    s = await get_server(db, server_id)
    await db.delete(s)
    await db.flush()


def _dump_json(value) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


async def _ensure_name_unique(db: AsyncSession, name: str, exclude_id: Optional[int]) -> None:
    q = select(MCPServer).where(MCPServer.name == name.strip())
    if exclude_id is not None:
        q = q.where(MCPServer.id != exclude_id)
    existing = (await db.execute(q)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"MCP 服务名称「{name}」已存在")


# ---------- 工具发现与调用 ----------


def _build_stdio_params(server: MCPServer):
    """构造 stdio 启动参数"""
    _, StdioServerParameters, _, _ = _require_mcp()
    args = []
    if server.args:
        try:
            args = json.loads(server.args)
        except Exception:
            args = []
    env = {}
    if server.env:
        try:
            env = json.loads(server.env)
        except Exception:
            env = {}
    return StdioServerParameters(
        command=server.command or "",
        args=args,
        env={k: str(v) for k, v in env.items()} if env else None,
    )


async def _with_session(server: MCPServer, coro):
    """建立 MCP 会话并执行 coro(session)；统一处理 stdio/sse 两种传输"""
    ClientSession, _, stdio_client, sse_client = _require_mcp()

    if server.transport == "sse":
        if not server.url:
            raise HTTPException(status_code=400, detail="SSE 传输缺少 url")
        async with sse_client(server.url) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await coro(session)
    else:
        if not server.command:
            raise HTTPException(status_code=400, detail="stdio 传输缺少 command")
        params = _build_stdio_params(server)
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await coro(session)


async def discover_tools(db: AsyncSession, server_id: int) -> DiscoverResponse:
    """调用 tools/list，缓存工具列表"""
    _require_mcp()
    server = await get_server(db, server_id)

    async def _list(session):
        resp = await session.list_tools()
        return [
            MCPToolItem(
                name=t.name,
                title=getattr(t, "title", None) or t.name,
                description=t.description or "",
                input_schema=t.inputSchema or {"type": "object", "properties": {}},
            )
            for t in (resp.tools or [])
        ]

    from datetime import datetime

    try:
        tools = await _with_session(server, _list)
    except HTTPException:
        raise
    except Exception as e:
        detail = str(e).replace("\n", " ")[:500]
        server.last_error = detail
        await db.flush()
        raise HTTPException(status_code=400, detail=f"发现工具失败：{detail}")

    server.tools_cache = json.dumps([t.model_dump() for t in tools], ensure_ascii=False)
    server.tools_cached_at = datetime.now().isoformat()
    server.last_error = None
    await db.flush()
    await db.refresh(server)
    return DiscoverResponse(success=True, message=f"发现 {len(tools)} 个工具", tools=tools)


async def call_tool(
    db: AsyncSession, server_id: int, tool_name: str, arguments: Dict[str, Any]
) -> str:
    """调用指定 MCP 工具，返回文本结果"""
    _require_mcp()
    server = await get_server(db, server_id)

    async def _call(session):
        resp = await session.call_tool(tool_name, arguments or {})
        chunks = []
        for c in resp.content or []:
            text = getattr(c, "text", None)
            if text:
                chunks.append(text)
            elif resp.isError:
                chunks.append(str(c))
        if not chunks:
            chunks.append("（工具无文本输出）")
        return "\n".join(chunks)

    try:
        return await asyncio.wait_for(
            _with_session(server, _call), timeout=60.0
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="MCP 工具调用超时（60s）")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"调用失败：{str(e).replace(chr(10), ' ')[:500]}")


async def load_cached_tools(db: AsyncSession, server_id: int) -> List[MCPToolItem]:
    """读取缓存的工具列表（不连接服务）"""
    server = await get_server(db, server_id)
    if not server.tools_cache:
        return []
    try:
        return [MCPToolItem(**t) for t in json.loads(server.tools_cache)]
    except Exception:
        return []


async def resolve_mcp_tool(
    db: AsyncSession, tool_ref: str
) -> Tuple[Optional[MCPServer], Optional[MCPToolItem]]:
    """解析 'server_id:tool_name' → (server, tool)；引用失效返回 (None, None)"""
    try:
        server_id_str, tool_name = tool_ref.split(":", 1)
        server_id = int(server_id_str)
    except (ValueError, IndexError):
        return None, None

    result = await db.execute(select(MCPServer).where(MCPServer.id == server_id))
    server = result.scalar_one_or_none()
    if server is None:
        return None, None
    tools = await load_cached_tools(db, server_id)
    for t in tools:
        if t.name == tool_name:
            return server, t
    return server, None
