"""测试中文分词器 — jieba 与 char_bigram 两种模式"""

import pytest

from app.config import settings
from app.rag.tokenizer import get_tokenizer, tokenize


class TestTokenize:
    """分词器 — tokenize"""

    def test_jieba模式_中文分词正确(self):
        """场景：中文句子 → jieba 切出有意义的多字词"""
        tokens = tokenize("这款手机电池续航很长，价格实惠。", mode="jieba")

        # 注意：jieba 可能将"手机电池"合并为单个 token，此处按子串覆盖断言
        assert any("手机" in token for token in tokens)
        assert any("电池" in token for token in tokens)
        assert "续航" in tokens
        assert "价格" in tokens
        assert "实惠" in tokens

    def test_char_bigram模式_生成相邻字符二元组(self):
        """场景：中文句子 → 生成保持原序的相邻字符二元组"""
        tokens = tokenize("这款手机电池续航很长，价格实惠。", mode="char_bigram")

        assert "手机" in tokens
        assert "电池" in tokens
        assert "价格" in tokens
        assert "实惠" in tokens
        assert "机手" not in tokens  # 二元组保持字符原序

    def test_标点_被过滤(self):
        """场景：句号逗号感叹号 → 从 token 结果中剔除"""
        tokens = tokenize("你好，世界！欢迎。", mode="jieba")

        assert "，" not in tokens
        assert "！" not in tokens
        assert "。" not in tokens
        assert "欢迎" in tokens

    def test_标点_在char_bigram模式也被过滤(self):
        """场景：标点符号 → char_bigram 模式同样剔除后再组词"""
        tokens = tokenize("你好，世界！欢迎。", mode="char_bigram")

        assert "你好" in tokens
        assert "世界" in tokens
        assert "欢迎" in tokens
        assert "，!" not in tokens

    def test_英文混合文本_正常分词(self):
        """场景：中英文混合 → jieba 正常处理"""
        tokens = tokenize("iPhone 15 电池容量很大", mode="jieba")

        assert "iPhone" in tokens
        assert any("电池" in token for token in tokens)
        assert len(tokens) > 0

    def test_jieba模式_补充CJK单字(self):
        """场景：中文分词 → 补充单字 token（"洗"能命中"洗涤/干洗"）"""
        tokens = tokenize("衣服怎么洗", mode="jieba")

        assert "洗" in tokens
        assert "衣" in tokens
        assert "服" in tokens
        assert "衣服" in tokens

    def test_jieba模式_英文单词不拆单字母(self):
        """场景：英文单词 → 不补充单字母 token（避免噪声匹配）"""
        tokens = tokenize("iPhone 15 Pro", mode="jieba")

        assert "iPhone" in tokens
        assert not any(len(t) == 1 and t.isascii() for t in tokens)

    def test_jieba模式_单字停用词不补充(self):
        """场景：单字停用词（的/了/是）→ 既不保留也不补充为单字"""
        tokens = tokenize("衣服是新的", mode="jieba")

        assert "是" not in tokens

    def test_空串_返回空列表(self):
        """场景：空字符串 / 纯空白 → 返回空列表"""
        assert tokenize("") == []
        assert tokenize("   ") == []


class TestGetTokenizer:
    """分词函数获取 — get_tokenizer"""

    def test_返回可调用对象(self):
        """场景：默认配置（jieba）→ 返回可调用的分词函数"""
        tokenizer = get_tokenizer()

        assert callable(tokenizer)
        tokens = tokenizer("这款手机")
        assert isinstance(tokens, list)
        assert "手机" in tokens

    def test_按配置模式_返回对应分词器(self):
        """场景：BM25_TOKENIZER=char_bigram → 返回 bigram 分词函数"""
        original = settings.BM25_TOKENIZER
        try:
            settings.BM25_TOKENIZER = "char_bigram"
            tokenizer = get_tokenizer()

            tokens = tokenizer("这款手机")
            assert "手机" in tokens
            assert "机手" not in tokens
        finally:
            settings.BM25_TOKENIZER = original
