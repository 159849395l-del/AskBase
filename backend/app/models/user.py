"""用户模型"""

from sqlalchemy import String, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from typing import List, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.knowledge_document import KnowledgeDocument


def _now() -> str:
    return datetime.now().isoformat()


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(10), nullable=False, default="user")  # "admin" | "user"
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[str] = mapped_column(
        String(30), nullable=False, default=_now
    )
    updated_at: Mapped[str] = mapped_column(
        String(30), nullable=False, default=_now, onupdate=_now
    )

    # 关系
    conversations: Mapped[List["Conversation"]] = relationship(
        "Conversation", back_populates="user", cascade="all, delete-orphan"
    )
    knowledge_documents: Mapped[List["KnowledgeDocument"]] = relationship(
        "KnowledgeDocument", back_populates="uploader", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', role='{self.role}')>"
