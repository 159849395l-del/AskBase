"""
嵌入模型 — OpenAI 兼容端点（百炼 text-embedding-v3 / 硅基流动等）
"""

from langchain_openai import OpenAIEmbeddings
from app.config import settings


def get_embeddings() -> OpenAIEmbeddings:
    """OpenAI 兼容 embedding 客户端（支持任意端点，通过 .env 配置）"""
    return OpenAIEmbeddings(
        model=settings.EMBEDDING_MODEL,
        api_key=settings.EMBEDDING_API_KEY,
        base_url=settings.EMBEDDING_API_BASE,
        chunk_size=25,  # 百炼 text-embedding 单批次上限
        # langchain-openai 0.3 默认将文本编码为 token ID 发送（OpenAI 新模型支持），
        # 但百炼兼容端点只接受文本输入，必须禁用
        check_embedding_ctx_length=False,
    )
