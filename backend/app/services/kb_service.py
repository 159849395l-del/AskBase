"""
知识库管理服务 — 文档 CRUD 和统计
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Tuple, List, Optional
from fastapi import HTTPException, status
from app.models.knowledge_document import KnowledgeDocument
from app.models.user import User
from app.schemas.kb import DocumentItem, KBStatsResponse, KBSearchResult
from app.rag.retriever import retrieve_similar_chunks
from app.rag.vector_store import get_vectorstore
import os
import time


async def list_documents(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    status_filter: Optional[str] = None,
    kb_id: Optional[int] = None,
) -> Tuple[List[DocumentItem], int]:
    """获取知识文档列表（分页+筛选；kb_id 限定所属知识库）"""
    conditions = []
    if status_filter:
        conditions.append(KnowledgeDocument.status == status_filter)
    if kb_id is not None:
        conditions.append(KnowledgeDocument.kb_id == kb_id)

    # 总数
    count_q = select(func.count()).select_from(KnowledgeDocument)
    if conditions:
        count_q = count_q.where(*conditions)
    total = (await db.execute(count_q)).scalar() or 0

    # 分页查询
    q = select(KnowledgeDocument).order_by(KnowledgeDocument.created_at.desc())
    if conditions:
        q = q.where(*conditions)
    q = q.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(q)
    docs = result.scalars().all()

    items = [
        DocumentItem(
            id=d.id,
            filename=d.filename,
            file_type=d.file_type,
            file_size=d.file_size,
            chunk_count=d.chunk_count,
            status=d.status,
            created_at=d.created_at,
        )
        for d in docs
    ]

    return items, total


async def get_document_detail(db: AsyncSession, doc_id: int) -> DocumentItem:
    """获取单个文档详情"""
    result = await db.execute(select(KnowledgeDocument).where(KnowledgeDocument.id == doc_id))
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在")
    return DocumentItem(
        id=doc.id,
        filename=doc.filename,
        file_type=doc.file_type,
        file_size=doc.file_size,
        chunk_count=doc.chunk_count,
        status=doc.status,
        created_at=doc.created_at,
    )


async def delete_document(db: AsyncSession, doc_id: int) -> None:
    """删除知识文档及其向量"""
    result = await db.execute(select(KnowledgeDocument).where(KnowledgeDocument.id == doc_id))
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在")

    # 删除 ChromaDB 向量
    try:
        from app.services.rag_service import delete_kb_document_chunks
        await delete_kb_document_chunks(doc_id)
    except Exception:
        pass  # 向量删除失败不阻塞记录删除

    # 删除上传文件（失败不阻断——外部来源文档可能无磁盘文件，或权限/占用导致删除失败）
    try:
        file_path = os.path.join("./data/uploads", doc.filename)
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception as e:
        print(f"[kb_service] 删除上传文件失败(忽略): {file_path}: {e}")

    # 删除数据库记录
    await db.delete(doc)
    await db.flush()


async def get_kb_stats(db: AsyncSession) -> KBStatsResponse:
    """获取知识库统计信息"""
    # 总数和各状态数量
    all_q = select(
        func.count(KnowledgeDocument.id).label("total"),
        func.coalesce(func.sum(KnowledgeDocument.chunk_count), 0).label("chunks"),
        func.coalesce(func.sum(KnowledgeDocument.file_size), 0).label("size"),
    )
    result = await db.execute(all_q)
    row = result.one()

    # 按状态统计
    status_q = select(
        KnowledgeDocument.status,
        func.count(KnowledgeDocument.id)
    ).group_by(KnowledgeDocument.status)
    status_result = await db.execute(status_q)
    by_status = {row[0]: row[1] for row in status_result.all()}

    # 最后摄入时间
    last_q = select(KnowledgeDocument.created_at).where(
        KnowledgeDocument.status == "indexed"
    ).order_by(KnowledgeDocument.created_at.desc()).limit(1)
    last_result = await db.execute(last_q)
    last_ingested = last_result.scalar_one_or_none()

    return KBStatsResponse(
        total_documents=row.total,
        total_chunks=row.chunks,
        total_size_bytes=row.size,
        by_status=by_status,
        last_ingested_at=last_ingested,
    )
