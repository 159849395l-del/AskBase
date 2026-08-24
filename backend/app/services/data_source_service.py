"""数据源服务 — CRUD + 密码加解密 + MySQL 连通性测试"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional, Tuple
from fastapi import HTTPException, status
import asyncio
import time

from app.models.data_source import DataSource
from app.schemas.data_source import (
    DataSourceCreate,
    DataSourceUpdate,
    DataSourceItem,
    TestConnectionResponse,
)
from app.utils.crypto import encrypt_password, decrypt_password


async def list_data_sources(db: AsyncSession) -> List[DataSourceItem]:
    """列出全部数据源（按 id 升序）"""
    result = await db.execute(select(DataSource).order_by(DataSource.id.asc()))
    return [DataSourceItem.model_validate(ds) for ds in result.scalars().all()]


async def get_data_source(db: AsyncSession, ds_id: int) -> DataSource:
    """取数据源 ORM 对象（不存在抛 404）"""
    result = await db.execute(select(DataSource).where(DataSource.id == ds_id))
    ds = result.scalar_one_or_none()
    if ds is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="数据源不存在")
    return ds


async def create_data_source(db: AsyncSession, body: DataSourceCreate) -> DataSourceItem:
    """创建数据源；名称唯一校验"""
    await _ensure_name_unique(db, body.name, exclude_id=None)

    ds = DataSource(
        name=body.name.strip(),
        type=body.type or "mysql",
        host=body.host,
        port=body.port,
        database=body.database,
        username=body.username,
        password_encrypted=encrypt_password(body.password) if body.password else None,
    )
    db.add(ds)
    await db.flush()
    await db.refresh(ds)
    return DataSourceItem.model_validate(ds)


async def update_data_source(
    db: AsyncSession, ds_id: int, body: DataSourceUpdate
) -> DataSourceItem:
    """更新数据源（部分字段）"""
    ds = await get_data_source(db, ds_id)
    data = body.model_dump(exclude_unset=True)
    password = data.pop("password", None)

    if "name" in data and data["name"]:
        data["name"] = data["name"].strip()
        await _ensure_name_unique(db, data["name"], exclude_id=ds_id)
    if "type" in data and not data["type"]:
        data["type"] = "mysql"

    for k, v in data.items():
        setattr(ds, k, v)

    # 密码：显式传了非空字符串才更新；空串/None 不修改
    if password:
        ds.password_encrypted = encrypt_password(password)

    await db.flush()
    await db.refresh(ds)
    return DataSourceItem.model_validate(ds)


async def delete_data_source(db: AsyncSession, ds_id: int) -> None:
    """删除数据源；被知识库引用时拒绝删除"""
    ds = await get_data_source(db, ds_id)

    # 引用检查：knowledge_bases 表在 Phase 2 才建，用 inspect 探测，表不存在时跳过
    from sqlalchemy import inspect as sa_inspect

    has_kb_table = await db.run_sync(
        lambda sync_session: "knowledge_bases" in sa_inspect(sync_session.get_bind()).get_table_names()
    )
    if has_kb_table:
        from app.models.knowledge_base import KnowledgeBase

        used = (
            await db.execute(
                select(KnowledgeBase.id).where(KnowledgeBase.data_source_id == ds_id).limit(1)
            )
        ).scalar_one_or_none()
        if used is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="该数据源已被知识库引用，请先删除或解绑相关知识库",
            )
    await db.delete(ds)
    await db.flush()


async def _ensure_name_unique(db: AsyncSession, name: str, exclude_id: Optional[int]) -> None:
    """数据源名称唯一（排除自身）"""
    q = select(DataSource).where(DataSource.name == name.strip())
    if exclude_id is not None:
        q = q.where(DataSource.id != exclude_id)
    existing = (await db.execute(q)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"数据源名称「{name}」已存在，请使用其他名称")


def _test_mysql_connection(
    host: str, port: int, database: str, username: str, password: str
) -> TestConnectionResponse:
    """同步执行 MySQL 连接测试（调用方负责 to_thread 包装）"""
    import pymysql

    start = time.perf_counter()
    try:
        conn = pymysql.connect(
            host=host,
            port=int(port),
            user=username,
            password=password or "",
            database=database,
            connect_timeout=5,
            read_timeout=5,
            write_timeout=5,
            charset="utf8mb4",
        )
        # 真正执行一次查询确认库可读（连接成功但库不存在时 connect 已报错）
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        latency_ms = int((time.perf_counter() - start) * 1000)
        return TestConnectionResponse(
            success=True, message="连接成功", latency_ms=latency_ms
        )
    except Exception as e:
        latency_ms = int((time.perf_counter() - start) * 1000)
        detail = str(e).replace("\n", " ")
        if len(detail) > 200:
            detail = detail[:200] + "..."
        return TestConnectionResponse(success=False, message=detail, latency_ms=latency_ms)
    finally:
        try:
            conn.close()  # noqa: F821 未建立成功时无此变量
        except Exception:
            pass


async def test_connection(
    host: str, port: int, database: str, username: str, password: str
) -> TestConnectionResponse:
    """异步包装的 MySQL 连通测试"""
    return await asyncio.to_thread(
        _test_mysql_connection, host, int(port), database, username, password or ""
    )


async def test_saved_connection(db: AsyncSession, ds_id: int) -> TestConnectionResponse:
    """用已保存的数据源配置测试连通（解密密码）"""
    ds = await get_data_source(db, ds_id)
    return await test_connection(
        host=ds.host,
        port=ds.port,
        database=ds.database,
        username=ds.username,
        password=decrypt_password(ds.password_encrypted or ""),
    )
