#!/usr/bin/env python3
"""一次性数据迁移脚本：旧版知识库数据 → 新版（知识库维度）结构

迁移内容：
1. 创建默认知识库（name='默认知识库', type=document），不存在则建
2. 旧 knowledge_documents（kb_id IS NULL）→ 归入默认知识库
3. 旧 agent_knowledge_bases（文档粒度）→ agent_kbs（知识库粒度），按 kb_doc_id 反查 kb_id 并去重
4. ChromaDB 向量：为所有缺 kb_id 的块补标签（按 kb_doc_id 反查）
5. 旧 agent_knowledge_bases 表保留不动（数据已拷贝）

用法：在 backend 目录下运行
    venv/Scripts/python.exe scripts/migrate_kb_v2.py
"""

import sys
import os

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

import asyncio
from sqlalchemy import select, text
from app.database import async_session_factory
from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_document import KnowledgeDocument
from app.models.agent import AgentKnowledgeBase

DEFAULT_KB_NAME = "默认知识库"


async def ensure_default_kb(db) -> KnowledgeBase:
    kb = (
        await db.execute(select(KnowledgeBase).where(KnowledgeBase.name == DEFAULT_KB_NAME))
    ).scalar_one_or_none()
    if kb:
        print(f"[迁移] 默认知识库已存在 id={kb.id}")
        return kb
    # 找一个 admin 用户作为 created_by（兜底取第一个用户）
    uid = (await db.execute(text("SELECT id FROM users ORDER BY id ASC LIMIT 1"))).scalar_one_or_none()
    kb = KnowledgeBase(
        name=DEFAULT_KB_NAME,
        label="",
        type="document",
        description="系统自动创建的默认知识库（历史文档归属）",
        created_by=uid or 1,
    )
    db.add(kb)
    await db.flush()
    await db.refresh(kb)
    print(f"[迁移] 已创建默认知识库 id={kb.id}")
    return kb


async def migrate_documents(db, default_kb: KnowledgeBase) -> int:
    """旧文档（kb_id 为空）归入默认知识库"""
    docs = (
        await db.execute(
            select(KnowledgeDocument).where(KnowledgeDocument.kb_id.is_(None))
        )
    ).scalars().all()
    for d in docs:
        d.kb_id = default_kb.id
    await db.flush()
    print(f"[迁移] 归入默认知识库的旧文档: {len(docs)} 条")
    return len(docs)


async def migrate_agent_links(db) -> tuple:
    """旧 agent_knowledge_bases（kb_doc_id）→ agent_kbs（kb_id），去重"""
    old_rows = (
        await db.execute(text("SELECT agent_id, kb_doc_id FROM agent_knowledge_bases"))
    ).all()
    print(f"[迁移] 旧智能体-文档关联: {len(old_rows)} 条")

    inserted = 0
    skipped = 0
    for agent_id, kb_doc_id in old_rows:
        kb_id = (
            await db.execute(
                select(KnowledgeDocument.kb_id).where(KnowledgeDocument.id == kb_doc_id)
            )
        ).scalar_one_or_none()
        if kb_id is None:
            skipped += 1
            continue
        # 去重检查
        existing = (
            await db.execute(
                text("SELECT 1 FROM agent_kbs WHERE agent_id=:a AND kb_id=:k"),
                {"a": agent_id, "k": kb_id},
            )
        ).fetchone()
        if existing:
            skipped += 1
            continue
        await db.execute(
            text("INSERT INTO agent_kbs (agent_id, kb_id) VALUES (:a, :k)"),
            {"a": agent_id, "k": kb_id},
        )
        inserted += 1
    await db.flush()
    print(f"[迁移] agent_kbs 新增: {inserted} 条，跳过（无文档/重复）: {skipped} 条")
    return inserted, skipped


async def backfill_chroma_kb_id() -> None:
    """ChromaDB：为缺 kb_id 标签的块补上（按 kb_doc_id 反查）"""
    from app.rag.vector_store import get_vectorstore

    vs = get_vectorstore()
    collection = vs._collection
    data = collection.get(include=["metadatas"])
    ids = data.get("ids") or []
    metas = data.get("metadatas") or []

    # kb_doc_id -> kb_id 映射（一次查全）
    doc_ids = {
        m["kb_doc_id"]
        for m in metas
        if m and m.get("kb_doc_id") is not None
    }
    if not doc_ids:
        print("[迁移] Chroma 无文档块，跳过")
        return

    async with async_session_factory() as db:
        rows = (
            await db.execute(
                select(KnowledgeDocument.id, KnowledgeDocument.kb_id).where(
                    KnowledgeDocument.id.in_(list(doc_ids))
                )
            )
        ).all()
    mapping = {r[0]: r[1] for r in rows if r[1] is not None}

    upd_ids = []
    upd_metas = []
    for cid, meta in zip(ids, metas):
        if meta is None or meta.get("kb_id") is not None:
            continue
        kb_doc_id = meta.get("kb_doc_id")
        if kb_doc_id in mapping:
            upd_ids.append(cid)
            upd_metas.append({**meta, "kb_id": mapping[kb_doc_id]})

    if upd_ids:
        collection.update(ids=upd_ids, metadatas=upd_metas)
        print(f"[迁移] Chroma 补 kb_id 标签: {len(upd_ids)} 块")
    else:
        print("[迁移] Chroma 无需补标签")


async def main():
    async with async_session_factory() as db:
        default_kb = await ensure_default_kb(db)
        await migrate_documents(db, default_kb)
        await migrate_agent_links(db)
        await db.commit()
    await backfill_chroma_kb_id()
    print("[迁移] 全部完成 ✅")


if __name__ == "__main__":
    asyncio.run(main())
