"""双通道抓取器"""
import asyncio
import time
from typing import Optional
from dataclasses import dataclass
import httpx
from playwright.async_api import async_playwright, Browser
from app.crawler.config import CRAWLER_STATIC_TIMEOUT_MS, CRAWLER_MAX_RETRIES


@dataclass
class FetchedPage:
    url: str
    final_url: str
    html: Optional[str] = None
    http_status: int = 0
    content_type: Optional[str] = None
    charset: Optional[str] = None
    fetch_time_ms: int = 0
    error_message: Optional[str] = None
    ok: bool = False


SPA_PATTERNS = [
    "<div id=\"app\"", "<div id=\"root\"", "<div id=\"__nuxt\"",
    "__nuxt__", "__next_data__", "__NEXT_DATA__", "createapp(", "createroot(",
    "data-server-rendered", "window.__initial_state__", "window.__PRELOADED_STATE__",
]


class StaticHttpFetcher:
    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(CRAWLER_STATIC_TIMEOUT_MS / 1000),
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                },
                max_redirects=10,
            )
        return self._client

    async def fetch(self, url: str) -> FetchedPage:
        start = time.monotonic()
        client = await self._get_client()
        for attempt in range(CRAWLER_MAX_RETRIES):
            try:
                resp = await client.get(url)
                elapsed = int((time.monotonic() - start) * 1000)
                html = resp.text if resp.status_code < 400 else None
                return FetchedPage(
                    url=url, final_url=str(resp.url), html=html,
                    http_status=resp.status_code, content_type=resp.headers.get("content-type", ""),
                    charset=resp.encoding or "utf-8", fetch_time_ms=elapsed,
                    ok=resp.status_code < 400 and html is not None,
                )
            except Exception as e:
                if attempt < CRAWLER_MAX_RETRIES - 1:
                    await asyncio.sleep(1 * (attempt + 1))
                else:
                    elapsed = int((time.monotonic() - start) * 1000)
                    return FetchedPage(url=url, final_url=url, http_status=0, fetch_time_ms=elapsed, error_message=str(e), ok=False)

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None


class PlaywrightFetcher:
    def __init__(self):
        self._browser: Optional[Browser] = None
        self._available = False
        self._checked = False

    async def is_available(self) -> bool:
        # 失败过一次则缓存，避免每页都尝试启动浏览器拖慢爬取
        if self._checked:
            return self._available
        self._checked = True
        try:
            if self._browser is None:
                p = await async_playwright().start()
                self._browser = await p.chromium.launch(headless=True)
                self._available = True
            return True
        except Exception:
            self._available = False
            return False

    async def fetch(self, url: str, timeout_ms: int = 30000) -> FetchedPage:
        start = time.monotonic()
        if not await self.is_available():
            return FetchedPage(url=url, final_url=url, ok=False, error_message="Playwright 不可用")
        try:
            page = await self._browser.new_page()
            await page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            html = await page.content()
            final_url = page.url
            elapsed = int((time.monotonic() - start) * 1000)
            await page.close()
            return FetchedPage(url=url, final_url=final_url, html=html, http_status=200, fetch_time_ms=elapsed, ok=True)
        except Exception as e:
            elapsed = int((time.monotonic() - start) * 1000)
            return FetchedPage(url=url, final_url=url, http_status=0, fetch_time_ms=elapsed, error_message=str(e), ok=False)

    async def close(self):
        if self._browser:
            await self._browser.close()
            self._browser = None
            self._available = False


class CrawlerRouter:
    @staticmethod
    def decide(url: str, plan_hint: Optional[str], static_result: FetchedPage) -> str:
        if plan_hint and plan_hint.upper() in ("JS", "JS_RENDER"):
            return "JS_RENDER"
        if static_result.ok and static_result.html:
            html_lower = static_result.html.lower()
            for pattern in SPA_PATTERNS:
                if pattern in html_lower:
                    return "JS_RENDER"
        return "STATIC"
