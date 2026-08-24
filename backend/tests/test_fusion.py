"""测试融合模块 — RRF 融合数学、对齐键、分数归一化与展示分数"""

import pytest
from langchain_core.documents import Document

from app.rag.fusion import (
    RetrievalHit,
    _doc_key,
    attach_display_scores,
    normalize_bm25_scores,
    rrr_fuse,
)


def _doc(content: str, **metadata) -> Document:
    """内联构造文档"""
    return Document(page_content=content, metadata=metadata)


class TestDocKey:
    """对齐键 — _doc_key"""

    def test_chunk_hash_优先(self):
        """场景：有 chunk_hash → 使用 hash 键"""
        doc = _doc("内容", chunk_hash="abc123", filename="f.md", chunk_index=0)

        assert _doc_key(doc) == "hash:abc123"

    def test_filename_chunk_index_回退(self):
        """场景：无 chunk_hash 但有 filename+chunk_index → 使用组合键"""
        doc = _doc("内容", filename="f.md", chunk_index=3)

        assert _doc_key(doc) == "file:f.md:3"

    def test_内容前64字符_兜底(self):
        """场景：无任何元数据 → 使用内容前 64 字符"""
        content = "这是一段没有元数据的测试文本" * 10
        doc = _doc(content)

        assert _doc_key(doc) == f"content:{content[:64]}"

    def test_同内容无元数据_键相同(self):
        """场景：两个无元数据文档内容相同 → 对齐键相同"""
        doc1 = _doc("相同内容")
        doc2 = _doc("相同内容")

        assert _doc_key(doc1) == _doc_key(doc2)


class TestRRFFuse:
    """RRF 融合 — rrr_fuse"""

    def test_双路命中_排在最前(self):
        """场景：文档 A 在两路均命中 → rrf 分数叠加排第一"""
        doc_a = _doc("A", chunk_hash="a")
        doc_b = _doc("B", chunk_hash="b")
        doc_c = _doc("C", chunk_hash="c")
        vector_results = [(doc_a, 0.9), (doc_b, 0.8)]
        bm25_results = [(doc_a, 1.5), (doc_c, 1.2)]

        hits = rrr_fuse(vector_results, bm25_results, k=60)

        assert hits[0].doc.page_content == "A"
        # RRF 数学：rank 从 1 计，A 在两路均为第 1 名 → 1/61 + 1/61 = 2/61
        assert hits[0].rrf_score == pytest.approx(2 / 61)

    def test_仅单路命中_按排名贡献排序(self):
        """场景：只有向量路 → 保持原排名顺序"""
        doc_a = _doc("A", chunk_hash="a")
        doc_b = _doc("B", chunk_hash="b")
        vector_results = [(doc_a, 0.9), (doc_b, 0.8)]

        hits = rrr_fuse(vector_results, [], k=60)

        assert [h.doc.page_content for h in hits] == ["A", "B"]
        assert hits[0].rrf_score == pytest.approx(1 / 61)
        assert hits[1].rrf_score == pytest.approx(1 / 62)

    def test_同文档两路分数_均保留(self):
        """场景：同一文档双路命中 → vector_score 与 bm25_score 都在"""
        doc_a = _doc("A", chunk_hash="a")

        hits = rrr_fuse([(doc_a, 0.9)], [(doc_a, 2.0)], k=60)

        assert hits[0].vector_score == 0.9
        assert hits[0].bm25_score == 2.0

    def test_空结果(self):
        """场景：两路均为空 → 返回空"""
        assert rrr_fuse([], [], k=60) == []


class TestNormalizeBM25Scores:
    """归一化 — normalize_bm25_scores"""

    def test_归一化到0到1_且保序(self):
        """场景：不同分数 → max-min 归一化到 [0,1] 且保序"""
        hits = [
            RetrievalHit(doc=_doc("a", chunk_hash="a"), bm25_score=1.0),
            RetrievalHit(doc=_doc("b", chunk_hash="b"), bm25_score=2.0),
            RetrievalHit(doc=_doc("c", chunk_hash="c"), bm25_score=4.0),
        ]

        normalize_bm25_scores(hits)

        scores = [h.bm25_score for h in hits]
        assert scores[0] == pytest.approx(0.0)
        assert scores[1] == pytest.approx(1 / 3)
        assert scores[2] == pytest.approx(1.0)
        assert scores[0] < scores[1] < scores[2]

    def test_分数全部相同_置为1(self):
        """场景：所有分数相等（max==min）→ 全部置 1.0 避免除零"""
        hits = [
            RetrievalHit(doc=_doc("a", chunk_hash="a"), bm25_score=2.0),
            RetrievalHit(doc=_doc("b", chunk_hash="b"), bm25_score=2.0),
        ]

        normalize_bm25_scores(hits)

        assert [h.bm25_score for h in hits] == [1.0, 1.0]

    def test_无bm25分数_不修改(self):
        """场景：命中无 BM25 分数 → 原样保留 None"""
        hits = [RetrievalHit(doc=_doc("a", chunk_hash="a"))]

        normalize_bm25_scores(hits)

        assert hits[0].bm25_score is None


class TestAttachDisplayScores:
    """展示分数 — attach_display_scores"""

    def test_有向量分_优先用向量分(self):
        """场景：向量分与 BM25 分都有 → 用向量分（前端百分比语义）"""
        hit = RetrievalHit(
            doc=_doc("a", chunk_hash="a"), vector_score=0.87, bm25_score=5.0
        )

        result = attach_display_scores([hit])

        assert result[0][1] == 0.87

    def test_无向量分_用归一化bm25分(self):
        """场景：仅有 BM25 分 → 用归一化后的 [0,1] 分数"""
        hit1 = RetrievalHit(doc=_doc("a", chunk_hash="a"), bm25_score=1.0)
        hit2 = RetrievalHit(doc=_doc("b", chunk_hash="b"), bm25_score=3.0)

        result = attach_display_scores([hit1, hit2])

        assert result[0][1] == pytest.approx(0.0)
        assert result[1][1] == pytest.approx(1.0)

    def test_两路均无分_返回0(self):
        """场景：无任何分数 → 展示分 0.0"""
        result = attach_display_scores([RetrievalHit(doc=_doc("a", chunk_hash="a"))])

        assert result[0][1] == 0.0

    def test_空列表(self):
        """场景：空命中列表 → 返回空"""
        assert attach_display_scores([]) == []
