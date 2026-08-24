"""
知识库管理 API — 仅管理员可访问
"""

from fastapi import APIRouter, Depends, UploadFile, File, Form, Query, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models.user import User
from app.models.knowledge_document import KnowledgeDocument
from app.core.dependencies import get_admin_user
from app.services.kb_service import list_documents, get_document_detail, delete_document, get_kb_stats
from app.services.rag_service import ingest_document, rebuild_index
from app.schemas.kb import (
    DocumentListResponse,
    DocumentItem,
    KBStatsResponse,
    KBSearchResponse,
    KBSearchResult,
    QAItemCreate,
    QAItemUpdate,
    QAItem,
    QAItemListResponse,
)
from app.schemas.auth import MessageResponse
from app.config import settings
from app.rag.retriever import retrieve_with_scores
import os
import sys
import uuid
import asyncio
from typing import Optional

router = APIRouter(prefix="/api/kb", tags=["知识库管理"])

# 爬虫数据摄入锁：同一时间只允许一个同步任务
_ingest_lock: asyncio.Lock | None = None


def _get_ingest_lock() -> asyncio.Lock:
    global _ingest_lock
    if _ingest_lock is None:
        _ingest_lock = asyncio.Lock()
    return _ingest_lock


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
    if len(contents) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件内容为空，无法上传",
        )
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
    kb_id: Optional[int] = Query(None, description="限定所属知识库"),
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """获取知识文档列表"""
    items, total = await list_documents(db, page, page_size, status, kb_id)
    return DocumentListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/documents/upload", response_model=DocumentItem, status_code=201)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    kb_id: int = Form(..., description="所属知识库 ID（A 类文档型）"),
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """上传文档并后台异步向量化（必须指定所属知识库）"""
    # 校验知识库存在且为文档型
    from app.models.knowledge_base import KnowledgeBase
    from sqlalchemy import select as sa_select

    kb = (
        await db.execute(sa_select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
    ).scalar_one_or_none()
    if kb is None:
        raise HTTPException(status_code=404, detail="知识库不存在")
    if kb.type != "document":
        raise HTTPException(status_code=400, detail="只有文档型知识库可以上传文档")

    # 保存文件
    file_path, saved_filename = await _save_upload_file(file)

    # 创建数据库记录
    kb_doc = KnowledgeDocument(
        filename=saved_filename,
        file_type=os.path.splitext(file.filename or "")[1].lower().lstrip("."),
        file_size=os.path.getsize(file_path),
        uploaded_by=current_user.id,
        kb_id=kb_id,
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
        kb_doc_id=kb_doc.id,
        kb_id=kb_id,
    )

    return DocumentItem(
        id=kb_doc.id,
        filename=kb_doc.filename,
        file_type=kb_doc.file_type,
        file_size=kb_doc.file_size,
        chunk_count=0,
        status="processing",
        created_at=kb_doc.created_at,
    )


async def _background_ingest(file_path: str, filename: str, kb_doc_id: int, kb_id: int):
    """后台任务：文档向量化摄入"""
    from app.database import async_session_factory
    async with async_session_factory() as db:
        try:
            await ingest_document(file_path, filename, kb_doc_id, db, kb_id=kb_id)
            await db.commit()
            print(f"[Ingest] 文档 {filename} 摄入成功 (kb={kb_id})")
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


@router.post("/ingest-crawl", response_model=MessageResponse)
async def ingest_crawl_data(
    current_user: User = Depends(get_admin_user),
):
    """同步爬虫数据到知识库：读取 ai_crawl 的 MySQL 有效结果，切分+向量化后摄入 ChromaDB（幂等增量）

    实际执行 backend/scripts/ingest_from_aicrawl.py（同一桥接脚本），阻塞等待完成。
    """
    async with _get_ingest_lock():
        # backend 根目录 = app/api/kb.py 向上两级
        backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        script = os.path.join(backend_dir, "scripts", "ingest_from_aicrawl.py")
        if not os.path.exists(script):
            raise HTTPException(status_code=500, detail=f"桥接脚本不存在: {script}")

        proc = await asyncio.create_subprocess_exec(
            sys.executable, script,
            cwd=backend_dir,  # 脚本依赖 cwd 加载 .env 与相对路径
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await proc.communicate()
        output = stdout.decode("utf-8", errors="replace")

        if proc.returncode != 0:
            raise HTTPException(status_code=500, detail=f"同步失败:\n{output[-1000:]}")

        # 提取关键结果行（摄入统计）
        tail = [l for l in output.splitlines() if l.strip()][-15:]
        summary = "\n".join(tail)
        return MessageResponse(message=f"同步完成\n{summary}")


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

    top_k: int = Query(5, ge=1, le=20),
    current_user: User = Depends(get_admin_user),
):
    """直接语义搜索知识库（调试用）"""
    docs_with_scores = await retrieve_with_scores(
        q, top_k=top_k
    )
    results = [
        KBSearchResult(
            chunk_text=doc.page_content[:500],
            filename=doc.metadata.get("filename", "未知"),
            similarity_score=round(score, 4),
            score_type=doc.metadata.get("_score_type", "vector"),

            metadata=doc.metadata,
        )
        for doc, score in docs_with_scores
    ]
    return KBSearchResponse(results=results)


# ---------- 问答集（A 类知识库子资源） ----------

@router.get("/qa", response_model=QAItemListResponse)
async def list_qa(
    kb_id: int = Query(..., description="所属知识库 ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """问答集列表"""
    from app.models.qa_item import QAItem as QAModel

    total = (
        await db.execute(
            select(func.count(QAModel.id)).where(QAModel.kb_id == kb_id)
        )
    ).scalar() or 0
    q = (
        select(QAModel)
        .where(QAModel.kb_id == kb_id)
        .order_by(QAModel.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = (await db.execute(q)).scalars().all()
    return QAItemListResponse(items=[QAItem.model_validate(x) for x in items], total=total)


@router.post("/qa", response_model=QAItem, status_code=201)
async def create_qa(
    body: QAItemCreate,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """录入一条问答并摄入向量（同步完成）"""
    from app.models.qa_item import QAItem as QAModel
    from app.models.knowledge_base import KnowledgeBase

    kb = (
        await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == body.kb_id))
    ).scalar_one_or_none()
    if kb is None:
        raise HTTPException(status_code=404, detail="知识库不存在")
    if kb.type != "document":
        raise HTTPException(status_code=400, detail="只有文档型知识库支持问答集")

    item = QAModel(
        kb_id=body.kb_id,
        question=body.question.strip(),
        answer=body.answer.strip(),
        created_by=current_user.id,
    )
    db.add(item)
    await db.flush()
    await db.refresh(item)

    # 同步摄入 Chroma（结构化条目）
    from app.services.rag_service import ingest_structured_item

    await ingest_structured_item(
        kb_id=item.kb_id,
        kind="qa",
        item_id=item.id,
        title=item.question,
        content=item.answer,
    )
    return QAItem.model_validate(item)


@router.put("/qa/{qa_id}", response_model=QAItem)
async def update_qa(
    qa_id: int,
    body: QAItemUpdate,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """更新问答（先删旧向量，再重新摄入）"""
    from app.models.qa_item import QAItem as QAModel
    from app.services.rag_service import ingest_structured_item, delete_structured_item_chunks

    item = (await db.execute(select(QAModel).where(QAModel.id == qa_id))).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="问答不存在")

    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(item, k, v.strip() if isinstance(v, str) else v)
    await db.flush()
    await db.refresh(item)

    await delete_structured_item_chunks("qa", item.id)
    await ingest_structured_item(
        kb_id=item.kb_id,
        kind="qa",
        item_id=item.id,
        title=item.question,
        content=item.answer,
    )
    return QAItem.model_validate(item)


@router.delete("/qa/{qa_id}", response_model=MessageResponse)
async def delete_qa(
    qa_id: int,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """删除问答（连带删除向量）"""
    from app.models.qa_item import QAItem as QAModel
    from app.services.rag_service import delete_structured_item_chunks

    item = (await db.execute(select(QAModel).where(QAModel.id == qa_id))).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="问答不存在")
    await delete_structured_item_chunks("qa", item.id)
    await db.delete(item)
    await db.flush()
    return MessageResponse(message="问答已删除")
