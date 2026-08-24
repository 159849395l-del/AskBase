"""
应用配置管理 — 使用 pydantic-settings 从 .env 文件和环境变量加载配置
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
import os


class Settings(BaseSettings):
    """应用全局配置"""

    # === 应用 ===
    APP_NAME: str = "E-Commerce RAG Knowledge Base"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # === LLM（OpenAI 兼容端点，如 DeepSeek / 百炼） ===
    LLM_API_KEY: str = ""
    LLM_API_BASE: str = "https://api.deepseek.com"
    LLM_MODEL: str = "deepseek-chat"
    LLM_TEMPERATURE: float = 0.3

    # === Embedding（OpenAI 兼容端点，如百炼 / 硅基流动） ===
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_API_BASE: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    EMBEDDING_MODEL: str = "text-embedding-v3"

    # === 数据库 ===
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/app.db"

    # === JWT ===
    JWT_SECRET: str = "change-this-to-a-random-string-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440  # 24小时

    # === ChromaDB ===
    CHROMA_PERSIST_DIR: str = "./data/chromadb"
    CHROMA_COLLECTION_NAME: str = "ecommerce_kb"

    # === RAG 参数 ===
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 100
    RETRIEVAL_TOP_K: int = 5
    # 向量路相似度阈值：混合检索（BM25 兜底精确匹配）下放宽到 0.3 提升召回，
    # 口语化短查询（如"衣服怎么洗"）更易命中，无关查询仍有 BM25 门槛兜底
    RETRIEVAL_SCORE_THRESHOLD: float = 0.3
    CHAT_HISTORY_WINDOW: int = 10

    # === 检索优化（混合检索 / 重排 / 改写 / 缓存） ===
    HYBRID_ENABLED: bool = True        # BM25 + 向量混合检索（RRF 融合）
    HYBRID_RRF_K: int = 60             # RRF 融合常数 k
    BM25_TOP_K: int = 5                # BM25 路召回数
    BM25_TOKENIZER: str = "jieba"      # 中文分词: "jieba" | "char_bigram"（jieba 缺失时的零依赖降级）
    RERANK_ENABLED: bool = False       # 重排开关
    RERANK_MODE: str = "bm25"          # "none" | "bm25" | "api"（api 仅占位，暂未实现）
    RERANK_TOP_N: int = 10             # 重排输入候选数（召回量）
    RERANK_OUTPUT_K: int = 5           # 重排输出数
    RERANK_MODEL: str = "gte-rerank-v2" # API 重排模型（百炼）
    QUERY_REWRITE_ENABLED: bool = False  # 查询改写（结合历史消解指代，多一次 LLM 调用）
    CACHE_ENABLED: bool = False        # 检索结果缓存
    CACHE_TTL: int = 300               # 缓存秒数
    CACHE_MAX_ENTRIES: int = 256

    # === 文件上传 ===
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: str = "txt,md,pdf,docx,csv,xlsx"

    # === CORS ===
    CORS_ORIGINS: str = "http://localhost:5175,http://localhost:3000"

    # === Admin 种子数据 ===
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "123456"

    @property
    def allowed_extensions_list(self) -> List[str]:
        return [ext.strip() for ext in self.ALLOWED_EXTENSIONS.split(",")]

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# 全局单例
settings = Settings()
