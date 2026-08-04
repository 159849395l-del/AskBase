"""
RAG 编排服务 — 文档摄入、检索、生成的全流程协调
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional, Dict, Any, AsyncIterator
import hashlib
import os

from app.rag.loader import load_document
from app.rag.splitter import get_text_splitter
from app.rag.vector_store import get_vectorstore, reset_vectorstore
from app.rag.retriever import retrieve_similar_chunks, retrieve_with_scores
from app.rag.chain import stream_rag_response, generate_rag_response
from app.models.knowledge_document import KnowledgeDocument
from app.config import settings


def _compute_chunk_hash(text: str) -> str:
    """计算文本块的 MD5 哈希用于去重"""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


async def ingest_document(
    file_path: str,
    filename: str,
    product_category: Optional[str],
    kb_doc_id: int,
    db: AsyncSession,
) -> int:
    """
    摄入单个文档到知识库
    返回 chunk 数量
    """
    try:
        # 1. 加载文档
        raw_docs = load_document(file_path)

        # 2. 分割文本
        splitter = get_text_splitter()
        chunks = splitter.split_documents(raw_docs)

        # 3. 元数据丰富
        for i, chunk in enumerate(chunks):
            chunk.metadata.update({
                "source_file": file_path,
                "filename": filename,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "product_category": product_category or "",
                "chunk_hash": _compute_chunk_hash(chunk.page_content),
                "kb_doc_id": kb_doc_id,
            })

        # 4. 存储到 ChromaDB（分批 embedding）
        vectorstore = get_vectorstore()
        batch_size = 25  # 百炼 API 单批次限制
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            vectorstore.add_documents(batch)

        # 5. 更新知识文档记录
        result = await db.execute(
            select(KnowledgeDocument).where(KnowledgeDocument.id == kb_doc_id)
        )
        kb_doc = result.scalar_one_or_none()
        if kb_doc:
            kb_doc.status = "indexed"
            kb_doc.chunk_count = len(chunks)
            db.add(kb_doc)
            await db.flush()

        return len(chunks)

    except Exception as e:
        # 标记为失败
        result = await db.execute(
            select(KnowledgeDocument).where(KnowledgeDocument.id == kb_doc_id)
        )
        kb_doc = result.scalar_one_or_none()
        if kb_doc:
            kb_doc.status = "failed"
            kb_doc.error_message = str(e)
            db.add(kb_doc)
            await db.flush()
        raise


async def delete_kb_document_chunks(kb_doc_id: int) -> None:
    """删除指定知识文档的所有 ChromaDB 向量"""
    vectorstore = get_vectorstore()
    # ChromaDB 按 metadata 过滤删除
    collection = vectorstore._collection
    collection.delete(where={"kb_doc_id": kb_doc_id})


async def rebuild_index(db: AsyncSession) -> int:
    """
    重建全量索引 — 清空 ChromaDB 并重新摄入所有已 indexed 的文档
    返回重新摄入的 chunk 总数
    """
    # 获取所有 indexed 状态的文档
    result = await db.execute(
        select(KnowledgeDocument).where(KnowledgeDocument.status == "indexed")
    )
    docs = result.scalars().all()

    if not docs:
        return 0

    # 重置向量存储
    reset_vectorstore()
    vectorstore = get_vectorstore()

    # 重新摄入
    total_chunks = 0
    splitter = get_text_splitter()

    for kb_doc in docs:
        try:
            file_path = os.path.join("./data/uploads", kb_doc.filename)
            if not os.path.exists(file_path):
                continue

            raw_docs = load_document(file_path)
            chunks = splitter.split_documents(raw_docs)

            for i, chunk in enumerate(chunks):
                chunk.metadata.update({
                    "source_file": file_path,
                    "filename": kb_doc.filename,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "product_category": kb_doc.product_category or "",
                    "chunk_hash": _compute_chunk_hash(chunk.page_content),
                    "kb_doc_id": kb_doc.id,
                })

            batch_size = 25
            for i in range(0, len(chunks), batch_size):
                batch = chunks[i:i + batch_size]
                vectorstore.add_documents(batch)

            kb_doc.chunk_count = len(chunks)
            total_chunks += len(chunks)
            db.add(kb_doc)

        except Exception as e:
            kb_doc.status = "failed"
            kb_doc.error_message = str(e)
            db.add(kb_doc)

    await db.flush()
    return total_chunks
