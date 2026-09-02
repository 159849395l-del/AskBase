"""
query_scope.py — 验证「智能体/会话绑定知识库」的轻量作用域检索（方案 C-lite）

用法（必须在 backend 目录下，用 venv 运行）:
  # 1) 列出当前已登记的 ai_crawl 知识库(task -> kb_doc_id 映射)
  python scripts/query_scope.py --list

  # 2) 全库检索(等价于原行为, 不带作用域)
  python scripts/query_scope.py --query "Sharp Objects"

  # 3) 仅在某几个知识库作用域内检索(智能体绑定 KB 的效果)
  python scripts/query_scope.py --query "Sharp Objects" --kb-doc-ids 5
  python scripts/query_scope.py --query "推荐" --kb-doc-ids 5,6,7

说明:
  - 不带 --kb-doc-ids 时走全库检索, 与历史行为完全一致(kb_doc_ids=None)。
  - 带 --kb-doc-ids 时仅在指定 kb_doc_id 集合内做向量+BM25 融合检索。
  - 这与原 product_category 过滤并存: 两者都为 None 才全库; kb_doc_ids 优先。
"""
import argparse
import asyncio

from app.rag.retriever import retrieve_with_scores
from app.rag.vector_store import get_vectorstore
from app.database import async_session_factory
from app.models.knowledge_document import KnowledgeDocument
from sqlalchemy import select


async def list_kbs():
    async with async_session_factory() as db:
        res = await db.execute(
            select(KnowledgeDocument)
            .where(KnowledgeDocument.filename.like("ai_crawl_task_%"))
            .order_by(KnowledgeDocument.id)
        )
        docs = res.scalars().all()
    print(f"已登记的 ai_crawl 知识库: {len(docs)} 个\n")
    print(f"  {'kb_doc_id':>9}  {'task':>5}  {'chunks':>6}  {'status':>9}  filename")
    print(f"  {'-'*9}  {'-'*5}  {'-'*6}  {'-'*9}  {'-'*22}")
    for d in docs:
        task = d.filename.replace("ai_crawl_task_", "")
        print(f"  {d.id:>9}  {task:>5}  {d.chunk_count:>6}  {d.status:>9}  {d.filename}")


def _fmt_source(meta: dict) -> str:
    return meta.get("source") or meta.get("filename") or "未知"


async def run_query(query: str, kb_doc_ids):
    # 全库(对照)
    full = await retrieve_with_scores(query, kb_doc_ids=None, use_cache=False)
    # 作用域(目标)
    scoped = await retrieve_with_scores(query, kb_doc_ids=kb_doc_ids, use_cache=False) if kb_doc_ids else []

    print(f"\n查询: {query!r}")
    print(f"  全库命中: {len(full)} 条 | 作用域{kb_doc_ids}命中: {len(scoped)} 条")

    if kb_doc_ids:
        print("\n--- 作用域内命中(前 5) ---")
        for doc, score in scoped[:5]:
            m = doc.metadata
            print(f"  [score={score:.4f}] kb_doc_id={m.get('kb_doc_id')} | {_fmt_source(m)}")
            print(f"      {doc.page_content[:70].replace(chr(10), ' ')}")

    # 交叉验证: 作用域命中的 kb_doc_id 必须全部落在给定集合内
    if kb_doc_ids:
        allowed = set(kb_doc_ids)
        leaked = [m.get("kb_doc_id") for doc, _ in scoped
                  if m.get("kb_doc_id") not in allowed]
        print(f"\n  作用域泄漏检查: {'通过 ✅' if not leaked else '失败 ❌ ' + str(leaked)}")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="列出 ai_crawl 知识库映射")
    ap.add_argument("--query", type=str, help="检索问题")
    ap.add_argument("--kb-doc-ids", type=str, default=None,
                    help="逗号分隔的 kb_doc_id 集合, 如 5 或 5,6,7; 省略=全库")
    args = ap.parse_args()

    if args.list:
        await list_kbs()
        return
    if not args.query:
        ap.error("需提供 --query 或 --list")

    kb_doc_ids = None
    if args.kb_doc_ids:
        kb_doc_ids = [int(x) for x in args.kb_doc_ids.split(",") if x.strip()]
    await run_query(args.query, kb_doc_ids)


if __name__ == "__main__":
    asyncio.run(main())
