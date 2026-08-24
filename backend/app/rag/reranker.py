"""
重排器 — BM25 粗排 / API 语义重排（阿里云百炼 gte-rerank，走 dashscope SDK）
"""

import asyncio
from typing import List

from app.config import settings
from app.rag.fusion import RetrievalHit


class BaseReranker:
    """重排器基类：抽象接口，默认原样截断"""

    async def rerank(
        self,
        query: str,
        hits: List[RetrievalHit],
        top_n: int,
    ) -> List[RetrievalHit]:
        """对候选命中重排，返回前 top_n 条"""
        return hits[:top_n]


class NoopReranker(BaseReranker):
    """空实现：不改变顺序，原样截断到 top_n"""

    async def rerank(
        self,
        query: str,
        hits: List[RetrievalHit],
        top_n: int,
    ) -> List[RetrievalHit]:
        return hits[:top_n]


class BM25Reranker(BaseReranker):
    """按 BM25 分数降序重排；所有命中均无 BM25 分数时退化 Noop 行为"""

    async def rerank(
        self,
        query: str,
        hits: List[RetrievalHit],
        top_n: int,
    ) -> List[RetrievalHit]:
        if not hits:
            return []
        if all(hit.bm25_score is None for hit in hits):
            # 无分数可排：保持原顺序截断
            return hits[:top_n]
        ranked = sorted(
            hits,
            key=lambda h: h.bm25_score if h.bm25_score is not None else -1.0,
            reverse=True,
        )
        return ranked[:top_n]


class ApiReranker(BaseReranker):
    """调用阿里云百炼 gte-rerank 做语义精排（cross-encoder，慢但准）

    - 依赖 dashscope SDK（pip install dashscope），key 复用 EMBEDDING_API_KEY
    - 失败时降级为原顺序截断，不影响主流程
    """

    def __init__(self):
        import dashscope

        self._dashscope = dashscope
        if settings.EMBEDDING_API_KEY:
            dashscope.api_key = settings.EMBEDDING_API_KEY
        self.model = settings.RERANK_MODEL

    async def rerank(
        self,
        query: str,
        hits: List[RetrievalHit],
        top_n: int,
    ) -> List[RetrievalHit]:
        if not hits:
            return []
        docs = [h.doc.page_content for h in hits]
        try:
            resp = await asyncio.to_thread(
                self._dashscope.TextReRank.call,
                model=self.model,
                query=query,
                documents=docs,
                top_n=len(hits),
                return_documents=False,
            )
        except Exception as e:
            print(f"[Reranker] API 调用异常，降级原顺序: {e}")
            return hits[:top_n]

        if resp.status_code != 200:
            print(f"[Reranker] API 错误 {getattr(resp, 'code', '?')}: {getattr(resp, 'message', '?')}，降级原顺序")
            return hits[:top_n]

        results = sorted(resp.output.results, key=lambda r: r["relevance_score"], reverse=True)
        ordered = [hits[r["index"]] for r in results if 0 <= r["index"] < len(hits)]
        return ordered[:top_n] if ordered else hits[:top_n]


def create_reranker() -> BaseReranker:
    """按配置装配重排器：RERANK_ENABLED=False → Noop；mode="bm25" → BM25Reranker；mode="api" → ApiReranker"""
    if not settings.RERANK_ENABLED:
        return NoopReranker()

    mode = settings.RERANK_MODE
    if mode == "bm25":
        return BM25Reranker()
    if mode == "api":
        return ApiReranker()

    print(f"[Reranker] 未知重排模式 {mode!r}，降级为 NoopReranker")
    return NoopReranker()
