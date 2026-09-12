"""聊天相关 Pydantic schemas"""

from pydantic import BaseModel, Field
from typing import Optional, List, Any


class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=8000, description="用户消息内容（上限 8000 字）")
    kb_ids: Optional[List[int]] = Field(
        None, description="可选知识库作用域（限定检索的 kb_id 集合）；为空则全库检索"
    )


class SourceItem(BaseModel):
    """引用来源：知识库片段 / SQL / 网页，前端按 kind 分支渲染

    只有 filename 是历史数据里一定有的；网页来源没有相似度、没有 chunk，
    因此这些字段一律给默认值，不为了凑格式编造数字。
    """
    filename: str
    chunk_text: str = ""
    similarity_score: float = 0.0
    chunk_index: int = 0
    kind: Optional[str] = None
    title: Optional[str] = None
    url: Optional[str] = None
    snippet: Optional[str] = None
    published: Optional[str] = None
    score_type: Optional[str] = None
    sql: Optional[str] = None


class ToolCallItem(BaseModel):
    """一次工具调用（用户可见的留痕：工具名 + 结果摘要）"""
    name: str
    content: str = ""


class MessageItem(BaseModel):
    id: int
    conversation_id: int
    role: str
    content: str
    sources: Optional[List[SourceItem]] = None
    tool_calls: Optional[List[ToolCallItem]] = None
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
