"""知识库服务 — CRUD + 类型校验 + 子资源统计

B 类（数据库型）创建/变更数据源后，会触发元数据同步（拉取源库表清单），
见 app/services/metadata_sync.py（Phase 4 实现，未就绪时静默跳过并在日志提示）。
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
from fastapi import HTTPException, status

from app.models.knowledge_base import KnowledgeBase
from app.models.data_source import DataSource
from app.schemas.knowledge_base import KnowledgeBaseCreate, KnowledgeBaseUpdate, KnowledgeBaseItem


async def _enrich_item(db: AsyncSession, kb: KnowledgeBase) -> KnowledgeBaseItem:
    """填充数据源别名 + 子资源计数（计数表不存在时按 0 处理）"""
    item = KnowledgeBaseItem.model_validate(kb)

    if kb.data_source_id:
        ds = (
            await db.execute(select(DataSource.name).where(DataSource.id == kb.data_source_id))
        ).scalar_one_or_none()
        item.data_source_name = ds

    # 计数：子资源表可能还没建（渐进开发），用 inspect 探测（异步安全版）
    from sqlalchemy import inspect as sa_inspect

    async def _table_exists_async(tbl: str) -> bool:
        return await db.run_sync(
            lambda s: tbl in sa_inspect(s.get_bind()).get_table_names()
        )

    try:
        if kb.type == "document":
            if await _table_exists_async("knowledge_documents"):
                from app.models.knowledge_document import KnowledgeDocument

                item.doc_count = (
                    await db.execute(
                        select(func.count(KnowledgeDocument.id)).where(
                            KnowledgeDocument.kb_id == kb.id
                        )
                    )
                ).scalar() or 0
            if await _table_exists_async("qa_items"):
                from app.models.qa_item import QAItem

                item.qa_count = (
                    await db.execute(
                        select(func.count(QAItem.id)).where(QAItem.kb_id == kb.id)
                    )
                ).scalar() or 0
        else:
            if await _table_exists_async("db_tables"):
                from app.models.db_table import DBTable

                item.table_count = (
                    await db.execute(
                        select(func.count(DBTable.id)).where(DBTable.kb_id == kb.id)
                    )
                ).scalar() or 0
            if await _table_exists_async("db_knowledge_points"):
                from app.models.db_table import DBKnowledgePoint

                item.kp_count = (
                    await db.execute(
                        select(func.count(DBKnowledgePoint.id)).where(DBKnowledgePoint.kb_id == kb.id)
                    )
                ).scalar() or 0
    except Exception as e:
        print(f"[kb_service] 统计子资源失败(忽略): {e}")

    return item


async def list_knowledge_bases(db: AsyncSession) -> List[KnowledgeBaseItem]:
    """列出全部知识库（按 id 升序）"""
    result = await db.execute(select(KnowledgeBase).order_by(KnowledgeBase.id.asc()))
    kbs = result.scalars().all()
    return [await _enrich_item(db, kb) for kb in kbs]


async def get_knowledge_base(db: AsyncSession, kb_id: int) -> KnowledgeBase:
    """取知识库 ORM（不存在抛 404）"""
    result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
    kb = result.scalar_one_or_none()
    if kb is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识库不存在")
    return kb


def _validate_body(body: KnowledgeBaseCreate) -> None:
    """类型与数据源字段的互斥/必填校验"""
    if body.type == "database":
        if not body.data_source_id:
            raise HTTPException(status_code=400, detail="数据库型知识库必须选择数据源")
        if not body.database_name or not body.database_name.strip():
            raise HTTPException(status_code=400, detail="数据库型知识库必须填写库名（库/服务名）")
    elif body.type == "document":
        if body.data_source_id or body.database_name:
            raise HTTPException(status_code=400, detail="文档型知识库不能绑定数据源，请清空数据源和库名")
    else:
        raise HTTPException(status_code=400, detail=f"不支持的知识库类型: {body.type}")


async def create_knowledge_base(
    db: AsyncSession, body: KnowledgeBaseCreate, created_by: int
) -> KnowledgeBaseItem:
    """创建知识库；B 类校验数据源存在 + 联合唯一；成功后触发元数据同步"""
    _validate_body(body)

    if body.data_source_id:
        ds = (
            await db.execute(select(DataSource.id).where(DataSource.id == body.data_source_id))
        ).scalar_one_or_none()
        if ds is None:
            raise HTTPException(status_code=400, detail="所选数据源不存在")

    # 联合唯一：同一 data_source + database_name 不能重复建（B 类）
    if body.type == "database":
        dup = (
            await db.execute(
                select(KnowledgeBase).where(
                    KnowledgeBase.data_source_id == body.data_source_id,
                    KnowledgeBase.database_name == body.database_name.strip(),
                )
            )
        ).scalar_one_or_none()
        if dup is not None:
            raise HTTPException(
                status_code=409,
                detail=f"数据源「{dup.data_source_id}」下的库「{body.database_name}」已存在知识库「{dup.name}」",
            )

    kb = KnowledgeBase(
        name=body.name.strip(),
        label=body.label.strip(),
        authorized_user_id=body.authorized_user_id,
        type=body.type,
        data_source_id=body.data_source_id,
        database_name=body.database_name.strip() if body.database_name else None,
        description=body.description,
        created_by=created_by,
    )
    db.add(kb)
    await db.flush()
    await db.refresh(kb)

    # B 类：触发元数据同步（拉表清单 + 字段注释）
    if kb.type == "database":
        await _trigger_schema_sync(db, kb.id)

    return await _enrich_item(db, kb)


async def update_knowledge_base(
    db: AsyncSession, kb_id: int, body: KnowledgeBaseUpdate
) -> KnowledgeBaseItem:
    """更新知识库（type 不可变；数据源变更后重新同步）"""
    kb = await get_knowledge_base(db, kb_id)
    data = body.model_dump(exclude_unset=True)

    # 部分字段校验
    new_ds = data.get("data_source_id", kb.data_source_id)
    new_db = data.get("database_name", kb.database_name)
    if kb.type == "database":
        if new_ds is None:
            raise HTTPException(status_code=400, detail="数据库型知识库不能移除数据源")
        if new_db is None or not str(new_db).strip():
            raise HTTPException(status_code=400, detail="数据库型知识库必须填写库名")
        if new_ds != kb.data_source_id or new_db != kb.database_name:
            # 联合唯一检查（排除自身）
            dup = (
                await db.execute(
                    select(KnowledgeBase).where(
                        KnowledgeBase.data_source_id == new_ds,
                        KnowledgeBase.database_name == str(new_db).strip(),
                        KnowledgeBase.id != kb.id,
                    )
                )
            ).scalar_one_or_none()
            if dup is not None:
                raise HTTPException(status_code=409, detail="同数据源同库名已存在其他知识库")
    else:
        if new_ds or new_db:
            raise HTTPException(status_code=400, detail="文档型知识库不能绑定数据源")

    for k, v in data.items():
        if k == "name" and v:
            v = v.strip()
        if k == "database_name" and v:
            v = v.strip()
        setattr(kb, k, v)

    await db.flush()
    await db.refresh(kb)

    # B 类数据源/库名变更 → 重新同步元数据
    if kb.type == "database" and (new_ds is not None):
        await _trigger_schema_sync(db, kb.id)

    return await _enrich_item(db, kb)


async def delete_knowledge_base(db: AsyncSession, kb_id: int) -> None:
    """删除知识库（级联删除子资源记录；Chroma 向量由各自资源删除时清理）"""
    kb = await get_knowledge_base(db, kb_id)

    from app.models.qa_item import QAItem
    from app.models.db_table import DBTable, DBTableField, DBKnowledgePoint
    from app.models.knowledge_document import KnowledgeDocument

    # 问答集
    for x in (await db.execute(select(QAItem).where(QAItem.kb_id == kb_id))).scalars().all():
        await db.delete(x)
    # 知识点
    for x in (await db.execute(select(DBKnowledgePoint).where(DBKnowledgePoint.kb_id == kb_id))).scalars().all():
        await db.delete(x)
    # 表 + 字段
    for t in (await db.execute(select(DBTable).where(DBTable.kb_id == kb_id))).scalars().all():
        for f in (await db.execute(select(DBTableField).where(DBTableField.db_table_id == t.id))).scalars().all():
            await db.delete(f)
        await db.delete(t)
    # 文档记录（磁盘文件与向量：尽量清理，失败不阻断）
    for d in (await db.execute(select(KnowledgeDocument).where(KnowledgeDocument.kb_id == kb_id))).scalars().all():
        try:
            from app.services.rag_service import delete_kb_document_chunks
            await delete_kb_document_chunks(d.id)
        except Exception:
            pass
        try:
            import os
            fp = os.path.join("./data/uploads", d.filename)
            if os.path.exists(fp):
                os.remove(fp)
        except Exception:
            pass
        await db.delete(d)

    await db.delete(kb)
    await db.flush()


async def _trigger_schema_sync(db: AsyncSession, kb_id: int) -> None:
    """触发源库表结构同步（metadata_sync 未就绪时打印提示，不阻塞）"""
    try:
        from app.services.metadata_sync import sync_kb_schema

        await sync_kb_schema(db, kb_id)
        print(f"[kb_service] 知识库 {kb_id} 元数据同步完成")
    except ImportError:
        print(f"[kb_service] 提示: metadata_sync 模块尚未就绪（Phase 4），知识库 {kb_id} 暂未同步表结构")
    except Exception as e:
        print(f"[kb_service] 元数据同步失败(不阻塞): {e}")
