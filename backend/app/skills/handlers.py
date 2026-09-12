"""内置 Skill 的具体实现

每个 handler 签名统一为：async def handler(args: dict) -> str | (str, list)
- 返回 str：只有给 LLM 看的纯文本结果（大多数工具）
- 返回 (str, list)：文本 + 结构化来源。文本里的 [N] 指代 sources[N-1]，
  由 executor 统一改写成与来源面板一致的全局编号后再交给模型。
异常在 executor 层统一捕获。
"""

import asyncio
import html
import json
import re
import ast
import operator
from datetime import datetime
from typing import Any, Dict, List, Tuple

import httpx


# ---------- 联网搜索（Bing 网页搜索，免 API Key，国内可达） ----------

# 原实现走 DuckDuckGo，在中国大陆不可达（ConnectTimeout）；cn.bing.com 境内可达
_BING_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
}


def _bing_clean_title(raw: str) -> str:
    """清洗 Bing 结果标题：去标签 + 去掉内嵌的 display-url（'站点名 https://... › getit'）"""
    t = re.sub(r"<[^>]+>", " ", raw)
    t = re.sub(r"\s*https?://[^\s›]*\s*(?:›[^\s]*)?", "", t)
    return re.sub(r"\s+", " ", t).strip(" ›- ")


async def _bing_fetch(client, url: str, params: dict) -> str:
    """抓取 Bing 搜索页；失败抛异常由调用方决定是否重试"""
    resp = await client.get(url, params=params, headers=_BING_HEADERS, follow_redirects=True)
    resp.raise_for_status()
    return resp.text


# 自动打开阅读前几个搜索结果（像人一样点进去看正文）
_BING_READ_LIMIT = 3
_PAGE_TEXT_LIMIT = 1000


async def _bing_search_items(query: str, count: int = 8) -> list:
    """搜索 Bing 并解析出 [{title,url,snippet}]；失败或被反爬返回空列表"""
    url = "https://cn.bing.com/search"
    params = {"q": query, "count": str(count), "setlang": "zh-hans", "cc": "cn"}
    page_html = ""
    for attempt in (1, 2):
        try:
            async with httpx.AsyncClient(timeout=12) as client:
                page_html = await _bing_fetch(client, url, params)
            break
        except Exception:
            if attempt == 2:
                return []
    items = []
    for it in re.findall(r'<li class="b_algo".*?</li>', page_html, re.S):
        h2 = re.search(r"<h2[^>]*>(.*?)</h2>", it, re.S)
        if not h2:
            continue
        title = _bing_clean_title(h2.group(1))
        a = re.search(r'<h2[^>]*>.*?href="(http[^"]+)"', it, re.S)
        p = re.search(r"<p[^>]*>(.*?)</p>", it, re.S)
        snippet = ""
        if p:
            snippet = html.unescape(re.sub(r"<[^>]+>", "", p.group(1)))
            snippet = re.sub(r"&ensp;|&#0183;|&quot;|&nbsp;", " ", snippet)
            snippet = re.sub(r"\s+", " ", snippet).strip()
        items.append({
            "title": title,
            "url": a.group(1) if a else "",
            "snippet": snippet,
        })
    return items


async def _fetch_page_text(url: str, limit: int = _PAGE_TEXT_LIMIT) -> str:
    """抓取单个网页并提取正文；失败返回空串（不抛异常）"""
    try:
        async with httpx.AsyncClient(timeout=8, follow_redirects=True) as client:
            resp = await client.get(url, headers=_BING_HEADERS)
            resp.raise_for_status()
            ctype = (resp.headers.get("content-type") or "").lower()
            if "html" not in ctype and "text" not in ctype:
                return ""
            from app.crawler.engine.html_cleaner import HtmlCleaner

            cleaned = HtmlCleaner().clean(resp.text, url)
            text = re.sub(r"\s+", " ", cleaned.clean_text or "").strip()
            # 去掉页头常见脚本/样式噪音
            text = re.sub(r"^(<style>.*?</style>|修改背景颜色|全网黑白)\s*", "", text)
            return text[:limit]
    except Exception:
        return ""


