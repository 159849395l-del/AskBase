"""大模型库 Pydantic schemas"""

from pydantic import BaseModel, Field
from typing import Optional, List


PROVIDER_OPTIONS = [
    {"label": "深度求索 DeepSeek", "value": "deepseek", "default_base_url": "https://api.deepseek.com"},
    {"label": "字节豆包 火山方舟", "value": "volcengine", "default_base_url": "https://ark.cn-beijing.volces.com/api/v3"},
    {"label": "阿里云百炼", "value": "aliyun", "default_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1"},
    {"label": "OpenAI", "value": "openai", "default_base_url": "https://api.openai.com/v1"},
    {"label": "月之暗面 Kimi", "value": "moonshot", "default_base_url": "https://api.moonshot.cn/v1"},
    {"label": "智谱 GLM", "value": "zhipu", "default_base_url": "https://open.bigmodel.cn/api/paas/v4"},
    {"label": "本地 / Ollama", "value": "local", "default_base_url": "http://localhost:11434/v1"},
    {"label": "自定义", "value": "custom", "default_base_url": ""},
]


class LLMModelBase(BaseModel):
    """大模型通用字段"""

    name: str = Field(..., min_length=1, max_length=100, description="显示名称")
    provider: str = Field("custom", max_length=50, description="厂商标识")
    model_id: str = Field(..., min_length=1, max_length=100, description="真实模型 ID")
    base_url: str = Field(..., min_length=1, max_length=255, description="OpenAI 兼容 endpoint")
    api_key: str = Field("", max_length=1024, description="API Key（仅入参，不返回）")
    is_active: bool = Field(True, description="是否启用")
    is_vision: bool = Field(False, description="是否视觉模型")
    supports_tool_call: bool = Field(False, description="是否支持 function calling")
    temperature: float = Field(0.3, ge=0, le=2, description="默认温度")
    max_tokens: Optional[int] = Field(None, ge=1, description="最大输出 token（空=不限制）")
    sort_order: int = Field(0, description="排序（升序）")


class LLMModelCreate(LLMModelBase):
    """创建大模型"""

    is_default: bool = Field(False, description="是否设为系统默认模型")


class LLMModelUpdate(BaseModel):
    """更新大模型（部分字段；api_key 为空表示不修改）"""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    provider: Optional[str] = Field(None, max_length=50)
    model_id: Optional[str] = Field(None, min_length=1, max_length=100)
    base_url: Optional[str] = Field(None, min_length=1, max_length=255)
    api_key: Optional[str] = Field(None, max_length=1024, description="留空/None 表示不修改密钥")
    is_active: Optional[bool] = None
    is_vision: Optional[bool] = None
    supports_tool_call: Optional[bool] = None
    is_default: Optional[bool] = None
    temperature: Optional[float] = Field(None, ge=0, le=2)
    max_tokens: Optional[int] = Field(None, ge=1)
    sort_order: Optional[int] = None


class LLMModelItem(BaseModel):
    """大模型列表/详情（不含 api_key）"""

    id: int
    name: str
    provider: str
    model_id: str
    base_url: str
    is_active: bool
    is_vision: bool
    supports_tool_call: bool
    is_default: bool
    temperature: float
    max_tokens: Optional[int] = None
    sort_order: int
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class ModelTestResponse(BaseModel):
    """模型连通测试响应"""

    success: bool
    message: str
    latency_ms: Optional[int] = None


class ProviderOption(BaseModel):
    """厂商选项（供前端下拉使用）"""

    label: str
    value: str
    default_base_url: str
