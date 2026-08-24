"""robots.txt 策略"""
import asyncio
import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser


class RobotsPolicy:
    def __init__(self, user_agent: str = "AICrawlBot/1.0"):
        self._user_agent = user_agent
        self._cache: dict[str, tuple[RobotFileParser, float]] = {}
        self._cache_ttl = 3600

    async def is_allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        now = time.time()
        if base in self._cache:
            rp, cached_at = self._cache[base]
            if now - cached_at < self._cache_ttl:
                return rp.can_fetch(self._user_agent, url)
        rp = RobotFileParser()
        rp.set_url(f"{base}/robots.txt")
        try:
            await asyncio.to_thread(rp.read)
        except Exception:
            self._cache[base] = (rp, now)
            return True
        self._cache[base] = (rp, now)
        return rp.can_fetch(self._user_agent, url)
