"""
BM25 索引 — ChromaDB 文档全量离线索引，供混合检索（RRF 融合）使用
"""

from typing import List, Optional, Tuple

from langchain_core.documents import Document

from app.config import settings
from app.rag.tokenizer import get_tokenizer
from app.rag.vector_store import get_vectorstore

# rank_bm25 可选依赖：缺失时 search 抛 ImportError，由调用方捕获降级
try:
    from rank_bm25 import BM25Plus
except ImportError:
    BM25Plus = None


class BM25Index:
    """BM25 索引：文档列表 + rank_bm25.BM25Plus 实例（可为 None）

    用 BM25Plus 而非 BM25Okapi：Okapi 的 idf = log((N-df+.5)/(df+.5))，
    小语料（df ≈ N/2）时 idf 归零或为负，导致"洗"这类单字命中得 0 分、
    检索完全失效；BM25Plus 的 idf = log((N+1)/df) 恒为正，小语料不塌缩。
    """

    def __init__(self):
        self._docs: List[Document] = []
        self._bm25: Optional[BM25Plus] = None

    def build_from_documents(self, docs: List[Document]) -> None:
        """离线构造索引（供测试与显式重建使用）"""
        self._docs = list(docs)
        if not self._docs:
            self._bm25 = None
            return
        tokenizer = get_tokenizer()
        corpus = [tokenizer(doc.page_content) for doc in self._docs]
        self._bm25 = BM25Plus(corpus)

    def _load_from_chromadb(self) -> None:
        """从 ChromaDB 全量加载文档并重建索引（metadata 原样保留）"""
        collection = get_vectorstore()._collection
        data = collection.get(include=["documents", "metadatas"])
        documents = data.get("documents") or []
        metadatas = data.get("metadatas") or []
        docs = [
            Document(page_content=content, metadata=metadata or {})
            for content, metadata in zip(documents, metadatas)
        ]
        self.build_from_documents(docs)

    def search(
        self,
        query: str,
        top_k: int,
        kb_doc_ids: Optional[List[int]] = None,
        kb_ids: Optional[List[int]] = None,
    ) -> List[Tuple[Document, float]]:
        """BM25 检索：先全量打分，再按作用域(kb_doc_ids / kb_ids)过滤，最后取 top_k

        - kb_ids 非空：按 metadata.kb_id 过滤（知识库维度）
        - 否则 kb_doc_ids 非空：按 metadata.kb_doc_id 过滤（文档维度，旧兼容）
        - 两者都为空：不过滤，等价于全库检索
        """
        if BM25Plus is None:
            raise ImportError("rank_bm25 未安装，无法执行 BM25 检索")
        if self._bm25 is None:
            # 空语料 / 尚未构建
            return []

        allowed_kb = set(int(x) for x in kb_ids) if kb_ids else None
        allowed_doc = set(int(x) for x in kb_doc_ids) if kb_doc_ids else None
        tokenizer = get_tokenizer()
        tokens = tokenizer(query)
        scores = self._bm25.get_scores(tokens)

        scored = []
        for i, (doc, score) in enumerate(zip(self._docs, scores)):
            meta = doc.metadata
            if allowed_kb is not None and meta.get("kb_id") not in allowed_kb:
                continue
            if allowed_kb is None and allowed_doc is not None and meta.get("kb_doc_id") not in allowed_doc:
                continue
            if not self._is_real_hit(tokens, i, len(query)):
                continue
            scored.append((doc, score))

        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:top_k]

    def _is_real_hit(self, tokens: list, doc_idx: int, query_len: int) -> bool:
        """判断第 doc_idx 篇文档对查询是否为"真实命中"

        注意：不能用 BM25Plus 分数判断命中——Plus 变体对"不含查询词的文档"
        也有 idf×delta 的正底分（平滑设计），分数 > 0 不代表词真在文档里。
        这里基于词频（doc_freqs）判断。

        门槛规则（配合 tokenizer 的 CJK 单字补充）：
        - 命中词（长度≥2）≥ 1 个 → 真实命中（如"华为"、"续航"匹配）
        - 短查询（≤6 字，口语化）且命中单字 ≥ 2 个 → 真实命中
          （如"衣服怎么洗"的"洗"+"服"——口语短句的实义靠单字承载）
        - 长查询的单字重叠多为巧合（如"量子色动力学"的"色"撞上"颜色"），
          不构成真实命中，避免无关查询靠单字噪声放行、空结果兜底永不触发
        """
        doc_freqs = self._bm25.doc_freqs[doc_idx]  # type: ignore[union-attr]
        hit_multi = 0
        hit_single = 0
        for token in tokens:
            if doc_freqs.get(token, 0) <= 0:
                continue
            if len(token) >= 2:
                hit_multi += 1
            else:
                hit_single += 1
        if hit_multi >= 1:
            return True
        return query_len <= 6 and hit_single >= 2

    def invalidate(self) -> None:
        """清空索引（下次构建时重建）"""
        self._docs = []
        self._bm25 = None


# 模块级单例（懒加载）
_bm25_index: Optional[BM25Index] = None


def get_bm25_index() -> BM25Index:
    """获取 BM25 索引单例（首次调用时从 ChromaDB 全量构建，构建失败向上抛异常）"""
    global _bm25_index
    if _bm25_index is None:
        index = BM25Index()
        index._load_from_chromadb()
        _bm25_index = index
    return _bm25_index


def invalidate_bm25_index() -> None:
    """使 BM25 索引失效（知识库文档增删后调用，下次检索时自动重建）"""
    global _bm25_index
    if _bm25_index is not None:
        _bm25_index.invalidate()
    _bm25_index = None
