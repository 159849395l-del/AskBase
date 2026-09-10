"""HTML 清洗"""
import re
from datetime import datetime
from typing import List
from dataclasses import dataclass, field
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from app.crawler.utils import normalize, is_static_asset, is_wechat_article


@dataclass
class Link:
    url: str
    anchor_text: str


@dataclass
class CleanResult:
    clean_text: str
    title: str
    links: List[Link] = field(default_factory=list)
    # 页面发布时间（尽量 ISO 格式）。取不到为空串，由调用方决定是否使用。
    publish_time: str = ""


REMOVE_TAGS = {"script", "style", "nav", "footer", "header", "aside",
               "noscript", "iframe", "button", "select", "textarea",
               "svg", "path", "meta", "link"}
# 注意：form 不在删除列表——多数 CMS 用 <form> 包裹正文容器，
# 删除 form 会连同正文一起丢失（西华师大等站点踩过坑）
BLOCK_TAGS = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6",
              "li", "tr", "section", "article", "blockquote", "pre",
              "ol", "ul", "table", "br", "hr"}

# 仅用于微信正文的隐藏节点过滤：只认 display:none。
# 注意不要扩展到 visibility:hidden——微信把 #js_content 容器本身设成
# visibility:hidden（JS 加载后再显示），按它过滤会把正文整块丢掉。
HIDDEN_STYLE_RE = re.compile(r"display\s*:\s*none", re.I)

# 微信文章发布时间的 JS 变量（Unix 秒级时间戳），页面形如 var ct = "1757491200";
WECHAT_CT_RE = re.compile(r'var\s+ct\s*=\s*"?(\d{9,11})"?')

# 通用站点的发布时间 meta（meta 在 REMOVE_TAGS 里，须在清理前读取）
PUBLISH_META_KEYS = ("article:published_time", "og:release_date", "publishdate")


class HtmlCleaner:
    def clean(self, html: str, base_url: str) -> CleanResult:
        if not html or not html.strip():
            return CleanResult(clean_text="", title="")
        soup = BeautifulSoup(html, "lxml")
        is_wechat = is_wechat_article(base_url)
        # 标题与发布时间须在 REMOVE_TAGS 清理前读取：og:title / article:published_time
        # 都是 meta 标签，会被清掉
        title = self._page_title(soup, is_wechat)
        publish_time = self._page_publish_time(soup, html, is_wechat)
        for tag in REMOVE_TAGS:
            for el in soup.find_all(tag):
                el.decompose()
        links = self._extract_links(soup, base_url)
        if is_wechat:
            # 正文限定 #js_content，避开赞赏/点赞/推荐阅读等界面噪音；
            # 结构变化导致取空时回退通用逻辑，避免整篇丢失
            clean_text = self._extract_wechat_text(soup) or self._extract_text(soup)
        else:
            clean_text = self._extract_text(soup)
        return CleanResult(clean_text=clean_text.strip(), title=title, links=links,
                           publish_time=publish_time)

    def _page_title(self, soup: BeautifulSoup, is_wechat: bool) -> str:
        """取页面标题。非微信站点与原有逻辑保持一致（<title>）"""
        if is_wechat:
            og = soup.find("meta", attrs={"property": "og:title"})
            if og:
                content = (og.get("content") or "").strip()
                if content:
                    return content
            node = soup.find(id="activity-name")
            if node:
                t = node.get_text(strip=True)
                if t:
                    return t
        title_tag = soup.find("title")
        return title_tag.get_text(strip=True) if title_tag else ""

    def _page_publish_time(self, soup: BeautifulSoup, raw_html: str, is_wechat: bool) -> str:
        """提取页面发布时间，取不到返回空串。只读元信息，不影响正文与既有字段。"""
        if is_wechat:
            t = self._wechat_publish_time(soup, raw_html)
            if t:
                return t
        for key in PUBLISH_META_KEYS:
            meta = soup.find("meta", attrs={"property": key}) or soup.find("meta", attrs={"name": key})
            if meta:
                content = (meta.get("content") or "").strip()
                if content:
                    return content
        return ""

    def _wechat_publish_time(self, soup: BeautifulSoup, raw_html: str) -> str:
        """微信发布时间：优先 JS 变量 ct（Unix 时间戳，最完整），兜底 #publish_time 元素"""
        m = WECHAT_CT_RE.search(raw_html)
        if m:
            try:
                return datetime.fromtimestamp(int(m.group(1))).strftime("%Y-%m-%d %H:%M")
            except Exception:
                pass
        node = soup.find(id="publish_time")
        if node:
            text = node.get_text(strip=True)
            if text:
                return text
        return ""

    def _extract_wechat_text(self, soup: BeautifulSoup) -> str:
        """微信文章正文：只取 #js_content 内的可见文本"""
        node = soup.find(id="js_content")
        if node is None:
            return ""
        parts = []
        for child in node.children:
            if self._is_hidden(child):
                continue
            text = self._element_text(child)
            if text.strip():
                parts.append(text.strip())
        return "\n\n".join(parts)

    def _is_hidden(self, el) -> bool:
        """style 含 display:none 视为隐藏（NavigableString 无 get，直接判否）"""
        try:
            style = el.get("style") or ""
        except Exception:
            return False
        return bool(HIDDEN_STYLE_RE.search(style))

    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> List[Link]:
        links = []
        seen = set()
        for a in soup.find_all("a", href=True):
            href = a.get("href", "").strip()
            if not href or href.startswith("#") or href.startswith("javascript:"):
                continue
            full_url = urljoin(base_url, href)
            full_url = normalize(full_url)
            if is_static_asset(full_url) or full_url in seen:
                continue
            seen.add(full_url)
            anchor = a.get_text(strip=True)[:100]
            links.append(Link(url=full_url, anchor_text=anchor))
        return links

    def _extract_text(self, soup: BeautifulSoup) -> str:
        parts = []
        for el in soup.body.children if soup.body else soup.children:
            text = self._element_text(el)
            if text.strip():
                parts.append(text.strip())
        return "\n\n".join(parts)

    def _element_text(self, el) -> str:
        if isinstance(el, str):
            t = el.strip()
            return t if t else ""
        if not hasattr(el, "name") or el.name is None:
            return el.get_text(strip=True) if hasattr(el, "get_text") else ""
        tag = el.name.lower()
        if tag == "li":
            text = el.get_text(separator=" ", strip=True)
            return f"\u2022 {text}" if text else ""
        if tag == "table":
            rows = []
            for tr in el.find_all("tr"):
                cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                rows.append(" | ".join(cells))
            return "\n".join(rows)
        if tag in BLOCK_TAGS:
            texts = []
            for child in el.children:
                t = self._element_text(child)
                if t.strip():
                    texts.append(t.strip())
            sep = "\n" if tag in ("br", "hr") else " "
            return sep.join(texts)
        return el.get_text(strip=True) if hasattr(el, "get_text") else ""
