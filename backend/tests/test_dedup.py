"""测试摄入去重 — _dedup_chunks 纯函数（离线，不连网不 mock）"""

from langchain_core.documents import Document
from app.services.rag_service import _dedup_chunks, _compute_chunk_hash


def _make_chunk(text, chunk_hash=None):
    """构造带 chunk_hash 元数据的分块"""
    metadata = {"chunk_hash": chunk_hash} if chunk_hash is not None else {}
    return Document(page_content=text, metadata=metadata)


class TestDedupChunks:
    """摄入去重 — 按 chunk_hash 过滤已存在块"""

    def test_未命中_全部保留(self):
        """场景：existing_hashes 为空 → 所有块保留，跳过 0 个"""
        chunks = [
            _make_chunk("文本A", _compute_chunk_hash("文本A")),
            _make_chunk("文本B", _compute_chunk_hash("文本B")),
        ]
        kept, skipped = _dedup_chunks(chunks, set())

        assert skipped == 0
        assert len(kept) == 2
        assert kept == chunks  # 顺序不变

    def test_全命中_全部跳过(self):
        """场景：所有块哈希都已存在 → 全部跳过，保留为空"""
        hash_a = _compute_chunk_hash("文本A")
        chunks = [_make_chunk("文本A", hash_a)]
        kept, skipped = _dedup_chunks(chunks, {hash_a})

        assert skipped == 1
        assert kept == []

    def test_部分命中_只保留新块(self):
        """场景：部分块已存在 → 只保留新块，跳过已存在的"""
        hash_a = _compute_chunk_hash("文本A")
        hash_b = _compute_chunk_hash("文本B")
        hash_c = _compute_chunk_hash("文本C")
        chunks = [
            _make_chunk("文本A", hash_a),
            _make_chunk("文本B", hash_b),
            _make_chunk("文本C", hash_c),
        ]
        kept, skipped = _dedup_chunks(chunks, {hash_a, hash_c})

        assert skipped == 2
        assert len(kept) == 1
        assert kept[0].page_content == "文本B"

    def test_空chunks_返回空(self):
        """场景：chunks 为空列表 → 返回空列表和 0"""
        kept, skipped = _dedup_chunks([], {"a"})

        assert kept == []
        assert skipped == 0

    def test_同哈希同文本_被去重(self):
        """场景：两个相同文本块（相同 hash）→ 第二个被跳过"""
        hash_x = _compute_chunk_hash("相同文本")
        chunks = [
            _make_chunk("相同文本", hash_x),
            _make_chunk("相同文本", hash_x),
        ]
        kept, skipped = _dedup_chunks(chunks, {hash_x})

        assert skipped == 2
        assert kept == []

    def test_同文本不同hash_不误杀(self):
        """场景：同文本但 metadata 中 hash 值不同 → 按 hash 直接比较，两者都保留"""
        chunks = [
            _make_chunk("相同文本", "hash-old"),
            _make_chunk("相同文本", "hash-new"),
        ]
        kept, skipped = _dedup_chunks(chunks, {"hash-old"})

        assert skipped == 1
        assert len(kept) == 1
        assert kept[0].metadata["chunk_hash"] == "hash-new"

    def test_缺chunk_hash元数据_视为保留不报错(self):
        """场景：块没有 chunk_hash 元数据 → 不报错，按保留处理（宁多勿漏）"""
        chunks = [
            _make_chunk("无哈希块"),
            _make_chunk("正常块", _compute_chunk_hash("正常块")),
        ]
        kept, skipped = _dedup_chunks(chunks, {_compute_chunk_hash("正常块")})

        assert skipped == 1
        assert len(kept) == 1
        assert kept[0].page_content == "无哈希块"

    def test_缺hash且全库为空_全部保留(self):
        """场景：chunks 缺 hash 且 existing_hashes 为空 → 全部保留，跳过 0"""
        chunks = [_make_chunk("无哈希块")]
        kept, skipped = _dedup_chunks(chunks, set())

        assert skipped == 0
        assert len(kept) == 1
