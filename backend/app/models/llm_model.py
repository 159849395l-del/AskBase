"""大模型库模型 — 管理可配置的 LLM（OpenAI 兼容端点）

一条记录 = 一个可用模型。api_key 用 Fernet 加密存储（见 app/utils/crypto.py）。
后台未配置任何模型时，系统回退到 .env 里的 LLM_* 配置。
"""

from sqlalchemy import String, Integer, Float, Boolean, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from datetime import datetime
from typing import Optional


def _now() -> str:
    return datetime.now().isoformat()


class LLMModel(Base):
    """大模型：厂商 + 真实模型 ID + OpenAI 兼容端点 + 加密密钥"""

    __tablename__ = "llm_models"
    __table_args__ = (
        UniqueConstraint("provider", "model_id", name="uq_llm_provider_model"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="显示名称，如 DeepSeek V3")
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="custom", comment="厂商标识：deepseek/volcengine/openai/aliyun/local/custom")
    model_id: Mapped[str] = mapped_column(String(100), nullable=False, comment="真实模型 ID，如 deepseek-chat")
    base_url: Mapped[str] = mapped_column(String(255), nullable=False, comment="OpenAI 兼容 endpoint")
    api_key_encrypted: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True, comment="API Key（Fernet 加密）")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="是否启用")
    is_vision: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否视觉模型")
    supports_tool_call: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否支持 function calling")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否系统默认模型（唯一）")
    temperature: Mapped[float] = mapped_column(Float, nullable=False, default=0.3, comment="默认温度")
    max_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="最大输出 token（空=不限制）")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(String(30), nullable=False, default=_now)
    updated_at: Mapped[str] = mapped_column(String(30), nullable=False, default=_now, onupdate=_now)

    def __repr__(self) -> str:
        return f"<LLMModel(id={self.id}, name='{self.name}', model_id='{self.model_id}')>"
