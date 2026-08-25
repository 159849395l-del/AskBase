"""ExtractorAgent — LLM 结构化提取"""
import json
import time
from datetime import datetime
from sqlalchemy import select, func
from app.crawler.models import CrawlTask, CrawlPage, CrawlResult, AgentLog, TaskStatus, get_crawler_session_factory
from app.crawler.engine.html_cleaner import HtmlCleaner
from app.crawler.utils import sha256_hex, safe_json
from app.crawler.sse_publisher import publish_agent_log, publish_stage_progress, publish_result_new
from app.crawler.config import CRAWLER_TEXT_CHUNK_LIMIT
from app.config import settings
import openai

EXTRACTION_SYSTEM_TEMPLATE = """你是数据提取器。严格按 schema 从给定文本提取数据。
schema: {schema}
规则：
1. 输出 JSON 的字段名必须与 schema 中的 name 完全一致（例如 schema 字段名是 title 就输出 "title"，禁止翻译成"标题"）
2. 字段缺失填 null；date 转 ISO-8601；数组字段输出数组
3. 若页面是【列表页】（含多条同类条目，如新闻列表/商品列表），输出 {{"records":[每条一条记录,...]}}，每条记录按 schema 提取
4. 若页面是单条内容（一篇文章/一件商品），直接输出 schema 对象
5. 若页面内容与主题无关（无任何可提取条目），输出 {{"__empty__": true}}
6. 若 schema 含 url/link 字段，从"页面链接列表"中按锚文本匹配对应的链接；匹配不到才填 null
只输出 JSON。"""

SCHEMA_MARKER_KEYS = ("fields", "dedup_keys")

# 任务标题 → 来源名 的常见前后缀（"爬XX大学招生就业" → "XX大学"）
_SOURCE_PREFIXES = ("爬取", "抓取", "采集", "爬虫", "爬", "抓")
_SOURCE_SUFFIXES = (
    "招生就业", "新闻中心", "招聘信息", "官网新闻", "通知公告",
    "新闻标题", "新闻链接", "招聘", "招生", "新闻", "官网", "公告",
    "信息", "合集", "动态", "文章",
)


def extract_source_name(task_title: str) -> str:
    """从任务标题提取来源名（一个任务 = 一个来源）

    '爬西华师范大学招生就业' → '西华师范大学'
    '抓取西南大学官网新闻'   → '西南大学'
    '爬四川大学招聘信息合集' → '四川大学'
    提取失败时返回任务标题去掉前后缀后的剩余文本（兜底），再不行返回空串。
    """
    t = (task_title or "").strip()
    if not t:
        return ""
    for p in _SOURCE_PREFIXES:
        if t.startswith(p):
            t = t[len(p):]
            break
    t = t.lstrip(":：-–— ")
    for suf in _SOURCE_SUFFIXES:
        if t.endswith(suf) and len(t) > len(suf):
            t = t[: -len(suf)]
            break
    t = t.strip(":：-–— ")
    import re

    # 1. 优先匹配机构实体（大学/学院/学校…），非贪婪取最短片段
    m = re.search(r"[\u4e00-\u9fa5A-Za-z0-9]{2,}?(?:大学|学院|学校|职业技术学院)", t)
    if m:
        return m.group(0)[:100]
    # 2. 其次匹配 网/网站/公司/集团/中心/政府 类实体
    m = re.search(r"[\u4e00-\u9fa5A-Za-z0-9]{2,}?(?:新闻网|网站|网|公司|集团|中心|政府)", t)
    if m:
        return m.group(0)[:100]
    # 3. 泛化描述（"这条新闻的标题、正文内容"这类无实体词）→ 提取失败返回空
    if re.search(r"(这条|这个|该|的标题|的正文|的内容|列表)", t):
        return ""
    # 4. 系统默认标题（"任务 T260824-19"）→ 返回空，调用方回退 description
    if "任务" in t or re.match(r"^T\d", t):
        return ""
    return t[:100]


def extract_source_from_task(task) -> str:
    """从任务对象提取来源名：优先标题，标题提取不出实体（如系统默认名）时回退描述"""
    source = extract_source_name(task.title)
    if source:
        return source
    desc = (task.description or "").strip()
    if desc:
        return extract_source_name(desc)
    return ""