async def _baidu_search_items(query: str, count: int = 8) -> list:
    """百度网页搜索（中文结果质量高）。返回 [{title,url,snippet}]；失败/验证页返回 []"""
    url = "https://www.baidu.com/s"
    params = {"wd": query, "rn": str(min(count, 10))}
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.get(url, params=params, headers=_BING_HEADERS)
            resp.raise_for_status()
            page_html = resp.text
    except Exception:
        return []
    # 命中"百度安全验证"说明被反爬，返回空让调用方换源
    if "安全验证" in page_html or "wappass" in page_html:
        return []
    items = []
    # 结果: <h3 ...><a href="http://www.baidu.com/link?url=..." ...>标题</a></h3>
    for m in re.finditer(r'<h3[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', page_html, re.S):
        link, title_html = m.group(1), m.group(2)
        if not link.startswith("http"):
            continue
        # 百度标题里带 &nbsp; 这类实体，来源面板要能直接读
        title = html.unescape(re.sub(r"<[^>]+>", "", title_html))
        title = re.sub(r"\s+", " ", title).strip()
        if not title:
            continue
        items.append({"title": title, "url": link, "snippet": ""})
        if len(items) >= count:
            break
    return items


async def _search_items(query: str) -> list:
    """搜索入口：百度优先，失败/反爬则回退 Bing"""
    items = await _baidu_search_items(query)
    if items:
        return items
    return await _bing_search_items(query)


def _web_source(title: str = "", url: str = "", snippet: str = "", published: str = "") -> Dict[str, Any]:
    """构造一条网页来源（与知识库来源同构，前端按 kind 分支渲染）

    不编造相似度：网页结果之间没有可比的相似度分数，该字段留空。
    """
    label = (title or "").strip() or url or "网页"
    return {
        "kind": "web",
        "title": label,
        "url": (url or "").strip(),
        "snippet": (snippet or "").strip()[:300],
        "published": (published or "").strip(),
        "filename": label,  # 兼容既有的 filename 展示字段
        "chunk_text": (snippet or "").strip()[:300],
    }


def _exa_citations(payload: dict) -> List[Dict[str, Any]]:
    """把 Exa 的 citations 转成本站来源（缺字段一律留空，不猜）"""
    out: List[Dict[str, Any]] = []
    for c in (payload or {}).get("citations") or []:
        if isinstance(c, str):
            out.append(_web_source(url=c))
        elif isinstance(c, dict):
            out.append(_web_source(
                title=c.get("title") or "",
                url=c.get("url") or c.get("id") or "",
                snippet=c.get("text") or "",
                published=c.get("publishedDate") or "",
            ))
    return out


async def _exa_answer(query: str) -> Tuple[str, List[Dict[str, Any]]]:
    """Exa Answer：一条请求直接返回整理好、带引用的答案（质量高）。

    需要配置 EXA_API_KEY；任何失败（无 key/超时/异常）都返回空，由调用方回退。
    引用列表必须一起带出来 —— 答案正文里的 [N] 指的就是它。
    """
    from app.config import settings

    api_key = (settings.EXA_API_KEY or "").strip()
    if not api_key:
        return "", []
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.exa.ai/answer",
                headers={"Content-Type": "application/json", "x-api-key": api_key},
                json={"query": f"{query}（尽量列出明细数据）", "text": False},
            )
            if resp.status_code == 200:
                data = resp.json() or {}
                ans = data.get("answer") or ""
                if not ans:
                    return "", []
                return ans[:4000], _exa_citations(data)
    except Exception:
        pass
    return "", []


