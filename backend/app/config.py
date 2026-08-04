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
    RETRIEVAL_SCORE_THRESHOLD: float = 0.4
    CHAT_HISTORY_WINDOW: int = 10

    # === 文件上传 ===
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: str = "txt,md,pdf,docx,csv,xlsx"

    # === CORS ===
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

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
