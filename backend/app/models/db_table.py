"""表信息模型（B 类·数据库型知识库）— 一张表对应源库中的一张真实表

字段描述（field_comment）默认从源库 COLUMN_COMMENT 拉取，管理员可人工修改；
源库字段被删除时，本地字段标记 status=conflict 提示管理员处理（不自动删）。
"""

from sqlalchemy import String, Integer, Boolean, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from datetime import datetime


def _now() -> str:
    return datetime.now().isoformat()


class DBTable(Base):
    __tablename__ = "db_tables"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    kb_id: Mapped[int] = mapped_column(Integer, ForeignKey("knowledge_bases.id"), nullable=False)
    table_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="表名")
    table_comment: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="表描述（默认源库注释，可改）")
    column_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="列数")
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="必选开关（加入 SQL 生成范围）")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="normal", comment="normal | conflict（源库已消失）")
    created_at: Mapped[str] = mapped_column(String(30), nullable=False, default=_now)
    updated_at: Mapped[str] = mapped_column(String(30), nullable=False, default=_now, onupdate=_now)

    def __repr__(self) -> str:
        return f"<DBTable(id={self.id}, kb_id={self.kb_id}, table='{self.table_name}')>"


class DBTableField(Base):
    __tablename__ = "db_table_fields"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    db_table_id: Mapped[int] = mapped_column(Integer, ForeignKey("db_tables.id"), nullable=False)
    field_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="字段名")
    field_type: Mapped[str] = mapped_column(String(100), nullable=False, default="", comment="字段类型")
    field_comment: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="字段描述（默认源库注释，可改）")
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="是否必带字段")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="normal", comment="normal | conflict（源库字段已消失）")
    deleted_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="软删除（管理员删除后保留历史）")
    created_at: Mapped[str] = mapped_column(String(30), nullable=False, default=_now)
    updated_at: Mapped[str] = mapped_column(String(30), nullable=False, default=_now, onupdate=_now)

    def __repr__(self) -> str:
        return f"<DBTableField(id={self.id}, field='{self.field_name}')>"


class DBKnowledgePoint(Base):
    """知识点（B 类·数据库型知识库）— 类似问答集，辅助 AI 理解库/表语义"""

    __tablename__ = "db_knowledge_points"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    kb_id: Mapped[int] = mapped_column(Integer, ForeignKey("knowledge_bases.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="名称")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="内容")
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[str] = mapped_column(String(30), nullable=False, default=_now)
    updated_at: Mapped[str] = mapped_column(String(30), nullable=False, default=_now, onupdate=_now)

    def __repr__(self) -> str:
        return f"<DBKnowledgePoint(id={self.id}, kb_id={self.kb_id}, name='{self.name[:30]}')>"
