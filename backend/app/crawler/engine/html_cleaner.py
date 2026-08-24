"""HTML 清洗"""
from typing import List
from dataclasses import dataclass, field
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from app.crawler.utils import normalize, is_static_asset


@dataclass
class Link:
    url: str
    anchor_text: str


@dataclass
class CleanResult:
    clean_text: str
    title: str
    links: List[Link] = field(default_factory=list)


REMOVE_TAGS = {"script", "style", "nav", "footer", "header", "aside",
               "noscript", "iframe", "button", "select", "textarea",
               "svg", "path", "meta", "link"}
# 注意：form 不在删除列表——多数 CMS 用 <form> 包裹正文容器，
# 删除 form 会连同正文一起丢失（西华师大等站点踩过坑）
BLOCK_TAGS = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6",
              "li", "tr", "section", "article", "blockquote", "pre",
              "ol", "ul", "table", "br", "hr"}


class HtmlCleaner:
    def clean(self, html: str, base_url: str) -> CleanResult:
        if not html or not html.strip():
            return CleanResult(clean_text="", title="")
        soup = BeautifulSoup(html, "lxml")
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else ""
        for tag in REMOVE_TAGS:
            for el in soup.find_all(tag):
                el.decompose()
        links = self._extract_links(soup, base_url)
        clean_text = self._extract_text(soup)
        return CleanResult(clean_text=clean_text.strip(), title=title, links=links)

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