async def execute_extracting(task_id: int):
    start_ms = int(time.time() * 1000)
    factory = get_crawler_session_factory()
    async with factory() as db:
        log = AgentLog(task_id=task_id, agent="EXTRACTOR", stage="llm_extract", status="RUNNING", started_at=datetime.now())
        db.add(log)
        task = await db.get(CrawlTask, task_id)
        if not task: return None
        schema = safe_json(task.schema_json) or {"fields":[],"dedup_keys":[]}
        if not isinstance(schema, dict):
            schema = {"fields":[],"dedup_keys":[]}
        field_names = [f["name"] for f in schema.get("fields",[]) if isinstance(f, dict) and f.get("name")]
        dedup_keys = schema.get("dedup_keys",[])
        pages = (await db.execute(select(CrawlPage).where(CrawlPage.task_id == task_id, CrawlPage.clean_text != None, CrawlPage.clean_text != "").order_by(CrawlPage.id.asc()))).scalars().all()
        extracted = set((await db.execute(select(CrawlResult.page_id).where(CrawlResult.task_id == task_id, CrawlResult.status=="VALID"))).scalars().all())
        valid=0; invalid=0; skipped=0; tokens=0
        cleaner = HtmlCleaner()
        for page in pages:
            if page.id in extracted: continue
            if not page.clean_text or not page.clean_text.strip(): invalid+=1; continue
            try:
                data, used = await _extract_page(task, page, schema, field_names, cleaner)
                tokens += used
            except Exception as e:
                print(f"[Extractor] task={task_id} page={page.id} LLM 抽取失败: {e}")
                invalid+=1; continue
            if data is None or data.get("__empty__"):
                invalid+=1; continue
            records = data.get("records")
            if records and isinstance(records, list):
                for rec in records:
                    if not isinstance(rec, dict):
                        continue
                    rh = _record_hash(rec, dedup_keys, field_names)
                    exists = await db.scalar(select(func.count()).select_from(CrawlResult).where(CrawlResult.task_id==task_id, CrawlResult.record_hash==rh, CrawlResult.status=="VALID"))
                    if exists and exists > 0: skipped+=1; continue
                    r = CrawlResult(task_id=task_id, url=page.url, page_id=page.id, data_json=rec, record_hash=rh, status="VALID", extracted_at=datetime.now())
                    db.add(r); await db.flush(); await db.refresh(r); valid+=1
                    summary = str(rec.get(field_names[0],""))[:60] if field_names else ""
                    await publish_result_new(task_id, r.id, summary)
                    await _sync_to_school_articles(db, task, rec, page.url)
            else:
                if not isinstance(data, dict) or not data:
                    invalid+=1; continue
                rh = _record_hash(data, dedup_keys, field_names)
                exists = await db.scalar(select(func.count()).select_from(CrawlResult).where(CrawlResult.task_id==task_id, CrawlResult.record_hash==rh, CrawlResult.status=="VALID"))
                if exists and exists > 0: skipped+=1; continue
                r = CrawlResult(task_id=task_id, url=page.url, page_id=page.id, data_json=data, record_hash=rh, status="VALID", extracted_at=datetime.now())
                db.add(r); await db.flush(); await db.refresh(r); valid+=1
                summary = str(data.get(field_names[0],""))[:60] if field_names else ""
                await publish_result_new(task_id, r.id, summary)
                await _sync_to_school_articles(db, task, data, page.url)
        task = await db.get(CrawlTask, task_id)
        if task:
            stats = safe_json(task.stats_json) or {}
            stats.update({"extracted":valid+invalid+skipped,"valid":valid,"invalid":invalid,"skipped":skipped})
            task.stats_json = stats
            await db.flush()
            await db.commit()
        await publish_stage_progress(task_id, "extract", valid+invalid, valid+invalid)
        log2 = AgentLog(task_id=task_id, agent="EXTRACTOR", stage="llm_extract", status="SUCCESS", cost_tokens=tokens, duration_ms=int(time.time()*1000-start_ms), started_at=datetime.now(), finished_at=datetime.now())
        db.add(log2)
        await db.commit()
        await publish_agent_log(task_id, "EXTRACTOR", "SUCCESS", "llm_extract", tokens)
        print(f"[Extractor] Task {task_id}: {valid} valid, {invalid} invalid, {skipped} skipped, tokens={tokens}")
        return None


