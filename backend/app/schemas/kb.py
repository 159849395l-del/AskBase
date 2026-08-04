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
    product_category: Optional[str] = None
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
    by_category: dict
    by_status: dict
    last_ingested_at: Optional[str] = None


class KBSearchResult(BaseModel):
    chunk_text: str
    filename: str
    similarity_score: float
    metadata: dict


class KBSearchResponse(BaseModel):
    results: List[KBSearchResult]
