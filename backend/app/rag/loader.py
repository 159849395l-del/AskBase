"""
文档加载器 — 多格式文件分发加载
"""

from langchain_community.document_loaders import (
    TextLoader,
    PyPDFLoader,
    CSVLoader,
    UnstructuredExcelLoader,
    UnstructuredWordDocumentLoader,
)
from langchain_core.documents import Document
from typing import List
import os


LOADER_MAP = {
    ".txt": "text",
    ".md": "text",
    ".pdf": "pdf",
    ".csv": "csv",
    ".xlsx": "excel",
    ".docx": "word",
}


def detect_file_type(file_path: str) -> str:
    """根据扩展名检测文件类型"""
    ext = os.path.splitext(file_path)[1].lower()
    return LOADER_MAP.get(ext, "unknown")


def load_document(file_path: str) -> List[Document]:
    """根据文件类型加载文档"""
    file_type = detect_file_type(file_path)
    ext = os.path.splitext(file_path)[1].lower()

    if file_type == "text":
        loader = TextLoader(file_path, encoding="utf-8")
    elif file_type == "pdf":
        loader = PyPDFLoader(file_path)
    elif file_type == "csv":
        loader = CSVLoader(file_path, encoding="utf-8")
    elif file_type == "excel":
        loader = UnstructuredExcelLoader(file_path, mode="elements")
    elif file_type == "word":
        loader = UnstructuredWordDocumentLoader(file_path)
    else:
        raise ValueError(f"不支持的文件类型: {ext}")

    return loader.load()
