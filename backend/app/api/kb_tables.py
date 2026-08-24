"""
B 类（数据库型）知识库子资源 API — 表信息 / 字段 / 知识点
前缀：/api/knowledge-bases/{kb_id}/...
仅管理员可访问
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models.user import User
from app.core.dependencies import get_admin_user
from app.models.knowledge_base import KnowledgeBase
from app.models.db_table import DBTable, DBTableField, DBKnowledgePoint
from app.schemas.db_table import (
    DBTableItem,
    DBTableUpdate,
    DBTableFieldItem,
    DBTableFieldUpdate,
    DBKnowledgePointCreate,
    DBKnowledgePointUpdate,
    DBKnowledgePointItem,
    DBKnowledgePointListResponse,
)
from app.schemas.auth import MessageResponse
from app.services import metadata_sync
from app.services.rag_service import ingest_structured_item, delete_structured_item_chunks

router = APIRouter(prefix="/api/knowledge-bases", tags=["B类知识库子资源"])


async def _get_kb(db: AsyncSession, kb_id: int, expect_database: bool = True) -> KnowledgeBase:
    kb = (await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))).scalar_one_or_none()
    if kb is None:
        raise HTTPException(status_code=404, detail="知识库不存在")
    if expect_database and kb.type != "database":
        raise HTTPException(status_code=400, detail="只有数据库型知识库支持表信息/知识点")
    return kb


async def _get_table(db: AsyncSession, kb_id: int, table_id: int) -> DBTable:
    t = (
        await db.execute(
            select(DBTable).where(DBTable.id == table_id, DBTable.kb_id == kb_id)
        )
    ).scalar_one_or_none()
    if t is None:
        raise HTTPException(status_code=404, detail="表不存在")
    return t


async def _table_item(db: AsyncSession, t: DBTable) -> DBTableItem:
    fields = (
        await db.execute(
            select(DBTableField)
            .where(DBTableField.db_table_id == t.id)
            .order_by(DBTableField.id.asc())
        )
    ).scalars().all()
    item = DBTableItem.model_validate(t)
    item.fields = [DBTableFieldItem.model_validate(f) for f in fields]
    return item


# ---------- 表信息 ----------

@router.get("/{kb_id}/tables", response_model=list[DBTableItem])
async def list_tables(
    kb_id: int,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """表信息列表（含字段）"""
    await _get_kb(db, kb_id)
    tables = (
        await db.execute(select(DBTable).where(DBTable.kb_id == kb_id).order_by(DBTable.id.asc()))
    ).scalars().all()
    return [await _table_item(db, t) for t in tables]


@router.post("/{kb_id}/tables/sync", response_model=MessageResponse)
async def sync_tables(
    kb_id: int,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """手动重新同步表结构（连源库拉表清单/字段注释）"""
    await _get_kb(db, kb_id)
    try:
        stats = await metadata_sync.sync_kb_schema(db, kb_id)
        return MessageResponse(
            message=(
                f"同步完成：新增表 {stats['tables']}，新增字段 {stats['added_fields']}，"
                f"冲突 {stats['conflicted'] + stats['missing']}（字段 {stats['conflicted']} + 表 {stats['missing']}）"
            )
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"同步失败：{e}")


@router.put("/{kb_id}/tables/{table_id}", response_model=DBTableItem)
async def update_table(
    kb_id: int,
    table_id: int,
    body: DBTableUpdate,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """编辑表（表描述 / 必选开关）"""
    await _get_kb(db, kb_id)
    t = await _get_table(db, kb_id, table_id)
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(t, k, v)
    await db.flush()
    return await _table_item(db, t)


@router.delete("/{kb_id}/tables/{table_id}", response_model=MessageResponse)
async def delete_table(
    kb_id: int,
    table_id: int,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """删除表及其字段记录"""
    await _get_kb(db, kb_id)
    t = await _get_table(db, kb_id, table_id)
    # 级联删字段
    fields = (
        await db.execute(select(DBTableField).where(DBTableField.db_table_id == t.id))
    ).scalars().all()
    for f in fields:
        await db.delete(f)
    await db.delete(t)
    await db.flush()
    return MessageResponse(message="表已删除")


# ---------- 字段 ----------

@router.put("/{kb_id}/tables/{table_id}/fields/{field_id}", response_model=DBTableItem)
async def update_field(
    kb_id: int,
    table_id: int,
    field_id: int,
    body: DBTableFieldUpdate,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """编辑字段（字段描述 / 必带开关 / 状态）"""
    await _get_kb(db, kb_id)
    await _get_table(db, kb_id, table_id)
    f = (
        await db.execute(
            select(DBTableField).where(DBTableField.id == field_id, DBTableField.db_table_id == table_id)
        )
    ).scalar_one_or_none()
    if f is None:
        raise HTTPException(status_code=404, detail="字段不存在")
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(f, k, v)
    await db.flush()
    t = await _get_table(db, kb_id, table_id)
    return await _table_item(db, t)


@router.delete("/{kb_id}/tables/{table_id}/fields/{field_id}", response_model=MessageResponse)
async def delete_field(
    kb_id: int,
    table_id: int,
    field_id: int,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """删除字段（软删除，保留历史）"""
    await _get_kb(db, kb_id)
    await _get_table(db, kb_id, table_id)
    f = (
        await db.execute(
            select(DBTableField).where(DBTableField.id == field_id, DBTableField.db_table_id == table_id)
        )
    ).scalar_one_or_none()
    if f is None:
        raise HTTPException(status_code=404, detail="字段不存在")
    f.deleted_flag = True
    f.status = "conflict"
    await db.flush()
    return MessageResponse(message="字段已删除")


# ---------- 知识点 ----------

@router.get("/{kb_id}/knowledge-points", response_model=DBKnowledgePointListResponse)
async def list_knowledge_points(
    kb_id: int,
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """知识点列表"""
    await _get_kb(db, kb_id)
    total = (await db.execute(select(func.count(DBKnowledgePoint.id)).where(DBKnowledgePoint.kb_id == kb_id))).scalar() or 0
    items = (
        await db.execute(
            select(DBKnowledgePoint)
            .where(DBKnowledgePoint.kb_id == kb_id)
            .order_by(DBKnowledgePoint.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return DBKnowledgePointListResponse(items=[DBKnowledgePointItem.model_validate(x) for x in items], total=total)


@router.post("/{kb_id}/knowledge-points", response_model=DBKnowledgePointItem, status_code=201)
async def create_knowledge_point(
    kb_id: int,
    body: DBKnowledgePointCreate,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """新增知识点（同步摄入 Chroma，kind=db_kp）"""
    await _get_kb(db, kb_id)
    kp = DBKnowledgePoint(
        kb_id=kb_id,
        name=body.name.strip(),
        content=body.content.strip(),
        created_by=current_user.id,
    )
    db.add(kp)
    await db.flush()
    await db.refresh(kp)
    await ingest_structured_item(
        kb_id=kb_id, kind="db_kp", item_id=kp.id,
        title=kp.name, content=kp.content,
    )
    return DBKnowledgePointItem.model_validate(kp)


@router.put("/{kb_id}/knowledge-points/{kp_id}", response_model=DBKnowledgePointItem)
async def update_knowledge_point(
    kb_id: int,
    kp_id: int,
    body: DBKnowledgePointUpdate,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """更新知识点（重摄入）"""
    await _get_kb(db, kb_id)
    kp = (
        await db.execute(select(DBKnowledgePoint).where(DBKnowledgePoint.id == kp_id, DBKnowledgePoint.kb_id == kb_id))
    ).scalar_one_or_none()
    if kp is None:
        raise HTTPException(status_code=404, detail="知识点不存在")
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(kp, k, v.strip() if isinstance(v, str) else v)
    await db.flush()
    await db.refresh(kp)
    await delete_structured_item_chunks("db_kp", kp.id)
    await ingest_structured_item(
        kb_id=kb_id, kind="db_kp", item_id=kp.id,
        title=kp.name, content=kp.content,
    )
    return DBKnowledgePointItem.model_validate(kp)


@router.delete("/{kb_id}/knowledge-points/{kp_id}", response_model=MessageResponse)
async def delete_knowledge_point(
    kb_id: int,
    kp_id: int,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """删除知识点（连带删向量）"""
    await _get_kb(db, kb_id)
    kp = (
        await db.execute(select(DBKnowledgePoint).where(DBKnowledgePoint.id == kp_id, DBKnowledgePoint.kb_id == kb_id))
    ).scalar_one_or_none()
    if kp is None:
        raise HTTPException(status_code=404, detail="知识点不存在")
    await delete_structured_item_chunks("db_kp", kp.id)
    await db.delete(kp)
    await db.flush()
    return MessageResponse(message="知识点已删除")
