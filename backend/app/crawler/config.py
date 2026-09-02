"""
爬虫模块 MySQL 连接配置 — 从 backend/.env 加载
"""
import os
from dataclasses import dataclass


@dataclass
class CrawlerDbConfig:
    """爬虫 MySQL 连接参数"""
    host: str = "127.0.0.1"
    port: int = 3306
    user: str = "root"
    password: str = ""  # 通过 CRAWLER_DB_PASSWORD 提供，勿硬编码
    database: str = "ai_crawl"

    @property
    def url(self) -> str:
        return f"mysql+pymysql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}?charset=utf8mb4"


def load_crawler_config() -> CrawlerDbConfig:
    """从环境变量加载爬虫 MySQL 配置"""
    return CrawlerDbConfig(
        host=os.getenv("CRAWLER_DB_HOST", "127.0.0.1"),
        port=int(os.getenv("CRAWLER_DB_PORT", "3306")),
        user=os.getenv("CRAWLER_DB_USER", "root"),
        password=os.getenv("CRAWLER_DB_PASSWORD", ""),
        database=os.getenv("CRAWLER_DB_NAME", "ai_crawl"),
    )


# 爬虫引擎参数
CRAWLER_CONCURRENCY = 8
CRAWLER_STATIC_TIMEOUT_MS = 15000
CRAWLER_RATE_LIMIT_MS = 500
CRAWLER_MAX_RETRIES = 3
CRAWLER_MAX_PAGES_DEFAULT = 100
CRAWLER_TEXT_CHUNK_LIMIT = 8000
