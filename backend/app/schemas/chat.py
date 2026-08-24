"""聊天相关 Pydantic schemas"""

from pydantic import BaseModel, Field
from typing import Optional, List, Any


class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=8000, description="用户消息内容（上限 8000 字）")
    kb_ids: Optional[List[int]] = Field(
        None, description="可选知识库作用域（限定检索的 kb_id 集合）；为空则全库检索"
    )


class SourceItem(BaseModel):
    """知识库引用来源"""
    filename: str
    chunk_text: str
    similarity_score: float
    chunk_index: int


class MessageItem(BaseModel):
    id: int
    conversation_id: int
    role: str
    content: str
    sources: Optional[List[SourceItem]] = None
    token_count: Optional[int] = None
    created_at: str

    class Config:
        from_attributes = True


class SSETokenEvent(BaseModel):
    token: str


class SSESourcesEvent(BaseModel):
    sources: List[SourceItem]


class SSEDoneEvent(BaseModel):
    message_id: int
    token_count: Optional[int] = None
