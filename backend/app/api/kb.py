"""
知识库管理 API — 仅管理员可访问
"""

from fastapi import APIRouter, Depends, UploadFile, File, Form, Query, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.user import User
from app.models.knowledge_document import KnowledgeDocument
from app.core.dependencies import get_admin_user
from app.services.kb_service import list_documents, get_document_detail, delete_document, get_kb_stats
from app.services.rag_service import ingest_document, rebuild_index
from app.schemas.kb import DocumentListResponse, DocumentItem, KBStatsResponse, KBSearchResponse, KBSearchResult
from app.schemas.auth import MessageResponse
from app.config import settings
from app.rag.retriever import retrieve_similar_chunks
import os
import uuid
from typing import Optional

router = APIRouter(prefix="/api/kb", tags=["知识库管理"])


async def _save_upload_file(file: UploadFile) -> tuple:
    """保存上传文件到本地，返回 (file_path, filename)"""
    # 验证扩展名
    ext = os.path.splitext(file.filename or "")[1].lower().lstrip(".")
    if ext not in settings.allowed_extensions_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件类型: .{ext}，允许的类型: {settings.ALLOWED_EXTENSIONS}",
        )

    # 验证文件大小
    contents = await file.read()
    if len(contents) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"文件大小超过限制 ({settings.MAX_UPLOAD_SIZE_MB}MB)",
        )

    # 生成唯一文件名
    unique_name = f"{uuid.uuid4().hex}_{file.filename}"
    upload_dir = "./data/uploads"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, unique_name)

    with open(file_path, "wb") as f:
        f.write(contents)

    return file_path, unique_name


@router.get("/documents", response_model=DocumentListResponse)
async def list_docs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """获取知识文档列表"""
    items, total = await list_documents(db, page, page_size, status, category)
    return DocumentListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/documents/upload", response_model=DocumentItem, status_code=201)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    product_category: Optional[str] = Form(None),
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """上传文档并后台异步向量化"""
    # 保存文件
    file_path, saved_filename = await _save_upload_file(file)

    # 创建数据库记录
    kb_doc = KnowledgeDocument(
        filename=saved_filename,
        file_type=os.path.splitext(file.filename or "")[1].lower().lstrip("."),
        file_size=os.path.getsize(file_path),
        product_category=product_category,
        uploaded_by=current_user.id,
        status="processing",
    )
    db.add(kb_doc)
    await db.flush()
    await db.refresh(kb_doc)

    # 后台异步摄入
    background_tasks.add_task(
        _background_ingest,
        file_path=file_path,
        filename=saved_filename,
        product_category=product_category,
        kb_doc_id=kb_doc.id,
    )

    return DocumentItem(
        id=kb_doc.id,
        filename=kb_doc.filename,
        file_type=kb_doc.file_type,
        file_size=kb_doc.file_size,
        chunk_count=0,
        status="processing",
        product_category=kb_doc.product_category,
        created_at=kb_doc.created_at,
    )


async def _background_ingest(file_path: str, filename: str, product_category: Optional[str], kb_doc_id: int):
    """后台任务：文档向量化摄入"""
    from app.database import async_session_factory
    async with async_session_factory() as db:
        try:
            await ingest_document(file_path, filename, product_category, kb_doc_id, db)
            await db.commit()
            print(f"[Ingest] 文档 {filename} 摄入成功")
        except Exception as e:
            await db.rollback()
            print(f"[Ingest] 文档 {filename} 摄入失败: {e}")


@router.get("/documents/{doc_id}", response_model=DocumentItem)
async def get_doc(
    doc_id: int,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """获取文档详情"""
    return await get_document_detail(db, doc_id)


@router.delete("/documents/{doc_id}", response_model=MessageResponse)
async def delete_doc(
    doc_id: int,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """删除知识文档及其向量"""
    await delete_document(db, doc_id)
    return MessageResponse(message="文档已删除")


@router.post("/reindex", response_model=MessageResponse)
async def reindex(
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """重建全量索引"""
    total = await rebuild_index(db)
    return MessageResponse(message=f"重建索引完成，共处理 {total} 个文本块")


@router.get("/stats", response_model=KBStatsResponse)
async def kb_stats(
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """获取知识库统计信息"""
    return await get_kb_stats(db)


@router.get("/search", response_model=KBSearchResponse)
async def kb_search(
    q: str = Query(..., min_length=1),
    category: Optional[str] = Query(None),
    top_k: int = Query(5, ge=1, le=20),
    current_user: User = Depends(get_admin_user),
):
    """直接语义搜索知识库（调试用）"""
    docs = await retrieve_similar_chunks(q, top_k=top_k, product_category=category)
    results = [
        KBSearchResult(
            chunk_text=doc.page_content[:500],
            filename=doc.metadata.get("filename", "未知"),
            similarity_score=0.0,  # 简化版不返回分数
            metadata=doc.metadata,
        )
        for doc in docs
    ]
    return KBSearchResponse(results=results)
