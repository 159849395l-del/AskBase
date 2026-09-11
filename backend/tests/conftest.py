"""pytest 配置文件 — 测试夹具和全局配置"""

import pytest
import os
import sys
import asyncio

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环用于异步测试"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def usage_db(tmp_path, monkeypatch):
    """临时文件 SQLite，并把用量采集模块的会话工厂指过去。

    必须是**文件库**而不是内存库：采集写入与测试断言用的是不同会话，
    内存库在会话之间不共享数据。

    同时确保全部 ORM 模型已注册（与 app/main.py 的「新表依赖」同一集合，
    否则 agents.model_id 这类外键会因为目标表未注册而建表失败）。
    """
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

    from app.database import Base
    import app.models  # noqa: F401
    from app.models.llm_model import LLMModel  # noqa: F401
    from app.models.skill import Skill  # noqa: F401
    from app.models.mcp_server import MCPServer  # noqa: F401

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'usage.db'}")

    async def _create_tables():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_create_tables())
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr("app.services.usage_service.async_session_factory", factory)
    yield factory
    asyncio.run(engine.dispose())


@pytest.fixture
def read_rows():
    """用独立会话读回全部用量流水。

    与采集写入用的是不同会话，因此这本身也是一次「真的落库了」的验证。
    """
    from sqlalchemy import select

    from app.models.llm_usage import LLMUsageLog

    def _read(factory):
        async def _run():
            async with factory() as db:
                return (await db.execute(select(LLMUsageLog))).scalars().all()

        return asyncio.run(_run())

    return _read
