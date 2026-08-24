"""
中文分词器 — jieba 分词，jieba 缺失时零依赖降级为字符 bigram
"""

import re
from typing import Callable, List

from app.config import settings

# 单字停用词（过滤常见无信息量的单字）
_STOPWORDS = {
    "的", "了", "和", "是", "在", "有", "我", "你", "他", "她", "它",
    "这", "那", "就", "都", "而", "及", "与", "或", "之", "于", "以", "被",
    "把", "向", "从", "到", "等", "个", "种", "来", "去", "也", "又", "还",
}

# 纯标点/空白字符（含中英文标点与空格）
_PUNCT_RE = re.compile(r"^[^\w]+$", re.UNICODE)

# CJK 单字符（仅补充中文单字 token，不拆英文单词）
_CJK_CHAR_RE = re.compile(r"^[一-鿿]$")

# jieba 可选依赖：导入失败时自动降级为 char_bigram
try:
    import jieba

    _JIEBA_AVAILABLE = True
except ImportError:
    _JIEBA_AVAILABLE = False


def _is_punct(char: str) -> bool:
    """判断单个字符是否为标点或空白"""
    return bool(_PUNCT_RE.match(char))


def _jieba_tokens(text: str) -> List[str]:
    """jieba 分词：过滤空白、纯标点 token 和单字停用词，并补充 CJK 单字 token

    补充单字的意义：查询"洗"能命中文档中的"洗涤/干洗"（jieba 将两者切成不同
    词，但单字"洗"是重叠的），显著提升口语短查询的召回率。
    """
    tokens = jieba.lcut(text)
    result: List[str] = []
    for token in tokens:
        if not token.strip() or _PUNCT_RE.match(token):
            continue
        if len(token) == 1 and token in _STOPWORDS:
            continue
        result.append(token)
        # 补充 CJK 单字（过滤停用词），英文/数字 token 不拆
        for ch in token:
            if _CJK_CHAR_RE.match(ch) and ch not in _STOPWORDS:
                result.append(ch)
    # 去重保序（同一字符重复出现只算一个 token）
    return list(dict.fromkeys(result))


def _char_bigram_tokens(text: str) -> List[str]:
    """字符 bigram 分词（零依赖降级方案）：去空白标点后生成相邻字符二元组"""
    chars = [ch for ch in text if ch.strip() and not _is_punct(ch)]
    return ["".join(pair) for pair in zip(chars, chars[1:])]


def tokenize(text: str, mode: str = "jieba") -> List[str]:
    """将文本切分为 token 列表

    mode 支持：
    - "jieba": jieba 分词（缺失时自动降级为 char_bigram）
    - "char_bigram": 字符二元组（零依赖）
    """
    if not text or not text.strip():
        return []

    if mode == "char_bigram":
        return _char_bigram_tokens(text)

    if mode == "jieba":
        if _JIEBA_AVAILABLE:
            return _jieba_tokens(text)
        # jieba 未安装时自动降级
        return _char_bigram_tokens(text)

    raise ValueError(f"未知分词模式: {mode!r}")


def get_tokenizer() -> Callable[[str], List[str]]:
    """按 settings.BM25_TOKENIZER 返回分词函数"""
    mode = settings.BM25_TOKENIZER
    return lambda text: tokenize(text, mode=mode)
