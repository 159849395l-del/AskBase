"""
系统 API — 健康检查
"""

from fastapi import APIRouter
from app.config import settings

router = APIRouter(tags=["系统"])


@router.get("/api/health")
async def health_check():
    """健康检查 — 返回服务和 API 连接状态"""
    health = {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "llm": settings.LLM_MODEL if settings.LLM_API_KEY else "not_configured",
        "embedding": settings.EMBEDDING_MODEL if settings.EMBEDDING_API_KEY else "not_configured",
        "chromadb": settings.CHROMA_PERSIST_DIR,
        "database": settings.DATABASE_URL.split("://")[0],
    }
    return health

