"""知识库模型 — 两种类型：

- document（A 类·文档型）：无数据源，包含文档集 + 问答集
- database（B 类·数据库型）：绑定数据源 + 库名，包含表信息 + 知识点

同一 data_source_id + database_name 联合唯一（同一数据库不能重复建 KB）。
A 类 KB 两字段均为 NULL，SQLite 唯一索引允许多个 NULL 行共存，可建多个。
"""

from sqlalchemy import String, Integer, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from datetime import datetime
from typing import Optional


def _now() -> str:
    return datetime.now().isoformat()


class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"
    __table_args__ = (
        UniqueConstraint("data_source_id", "database_name", name="uq_kb_data_source_db"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="知识库名称")
    label: Mapped[str] = mapped_column(String(50), nullable=False, default="", comment="标签")
    authorized_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, comment="授权用户（可选）"
    )
    type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="document", comment="document(文档型) | database(数据库型)"
    )
    data_source_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("data_sources.id"), nullable=True, comment="绑定数据源（B 类必填）"
    )
    database_name: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="库名（B 类必填，可覆盖数据源默认库名）"
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="描述")
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[str] = mapped_column(String(30), nullable=False, default=_now)
    updated_at: Mapped[str] = mapped_column(String(30), nullable=False, default=_now, onupdate=_now)

    def __repr__(self) -> str:
        return f"<KnowledgeBase(id={self.id}, name='{self.name}', type='{self.type}')>"
