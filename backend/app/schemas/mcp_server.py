"""MCP 服务 Pydantic schemas"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class MCPToolItem(BaseModel):
    """MCP 工具定义（tools/list 结果）"""

    name: str
    title: str = ""
    description: str = ""
    input_schema: Dict[str, Any] = Field(default_factory=lambda: {"type": "object", "properties": {}})


class MCPServerBase(BaseModel):
    """MCP 服务通用字段"""

    name: str = Field(..., min_length=1, max_length=100, description="服务名称")
    description: str = Field("", max_length=500, description="描述")
    transport: str = Field("stdio", description="stdio | sse")
    command: Optional[str] = Field(None, max_length=255, description="stdio 启动命令，如 npx / python")
    args: Optional[List[str]] = Field(None, description="stdio 参数数组")
    env: Optional[Dict[str, str]] = Field(None, description="环境变量（键值对）")
    url: Optional[str] = Field(None, max_length=500, description="SSE 服务地址")
    is_active: bool = Field(True, description="是否启用")


class MCPServerCreate(MCPServerBase):
    """创建 MCP 服务"""


class MCPServerUpdate(BaseModel):
    """更新 MCP 服务（部分字段）"""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    transport: Optional[str] = None
    command: Optional[str] = None
    args: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None
    url: Optional[str] = None
    is_active: Optional[bool] = None


class MCPServerItem(BaseModel):
    """MCP 服务列表项"""

    id: int
    name: str
    description: str
    transport: str
    is_active: bool
    tool_count: int = 0
    tools_cached_at: Optional[str] = None
    last_error: Optional[str] = None
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class MCPServerDetail(MCPServerItem):
    """MCP 服务详情（管理员；含命令与环境变量）"""

    command: Optional[str] = None
    args: Optional[str] = None
    env: Optional[str] = None
    url: Optional[str] = None
    tools_cache: Optional[str] = None


class DiscoverResponse(BaseModel):
    """工具发现响应"""

    success: bool
    message: str
    tools: List[MCPToolItem] = []


class MCPToolCallRequest(BaseModel):
    """管理员测试调用 MCP 工具"""

    arguments: Dict[str, Any] = Field(default_factory=dict)


class MCPToolCallResponse(BaseModel):
    """工具调用响应"""

    success: bool
    result: str = ""
    message: str = ""
