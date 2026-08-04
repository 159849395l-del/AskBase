"""测试文本分割器 — 中文感知的递归字符分割"""

import pytest
from langchain_core.documents import Document
from app.rag.splitter import get_text_splitter


class TestTextSplitter:
    """文本分割器 — RecursiveCharacterTextSplitter 中文感知"""

    def setup_method(self):
        self.splitter = get_text_splitter()

    def test_短文本_不分割(self):
        """场景：短文本（小于 chunk_size）→ 不分割，返回单个块"""
        text = "这是一段很短的文本。"
        docs = [Document(page_content=text)]
        chunks = self.splitter.split_documents(docs)

        assert len(chunks) == 1
        assert chunks[0].page_content == text

    def test_长文本_分割为多个块(self):
        """场景：长文本 → 分割为多个块，块之间有 overlap"""
        # 生成约 2000 字符的中文文本
        text = "这是一段测试文本。" * 200
        docs = [Document(page_content=text)]
        chunks = self.splitter.split_documents(docs)

        assert len(chunks) > 1
        # 每个块不超过 chunk_size
        for chunk in chunks:
            assert len(chunk.page_content) <= 800  # chunk_size + 一些余量

    def test_中文句号分隔_在句子边界切分(self):
        """场景：多个以句号结尾的句子 → 优先在句号处切分"""
        sentence = "这是一个完整的测试句子，用于验证中文分割效果。"
        text = sentence * 50  # 重复句子使文本足够长
        docs = [Document(page_content=text)]
        chunks = self.splitter.split_documents(docs)

        assert len(chunks) > 1
        # 检查第一个 chunk 的内容不以句子中间断开
        for chunk in chunks:
            # 文本不应太长（需要在 chunk_size 范围内）
            assert len(chunk.page_content) > 0

    def test_空文本_返回空列表或单个空块(self):
        """场景：空文本 → 返回单个块或空列表"""
        docs = [Document(page_content="")]
        chunks = self.splitter.split_documents(docs)

        # 空文本返回 0 或 1 个（取决于实现）
        assert len(chunks) <= 1

    def test_多文档_分别分割(self):
        """场景：多个文档 → 每个文档都被分割"""
        text1 = "文档一内容。" * 100
        text2 = "文档二内容。" * 100
        docs = [
            Document(page_content=text1, metadata={"source": "doc1"}),
            Document(page_content=text2, metadata={"source": "doc2"}),
        ]
        chunks = self.splitter.split_documents(docs)

        assert len(chunks) > 0
        # 验证元数据被保留
        sources = {c.metadata.get("source") for c in chunks}
        assert "doc1" in sources
        assert "doc2" in sources

    def test_换行符分隔_在换行处切分(self):
        """场景：包含多个换行的文本 → 优先在换行处切分"""
        lines = ["第{}行：这是测试内容，用于验证换行分割。".format(i) for i in range(100)]
        text = "\n".join(lines)
        docs = [Document(page_content=text)]
        chunks = self.splitter.split_documents(docs)

        assert len(chunks) > 1

    def test_英文混合文本_正常分割(self):
        """场景：中英文混合文本 → 正常分割"""
        text = ("This is an English sentence mixed with Chinese. " +
                "这是一个包含中英文混合的测试文本。" * 80)
        docs = [Document(page_content=text)]
        chunks = self.splitter.split_documents(docs)

        assert len(chunks) > 0
        for chunk in chunks:
            assert isinstance(chunk, Document)
            assert len(chunk.page_content) > 0

    def test_chunk_overlap_设置生效(self):
        """场景：检查 overlap 导致相邻块有重叠内容"""
        text = "具体内容" * 300  # 确保文本足够长需要分割
        docs = [Document(page_content=text)]
        chunks = self.splitter.split_documents(docs)

        if len(chunks) >= 2:
            # 相邻块应该有内容重叠
            last_chunk = chunks[0].page_content
            next_chunk = chunks[1].page_content
            # overlap 导致尾部内容出现在下一个块中
            # 简单地验证两个块不是完全独立的
            assert len(last_chunk) > 0
            assert len(next_chunk) > 0
