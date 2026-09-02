"""测试配置模块 — 验证所有配置项正确加载"""

import pytest
import os
from app.config import Settings, settings


class TestSettings:
    """配置管理 — 环境变量和默认值"""

    def test_默认值_正确设置(self):
        """场景：检查关键默认配置项（不读 .env，验证代码默认值）"""
        defaults = Settings(_env_file=None)
        assert defaults.APP_NAME == "E-Commerce RAG Knowledge Base"
        assert defaults.LLM_MODEL == "deepseek-chat"
        assert defaults.EMBEDDING_MODEL == "text-embedding-v3"
        assert defaults.LLM_TEMPERATURE == 0.3
        assert defaults.CHUNK_SIZE == 800
        assert defaults.CHUNK_OVERLAP == 100
        assert defaults.RETRIEVAL_TOP_K == 5
        assert defaults.RETRIEVAL_SCORE_THRESHOLD == 0.3  # 混合检索下放宽以提升召回
        assert defaults.CHAT_HISTORY_WINDOW == 10
        assert defaults.MAX_UPLOAD_SIZE_MB == 50
        assert defaults.JWT_ALGORITHM == "HS256"
        assert defaults.JWT_EXPIRE_MINUTES == 1440
        # 检索优化
        assert defaults.HYBRID_ENABLED is True
        assert defaults.HYBRID_RRF_K == 60
        assert defaults.BM25_TOP_K == 5
        assert defaults.BM25_TOKENIZER == "jieba"
        assert defaults.RERANK_ENABLED is False
        assert defaults.RERANK_MODE == "bm25"
        assert defaults.RERANK_TOP_N == 10
        assert defaults.RERANK_OUTPUT_K == 5
        assert defaults.QUERY_REWRITE_ENABLED is False
        assert defaults.CACHE_ENABLED is False
        assert defaults.CACHE_TTL == 300
        assert defaults.CACHE_MAX_ENTRIES == 256

    def test_管理员种子数据_配置正确(self):
        """场景：管理员用户名和密码已配置"""
        assert settings.ADMIN_USERNAME == "admin"
        assert settings.ADMIN_PASSWORD == "123456"

    def test_LLM_API_Key_已配置(self):
        """场景：LLM API Key 不为空"""
        assert settings.LLM_API_KEY != ""
        assert len(settings.LLM_API_KEY) > 10
        assert settings.LLM_API_KEY.startswith("sk-")

    def test_Embedding_API_Key_已配置(self):
        """场景：Embedding API Key 不为空"""
        assert settings.EMBEDDING_API_KEY != ""
        assert len(settings.EMBEDDING_API_KEY) > 10
        assert settings.EMBEDDING_API_KEY.startswith("sk-")

    def test_允许的文件扩展名_解析正确(self):
        """场景：ALLOWED_EXTENSIONS 正确解析为列表"""
        extensions = settings.allowed_extensions_list
        assert "txt" in extensions
        assert "md" in extensions
        assert "pdf" in extensions
        assert "docx" in extensions
        assert "csv" in extensions
        assert "xlsx" in extensions
        assert len(extensions) == 6

    def test_CORS_来源_解析正确(self):
        """场景：CORS_ORIGINS 正确解析为列表"""
        origins = settings.cors_origins_list
        assert "http://localhost:5175" in origins
        assert len(origins) >= 1

    def test_数据库URL_配置正确(self):
        """场景：DATABASE_URL 指向 SQLite"""
        assert "sqlite" in settings.DATABASE_URL
        assert "aiosqlite" in settings.DATABASE_URL

    def test_ChromaDB_配置正确(self):
        """场景：ChromaDB 持久化目录和集合名配置正确"""
        assert settings.CHROMA_PERSIST_DIR == "./data/chromadb"
        assert settings.CHROMA_COLLECTION_NAME == "ecommerce_kb"
