"""内部 Skill（AI 智能工具）模型

一条记录 = 一个可被 LLM 调用的内部工具。实际执行逻辑由 app/skills/registry.py 按 name 路由。
内置的 Skill（is_builtin=True）不可删除，只能启停。
"""

from sqlalchemy import String, Integer, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from datetime import datetime
from typing import Optional


def _now() -> str:
    return datetime.now().isoformat()


class Skill(Base):
    """内部 Skill：名称 + 描述 + 参数 schema + 后端处理函数"""

    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, comment="工具名（英文，LLM 可见，如 web_search）"
    )
    title: Mapped[str] = mapped_column(String(100), nullable=False, default="", comment="显示标题")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="功能描述（给 LLM 看）")
    icon: Mapped[str] = mapped_column(String(50), nullable=False, default="🔧", comment="图标（emoji）")
    handler: Mapped[str] = mapped_column(
        String(100), nullable=False, default="", comment="处理函数标识（registry 里注册的 key，空=用 name）"
    )
    input_schema: Mapped[str] = mapped_column(
        Text, nullable=False, default='{"type":"object","properties":{}}',
        comment="JSON Schema 参数定义（字符串存储）"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="内置工具不可删除")
    is_dangerous: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="是否危险/写操作（前端调用前需确认）"
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(String(30), nullable=False, default=_now)
    updated_at: Mapped[str] = mapped_column(String(30), nullable=False, default=_now, onupdate=_now)

    def __repr__(self) -> str:
        return f"<Skill(id={self.id}, name='{self.name}')>"
