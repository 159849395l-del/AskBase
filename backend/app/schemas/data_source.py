"""数据源管理 Pydantic schemas"""

from pydantic import BaseModel, Field
from typing import Optional


class DataSourceBase(BaseModel):
    """创建/测试连接共用的连接信息字段"""

    name: str = Field("", max_length=100, description="数据源名称（别名），创建时必填")
    type: str = Field("mysql", max_length=20, description="类型，当前仅支持 mysql")
    host: str = Field(..., min_length=1, max_length=255, description="地址/IP")
    port: int = Field(3306, ge=1, le=65535, description="端口")
    database: str = Field(..., min_length=1, max_length=255, description="库/服务名（真实库名）")
    username: str = Field(..., min_length=1, max_length=100, description="用户名")
    password: str = Field("", max_length=255, description="密码（仅入参，不返回）")


class DataSourceCreate(DataSourceBase):
    """创建数据源（仅管理员）"""

    name: str = Field(..., min_length=1, max_length=100, description="数据源名称（别名），需唯一")


class DataSourceUpdate(BaseModel):
    """更新数据源（部分字段；password 为空表示不修改密码）"""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    type: Optional[str] = Field(None, max_length=20)
    host: Optional[str] = Field(None, min_length=1, max_length=255)
    port: Optional[int] = Field(None, ge=1, le=65535)
    database: Optional[str] = Field(None, min_length=1, max_length=255)
    username: Optional[str] = Field(None, min_length=1, max_length=100)
    password: Optional[str] = Field(None, max_length=255, description="留空/None 表示不修改密码")


class DataSourceItem(BaseModel):
    """数据源列表/详情（不含密码）"""

    id: int
    name: str
    type: str
    host: str
    port: int
    database: str
    username: str
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class TestConnectionRequest(DataSourceBase):
    """用传入的连接信息测试连通（不落库；name 可空）"""

    name: str = Field("", max_length=100)


class TestConnectionResponse(BaseModel):
    success: bool
    message: str
    latency_ms: Optional[int] = None
