"""测试重排器 — Noop 截断、BM25 降序重排、缺分数退化与工厂装配"""

import asyncio

import pytest
from langchain_core.documents import Document

from app.config import settings
from app.rag.fusion import RetrievalHit
from app.rag.reranker import (
    ApiReranker,
    BM25Reranker,
    NoopReranker,
    create_reranker,
)


def _hit(content: str, bm25_score=None) -> RetrievalHit:
    """内联构造带可选 BM25 分数的命中"""
    return RetrievalHit(
        doc=Document(page_content=content, metadata={"chunk_hash": content}),
        bm25_score=bm25_score,
    )


def _run(coro):
    """同步运行协程"""
    return asyncio.run(coro)


class TestNoopReranker:
    """空实现 — 原样截断"""

    def test_截断到top_n_保持原序(self):
        """场景：候选数 > top_n → 截断且不改变顺序"""
        hits = [_hit(f"doc{i}", bm25_score=float(i)) for i in range(5)]

        result = _run(NoopReranker().rerank("q", hits, top_n=3))

        assert len(result) == 3
        assert [h.doc.page_content for h in result] == ["doc0", "doc1", "doc2"]

    def test_top_n大于候选数_返回全部(self):
        """场景：候选数 < top_n → 全部返回"""
        hits = [_hit(f"doc{i}") for i in range(3)]

        result = _run(NoopReranker().rerank("q", hits, top_n=5))

        assert len(result) == 3


class TestBM25Reranker:
    """BM25 重排 — 按 bm25_score 降序"""

    def test_按分数降序排列(self):
        """场景：乱序候选 → 按 bm25_score 降序输出"""
        hits = [
            _hit("low", bm25_score=1.0),
            _hit("high", bm25_score=9.0),
            _hit("mid", bm25_score=5.0),
        ]

        result = _run(BM25Reranker().rerank("q", hits, top_n=3))

        assert [h.doc.page_content for h in result] == ["high", "mid", "low"]

    def test_截断到top_n(self):
        """场景：候选数 > top_n → 取分数最高的前 top_n"""
        hits = [_hit(f"doc{i}", bm25_score=float(i)) for i in range(5)]

        result = _run(BM25Reranker().rerank("q", hits, top_n=2))

        assert [h.doc.page_content for h in result] == ["doc4", "doc3"]

    def test_缺分数的命中_排在末尾(self):
        """场景：部分命中无分数 → 无分数者沉底，其余按分数降序"""
        hits = [
            _hit("none", bm25_score=None),
            _hit("high", bm25_score=9.0),
            _hit("low", bm25_score=1.0),
        ]

        result = _run(BM25Reranker().rerank("q", hits, top_n=3))

        assert [h.doc.page_content for h in result] == ["high", "low", "none"]

    def test_全部缺分数_退化Noop保序(self):
        """场景：全部无分数 → 退化 Noop 行为，保持原顺序截断"""
        hits = [_hit(f"doc{i}") for i in range(4)]

        result = _run(BM25Reranker().rerank("q", hits, top_n=4))

        assert [h.doc.page_content for h in result] == ["doc0", "doc1", "doc2", "doc3"]

    def test_空列表(self):
        """场景：空候选 → 返回空"""
        assert _run(BM25Reranker().rerank("q", [], top_n=5)) == []


class TestCreateReranker:
    """工厂装配 — create_reranker"""

    def teardown_method(self):
        """恢复默认配置，避免影响其他测试"""
        settings.RERANK_ENABLED = False
        settings.RERANK_MODE = "bm25"

    def test_关闭重排_返回Noop(self):
        """场景：RERANK_ENABLED=False → NoopReranker"""
        settings.RERANK_ENABLED = False

        assert isinstance(create_reranker(), NoopReranker)

    def test_mode_bm25_返回BM25Reranker(self):
        """场景：RERANK_ENABLED=True 且 mode=bm25 → BM25Reranker"""
        settings.RERANK_ENABLED = True
        settings.RERANK_MODE = "bm25"

        assert isinstance(create_reranker(), BM25Reranker)

    def test_mode_api_返回ApiReranker(self):
        """场景：mode=api → ApiReranker（百炼 gte-rerank，key 复用 EMBEDDING_API_KEY）"""
        settings.RERANK_ENABLED = True
        settings.RERANK_MODE = "api"

        assert isinstance(create_reranker(), ApiReranker)

    def test_未知模式_返回Noop(self):
        """场景：未知 mode → 降级 Noop"""
        settings.RERANK_ENABLED = True
        settings.RERANK_MODE = "unknown"

        assert isinstance(create_reranker(), NoopReranker)
