"""域级限速器"""
import asyncio
import time
from collections import defaultdict
from urllib.parse import urlparse
from app.crawler.config import CRAWLER_RATE_LIMIT_MS


class RateLimiter:
    def __init__(self, min_interval_ms: int = CRAWLER_RATE_LIMIT_MS):
        self._min_interval = min_interval_ms / 1000
        self._last_access: dict[str, float] = defaultdict(float)

    async def acquire(self, url: str):
        domain = urlparse(url).netloc.lower()
        now = time.monotonic()
        elapsed = now - self._last_access[domain]
        if elapsed < self._min_interval:
            await asyncio.sleep(self._min_interval - elapsed)
        self._last_access[domain] = time.monotonic()
