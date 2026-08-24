"""智能体模型：管理员配置的专属 AI 助手"""

from sqlalchemy import String, Integer, Boolean, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from typing import List, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.knowledge_document import KnowledgeDocument
    from app.models.conversation import Conversation


def _now() -> str:
    return datetime.now().isoformat()


class Agent(Base):
    """智能体：每个智能体有自己的系统提示词、欢迎语、关联知识库"""

    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    icon: Mapped[str] = mapped_column(String(50), nullable=False, default="🤖")
    welcome_message: Mapped[str] = mapped_column(Text, nullable=False, default="您好，我是您的专属AI助手，请问有什么可以帮助您呢？")
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="对用户隐藏（管理员仍可见/可编辑）")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[str] = mapped_column(String(30), nullable=False, default=_now)
    updated_at: Mapped[str] = mapped_column(String(30), nullable=False, default=_now, onupdate=_now)

    # 关系：创建者、关联的知识文档（多对多）、关联的会话
    creator: Mapped["User"] = relationship("User", back_populates="agents")
    knowledge_documents: Mapped[List["KnowledgeDocument"]] = relationship(
        "KnowledgeDocument",
        secondary="agent_knowledge_bases",
        back_populates="agents",
    )
    conversations: Mapped[List["Conversation"]] = relationship(
        "Conversation", back_populates="agent"
    )

    def __repr__(self) -> str:
        return f"<Agent(id={self.id}, name='{self.name}')>"


class AgentKnowledgeBase(Base):
    """智能体 ↔ 知识文档 关联表（多对多）"""

    __tablename__ = "agent_knowledge_bases"

    agent_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True
    )
    kb_doc_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("knowledge_documents.id", ondelete="CASCADE"), primary_key=True
    )