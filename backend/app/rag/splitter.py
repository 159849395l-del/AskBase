"""
文本分割器配置 — 中文感知的递归字符分割
"""

from langchain.text_splitter import RecursiveCharacterTextSplitter
from app.config import settings


def get_text_splitter() -> RecursiveCharacterTextSplitter:
    """获取中文感知的文本分割器"""
    return RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
        # 中文感知分隔符：段落 → 换行 → 句子结束 → 分号 → 逗号 → 空格 → 字符
        separators=["\n\n", "\n", "。", "；", "，", " ", ""],
        length_function=len,
    )
