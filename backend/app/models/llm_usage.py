"""LLM 用量流水模型 — append-only 账单，不设外键

取舍见 docs/adr/0001-usage-log-append-only.md：
删除智能体/会话不得抹掉历史归属，因此不设外键，改为在写入时冗余名称快照。
"""

from sqlalchemy import String, Integer, Boolean, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from datetime import datetime
from typing import Optional


def _now() -> str:
    return datetime.now().isoformat()


class LLMUsageLog(Base):
    """一次模型调用 = 一条记录"""

    __tablename__ = "llm_usage_logs"
    __table_args__ = (
        Index("ix_llm_usage_created_at", "created_at"),
        Index("ix_llm_usage_agent_created", "agent_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # 归属：故意不设外键（ADR-0001）；agent_name 是写入当时的名称快照，
    # 保证智能体改名或删除后，历史用量仍归到同一行、仍可读。
    agent_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    agent_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    conversation_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # 模型：model_id 仅当智能体显式绑定大模型时有值；model_name 始终记录实际模型串
    model_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False, default="")

    call_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="chat",
        comment="chat | tool | rewrite | compress | text2sql | agent_test",
    )
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_estimated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        comment="端点未返回用量而按字符估算；该行不进入任何统计",
    )
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="success")
    error_message: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[str] = mapped_column(String(30), nullable=False, default=_now)

    def __repr__(self) -> str:
        return f"<LLMUsageLog(id={self.id}, agent='{self.agent_name}', tokens={self.total_tokens})>"
