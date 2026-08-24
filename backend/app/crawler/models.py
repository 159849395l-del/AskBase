"""
爬虫模块数据模型 — 映射 MySQL ai_crawl 库的现有表结构
"""
import enum
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column, Integer, BigInteger, String, Text, JSON, DateTime,
    Boolean, Time, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.crawler.config import load_crawler_config


class Base(DeclarativeBase):
    pass


class TaskStatus(str, enum.Enum):
    PENDING = "PENDING"
    PLANNING = "PLANNING"
    DISCOVERING = "DISCOVERING"
    CRAWLING = "CRAWLING"
    EXTRACTING = "EXTRACTING"
    VERIFYING = "VERIFYING"
    AGGREGATING = "AGGREGATING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

    def is_terminal(self) -> bool:
        return self in (TaskStatus.COMPLETED, TaskStatus.PARTIAL, TaskStatus.FAILED, TaskStatus.CANCELLED)

    def is_running(self) -> bool:
        return not self.is_terminal() and self != TaskStatus.PENDING


class CrawlTask(Base):
    __tablename__ = "t_task"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_no: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    seed_urls: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    max_pages: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    max_depth: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    same_domain_only: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False, index=True)
    schema_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    plan_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    stats_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(3), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(3), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(3), default=datetime.now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(3), default=datetime.now, onupdate=datetime.now)


class UrlQueueItem(Base):
    __tablename__ = "t_url_queue"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("t_task.id"), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    url_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    depth: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    source: Mapped[str] = mapped_column(String(20), default="SEED", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False)
    crawl_mode: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    http_status: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    page_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    last_attempt_at: Mapped[Optional[datetime]] = mapped_column(DateTime(3), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(3), default=datetime.now)
    __table_args__ = (UniqueConstraint("task_id", "url_hash", name="uk_task_url"),)


class CrawlPage(Base):
    __tablename__ = "t_page"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("t_task.id"), nullable=False, index=True)
    url_queue_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("t_url_queue.id"), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    final_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    http_status: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    content_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    rendered_html: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    clean_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    charset: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    crawl_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    fetch_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    fetched_at: Mapped[Optional[datetime]] = mapped_column(DateTime(3), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(3), default=datetime.now)


class CrawlResult(Base):
    __tablename__ = "t_result"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("t_task.id"), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    page_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    data_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    record_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="VALID", nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    extracted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(3), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(3), default=datetime.now)


class AgentLog(Base):
    __tablename__ = "t_agent_log"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("t_task.id"), nullable=False, index=True)
    agent: Mapped[str] = mapped_column(String(20), nullable=False)
    stage: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    detail: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    cost_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(3), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(3), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(3), default=datetime.now)


class CrawlSchedule(Base):
    __tablename__ = "t_schedule"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("t_task.id"), nullable=False, unique=True)
    interval_days: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    run_time: Mapped[str] = mapped_column(String(10), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(3), nullable=True)
    last_status: Mapped[str] = mapped_column(String(20), default="NONE", nullable=False)
    last_detail: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(3), default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(3), default=datetime.now, onupdate=datetime.now)


class ExportRecord(Base):
    __tablename__ = "t_export_record"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("t_task.id"), nullable=False, index=True)
    format: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False)
    file_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    file_size: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    row_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(3), default=datetime.now)


_crawler_engine = None
_crawler_session_factory = None


def get_crawler_engine():
    global _crawler_engine
    if _crawler_engine is None:
        cfg = load_crawler_config()
        _crawler_engine = create_async_engine(
            cfg.url.replace("mysql+pymysql://", "mysql+aiomysql://"),
            pool_size=5, max_overflow=10, pool_pre_ping=False, echo=False,
        )
    return _crawler_engine


def get_crawler_session_factory():
    global _crawler_session_factory
    if _crawler_session_factory is None:
        _crawler_session_factory = async_sessionmaker(
            get_crawler_engine(), class_=AsyncSession, expire_on_commit=False,
        )
    return _crawler_session_factory


async def get_crawler_db():
    factory = get_crawler_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
