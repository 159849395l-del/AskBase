"""
检索器 — ChromaDB 语义相似搜索（异步化，不阻塞事件循环）
"""

import asyncio
from langchain_core.documents import Document
from typing import List, Optional
from app.config import settings
from app.rag.vector_store import get_vectorstore

# ChromaDB 并发检索锁（限制同时检索数，避免文件I/O竞争）
_search_semaphore = asyncio.Semaphore(10)


async def _search_async(query: str, top_k: int, filter_dict: Optional[dict] = None):
    """在独立线程中执行 ChromaDB 检索，避免阻塞事件循环"""
    vectorstore = get_vectorstore()
    kwargs = {"k": top_k}
    if filter_dict:
        kwargs["filter"] = filter_dict

    async with _search_semaphore:
        return await asyncio.to_thread(
            vectorstore.similarity_search_with_relevance_scores,
            query, **kwargs
        )


async def retrieve_similar_chunks(
    query: str,
    top_k: Optional[int] = None,
    score_threshold: Optional[float] = None,
    product_category: Optional[str] = None,
) -> List[Document]:
    """从向量存储中检索与查询最相似的文档片段（异步）"""
    top_k = top_k or settings.RETRIEVAL_TOP_K
    score_threshold = score_threshold or settings.RETRIEVAL_SCORE_THRESHOLD

    filter_dict = None
    if product_category:
        filter_dict = {"product_category": product_category}

    results_with_scores = await _search_async(query, top_k, filter_dict)

    filtered = [
        (doc, score)
        for doc, score in results_with_scores
        if score >= score_threshold
    ]

    return [doc for doc, _ in filtered]


async def retrieve_with_scores(
    query: str,
    top_k: Optional[int] = None,
    score_threshold: Optional[float] = None,
) -> List[tuple]:
    """检索并返回 (Document, score) 元组，用于引用展示（异步）"""
    try:
        top_k = top_k or settings.RETRIEVAL_TOP_K
        score_threshold = score_threshold or settings.RETRIEVAL_SCORE_THRESHOLD

        results_with_scores = await _search_async(query, top_k)

        return [
            (doc, score)
            for doc, score in results_with_scores
            if score >= score_threshold
        ]
    except Exception as e:
        print(f"[Retriever] 检索异常: {e}")
        return []
