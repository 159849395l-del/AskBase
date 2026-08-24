"""测试检索缓存 — TTL 过期、最旧淘汰、清空与模块级单例"""

import pytest

from app.rag.cache import TTLCache, invalidate_retrieval_cache, retrieval_cache


class TestTTLCache:
    """TTLCache — set/get/过期/淘汰/clear"""

    def test_set_get(self):
        """场景：写入后读取 → 返回原值"""
        cache = TTLCache(ttl=300)
        cache.set("key", [1, 2, 3])

        assert cache.get("key") == [1, 2, 3]

    def test_get_不存在的键_返回None(self):
        """场景：键未写入 → 返回 None"""
        cache = TTLCache(ttl=300)

        assert cache.get("missing") is None

    def test_ttl过期_返回None(self):
        """场景：注入必然过期的 ttl → 读取返回 None（惰性删除）"""
        cache = TTLCache(ttl=-1)  # 过期时间必然早于当前
        cache.set("key", "value")

        assert cache.get("key") is None

    def test_未过期_正常返回(self):
        """场景：TTL 内读取 → 返回原值"""
        cache = TTLCache(ttl=300)
        cache.set("key", "value")

        assert cache.get("key") == "value"

    def test_max_entries_淘汰最旧(self):
        """场景：超过 max_entries → 淘汰最早写入的条目"""
        cache = TTLCache(ttl=300, max_entries=2)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)  # 超出上限，淘汰最早写入的 "a"

        assert cache.get("a") is None
        assert cache.get("b") == 2
        assert cache.get("c") == 3
        assert len(cache) == 2

    def test_clear_清空全部(self):
        """场景：clear → 所有键失效"""
        cache = TTLCache(ttl=300)
        cache.set("a", 1)
        cache.set("b", 2)

        cache.clear()

        assert len(cache) == 0
        assert cache.get("a") is None
        assert cache.get("b") is None


class TestRetrievalCache:
    """模块级检索缓存单例 — retrieval_cache / invalidate_retrieval_cache"""

    def test_单例_可读写(self):
        """场景：模块级缓存 → 可正常读写"""
        retrieval_cache.set("q", [(None, 0.5)])

        assert retrieval_cache.get("q") == [(None, 0.5)]
        retrieval_cache.clear()

    def test_invalidate_清空缓存(self):
        """场景：invalidate_retrieval_cache → 缓存被清空"""
        retrieval_cache.set("k", "v")

        invalidate_retrieval_cache()

        assert retrieval_cache.get("k") is None
