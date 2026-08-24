#!/usr/env python3
"""
把 ai_crawl 爬取的文章(MySQL t_result)直接接入本 RAG 项目的 ChromaDB,
并同步在 RAG 的 knowledge_documents 表登记, 使这些文档出现在前端知识库列表、
可被正常删除(删除会按 kb_doc_id 连带清掉 Chroma 向量)。

完全复用本项目已有能力, 不做重复实现:
  - app.rag.splitter.get_text_splitter()   中文感知切分(800/100, 按句号逗号断)
  - app.rag.vector_store.get_vectorstore()  Chroma + 百炼 text-embedding-v3 自动向量化
  - app.database.async_session_factory      本项目 SQLite 异步会话

前置:
  1. 必须在 LangChainRAG项目/backend 目录下运行(加载 .env 与相对 chroma 路径)
  2. 安装 PyMySQL:  pip install pymysql
  3. ai_crawl 的 MySQL 可达(127.0.0.1:3306, root/123, db=ai_crawl)
     密码/用户可用环境变量 AI_CRAWL_DB_PASSWORD / AI_CRAWL_DB_USER 覆盖
     连不上时会给出清晰提示; 本机可用 ai_crawl/scripts/start_mysql.cmd 一键拉起 MySQL

特性:
  - 增量摄入: 基于内容指纹 chunk_hash 去重, 已摄入的块不会重复向量化; 每块带 record_hash(取自 t_result)用于溯源, 旧块在过渡运行里被回填
  - 友好命名: 知识库名取自 t_task.title, 形如 "抓取书籍标题和价格 〔#18〕"
  - 块数从 Chroma 实查, 重跑不会被清零
  - MySQL 自愈: 连不上时自动拉起本机 mysqld 再连, 无需手动干预

用法:
  python scripts/ingest_from_aicrawl.py                # 摄入全部 VALID 文章
  python scripts/ingest_from_aicrawl.py --task-id 22  # 只导某个爬取任务
  python scripts/ingest_from_aicrawl.py --dry-run     # 只预览, 不写库
"""
import sys
import os
import json
import hashlib
import argparse
import asyncio
import time
import subprocess
import pymysql

# 让脚本能 import 本项目 app (backend 目录)
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from sqlalchemy import select, text
from langchain_core.documents import Document
from app.config import settings
from app.rag.splitter import get_text_splitter
from app.rag.vector_store import get_vectorstore
from app.rag.embeddings import get_embeddings
from app.database import async_session_factory
from app.models.knowledge_document import KnowledgeDocument

# ---- ai_crawl MySQL 连接 ----
# 本地 MySQL 密码默认 123(与 application.yml 的 aicrawl123 不同), 可用环境变量覆盖
# ssl_disabled: 本地 MySQL 通常不配 SSL, 否则连接会在 SSL 协商阶段被重置
# host 用 127.0.0.1: Windows 下 localhost 会解析成 ::1 被拒
AI_CRAWL_DB = dict(
    host=os.getenv("AI_CRAWL_DB_HOST", "127.0.0.1"),
    port=int(os.getenv("AI_CRAWL_DB_PORT", "3306")),
    user=os.getenv("AI_CRAWL_DB_USER", "root"),
    password=os.getenv("AI_CRAWL_DB_PASSWORD", "123"),
    database=os.getenv("AI_CRAWL_DB_NAME", "ai_crawl"),
    charset="utf8mb4",
    ssl_disabled=True,
)

TITLE_HINTS = ("title", "name", "heading", "标题", "题目")
TEXT_HINTS = ("content", "body", "text", "article", "正文", "内容")


def _pick(data, hints):
    for h in hints:
        v = data.get(h)
        if isinstance(v, str) and v.strip():
            return h
    return None


