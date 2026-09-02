"""内部 Skill（AI 智能工具）Pydantic schemas"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any


class SkillBase(BaseModel):
    """Skill 通用字段"""

    name: str = Field(..., min_length=1, max_length=100, description="工具名（英文，LLM 可见）")
    title: str = Field(..., min_length=1, max_length=100, description="显示标题")
    description: str = Field("", description="功能描述（给 LLM 看）")
    icon: str = Field("🔧", max_length=50, description="图标（emoji）")
    handler: str = Field("", max_length=100, description="处理函数标识（空=用 name）")
    input_schema: Dict[str, Any] = Field(
        default_factory=lambda: {"type": "object", "properties": {}},
        description="JSON Schema 参数定义"
    )
    is_active: bool = Field(True, description="是否启用")
    is_dangerous: bool = Field(False, description="是否危险/写操作")
    sort_order: int = Field(0, description="排序（升序）")


class SkillCreate(SkillBase):
    """创建 Skill"""


class SkillUpdate(BaseModel):
    """更新 Skill（部分字段）"""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    title: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    icon: Optional[str] = Field(None, max_length=50)
    handler: Optional[str] = Field(None, max_length=100)
    input_schema: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    is_dangerous: Optional[bool] = None
    sort_order: Optional[int] = None


class SkillItem(BaseModel):
    """Skill 列表/详情"""

    id: int
    name: str
    title: str
    description: str
    icon: str
    handler: str
    input_schema: Dict[str, Any] = {}
    is_active: bool
    is_builtin: bool = False
    is_dangerous: bool = False
    sort_order: int
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class SkillTestRequest(BaseModel):
    """管理员测试调用 Skill"""

    arguments: Dict[str, Any] = Field(default_factory=dict)


class SkillTestResponse(BaseModel):
    success: bool
    result: str = ""
    message: str = ""
