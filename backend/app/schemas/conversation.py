"""会话相关 Pydantic schemas"""

from pydantic import BaseModel, Field
from typing import Optional, List


class ConversationCreate(BaseModel):
    title: Optional[str] = Field(None, max_length=200, description="会话标题，为空则自动生成")


class ConversationUpdate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="新标题")


class ConversationItem(BaseModel):
    id: int
    title: str
    is_active: bool
    message_count: int = 0
    last_message_preview: Optional[str] = None
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class ConversationListResponse(BaseModel):
    items: List[ConversationItem]
    total: int
    page: int
    page_size: int


class ConversationDetail(BaseModel):
    id: int
    title: str
    is_active: bool
    created_at: str
    updated_at: str
    messages: List["MessageItem"]

    class Config:
        from_attributes = True


from app.schemas.chat import MessageItem  # noqa: E402