async def _extract_page(task, page, schema, field_names, cleaner):
    """调用 LLM 抽取单页。成功返回 (data, tokens)；任何失败抛异常，由调用方计 invalid。

    严禁降级为"截断原文塞进字段"——那正是历史版本产生伪数据的根源。
    """
    text = page.clean_text[:CRAWLER_TEXT_CHUNK_LIMIT] if page.clean_text else ""
    links = ""
    if page.rendered_html:
        try:
            cleaned = cleaner.clean(page.rendered_html, page.url)
            for i, link in enumerate(cleaned.links[:50]):
                links += f"{link.anchor_text} => {link.url}\n"
        except: pass
    client = openai.AsyncOpenAI(api_key=settings.LLM_API_KEY, base_url=settings.LLM_API_BASE)
    system = EXTRACTION_SYSTEM_TEMPLATE.format(schema=json.dumps(schema, ensure_ascii=False))
    user = f"来源URL: {page.url}\n正文: {text}"
    if links: user += f"\n页面链接列表（锚文本 => 链接）:\n{links}"
    resp = await client.chat.completions.create(model=settings.LLM_MODEL, messages=[{"role":"system","content":system},{"role":"user","content":user}], temperature=0.1, response_format={"type":"json_object"})
    used = resp.usage.total_tokens if resp.usage else 0
    content = resp.choices[0].message.content
    data = json.loads(content)
    if not isinstance(data, dict):
        raise ValueError("LLM 输出不是 JSON 对象")
    if any(k in data for k in SCHEMA_MARKER_KEYS):
        raise ValueError("LLM 复述了 schema 而非抽取结果")
    return data, used


def _record_hash(data, dedup_keys, field_names):
    """对齐旧版：去重键缺失/为空时跳过，避免同内容因字段残缺被当成不同记录"""
    keys = dedup_keys if dedup_keys else (field_names[:1] if field_names else ["title"])
    parts = []
    for k in keys:
        v = data.get(k)
        if v is not None and str(v) != "":
            parts.append(str(v))
    if not parts:
        return sha256_hex(json.dumps(data, sort_keys=True, ensure_ascii=False))
    return sha256_hex("|".join(parts))


# ---------- school_articles 通用文章落库（任务标题 → 来源名） ----------

def _pick_field(rec: dict, *names) -> str:
    """按候选字段名依次取值（兼容中英文字段名）"""
    for n in names:
        v = rec.get(n)
        if v is not None and str(v) != "":
            return str(v)
    return ""


async def _sync_to_school_articles(db, task, rec: dict, page_url: str):
    """把单条提取结果同步写入 school_articles（按 url_hash 去重，失败不阻断主流程）

    字段映射（兼容中英文 schema）：
      title        ← title/标题
      content      ← content/正文/正文内容
      publish_date ← publish_date/publishDate/发布时间/日期
      url          ← 优先 rec 里的 url/link/链接（列表页提取时是详情页地址）；否则用当前页面地址
      source       ← 任务标题提取的来源名（如"西华师范大学"）
    """
    try:
        source = extract_source_from_task(task)
        if not source:
            return
        title = _pick_field(rec, "title", "标题")[:500]
        content = _pick_field(rec, "content", "正文", "正文内容") or ""
        publish_date = _pick_field(rec, "publish_date", "publish_time", "publishDate", "发布时间", "日期")[:30]
        if not title:
            return
        from sqlalchemy import text as sa_text

        # 去重键：优先用记录自带 url（列表页提取出的每条记录 url 是详情页地址，
        # 避免同列表页的多条记录因共用页面地址而互相覆盖）；没有则用当前页地址
        rec_url = _pick_field(rec, "url", "link", "链接", "原文链接") or page_url
        url_hash = sha256_hex(rec_url)
        await db.execute(sa_text("""
            INSERT INTO school_articles (source, title, content, publish_date, url, url_hash)
            VALUES (:source, :title, :content, :publish_date, :url, :url_hash)
            ON DUPLICATE KEY UPDATE
              source = VALUES(source),
              title = VALUES(title),
              content = VALUES(content),
              publish_date = VALUES(publish_date)
        """), {
            "source": source,
            "title": title,
            "content": content,
            "publish_date": publish_date,
            "url": rec_url,
            "url_hash": url_hash,
        })
        await db.flush()
        print(f"[Extractor] 已同步 school_articles: source={source} title={title[:30]}")
    except Exception as e:
        print(f"[Extractor] 同步 school_articles 失败(忽略): {e}")
