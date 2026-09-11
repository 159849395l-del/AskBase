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


def _temp_engine(db_path, create_all: bool):
    """建一个临时**文件库**并返回 engine。

    必须是文件库而不是内存库：采集写入与测试断言用的是不同会话，
    内存库在会话之间不共享数据。

    create_all=True 建全部表（供需要其他表的用例）；
    否则只建用量流水表 —— 它没有外键，建表开销最小。
    """
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.database import Base
    from app.models.llm_usage import LLMUsageLog

    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")

    async def _create():
        async with engine.begin() as conn:
            if create_all:
                # 触发全部 ORM 模型注册（与 app/main.py 的「新表依赖」同一集合），
                # 否则 agents.model_id 这类外键会因为目标表未注册而建表失败
                import app.models  # noqa: F401
                from app.models.llm_model import LLMModel  # noqa: F401
                from app.models.skill import Skill  # noqa: F401
                from app.models.mcp_server import MCPServer  # noqa: F401

                await conn.run_sync(Base.metadata.create_all)
            else:
                await conn.run_sync(LLMUsageLog.__table__.create)

    asyncio.run(_create())
    return engine


def _session_factory(engine):
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(autouse=True)
def _isolate_usage_writes(tmp_path, monkeypatch):
    """所有测试默认把用量写入隔离到临时库，绝不落到开发数据库。

    采集是旁路副作用，很多与用量无关的用例（如既有的压缩、改写测试）也会触发它。
    需要断言流水的用例用 usage_db 夹具覆盖这里（后 patch 生效）。
    """
    engine = _temp_engine(tmp_path / "usage-isolated.db", create_all=False)
    factory = _session_factory(engine)
    monkeypatch.setattr("app.services.usage_service.async_session_factory", factory)
    # 第二道保险：将来若出现绕过采集入口的直写路径，也不该落到开发数据库
    monkeypatch.setattr("app.database.async_session_factory", factory)
    yield engine
    asyncio.run(engine.dispose())


@pytest.fixture
def usage_db(tmp_path, monkeypatch):
    """临时文件 SQLite（建全部表），并把用量采集模块的会话工厂指过去。

    覆盖 autouse 的隔离夹具，让需要断言流水的用例读写同一个库。
    """
    engine = _temp_engine(tmp_path / "usage.db", create_all=True)
    factory = _session_factory(engine)
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
