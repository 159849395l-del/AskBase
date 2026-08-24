"""知识库 Pydantic schemas"""

from pydantic import BaseModel, Field
from typing import Optional


class KnowledgeBaseCreate(BaseModel):
    """创建知识库（仅管理员）

    - type=document（A 类）：data_source_id / database_name 必须为空
    - type=database（B 类）：data_source_id + database_name 必须填写
    """

    name: str = Field(..., min_length=1, max_length=100, description="知识库名称")
    label: str = Field("", max_length=50, description="标签")
    authorized_user_id: Optional[int] = Field(None, description="授权用户 ID（可选）")
    type: str = Field("document", description="document | database")
    data_source_id: Optional[int] = Field(None, description="绑定数据源 ID（B 类必填）")
    database_name: Optional[str] = Field(None, max_length=255, description="库名（B 类必填）")
    description: str = Field("", max_length=500, description="描述")


class KnowledgeBaseUpdate(BaseModel):
    """更新知识库（部分字段；type 不允许变更）"""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    label: Optional[str] = Field(None, max_length=50)
    authorized_user_id: Optional[int] = Field(None)
    data_source_id: Optional[int] = Field(None)
    database_name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=500)


class KnowledgeBaseItem(BaseModel):
    """知识库列表/详情"""

    id: int
    name: str
    label: str
    authorized_user_id: Optional[int] = None
    type: str
    data_source_id: Optional[int] = None
    database_name: Optional[str] = None
    description: str
    created_at: str
    updated_at: str
    # 富信息（列表页展示用）
    data_source_name: Optional[str] = None       # 数据源别名（join 后填充）
    doc_count: int = 0                           # 文档数（A 类）
    qa_count: int = 0                            # 问答数（A 类）
    table_count: int = 0                         # 表数（B 类）
    kp_count: int = 0                            # 知识点数（B 类）

    class Config:
        from_attributes = True