def build_raw_documents(rows):
    """rows: [(task_id, url, data_json, record_hash, task_title, task_no), ...] -> 每篇一个未切分的 Document
    (命名用后两个字段; record_hash 透传进 metadata 以支持增量摄入)"""
    docs = []
    for row in rows:
        task_id, url, data_json, record_hash = row[0], row[1], row[2], row[3]
        try:
            data = json.loads(data_json)
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        title_f = _pick(data, TITLE_HINTS)
        text_f = _pick(data, TEXT_HINTS)
        if text_f:
            body = data[text_f]
            title = data.get(title_f) if title_f else ""
            text = (title + "\n\n" + body) if title else body
        else:
            # 无显式正文字段: 有内容性字段(如 price/描述)才拼接保留;
            # 只有"标题+链接"的纯列表任务跳过(无知识价值且污染检索)。
            URL_HINTS = ("url", "link", "href", "链接")
            has_content = any(
                k not in TITLE_HINTS and k not in URL_HINTS
                and isinstance(v, (str, int, float)) and str(v).strip()
                for k, v in data.items()
            )
            if not has_content:
                continue
            parts = [f"{k}: {v}" for k, v in data.items()
                     if isinstance(v, (str, int, float)) and str(v).strip()]
            text = "\n".join(parts)
        if not text.strip():
            continue
        meta = {
            "source": url or "",          # 文章原始 URL, 命中后可溯源跳回
            "task_id": task_id,
            "origin": "ai_crawl",
            "title": data.get(title_f) or "",
            "record_hash": record_hash or "",
        }
        docs.append(Document(page_content=text, metadata=meta))
    return docs


def split_and_dedup(raw_docs):
    """切分 + 去重 + 回填 record_hash。
    - 去重按 chunk_hash(跨任务相同内容也跳过, 避免重复新增)。
    - 回填按 (task_id, chunk_hash) 双键匹配, 精确对应到本任务的源块,
      避免跨任务内容重复导致 chunk_hash 碰撞、误判为已回填(西华师大等多任务爬同一站)。
    - 回填走 delete + add(显式同 id) 写路径, 与原始 300 块 add_documents 同路、可落盘;
      本机 chromadb(SegmentAPI) 的 update/upsert 不保证跨进程持久化, persist() 已移除, 故不用。
      embedding 由项目同一函数重算(确定性, 与原向量一致)。"""
    splitter = get_text_splitter()
    chunks = splitter.split_documents(raw_docs)
    vs = get_vectorstore()
    existing = vs._collection.get(include=["metadatas"])
    ex_ids = existing.get("ids") or []
    ex_metas = existing.get("metadatas") or []
    seen_hash = {}   # chunk_hash -> old_id            (去重/跳过用)
    seen_th = {}     # (task_id, chunk_hash) -> old_id (回填用)
    old_meta = {}    # old_id -> metadata
    for i, m in zip(ex_ids, ex_metas):
        if m and m.get("chunk_hash"):
            ch = m["chunk_hash"]
            seen_hash[ch] = i
            seen_th[(m.get("task_id"), ch)] = i
            old_meta[i] = m
    kept, skipped, backfilled = [], 0, 0
    embedder = get_embeddings()
    for i, c in enumerate(chunks):
        h = hashlib.md5(c.page_content.encode("utf-8")).hexdigest()
        c.metadata["chunk_hash"] = h
        c.metadata["chunk_index"] = i
        c.metadata["total_chunks"] = len(chunks)
        if h in seen_hash:
            skipped += 1
            # 仅在「本任务、同内容」的旧块仍缺 record_hash 时回填
            key = (c.metadata.get("task_id"), h)
            if key in seen_th:
                oid = seen_th[key]
                om = old_meta.get(oid) or {}
                rh = c.metadata.get("record_hash")
                if rh and not om.get("record_hash"):
                    try:
                        emb = embedder.embed_documents([c.page_content])[0]
                        new_meta = {**om, "record_hash": rh}
                        vs._collection.delete(ids=[oid])
                        vs._collection.add(
                            ids=[oid],
                            embeddings=[emb],
                            documents=[c.page_content],
                            metadatas=[new_meta],
                        )
                        backfilled += 1
                    except Exception as _e:
                        print(f"    [warn] 回填 record_hash 失败 old_id={oid}: {_e}")
            continue
        kept.append(c)
    tail = f" (回填 record_hash {backfilled})" if backfilled else ""
    print(f"  切分 {len(chunks)} 块, 去重跳过 {skipped}, 新增 {len(kept)}{tail}")
    return kept


