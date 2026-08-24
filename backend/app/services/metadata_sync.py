"""B 类知识库元数据同步服务 — 连源库拉取表清单与字段注释，写入 db_tables / db_table_fields

同步策略（幂等）：
- 源库的表 → 本地无 → 新建（字段描述默认填 COLUMN_COMMENT，源库无注释则为空待人工补）
- 本地已有表 → 比对字段：源库新增的字段 → 本地补建；本地有但源库已删除 → status=conflict（不自动删）
- 本地表在源库已消失 → status=conflict
- 字段描述：首次创建填源库注释；人工改过的（与源库注释不同）不覆盖
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, List, Tuple
import asyncio

from app.models.knowledge_base import KnowledgeBase
from app.models.data_source import DataSource
from app.models.db_table import DBTable, DBTableField
from app.utils.crypto import decrypt_password


def _fetch_schema_sync(host: str, port: int, database: str, username: str, password: str):
    """同步连源库拉 (表名, 表注释) 与 {表名: [(字段名, 类型, 注释), ...]}"""
    import pymysql

    conn = pymysql.connect(
        host=host,
        port=int(port),
        user=username,
        password=password or "",
        database=database,
        connect_timeout=8,
        read_timeout=15,
        charset="utf8mb4",
    )
    try:
        with conn.cursor() as cur:
            # 表清单
            cur.execute(
                "SELECT TABLE_NAME, IFNULL(TABLE_COMMENT, '') FROM INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE' ORDER BY TABLE_NAME",
                (database,),
            )
            tables = {row[0]: row[1] for row in cur.fetchall()}

            # 字段清单
            cur.execute(
                "SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE, IFNULL(COLUMN_COMMENT, '') "
                "FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = %s ORDER BY ORDINAL_POSITION",
                (database,),
            )
            fields: Dict[str, List[Tuple[str, str, str]]] = {}
            for t, c, ctype, ccomment in cur.fetchall():
                fields.setdefault(t, []).append((c, ctype, ccomment))

        return tables, fields
    finally:
        conn.close()


async def sync_kb_schema(db: AsyncSession, kb_id: int) -> dict:
    """同步指定 B 类知识库的表结构。返回统计信息 {tables, added_fields, conflicted, missing}"""
    kb = (
        await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
    ).scalar_one_or_none()
    if kb is None:
        raise ValueError(f"知识库 {kb_id} 不存在")
    if kb.type != "database" or not kb.data_source_id or not kb.database_name:
        raise ValueError(f"知识库 {kb_id} 不是数据库型（或缺少数据源/库名），无法同步表结构")

    ds = (
        await db.execute(select(DataSource).where(DataSource.id == kb.data_source_id))
    ).scalar_one_or_none()
    if ds is None:
        raise ValueError("数据源不存在")

    tables, fields = await asyncio.to_thread(
        _fetch_schema_sync,
        ds.host, ds.port, kb.database_name, ds.username,
        decrypt_password(ds.password_encrypted or ""),
    )

    # 本地现有表
    local_tables = {
        t.table_name: t
        for t in (await db.execute(
            select(DBTable).where(DBTable.kb_id == kb_id)
        )).scalars().all()
    }

    stats = {"tables": 0, "added_fields": 0, "conflicted": 0, "missing": 0}

    # 1. 源库表 → 本地
    for table_name, table_comment in tables.items():
        local = local_tables.get(table_name)
        if local is None:
            local = DBTable(
                kb_id=kb_id,
                table_name=table_name,
                table_comment=table_comment[:500],
                column_count=len(fields.get(table_name, [])),
                status="normal",
            )
            db.add(local)
            await db.flush()
            await db.refresh(local)
            stats["tables"] += 1
        else:
            # 恢复 normal（之前可能冲突，源库又出现了）
            if local.status != "normal":
                local.status = "normal"
            local.table_comment = table_comment[:500] or local.table_comment
            local.column_count = len(fields.get(table_name, []))

        # 字段比对
        local_fields = {
            f.field_name: f
            for f in (await db.execute(
                select(DBTableField).where(DBTableField.db_table_id == local.id)
            )).scalars().all()
        }
        source_field_names = set()
        for col_name, col_type, col_comment in fields.get(table_name, []):
            source_field_names.add(col_name)
            lf = local_fields.get(col_name)
            if lf is None:
                db.add(DBTableField(
                    db_table_id=local.id,
                    field_name=col_name,
                    field_type=col_type[:100],
                    field_comment=col_comment[:500],  # 默认填源库注释
                    status="normal",
                ))
                stats["added_fields"] += 1
            else:
                if lf.status != "normal":
                    lf.status = "normal"  # 源库又出现了 → 恢复
                if not lf.field_comment and col_comment:
                    lf.field_comment = col_comment[:500]  # 空描述补源库注释

        # 本地有但源库没有 → 冲突
        for fname, lf in local_fields.items():
            if fname not in source_field_names and lf.status == "normal" and not lf.deleted_flag:
                lf.status = "conflict"
                stats["conflicted"] += 1

    # 2. 本地有但源库已消失的表 → 冲突
    for tname, local in local_tables.items():
        if tname not in tables and local.status == "normal":
            local.status = "conflict"
            stats["missing"] += 1

    await db.flush()
    return stats
