"""会话模型"""

from sqlalchemy import String, Integer, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from typing import List, Optional, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.message import Message
    from app.models.agent import Agent


def _now() -> str:
    return datetime.now().isoformat()


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("agents.id", ondelete="SET NULL"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="新对话")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[str] = mapped_column(
        String(30), nullable=False, default=_now
    )
    updated_at: Mapped[str] = mapped_column(
        String(30), nullable=False, default=_now, onupdate=_now
    )

    # 关系
    user: Mapped["User"] = relationship("User", back_populates="conversations")
    agent: Mapped[Optional["Agent"]] = relationship("Agent", back_populates="conversations")
    messages: Mapped[List["Message"]] = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Conversation(id={self.id}, title='{self.title}', agent_id={self.agent_id})>"