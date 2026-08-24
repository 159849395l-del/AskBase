"""
爬虫模块工具函数 — URL 归一化、哈希、域名判断等
"""
import hashlib
import json
from urllib.parse import urlparse, urljoin, urlunparse


STATIC_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico",
    ".css", ".js", ".map", ".woff", ".woff2", ".ttf", ".eot",
    ".mp4", ".mp3", ".avi", ".mov", ".pdf", ".zip", ".tar", ".gz",
}


def normalize(url: str) -> str:
    """URL 归一化：移除 fragment、统一 scheme 小写、尾部斜杠"""
    if not url.startswith("http://") and not url.startswith("https://"):
        return url
    parsed = urlparse(url)
    cleaned = parsed._replace(fragment="", scheme=parsed.scheme.lower())
    path = cleaned.path.rstrip("/") or "/"
    cleaned = cleaned._replace(path=path)
    return urlunparse(cleaned)


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
