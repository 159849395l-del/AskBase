"""测试 BM25 索引 — 离线构建、检索、分类过滤、失效与重建"""

import pytest
from langchain_core.documents import Document

from app.rag.bm25_index import BM25Index, invalidate_bm25_index


def _build_docs():
    """构造测试语料（3 篇文档，2 个知识库 kb）"""
    return [
        Document(
            page_content="这款手机电池续航很长，支持快充",
            metadata={"kb_id": 1, "kb_doc_id": 1, "filename": "phone.md", "chunk_index": 0},
        ),
        Document(
            page_content="这款笔记本电脑重量很轻，适合携带",
            metadata={"kb_id": 1, "kb_doc_id": 2, "filename": "laptop.md", "chunk_index": 0},
        ),
        Document(
            page_content="这件纯棉T恤透气舒适，适合夏天",
            metadata={"kb_id": 2, "kb_doc_id": 3, "filename": "tshirt.md", "chunk_index": 0},
        ),
    ]


class TestBM25Index:
    """BM25 索引 — build_from_documents + search"""

    def setup_method(self):
        self.index = BM25Index()

    def test_构建后检索_含查询词的文档排前(self):
        """场景：离线构建后检索 → 同时含"手机""电池"的文档排第一且分数>0"""
        self.index.build_from_documents(_build_docs())

        results = self.index.search("手机电池", top_k=5)

        # 仅 phone.md 与查询有真实词重叠；其余文档 score=0 被分数门槛过滤
        assert len(results) == 1
        top_doc, top_score = results[0]
        assert "手机" in top_doc.page_content
        assert "电池" in top_doc.page_content
        assert top_score > 0

    def test_top_k_截断(self):
        """场景：指定 top_k → 只返回前 k 条"""
        self.index.build_from_documents(_build_docs())

        results = self.index.search("手机电池", top_k=1)

        assert len(results) == 1
        assert "手机" in results[0][0].page_content

    def test_按kb过滤_只返回该知识库(self):
        """场景：限定 kb_ids → 仅返回该知识库中与查询有词重叠的文档"""
        self.index.build_from_documents(_build_docs())

        # 注意：jieba 会把"手机电池"合并为单 token，查询须用文档内的真实词
        results = self.index.search("手机电池", top_k=5, kb_ids=[1])

        # kb1 含 phone+laptop；laptop 无词重叠（score=0）被门槛过滤，仅 phone 命中
        assert len(results) == 1
        for doc, _ in results:
            assert doc.metadata["kb_id"] == 1

    def test_过滤后不足k_返回全部命中(self):
        """场景：过滤后命中不足 top_k → 返回过滤后的全部（不补无关文档）"""
        self.index.build_from_documents(_build_docs())

        results = self.index.search("T恤", top_k=5, kb_ids=[2])

        assert len(results) == 1
        assert results[0][0].metadata["filename"] == "tshirt.md"

    def test_空语料_返回空列表(self):
        """场景：空语料 → 检索返回空"""
        self.index.build_from_documents([])

        assert self.index.search("手机", top_k=5) == []

    def test_完全无关查询_返回空(self):
        """场景：与语料无任何词重叠的查询 → 返回空（防止混合检索下兜底永不触发）"""
        self.index.build_from_documents(_build_docs())

        results = self.index.search("量子色动力学色荷", top_k=5)

        assert results == []

    def test_单字噪声_不视为命中(self):
        """场景：仅 1 个单字重叠（查询"子"撞上"笔记本电脑"的"子"）→ 过滤，防止无关查询放行"""
        self.index.build_from_documents(_build_docs())

        results = self.index.search("子", top_k=5)

        assert results == []

    def test_单字组合命中_视为真实命中(self):
        """场景：口语短查询"衣服怎么洗"与"服装/洗涤/干洗"仅"服"+"洗"两字重叠 → 命中

        这是补 CJK 单字 token 的意义：词面不重叠但单字重叠即可召回，
        解决"洗"匹配不到"洗涤/干洗"的口语化召回问题。
        """
        self.index.build_from_documents([
            Document(page_content="服装产品，洗涤方式建议干洗，不可漂白",
                     metadata={"filename": "care.md", "chunk_index": 0}),
            Document(page_content="量子力学是物理学的一个分支",
                     metadata={"filename": "physics.md", "chunk_index": 0}),
        ])

        results = self.index.search("衣服怎么洗", top_k=5)

        assert len(results) == 1
        assert results[0][0].metadata["filename"] == "care.md"
        assert results[0][1] > 0

    def test_长查询单字重叠_视为巧合(self):
        """场景：长查询"量子色动力学中的色荷"单字"色"撞上文档"颜色" → 不命中

        长查询字词丰富，单字重叠大概率是巧合；若放行会导致
        "量子色动力学"这类无关问题也拉回来源、空结果兜底永不触发。
        """
        self.index.build_from_documents([
            Document(page_content="这件衣服颜色是藏青色，适合夏天",
                     metadata={"filename": "clothing.md", "chunk_index": 0}),
        ])

        results = self.index.search("量子色动力学中的色荷是什么", top_k=5)

        assert results == []

    def test_invalidate_后检索为空_可重建(self):
        """场景：invalidate 清空 → 检索为空；重新 build → 可再次检索"""
        self.index.build_from_documents(_build_docs())
        assert len(self.index.search("手机电池", top_k=5)) > 0

        self.index.invalidate()
        assert self.index.search("手机电池", top_k=5) == []

        self.index.build_from_documents(_build_docs())
        assert len(self.index.search("手机电池", top_k=5)) > 0

    def test_元数据_原样保留(self):
        """场景：检索命中 → metadata 与构造时一致"""
        self.index.build_from_documents(_build_docs())

        doc, _ = self.index.search("手机电池", top_k=1)[0]

        assert doc.metadata["filename"] == "phone.md"
        assert doc.metadata["chunk_index"] == 0
        assert doc.metadata["kb_id"] == 1
        assert doc.metadata["kb_doc_id"] == 1


class TestInvalidateBM25Index:
    """模块级失效函数 — invalidate_bm25_index"""

    def test_可调用且清空单例(self):
        """场景：调用失效函数 → 清空全局单例，不抛异常"""
        invalidate_bm25_index()
        assert True
