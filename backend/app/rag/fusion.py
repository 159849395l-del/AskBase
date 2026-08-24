"""
融合模块 — RRF（Reciprocal Rank Fusion）融合向量 / BM25 两路检索结果，并处理展示分数
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from langchain_core.documents import Document


@dataclass
class RetrievalHit:
    """一条融合后的检索命中记录"""

    doc: Document
    vector_score: Optional[float] = None
    bm25_score: Optional[float] = None
    rrf_score: float = 0.0


def _doc_key(doc: Document) -> str:
    """两路检索结果的对齐键：chunk_hash 优先 → (filename, chunk_index) → 内容前 64 字符"""
    metadata = doc.metadata or {}

    chunk_hash = metadata.get("chunk_hash")
    if chunk_hash:
        return f"hash:{chunk_hash}"

    filename = metadata.get("filename")
    chunk_index = metadata.get("chunk_index")
    if filename is not None and chunk_index is not None:
        return f"file:{filename}:{chunk_index}"

    return f"content:{doc.page_content[:64]}"


def rrr_fuse(
    vector_results: List[Tuple[Document, float]],
    bm25_results: List[Tuple[Document, float]],
    k: int,
) -> List[RetrievalHit]:
    """RRF 融合：score = Σ 1 / (k + rank)，按 rrf_score 降序返回

    同一文档在两路均命中时分数叠加，天然排在前面。
    """
    hits_by_key: Dict[str, RetrievalHit] = {}

    for rank, (doc, score) in enumerate(vector_results):
        key = _doc_key(doc)
        hit = hits_by_key.get(key)
        if hit is None:
            hit = RetrievalHit(doc=doc, vector_score=score)
            hits_by_key[key] = hit
        else:
            hit.vector_score = score
        hit.rrf_score += 1.0 / (k + rank + 1)  # rank 从 1 计

    for rank, (doc, score) in enumerate(bm25_results):
        key = _doc_key(doc)
        hit = hits_by_key.get(key)
        if hit is None:
            hit = RetrievalHit(doc=doc, bm25_score=score)
            hits_by_key[key] = hit
        else:
            hit.bm25_score = score
        hit.rrf_score += 1.0 / (k + rank + 1)

    return sorted(hits_by_key.values(), key=lambda h: h.rrf_score, reverse=True)


def normalize_bm25_scores(hits: List[RetrievalHit]) -> None:
    """max-min 归一化 BM25 分数到 [0,1]（原地修改，仅用于显示）"""
    scored = [h for h in hits if h.bm25_score is not None]
    if not scored:
        return

    min_score = min(h.bm25_score for h in scored)
    max_score = max(h.bm25_score for h in scored)

    if max_score == min_score:
        # 分数无区分度时全部置 1.0，避免除零
        for h in scored:
            h.bm25_score = 1.0
        return

    span = max_score - min_score
    for h in scored:
        h.bm25_score = (h.bm25_score - min_score) / span


def attach_display_scores(hits: List[RetrievalHit]) -> List[Tuple[Document, float]]:
    """生成展示分数：有 vector_score 用 vector_score（保持前端百分比语义），否则用归一化 BM25 分

    同时把分数来源写入 doc.metadata["_score_type"]（"vector"/"bm25"/"none"，
    内部字段，仅用于前端展示区分：向量分是相似度，BM25 分是关键词匹配度）。
    """
    normalize_bm25_scores(hits)

    result: List[Tuple[Document, float]] = []
    for hit in hits:
        if hit.vector_score is not None:
            hit.doc.metadata["_score_type"] = "vector"
            result.append((hit.doc, hit.vector_score))
        elif hit.bm25_score is not None:
            hit.doc.metadata["_score_type"] = "bm25"
            result.append((hit.doc, hit.bm25_score))
        else:
            hit.doc.metadata["_score_type"] = "none"
            result.append((hit.doc, 0.0))
    return result
