"""知识库管理相关 Pydantic schemas"""

from pydantic import BaseModel, Field
from typing import Optional, List


class DocumentItem(BaseModel):
    id: int
    filename: str
    file_type: str
    file_size: int
    chunk_count: int
    status: str
    created_at: str

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    items: List[DocumentItem]
    total: int
    page: int
    page_size: int


class KBStatsResponse(BaseModel):
    total_documents: int
    total_chunks: int
    total_size_bytes: int
    by_status: dict
    last_ingested_at: Optional[str] = None


class KBSearchResult(BaseModel):
    chunk_text: str
    filename: str
    similarity_score: float
    score_type: Optional[str] = None  # "vector"=相似度 | "bm25"=关键词匹配
    metadata: dict


class KBSearchResponse(BaseModel):
    results: List[KBSearchResult]
