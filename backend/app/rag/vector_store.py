"""
向量存储配置 — ChromaDB 持久化，单例模式
"""

from langchain_chroma import Chroma
from app.config import settings
from app.rag.embeddings import get_embeddings
from typing import Optional

# 全局向量存储实例
_vectorstore: Optional[Chroma] = None


def get_vectorstore() -> Chroma:
    """获取 ChromaDB 向量存储实例（懒加载单例）"""
    global _vectorstore
    if _vectorstore is None:
        embeddings = get_embeddings()
        _vectorstore = Chroma(
            collection_name=settings.CHROMA_COLLECTION_NAME,
            embedding_function=embeddings,
            persist_directory=settings.CHROMA_PERSIST_DIR,
        )
    return _vectorstore


def reset_vectorstore():
    """重置向量存储实例（重新索引时使用）"""
    global _vectorstore
    _vectorstore = None
