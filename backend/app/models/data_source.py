"""数据源模型 — 管理外部 MySQL 数据库连接（仅存连接信息，不建业务表）"""

from sqlalchemy import String, Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from datetime import datetime
from typing import Optional


def _now() -> str:
    return datetime.now().isoformat()


class DataSource(Base):
    """数据源：一条记录 = 一台 MySQL 服务器 + 账号 + 一个参考库名（"库/服务名"）

    - name: 管理员自取的别名（如 mysql51），仅作展示代号
    - database: 数据源中真实存在的一个库名；知识库绑定「数据源 + 具体库名」时可覆盖
    - password_encrypted: Fernet 加密后的密码（见 app/utils/crypto.py）
    """

    __tablename__ = "data_sources"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, comment="数据源名称（别名）")
    type: Mapped[str] = mapped_column(String(20), nullable=False, default="mysql", comment="类型，当前仅 mysql")
    host: Mapped[str] = mapped_column(String(255), nullable=False, comment="地址/IP")
    port: Mapped[int] = mapped_column(Integer, nullable=False, default=3306, comment="端口")
    database: Mapped[str] = mapped_column(String(255), nullable=False, comment="库/服务名（真实库名）")
    username: Mapped[str] = mapped_column(String(100), nullable=False, comment="用户名")
    password_encrypted: Mapped[Optional[str]] = mapped_column(String(512), nullable=True, comment="密码（Fernet 加密）")
    created_at: Mapped[str] = mapped_column(String(30), nullable=False, default=_now)
    updated_at: Mapped[str] = mapped_column(String(30), nullable=False, default=_now, onupdate=_now)

    def __repr__(self) -> str:
        return f"<DataSource(id={self.id}, name='{self.name}', db='{self.database}')>"
