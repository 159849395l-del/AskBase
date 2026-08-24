"""知识文档模型 — 追踪知识库中已上传的文档"""

from sqlalchemy import String, Integer, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from typing import Optional, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.agent import Agent


def _now() -> str:
    return datetime.now().isoformat()


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)  # txt, pdf, csv, md, docx, xlsx
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)  # bytes
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="processing"
    )  # "processing" | "indexed" | "failed"
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    uploaded_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[str] = mapped_column(
        String(30), nullable=False, default=_now
    )

    # 关系
    uploader: Mapped["User"] = relationship("User", back_populates="knowledge_documents")
    agents: Mapped[list] = relationship(
        "Agent", secondary="agent_knowledge_bases", back_populates="knowledge_documents"
    )

    def __repr__(self) -> str:
        return f"<KnowledgeDocument(id={self.id}, filename='{self.filename}', status='{self.status}')>"
