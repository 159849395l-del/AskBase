"""
爬虫模块 MySQL 连接配置 — 从 backend/.env 加载

本模块用 os.getenv 取值，因此依赖下方显式的 load_dotenv（原因见该处注释）。
"""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# app/config.py 的 pydantic-settings 读 .env 只填充 Settings 对象，不会写入
# os.environ，而本模块用 os.getenv 取值，因此必须显式加载一次。否则
# CRAWLER_DB_PASSWORD 为空，连 MySQL 直接报 Access denied (using password: NO)，
# 表现为爬虫任务列表接口 500。
# override=False：已存在的真实环境变量优先，不覆盖部署环境注入的配置。
_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(_ENV_PATH, override=False)

# 注意：改完 .env 必须重启后端才生效——settings 在进程启动时构造，
# 运行时不会重新读取（uvicorn --reload 只在 .py 文件变更时重启子进程）。


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
