"""测试 RAG Chain 组件 — 提示模板、文档格式化、检索器、空结果兜底"""

import pytest
from langchain_core.documents import Document
from app.rag.chain import (
    format_docs_with_sources,
    SYSTEM_PROMPT,
    build_no_result_events,
    NO_RESULT_MESSAGE,
)


class TestFormatDocs:
    """文档格式化 — format_docs_with_sources"""

    def test_单个文档_格式化正确(self):
        """场景：单个文档 → 返回带来源标记的上下文和来源列表"""
        doc = Document(
            page_content="电池续航约14小时",
            metadata={"filename": "electronics.md", "chunk_index": 3},
        )
        score = 0.92

        context, sources = format_docs_with_sources([(doc, score)])

        assert "[来源1: electronics.md]" in context
        assert "电池续航约14小时" in context
        assert len(sources) == 1
        assert sources[0]["filename"] == "electronics.md"
        assert sources[0]["similarity_score"] == 0.92
        assert sources[0]["chunk_index"] == 3

    def test_多个文档_全部编号和排序(self):
        """场景：多个文档 → 每个都有独立的来源编号"""
        docs = [
            (Document(page_content="内容A", metadata={"filename": "file_a.md", "chunk_index": 0}), 0.95),
            (Document(page_content="内容B", metadata={"filename": "file_b.md", "chunk_index": 1}), 0.85),
            (Document(page_content="内容C", metadata={"filename": "file_c.md", "chunk_index": 2}), 0.75),
        ]

        context, sources = format_docs_with_sources(docs)

        assert "[来源1: file_a.md]" in context
        assert "[来源2: file_b.md]" in context
        assert "[来源3: file_c.md]" in context
        assert len(sources) == 3
        assert sources[0]["similarity_score"] == 0.95
        assert sources[2]["similarity_score"] == 0.75

    def test_空文档列表_返回空字符串和空列表(self):
        """场景：空文档列表 → 返回空上下文和空来源"""
        context, sources = format_docs_with_sources([])

        assert context == ""
        assert sources == []

    def test_来源文本预览_截断正确(self):
        """场景：chunk 文本超过 300 字 → 预览截断到 300 字"""
        long_text = "A" * 500
        doc = Document(
            page_content=long_text,
            metadata={"filename": "test.md", "chunk_index": 0},
        )

        _, sources = format_docs_with_sources([(doc, 0.9)])

        assert len(sources[0]["chunk_text"]) == 300  # 预览截断到 300

    def test_相似度分数_保留4位小数(self):
        """场景：浮点相似度分数 → 四舍五入到4位"""
        doc = Document(page_content="test", metadata={"filename": "test.md", "chunk_index": 0})

        _, sources = format_docs_with_sources([(doc, 0.12345678)])

        assert sources[0]["similarity_score"] == 0.1235

    def test_缺少元数据_使用默认值(self):
        """场景：文档缺少部分元数据 → 使用默认值填充"""
        doc = Document(page_content="test content", metadata={})

        _, sources = format_docs_with_sources([(doc, 0.8)])

        assert sources[0]["filename"] == "未知文件"
        assert sources[0]["chunk_index"] == 0
        assert sources[0]["score_type"] == "vector"


class TestSystemPrompt:
    """系统提示词 — 知识库问答助手"""

    def test_系统提示词_包含关键规则(self):
        """场景：提示词包含所有关键约束规则"""
        assert "知识库问答助手" in SYSTEM_PROMPT
        assert "参考文档" in SYSTEM_PROMPT
        assert "无法找到相关信息" in SYSTEM_PROMPT
        assert "引用来源" in SYSTEM_PROMPT
        assert "中文回答" in SYSTEM_PROMPT
        assert "表格形式" in SYSTEM_PROMPT
        assert "{context}" in SYSTEM_PROMPT  # 模板占位符

    def test_提示词_限制不编造信息(self):
        """场景：提示词明确要求不编造信息"""
        assert "不要使用外部知识" in SYSTEM_PROMPT or "不要编造" in SYSTEM_PROMPT


class TestNoResultEvents:
    """空结果兜底 — build_no_result_events"""

    def test_三个事件_顺序为no_results_token_done(self):
        """场景：空检索结果 → 依次产出 no_results、token、done 三个事件"""
        events = build_no_result_events()

        assert len(events) == 3
        assert [e["type"] for e in events] == ["no_results", "token", "done"]

    def test_事件载荷_携带统一提示消息(self):
        """场景：三个事件的载荷均为 NO_RESULT_MESSAGE"""
        events = build_no_result_events()

        assert events[0]["message"] == NO_RESULT_MESSAGE
        assert events[1]["content"] == NO_RESULT_MESSAGE
        assert events[2]["full_response"] == NO_RESULT_MESSAGE

    def test_空结果消息_为固定提示文案(self):
        """场景：空结果提示为固定中文文案"""
        assert "未找到相关资料" in NO_RESULT_MESSAGE
        assert NO_RESULT_MESSAGE == "知识库中未找到相关资料，请尝试更换关键词或咨询管理员。"
