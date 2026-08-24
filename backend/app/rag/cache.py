"""
检索结果缓存 — TTL 过期 + 最大条目数的进程内缓存（惰性过期、最旧淘汰）
"""

import time
from typing import Any, Dict, Optional, Tuple

from app.config import settings


class TTLCache:
    """简单的 TTL 缓存：惰性过期删除 + 超限时淘汰最旧条目"""

    def __init__(self, ttl: float = 300, max_entries: int = 256):
        self.ttl = ttl
        self.max_entries = max_entries
        # key -> (expire_at, value)
        self._data: Dict[Any, Tuple[float, Any]] = {}

    def get(self, key: Any) -> Optional[Any]:
        """读取缓存；条目已过期则惰性删除并返回 None"""
        item = self._data.get(key)
        if item is None:
            return None
        expire_at, value = item
        if time.monotonic() > expire_at:
            del self._data[key]
            return None
        return value

    def set(self, key: Any, value: Any) -> None:
        """写入缓存；超出 max_entries 时淘汰最早写入的条目"""
        expire_at = time.monotonic() + self.ttl
        self._data[key] = (expire_at, value)

        if self.max_entries > 0 and len(self._data) > self.max_entries:
            # 淘汰最早过期（即最早写入）的条目
            oldest_key = min(self._data, key=lambda k: self._data[k][0])
            del self._data[oldest_key]

    def clear(self) -> None:
        """清空缓存"""
        self._data.clear()

    def __len__(self) -> int:
        return len(self._data)


# 模块级检索缓存单例
retrieval_cache = TTLCache(
    ttl=settings.CACHE_TTL,
    max_entries=settings.CACHE_MAX_ENTRIES,
)


def invalidate_retrieval_cache() -> None:
    """清空检索缓存（知识库内容变更后调用）"""
    retrieval_cache.clear()
