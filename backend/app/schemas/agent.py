"""智能体 Pydantic schemas"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class AgentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="智能体名称")
    description: str = Field(default="", max_length=500, description="简介")
    icon: str = Field(default="🤖", max_length=50, description="图标（emoji 或 URL）")
    welcome_message: str = Field(default="您好，我是您的专属AI助手，请问有什么可以帮助您呢？", description="欢迎语")
    system_prompt: str = Field(default="", description="系统提示词 / 人设")
    is_active: bool = Field(default=True, description="是否启用")
    is_hidden: bool = Field(default=False, description="对用户隐藏（管理员仍可见/可编辑）")
    sort_order: int = Field(default=0, description="排序（升序）")


class AgentToolRef(BaseModel):
    """智能体挂载的工具引用"""

    tool_type: str = Field(..., description="skill | mcp_tool")
    tool_ref_id: Optional[int] = Field(None, description="内部 Skill 的 id（tool_type=skill 时必填）")
    tool_ref: Optional[str] = Field(None, description="MCP 工具引用 '<server_id>:<tool_name>'（tool_type=mcp_tool 时必填）")
    enabled: bool = Field(True)


class AgentCreate(AgentBase):
    """创建智能体（管理员）"""

    kb_ids: List[int] = Field(default_factory=list, description="关联的知识库 ID 列表（数据库型 KB 最多 1 个）")
    model_id: Optional[int] = Field(None, description="绑定的大模型 ID（NULL=系统默认）")
    tools: List[AgentToolRef] = Field(default_factory=list, description="挂载的工具列表")


class AgentUpdate(BaseModel):
    """更新智能体（部分字段）"""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    icon: Optional[str] = Field(None, max_length=50)
    welcome_message: Optional[str] = None
    system_prompt: Optional[str] = None
    is_active: Optional[bool] = None
    is_hidden: Optional[bool] = None
    sort_order: Optional[int] = None
    kb_ids: Optional[List[int]] = Field(None, description="若提供则全量替换关联的知识库")
    model_id: Optional[int] = Field(None, description="绑定的大模型 ID（NULL=系统默认）")
    tools: Optional[List[AgentToolRef]] = Field(None, description="若提供则全量替换挂载的工具")


class AgentItem(BaseModel):
    """智能体列表项（所有登录用户可见）"""

    id: int
    name: str
    description: str
    icon: str
    welcome_message: str
    is_active: bool
    is_hidden: bool = False
    sort_order: int
    created_at: str
    kb_ids: List[int] = []
    model_id: Optional[int] = None
    tools: List[AgentToolRef] = []

    class Config:
        from_attributes = True


class AgentDetail(AgentItem):
    """智能体详情（管理员可见 system_prompt 等）"""

    system_prompt: str = ""
    updated_at: str = ""
    kb_ids: List[int] = []
    model_id: Optional[int] = None
    tools: List[AgentToolRef] = []


class AgentCreateResponse(BaseModel):
    id: int
    name: str