def _try_start_mysql():
    """best-effort 自愈: MySQL 连不上时, 直接拉起本机 mysqld(无新窗口, DETACHED),
    让桥接在掉线后自愈。失败静默返回 False, 由调用方给友好提示。
    路径可用 AI_CRAWL_MYSQLD / AI_CRAWL_MYSQL_CNF 覆盖(默认本机独立安装路径)。"""
    mysqld = os.getenv("AI_CRAWL_MYSQLD") or r"D:\dev\mysql-8.0.31-winx64\bin\mysqld.exe"
    cnf = os.getenv("AI_CRAWL_MYSQL_CNF") or r"D:\dev\mysql-8.0.31-winx64\my.ini"
    if not os.path.exists(mysqld):
        return False
    try:
        # DETACHED_PROCESS(0x8): 后台独立运行, 不随本脚本退出而被杀
        subprocess.Popen(
            [mysqld, f"--defaults-file={cnf}"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=0x00000008,
        )
    except Exception:
        return False
    for _ in range(20):
        time.sleep(1)
        try:
            c = pymysql.connect(**{**AI_CRAWL_DB, "connect_timeout": 2})
            c.close()
            return True
        except Exception:
            continue
    return False


def fetch_rows(task_id=None, limit=None):
    """读取 VALID 结果, 顺带 JOIN t_task 拿到任务 title / task_no, 并取 record_hash 用于溯源/回填。
    返回: [(task_id, url, data_json, record_hash, task_title, task_no), ...]"""
    try:
        conn = pymysql.connect(**AI_CRAWL_DB)
    except Exception:
        # 自愈: 尝试直接拉起本机 MySQL 再连一次
        if _try_start_mysql():
            conn = pymysql.connect(**AI_CRAWL_DB)
        else:
            raise RuntimeError(
                f"无法连接 ai_crawl 的 MySQL ({AI_CRAWL_DB['host']}:{AI_CRAWL_DB['port']}, "
                f"user={AI_CRAWL_DB['user']})。\n"
                f"请确认 MySQL 已启动(本地可运行 ai_crawl/scripts/start_mysql.cmd 一键拉起), "
                f"且凭据正确; 可用环境变量 AI_CRAWL_DB_HOST/PORT/USER/PASSWORD/NAME 覆盖。"
            )
    try:
        with conn.cursor() as cur:
            sql = (
                "SELECT r.task_id, r.url, r.data_json, r.record_hash, t.title, t.task_no "
                "FROM t_result r LEFT JOIN t_task t ON t.id = r.task_id "
                "WHERE r.status='VALID'"
            )
            if task_id:
                sql += f" AND r.task_id={int(task_id)}"
            sql += " ORDER BY r.id ASC"
            if limit:
                sql += f" LIMIT {int(limit)}"
            cur.execute(sql)
            return cur.fetchall()
    finally:
        conn.close()


async def get_default_user_id(db) -> int:
    """knowledge_documents.uploaded_by 是外键(必填), 取第一个用户(通常是 admin)"""
    res = await db.execute(text("SELECT id FROM users ORDER BY id ASC LIMIT 1"))
    row = res.fetchone()
    if not row:
        raise RuntimeError("users 表为空, 无法设置 uploaded_by, 请先启动 RAG 后端初始化 admin")
    return row[0]


def canonical_filename(task_id, title=None, task_no=None):
    """友好展示名 = 任务标题/业务号 + 稳定令牌 〔#{task_id}〕。
    令牌 〔#{task_id}〕 唯一且不会误匹配 #{task_id}0(因为有右括号闭合),
    无论出现在文件名哪个位置都能被 LIKE '%#{task_id}〕%' 稳定命中, 保证跨运行去重。"""
    display = (title or "").strip() or (task_no or "")
    if display:
        return f"{display} 〔#{task_id}〕"
    return f"〔#{task_id}〕"


async def ensure_kb_doc(db, task_id, file_size, user_id, title=None, task_no=None) -> int:
    """按 task_id 找到或新建一条 KnowledgeDocument, 返回其 id。
    身份令牌 〔#{task_id}〕 稳定, 重跑不会新建重复条目; 命中后顺手把展示名刷新为最新标题。
    若出现多条同名(历史残留重复), 取 id 最小者作为正本, 避免歧义。"""
    filename = canonical_filename(task_id, title, task_no)
    res = await db.execute(
        select(KnowledgeDocument).where(
            KnowledgeDocument.filename.like(f"%#{task_id}〕%")
        )
    )
    candidates = res.scalars().all()
    doc = min(candidates, key=lambda d: d.id) if candidates else None
    # 兼容优化前纯 'ai_crawl_task_{id}' 命名的条目
    if not doc:
        res = await db.execute(
            select(KnowledgeDocument).where(
                KnowledgeDocument.filename == f"ai_crawl_task_{task_id}"
            )
        )
        doc = res.scalar_one_or_none()
    if doc:
        if doc.filename != filename:
            doc.filename = filename
            await db.flush()
        return doc.id
    doc = KnowledgeDocument(
        filename=filename,
        file_type="md",            # 爬取文本近似 markdown; 避开前端未知图标
        file_size=file_size,
        product_category=None,
        uploaded_by=user_id,
        status="processing",
    )
    db.add(doc)
    await db.flush()
    await db.refresh(doc)
    return doc.id


def count_chunks_in_scope(vs, kb_doc_id):
    """直接从 Chroma 统计该 kb_doc_id 下的向量块数(含本次新增 + 历史对齐),
    避免用 'aligned + kept' 估算在重跑时被清零。"""
    try:
        r = vs._collection.get(where={"kb_doc_id": kb_doc_id}, include=[])
        return len(r.get("ids") or [])
    except Exception as e:
        print(f"  [warn] 统计块数失败(保留传入值): {e}")
        return None


def existing_record_hashes(vs, task_id):
    """(保留备用) 本任务已在 Chroma 中的 record_hash 集合。当前增量改以 chunk_hash
    内容指纹去重, 不再用它做预跳过, 以免部分回填的任务卡死; 仅作溯源调试用。"""
    try:
        r = vs._collection.get(where={"task_id": task_id}, include=["metadatas"])
    except Exception:
        return set()
    s = set()
    for m in (r.get("metadatas") or []):
        if m and m.get("record_hash"):
            s.add(m["record_hash"])
    return s


async def finalize_kb_doc(db, kb_doc_id, vs, fallback_count):
    res = await db.execute(
        select(KnowledgeDocument).where(KnowledgeDocument.id == kb_doc_id)
    )
    doc = res.scalar_one_or_none()
    if doc:
        doc.status = "indexed"
        n = count_chunks_in_scope(vs, kb_doc_id)
        doc.chunk_count = n if n is not None else fallback_count


def align_existing_chunks(vs, task_id, kb_doc_id):
    """把该任务此前已灌入 Chroma(但没有 kb_doc_id)的旧块补上 kb_doc_id。
    仅更新 metadata, 不重算向量。幂等: 已带 kb_doc_id 的块再更新也无妨。
    注意: Chroma 的 get(where=) 不支持多字段平铺, 故只按 origin 查, 再在 Python 侧按 task_id 过滤。"""
    try:
        old = vs._collection.get(
            where={"origin": "ai_crawl"},
            include=["metadatas"],
        )
    except Exception as e:
        print(f"  [warn] 查询旧块失败(跳过对齐): {e}")
        return 0
    ids = old.get("ids") or []
    metas = old.get("metadatas") or []
    pairs = [(i, m) for i, m in zip(ids, metas)
             if m and m.get("task_id") == task_id and not m.get("kb_doc_id")]
    if not pairs:
        return 0
    upd_ids = [i for i, _ in pairs]
    new_metas = [{**(m or {}), "kb_doc_id": kb_doc_id} for _, m in pairs]
    try:
        vs._collection.update(ids=upd_ids, metadatas=new_metas)
    except Exception as e:
        print(f"  [warn] 更新旧块 metadata 失败(跳过对齐): {e}")
        return 0
    print(f"  对齐 {len(upd_ids)} 个旧块 -> kb_doc_id={kb_doc_id}")
    return len(upd_ids)


async def process_task(db, task_id, task_rows, task_title, task_no, dry_run):
    raw = build_raw_documents(task_rows)
    print(f"\n[task {task_id}] 读取 {len(task_rows)} 条 VALID, 构造 {len(raw)} 篇文档"
          + (f"  任务标题: {task_title}" if task_title else ""))
    if not raw:
        return
    if dry_run:
        for d in raw[:3]:
            print("  meta:", d.metadata)
            print("  text:", d.page_content[:200].replace("\n", " "))
        print(f"  预览知识库名: {canonical_filename(task_id, task_title, task_no)}")
        return

    vs = get_vectorstore()
    # 切分 + 全局 chunk_hash 去重: 已存在的块(内容相同)直接跳过、不重嵌;
    # 命中旧块时回填 record_hash(使溯源完整)。用全量 raw 跑 —— 不做记录级预跳过,
    # 否则"部分已回填"的任务会卡死: 有 token -> raw 被清空 -> 其余块永远补不上 record_hash。
    file_size = sum(len(d.page_content) for d in raw)
    kept = split_and_dedup(raw)
    user_id = await get_default_user_id(db)
    kb_doc_id = await ensure_kb_doc(db, task_id, file_size, user_id, task_title, task_no)
    # 补齐旧块(此前无 kb_doc_id 的那些), 返回对齐的旧块数
    aligned = align_existing_chunks(vs, task_id, kb_doc_id)
    # 新块打 kb_doc_id 后入库
    for c in kept:
        c.metadata["kb_doc_id"] = kb_doc_id
    BATCH = 10  # 百炼 text-embedding-v3 单批上限为 10
    for i in range(0, len(kept), BATCH):
        vs.add_documents(kept[i:i + BATCH])
    # 该任务在 Chroma 中的总块数从 Chroma 实查(含历史旧块), 重跑不会被清零
    await finalize_kb_doc(db, kb_doc_id, vs, fallback_count=aligned + len(kept))
    await db.commit()
    print(f"  -> kb_doc_id={kb_doc_id} 状态=indexed, 总块数 {count_chunks_in_scope(vs, kb_doc_id)}"
          + f"(本次新增 {len(kept)})")


async def main_async():
    ap = argparse.ArgumentParser(description="ai_crawl 文章 -> RAG ChromaDB (含知识库登记)")
    ap.add_argument("--task-id", type=int, default=None, help="只导某个爬取任务")
    ap.add_argument("--limit", type=int, default=None, help="限制读取条数")
    ap.add_argument("--dry-run", action="store_true", help="只预览, 不写库")
    args = ap.parse_args()

    rows = fetch_rows(args.task_id, args.limit)
    print(f"从 ai_crawl.t_result 读取 {len(rows)} 条 VALID 记录")

    # 按 task_id 分组, 并记录每个任务的 title / task_no(来自 JOIN)
    tasks = {}
    task_meta = {}
    for r in rows:
        task_id, _, _, _, title, no = r[0], r[1], r[2], r[3], r[4], r[5]
        tasks.setdefault(task_id, []).append(r)
        if task_id not in task_meta:
            task_meta[task_id] = (title, no)

    if args.dry_run:
        for task_id in sorted(tasks):
            title, no = task_meta[task_id]
            await process_task(None, task_id, tasks[task_id], title, no, dry_run=True)
        return

    async with async_session_factory() as db:
        for task_id in sorted(tasks):
            title, no = task_meta[task_id]
            await process_task(db, task_id, tasks[task_id], title, no, dry_run=False)
    print(f"\n完成 -> ChromaDB collection: {settings.CHROMA_COLLECTION_NAME}")


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