async def web_search(args: dict) -> Tuple[str, List[Dict[str, Any]]]:
    """联网搜索，获取互联网上的最新结果。

    优先走 Exa Answer（若配置了 EXA_API_KEY，直接返回整理好带引用的综合答案，
    质量最高）；Exa 不可用/无 key 时回退到「百度/Bing 搜索 + 正文阅读」。
    任何路径失败都不抛异常，返回可读提示。

    返回 (给模型看的文本, 网页来源列表)；文本里的 [N] 指代 sources[N-1]，
    执行器会把它改写成与来源面板一致的全局编号，保证正文与面板一一对应。
    """
    query = (args.get("query") or "").strip()
    if not query:
        return "错误：缺少搜索关键词 query", []

    # 第一优先：Exa Answer（快、准、自带整理）
    exa_text, exa_sources = await _exa_answer(query)
    if exa_text:
        return f"以下是根据联网搜索整理的信息（含来源标注）：\n\n{exa_text}", exa_sources

    # 回退：百度/Bing 搜索 + 阅读前几个结果正文
    read_n = int(args.get("read_pages", _BING_READ_LIMIT) or _BING_READ_LIMIT)
    items = await _search_items(query)
    if not items:
        return f"未找到「{query}」的相关搜索结果，建议换更具体的关键词。", []

    # 并行阅读前几个结果的正文（百度跳转链接会自动跟随到真实页面）
    targets = [it for it in items[:read_n] if it["url"].startswith("http")]
    texts = await asyncio.gather(*(_fetch_page_text(it["url"]) for it in targets)) if targets else []
    body_by_url = {it["url"]: t for it, t in zip(targets, texts)}

    parts = []
    sources: List[Dict[str, Any]] = []
    for i, it in enumerate(items, 1):
        line = f"[{i}] {it['title']}\n    链接：{it['url'] or '无'}"
        if it.get("snippet"):
            line += f"\n    摘要：{it['snippet'][:200]}"
        body = body_by_url.get(it["url"], "")
        if body:
            line += f"\n    正文：{body}"
        parts.append(line)
        sources.append(_web_source(
            title=it.get("title") or "",
            url=it.get("url") or "",
            snippet=it.get("snippet") or "",
            published=it.get("published") or "",
        ))
    return "\n\n".join(parts)[:6000], sources


# ---------- 当前时间 ----------

async def get_current_time(args: dict) -> str:
    """返回当前时间（可选指定格式与时区偏移小时）"""
    fmt = args.get("format") or "%Y-%m-%d %H:%M:%S"
    offset_hours = args.get("utc_offset_hours")
    now = datetime.now()
    if offset_hours is not None:
        from datetime import timedelta, timezone

        now = now.astimezone(timezone(timedelta(hours=float(offset_hours))))
    try:
        return now.strftime(fmt)
    except Exception:
        return now.isoformat()


# ---------- 计算器（白名单 AST，禁止任意代码执行） ----------

_ALLOWED_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_ALLOWED_UNARYOPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _safe_eval(node: ast.AST) -> Any:
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
        return _ALLOWED_BINOPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARYOPS:
        return _ALLOWED_UNARYOPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError(f"不支持的表达式片段：{type(node).__name__}")


async def calculator(args: dict) -> str:
    """计算数学表达式（仅允许数字与 + - * / // % ** 和括号）"""
    expr = (args.get("expression") or "").strip()
    if not expr:
        return "错误：缺少表达式 expression"
    if not re.fullmatch(r"[\d\s+\-*/().%]+|\*\*", expr) and "**" not in expr:
        if not re.fullmatch(r"[\d\s+\-*/().%]+", expr):
            return "错误：表达式只允许数字、四则运算符、括号和取模"
    try:
        tree = ast.parse(expr, mode="eval")
        result = _safe_eval(tree)
        return f"{expr} = {result}"
    except ZeroDivisionError:
        return "错误：除数为 0"
    except Exception as e:
        return f"计算失败：{e}"


# ---------- 注册表 ----------

HANDLERS = {
    "web_search": web_search,
    "get_current_time": get_current_time,
    "calculator": calculator,
}
