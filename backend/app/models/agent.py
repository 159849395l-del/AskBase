"""智能体模型：管理员配置的专属 AI 助手"""

from sqlalchemy import String, Integer, Boolean, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from typing import List, Optional, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.knowledge_document import KnowledgeDocument
    from app.models.knowledge_base import KnowledgeBase
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
    # 绑定的大模型（NULL = 使用系统默认模型 / .env 兜底）
    model_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("llm_models.id", ondelete="SET NULL"), nullable=True,
        comment="绑定的大模型 ID（NULL=系统默认）"
    )
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[str] = mapped_column(String(30), nullable=False, default=_now)
    updated_at: Mapped[str] = mapped_column(String(30), nullable=False, default=_now, onupdate=_now)

    # 关系：创建者、关联的知识库（多对多，粒度=知识库）、关联的会话
    creator: Mapped["User"] = relationship("User", back_populates="agents")
    knowledge_bases: Mapped[List["KnowledgeBase"]] = relationship(
        "KnowledgeBase",
        secondary="agent_kbs",
    )
    conversations: Mapped[List["Conversation"]] = relationship(
        "Conversation", back_populates="agent"
    )

    def __repr__(self) -> str:
        return f"<Agent(id={self.id}, name='{self.name}')>"


class AgentKnowledgeBase(Base):
    """智能体 ↔ 知识库 关联表（多对多，Phase 5 起使用；旧表 agent_knowledge_bases 保留待迁移）"""

    __tablename__ = "agent_kbs"

    agent_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True
    )
    kb_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), primary_key=True
    )


class AgentTool(Base):
    """智能体 ↔ 工具 关联表

    tool_type:
      - "skill"    → tool_ref_id = skill.id
      - "mcp_tool" → tool_ref  = "mcp_server_id:tool_name"（字符串键，便于 MCP 工具动态增减）
    """

    __tablename__ = "agent_tools"
    __table_args__ = (
        UniqueConstraint("agent_id", "tool_type", "tool_ref_id", "tool_ref", name="uq_agent_tool"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    agent_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )
    tool_type: Mapped[str] = mapped_column(String(20), nullable=False, comment="skill | mcp_tool")
    tool_ref_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="内部 Skill 的 id（tool_type=skill 时必填）"
    )
    tool_ref: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="MCP 工具引用：'<server_id>:<tool_name>'"
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)