"""
爬虫模块工具函数 — URL 归一化、哈希、域名判断等
"""
import hashlib
import json
from datetime import time as dtime, timedelta
from urllib.parse import urlparse, urljoin, urlunparse, urlencode, parse_qsl


STATIC_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico",
    ".css", ".js", ".map", ".woff", ".woff2", ".ttf", ".eot",
    ".mp4", ".mp3", ".avi", ".mov", ".pdf", ".zip", ".tar", ".gz",
}

# 跟踪/统计类 query 参数：同一内容带不同取值时不应视为不同页面（入队与去重前剔除）。
# 分页、搜索、ID 等**内容寻址**参数（page/id/keyword/cid/type…）不在其中，避免误合并。
TRACKING_QUERY_KEYS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "utm_id",
    "spm", "from", "fromid", "from_id", "fromurl", "isappinstalled",
    "scene", "timestamp", "_t", "_r", "ver", "cache",
    "share_token", "share_uid", "share_from", "share_platform", "share_id",
    "wechat_redirect", "hmsr", "hm_pl", "hm_lt", "hm_md", "hm_ci", "hmcu", "hmmt",
}


def _strip_tracking_query(query: str) -> str:
    """移除 query 中的跟踪参数；返回剩余部分（保留原顺序与编码）"""
    if not query:
        return ""
    keep = []
    for kv in query.split("&"):
        if not kv:
            continue
        k = kv.split("=", 1)[0].lower().strip()
        if k in TRACKING_QUERY_KEYS or k.startswith("utm_"):
            continue
        keep.append(kv)
    return "&".join(keep)


def normalize(url: str) -> str:
    """URL 归一化：移除 fragment、统一 scheme 小写、去掉尾部斜杠与跟踪参数。

    用于 url_queue 入队去重（url_hash 基于本函数结果）——
    同一篇文章带不同 utm/from/timestamp 等跟踪参数时合并为同一条。
    """
    if not url.startswith("http://") and not url.startswith("https://"):
        return url
    parsed = urlparse(url)
    cleaned = parsed._replace(fragment="", scheme=parsed.scheme.lower(), query=_strip_tracking_query(parsed.query))
    path = cleaned.path.rstrip("/") or "/"
    cleaned = cleaned._replace(path=path)
    return urlunparse(cleaned)


def canonical_url(url: str) -> str:
    """把 URL 归一到"是否指向同一内容"的判据。

    在 normalize 基础上进一步：主机去 www、去默认端口、小写、http/https 统一为 https、
    query 键排序（顺序无关）。用于提取结果/知识库落库的去重键，
    避免同一篇文章因 http vs https、带/不带 www、参数顺序不同被当成多条。
    """
    if not url or "://" not in url:
        return url
    try:
        p = urlparse(url)
        scheme = (p.scheme or "http").lower()
        host = (p.hostname or "").lower()
        if host.startswith("www."):
            host = host[4:]
        port = p.port
        default_port = 443 if scheme == "https" else 80
        netloc = host
        if port and port not in (default_port, 80, 443):
            netloc = f"{host}:{port}"
        path = p.path.rstrip("/") or "/"
        q = _strip_tracking_query(p.query)
        if q:
            q = urlencode(sorted(parse_qsl(q, keep_blank_values=True)))
        return urlunparse(("https", netloc, path, "", q, ""))
    except Exception:
        return url


def is_same_domain(url1: str, url2: str) -> bool:
    """判断两个 URL 是否同域"""
    try:
        p1 = urlparse(url1)
        p2 = urlparse(url2)
        return p1.netloc.lower() == p2.netloc.lower()
    except Exception:
        return False


def is_static_asset(url: str) -> bool:
    """判断是否为静态资源文件"""
    path = urlparse(url).path.lower()
    _, _, ext = path.rpartition(".")
    return "." + ext in STATIC_EXTENSIONS


def url_hash(task_id: int, url: str) -> str:
    """生成 URL 唯一哈希（用于去重）"""
    raw = f"{task_id}:{normalize(url)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def sha256_hex(text: str) -> str:
    """SHA256 哈希"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def resolve_url(base: str, href: str) -> str:
    """解析相对路径为绝对 URL"""
    return urljoin(base, href)


def extract_domain(url: str) -> str:
    """提取域名"""
    return urlparse(url).netloc.lower()


def safe_json(value, default=None):
    """兼容 JSON 列的双重编码：dict/list 直接用，字符串最多递归解析两层。

    历史版本曾用 json.dumps() 把 dict 序列化成字符串后存入 JSON 列，
    SQLAlchemy 的 JSON 类型对字符串值还会再包一层转义，导致库里出现
    dict / 单层 str / 双层 str 三种形态，统一在这里容错。

    注意：对 dict/list 返回【浅拷贝】。若返回原对象，调用方原地 update 后
    再赋回同一对象，SQLAlchemy 会认为属性未变化而不生成 UPDATE（stats 静默丢失）。
    """
    if value is None:
        return default
    for _ in range(2):
        if isinstance(value, dict):
            return dict(value)
        if isinstance(value, list):
            return list(value)
        if isinstance(value, str):
            try:
                value = json.loads(value)
                continue
            except Exception:
                return default
        return value
    return value


def normalize_run_time(value) -> str:
    """把 run_time 统一成 'HH:MM:SS' 字符串。

    兼容三种形态：MySQL TIME 列经 aiomysql/pymysql 读出是 timedelta、
    String 读出是 'HH:MM:SS'、SQLAlchemy Time 类型会转成 datetime.time。
    （超过 24h 的时刻按一天内取模截断，实际业务不会用到。）
    """
    if value is None:
        return "02:00:00"
    if isinstance(value, timedelta):
        total = int(value.total_seconds())
        hh, mm, ss = total // 3600, (total % 3600) // 60, total % 60
        return f"{hh % 24:02d}:{mm:02d}:{ss:02d}"
    if isinstance(value, dtime):
        return value.strftime("%H:%M:%S")
    text = str(value).strip()
    parts = text.split(":")
    if len(parts) >= 3:
        try:
            return f"{int(parts[0]) % 24:02d}:{int(parts[1]):02d}:{int(parts[2]):02d}"
        except ValueError:
            pass
    return text[:8] if text else "02:00:00"
