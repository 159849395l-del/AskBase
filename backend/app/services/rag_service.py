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


def _dedup_chunks(chunks: list, existing_hashes: set) -> tuple:
    """
    按 chunk_hash 对分块去重
    返回 (保留的分块, 跳过的数量)
    - 缺少 chunk_hash 元数据的块视为保留（宁多勿漏，避免误杀数据）
    - 同哈希即同文本（MD5 直接比较，天然不会误杀同哈希不同文本的块）
    """
    kept = []
    skipped = 0
    for chunk in chunks:
        chunk_hash = chunk.metadata.get("chunk_hash")
        if chunk_hash and chunk_hash in existing_hashes:
            skipped += 1
            continue
        kept.append(chunk)
    return kept, skipped


def _invalidate_indexes() -> None:
    """失效 BM25 索引与检索缓存（WP-A 模块未就绪时静默跳过）"""
    try:
        from app.rag.bm25_index import invalidate_bm25_index
        from app.rag.cache import invalidate_retrieval_cache
        invalidate_bm25_index()
        invalidate_retrieval_cache()
    except ImportError:
        pass  # WP-A 模块未就绪时跳过


async def ingest_document(
    file_path: str,
    filename: str,
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
                "chunk_hash": _compute_chunk_hash(chunk.page_content),
                "kb_doc_id": kb_doc_id,
            })

        # 4. 去重：跳过已存在的 chunk_hash（只拉元数据，不拉向量）
        vectorstore = get_vectorstore()
        collection = vectorstore._collection
        existing = collection.get(include=["metadatas"])
        existing_hashes = {
            m["chunk_hash"]
            for m in (existing.get("metadatas") or [])
            if m and m.get("chunk_hash")
        }
        kept, skipped = _dedup_chunks(chunks, existing_hashes)
        if skipped > 0:
            print(f"[rag_service] 去重跳过 {skipped} 个已存在的块（共 {len(chunks)} 个）")

        # 5. 存储到 ChromaDB（分批 embedding）
        batch_size = 10  # 百炼 text-embedding-v3 单批次上限为 10
        for i in range(0, len(kept), batch_size):
            batch = kept[i:i + batch_size]
            vectorstore.add_documents(batch)

        # 6. 更新知识文档记录
        result = await db.execute(
            select(KnowledgeDocument).where(KnowledgeDocument.id == kb_doc_id)
        )
        kb_doc = result.scalar_one_or_none()
        if kb_doc:
            kb_doc.status = "indexed"
            kb_doc.chunk_count = len(kept)
            db.add(kb_doc)
            await db.flush()

        # 7. 失效相关索引与缓存
        _invalidate_indexes()

        return len(kept)

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
    # 删除成功后失效相关索引与缓存
    _invalidate_indexes()


async def rebuild_index(db: AsyncSession) -> int:
    """
    重建索引 — 重新摄入所有已 indexed 的磁盘文档（位于 ./data/uploads）。

    注意：外部来源文档（如 ai_crawl 桥接灌入、无磁盘文件）的向量仍保存在
    ChromaDB 中，本函数不再 reset 整个 collection，避免误删这些爬取内容；
    它们由各自的桥接脚本负责重新灌入，可随时幂等重跑。
    返回重新摄入的 chunk 总数。
    """
    # 重建前先失效旧索引与缓存
    _invalidate_indexes()

    # 获取所有 indexed 状态的文档
    result = await db.execute(
        select(KnowledgeDocument).where(KnowledgeDocument.status == "indexed")
    )
    docs = result.scalars().all()

    if not docs:
        return 0

    vectorstore = get_vectorstore()
    splitter = get_text_splitter()

    # 重新摄入
    total_chunks = 0

    for kb_doc in docs:
        file_path = os.path.join("./data/uploads", kb_doc.filename)
        if not os.path.exists(file_path):
            # 无磁盘文件：外部来源文档（如 ai_crawl 桥接灌入），其向量仍在
            # ChromaDB 中，保留不动，不参与本次基于磁盘的重建。
            continue

        try:
            # 先删除该文档的旧块（按 kb_doc_id），保证重建结果幂等
            await delete_kb_document_chunks(kb_doc.id)

            raw_docs = load_document(file_path)
            chunks = splitter.split_documents(raw_docs)

            for i, chunk in enumerate(chunks):
                chunk.metadata.update({
                    "source_file": file_path,
                    "filename": kb_doc.filename,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "chunk_hash": _compute_chunk_hash(chunk.page_content),
                    "kb_doc_id": kb_doc.id,
                })

            batch_size = 10  # 百炼 text-embedding-v3 单批次上限为 10
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

    # 重建完成后再次失效，确保索引/缓存与最新数据一致
    _invalidate_indexes()
    return total_chunks
