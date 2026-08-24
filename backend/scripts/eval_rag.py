"""
RAG 检索评估脚本 — 对 eval_set.json 逐条检索，统计期望关键词在 top-k 结果中的命中率。

用法:
    cd backend
    venv\\Scripts\\python.exe scripts/eval_rag.py [--top-k 5]

指标:
    all-hit: 该条所有期望关键词都出现在 top-k 结果中（严格命中）
    any-hit: 至少一个期望关键词命中（宽松命中）
    per-cat: 按类别统计 all-hit 率
"""

import asyncio
import json
import os
import sys
import argparse

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)


async def evaluate(top_k: int) -> dict:
    from app.rag.retriever import retrieve_with_scores

    eval_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval_set.json")
    with open(eval_path, encoding="utf-8") as f:
        cases = json.load(f)

    stats = {
        "all": 0, "any": 0, "total": len(cases), "by_cat": {},
        "mrr": 0.0, "rank1": 0, "rank3": 0, "rank5": 0,
    }
    detail_rows = []

    for c in cases:
        try:
            hits = await retrieve_with_scores(c["q"], top_k=top_k, use_cache=False)
        except Exception as e:
            print(f"!! {c['q'][:30]} 检索异常: {e}")
            continue
        texts = [d.page_content for d, _ in hits]
        joined = "\n".join(texts)
        hit_kws = [k for k in c["kw"] if k in joined]
        ok_all = len(hit_kws) == len(c["kw"])
        ok_any = len(hit_kws) > 0
        stats["all"] += int(ok_all)
        stats["any"] += int(ok_any)
        cat = c.get("cat", "其他")
        b = stats["by_cat"].setdefault(cat, {"all": 0, "total": 0})
        b["total"] += 1
        b["all"] += int(ok_all)

        # 首个命中的排名（1-based；未命中记 0）
        first_rank = 0
        for i, t in enumerate(texts):
            if any(k in t for k in c["kw"]):
                first_rank = i + 1
                break
        if first_rank > 0:
            stats["mrr"] += 1.0 / first_rank
            stats["rank1"] += int(first_rank == 1)
            stats["rank3"] += int(first_rank <= 3)
            stats["rank5"] += int(first_rank <= 5)

        mark = "✓" if ok_all else ("~" if ok_any else "✗")
        detail_rows.append(
            f"{mark} [{cat}] {c['q'][:32]}  命中{len(hit_kws)}/{len(c['kw'])} 首名@#{first_rank}"
        )

    n = stats["total"]
    stats["mrr"] = stats["mrr"] / n if n else 0.0
    return stats, detail_rows


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    stats, rows = await evaluate(args.top_k)
    if not args.quiet:
        print("\n".join(rows))
    total = stats["total"]
    print("\n========== 评估汇总 (top_k=%d) ==========" % args.top_k)
    print(f"严格命中率 all-hit: {stats['all']}/{total} = {stats['all']/total*100:.1f}%")
    print(f"MRR (首个命中排名倒数均值): {stats['mrr']:.4f}")
    print(f"首名命中 rank@1: {stats['rank1']}/{total} = {stats['rank1']/total*100:.1f}%")
    print(f"前3命中 rank@3: {stats['rank3']}/{total} = {stats['rank3']/total*100:.1f}%")
    print(f"前5命中 rank@5: {stats['rank5']}/{total} = {stats['rank5']/total*100:.1f}%")
    for cat, b in stats["by_cat"].items():
        print(f"  [{cat}] all-hit {b['all']}/{b['total']} = {b['all']/b['total']*100:.1f}%")


if __name__ == "__main__":
    asyncio.run(main())
