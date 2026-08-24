"""B 类知识库子资源 Pydantic schemas（表信息 / 字段 / 知识点）"""

from pydantic import BaseModel, Field
from typing import Optional, List


class DBTableFieldItem(BaseModel):
    """字段信息"""

    id: int
    db_table_id: int
    field_name: str
    field_type: str
    field_comment: str
    is_required: bool
    status: str  # normal | conflict
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class DBTableItem(BaseModel):
    """表信息"""

    id: int
    kb_id: int
    table_name: str
    table_comment: str
    column_count: int
    is_required: bool
    status: str
    created_at: str
    updated_at: str
    fields: List[DBTableFieldItem] = []

    class Config:
        from_attributes = True


class DBTableUpdate(BaseModel):
    table_comment: Optional[str] = Field(None, max_length=500)
    is_required: Optional[bool] = None


class DBTableFieldUpdate(BaseModel):
    field_comment: Optional[str] = Field(None, max_length=500)
    is_required: Optional[bool] = None
    status: Optional[str] = None


class DBKnowledgePointCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)


class DBKnowledgePointUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    content: Optional[str] = Field(None, min_length=1)


class DBKnowledgePointItem(BaseModel):
    id: int
    kb_id: int
    name: str
    content: str
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class DBKnowledgePointListResponse(BaseModel):
    items: List[DBKnowledgePointItem]
    total: int
