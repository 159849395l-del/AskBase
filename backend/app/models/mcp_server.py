"""MCP 服务模型 — 管理外部 MCP（Model Context Protocol）服务器连接

- transport=stdio：由后端启动子进程（command + args + env），通过 stdin/stdout 通信
- transport=sse：连接远端 HTTP 服务（url）
- tools_cache：最近一次 tools/list 的结果，缓存下来供智能体挂载时展示
"""

from sqlalchemy import String, Integer, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from datetime import datetime
from typing import Optional


def _now() -> str:
    return datetime.now().isoformat()


class MCPServer(Base):
    """MCP 服务：一条记录 = 一个 MCP server 连接配置"""

    __tablename__ = "mcp_servers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, comment="服务名称")
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="描述")
    transport: Mapped[str] = mapped_column(
        String(20), nullable=False, default="stdio", comment="stdio | sse"
    )
    command: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="stdio 启动命令，如 npx / python"
    )
    args: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="stdio 参数数组（JSON 字符串）"
    )
    env: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="环境变量（JSON 对象字符串，值会加密存储）"
    )
    url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="SSE 服务地址")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    tools_cache: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="tools/list 结果（JSON 数组字符串）"
    )
    tools_cached_at: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="最近一次连接/发现的错误")
    created_at: Mapped[str] = mapped_column(String(30), nullable=False, default=_now)
    updated_at: Mapped[str] = mapped_column(String(30), nullable=False, default=_now, onupdate=_now)

    def __repr__(self) -> str:
        return f"<MCPServer(id={self.id}, name='{self.name}', transport='{self.transport}')>"
