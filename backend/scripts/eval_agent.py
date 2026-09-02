"""
Agent 端到端评估脚本 —— 在既有检索层评估（eval_rag.py）之上，补「整体任务层」：
  ① 答案正确率（关键词兜底 + 可选 LLM-as-judge）
  ② 工具调用准确率（retrieval / sql 是否按预期触发）
  ③ 忠实度（答案是否仅基于引用 sources，对齐 RAG_RULES「只根据参考文档回答」）
并复用 eval_rag.py 的 compute_retrieval_metrics（all-hit / MRR / rank@k）。

用法（在 backend/ 目录下）:
    python scripts/eval_agent.py                # 跑完整评测集
    python scripts/eval_agent.py --case 0       # 仅跑第 0 条（smoke）
    python scripts/eval_agent.py --no-judge     # 关闭 LLM 裁判，纯规则打分
    python scripts/eval_agent.py --top-k 5

依赖：本脚本所有项目依赖（app.*、langchain 等）均延迟到函数内 import，
因此 py_compile 与「缺依赖时仅校验 JSON / 逻辑」都可离线进行，不会在导入期崩溃。

注意（设计文档方案 B 边界）：
  - LLM-as-judge 必须人工标定校准，避免 judge 偏倚；默认开启，但失败时自动回退纯关键词规则打分。
  - 评测集里 SQL 类 case 的 kb_ids 为示意值（null）；要让 SQL 路径真正触发，
    需在 eval_agent_set.json 的 agent_config.kb_ids 填入真实的「数据库型 KB」ID。
"""

import asyncio
import json
import os
import re
import sys
import argparse

# 把 backend/ 与 backend/scripts/ 同时加入路径，便于 import app.* 与同目录的 eval_rag
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND_DIR)
sys.path.insert(0, SCRIPT_DIR)


# ===================== 模块级配置常量（不写入 config.py） =====================
EVAL_SET_PATH = os.path.join(SCRIPT_DIR, "eval_agent_set.json")
REPORT_PATH = os.path.join(SCRIPT_DIR, "eval_agent_report.json")

ANSWER_ACCURACY_MIN = 0.85   # 答案正确率上线阈值
TOOL_ACCURACY_MIN = 0.90     # 工具调用准确率上线阈值
FAITHFULNESS_MIN = 0.50      # 忠实度轻量阈值（仅作参考告警，不计入 pass）

TOP_K = 10                   # 复用检索指标时的召回深度
JUDGE_ENABLED = True         # LLM-as-judge 总开关
JUDGE_TEMPERATURE = 0.0      # 裁判模型温度（确定性）

# 评测集字段名（与 eval_agent_set.json 对齐）
F_QUESTION = "question"
F_MULTI_TURN = "multi_turn"
F_AGENT_CFG = "agent_config"
F_EXPECTED_TOOLS = "expected_tools"
F_EXPECTED_KW = "expected_answer_keywords"
F_EXPECTED_SRC = "expected_sources"


# ===================== 规则兜底打分器（纯关键词，零调参可跑） =====================
def rule_answer_score(answer: str, keywords: list) -> float:
    """答案正确率·规则版：期望关键词在最终答案中的覆盖率。"""
    if not keywords:
        # 无期望关键词时：有实质回答（非拒答）即给满分
        return 1.0 if answer and ("未找到" not in answer and "无法" not in answer) else 0.0
    hit = sum(1 for k in keywords if k in answer)
    return hit / len(keywords)


def rule_faithfulness_score(answer: str, sources: list) -> float:
    """忠实度·规则版：引用来源文件名在答案中出现的比例。
    无来源且为拒答提示 → 视为忠实（1.0）；有来源但完全未引用 → 低分。"""
    if not sources:
        return 1.0 if ("未找到" in answer or "无法" in answer) else 0.5
    names = [s.get("filename", "") for s in sources if s.get("filename")]
    if not names:
        return 0.5
    cited = sum(1 for n in names if n and n in answer)
    return cited / len(names)


# ===================== LLM-as-judge（复用项目配置，失败回退规则） =====================
def get_judge_llm():
    """构造非流式裁判 LLM（读取 settings，不修改 config.py）。无 API key 时返回 None。"""
    try:
        from langchain_openai import ChatOpenAI
        from app.config import settings
    except Exception:
        return None
    if not getattr(settings, "LLM_API_KEY", ""):
        return None
    return ChatOpenAI(
        model=settings.LLM_MODEL,
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_API_BASE,
        temperature=JUDGE_TEMPERATURE,
        streaming=False,
    )


def _parse_score(text: str):
    """从裁判回复中解析 0~1 分数；兼容 0-10 量表（自动归一）。失败返回 None。"""
    if not text:
        return None
    for tok in re.findall(r"0?\.\d+|\d+\.?\d*", text):
        v = float(tok)
        if 0.0 <= v <= 1.0:
            return v
        if 1.0 < v <= 10.0:
            return v / 10.0
    return None


def llm_judge_answer(question: str, answer: str, sources: list):
    """答案正确率·LLM 裁判。返回 0~1 或 None（异常/无 key 时回退规则）。"""
    llm = get_judge_llm()
    if llm is None:
        return None
    ctx = "\n".join(s.get("chunk_text", "") for s in sources[:5])
    prompt = (
        "你是严谨的评测裁判。请判断【回答】是否准确、完整地回答了【问题】，"
        "且仅基于【参考来源】、没有编造。\n"
        "只输出一个 0 到 1 之间的小数分数，不要输出任何其他内容。\n\n"
        f"问题:\n{question}\n\n参考来源:\n{ctx}\n\n回答:\n{answer}\n\n分数:"
    )
    try:
        resp = llm.invoke(prompt)
        return _parse_score(resp.content)
    except Exception:
        return None


def llm_judge_faithfulness(answer: str, sources: list):
    """忠实度·LLM 裁判。返回 0~1 或 None。"""
    llm = get_judge_llm()
    if llm is None:
        return None
    ctx = "\n".join(s.get("chunk_text", "") for s in sources[:5])
    prompt = (
        "判断【回答】是否仅基于【参考来源】、未引入外部知识或编造。\n"
        "只输出一个 0 到 1 之间的小数分数，不要输出任何其他内容。\n\n"
        f"参考来源:\n{ctx}\n\n回答:\n{answer}\n\n分数:"
    )
    try:
        resp = llm.invoke(prompt)
        return _parse_score(resp.content)
    except Exception:
        return None


# ===================== 单条 case 执行 =====================
async def run_case(case: dict, top_k: int, compute_retrieval_metrics) -> dict:
    """跑完整链路 stream_rag_response，收集答案/sources/是否走 SQL，并三层判分。"""
    from app.rag.chain import stream_rag_response
    from app.rag.retriever import retrieve_with_scores

    question = case.get(F_QUESTION, "")
    multi_turn = case.get(F_MULTI_TURN) or []
    # multi_turn 视为前置用户轮（示意性；chat.py 的 chat_history 为 [(role, content), ...]）
    chat_history = [("human", q) for q in multi_turn]

    agent_cfg = case.get(F_AGENT_CFG) or {}
    kb_ids = agent_cfg.get("kb_ids")
    system_prompt = agent_cfg.get("system_prompt")

    # —— 消费 async generator，收集最终答案 / sources / 是否执行 SQL ——
    answer_text = ""
    sources = []
    async for evt in stream_rag_response(
        question, chat_history, kb_ids=kb_ids, system_prompt=system_prompt
    ):
        t = evt.get("type")
        if t == "token":
            answer_text += evt.get("content", "")
        elif t == "sources":
            sources = evt.get("sources", [])
        elif t == "done":
            answer_text = evt.get("full_response", answer_text)
        elif t == "no_results":
            answer_text = evt.get("message", answer_text)

    # SQL 是否执行：来源里存在 kind=="sql" 或 score_type=="sql"
    used_sql = any(
        s.get("kind") == "sql" or s.get("score_type") == "sql" for s in sources
    )
    # 是否走文档检索：来源中存在非 SQL 类（score_type != "sql"）
    retrieval_used = any(s.get("score_type") != "sql" for s in sources)

    # —— ② 工具调用准确率 ——
    expected_tools = case.get(F_EXPECTED_TOOLS, [])
    tool_results = {}
    if "sql" in expected_tools:
        tool_results["sql"] = bool(used_sql)
    if "retrieval" in expected_tools:
        tool_results["retrieval"] = bool(retrieval_used)
    satisfied = sum(1 for v in tool_results.values() if v)
    tool_score = satisfied / len(expected_tools) if expected_tools else 1.0

    # 期望来源命中率（信息性指标，不计入 pass）
    expected_src = case.get(F_EXPECTED_SRC, [])
    src_names = [s.get("filename", "") for s in sources]
    src_hit = [s for s in expected_src if any(s in n for n in src_names)]
    src_hit_rate = len(src_hit) / len(expected_src) if expected_src else 1.0

    # —— ① 答案正确率（规则兜底 + 可选 LLM 裁判）——
    kws = case.get(F_EXPECTED_KW, [])
    rule_ans = rule_answer_score(answer_text, kws)
    judge_ans = llm_judge_answer(question, answer_text, sources) if JUDGE_ENABLED else None
    answer_score = judge_ans if judge_ans is not None else rule_ans
    # 若 judge 可用，最终分取「规则 + 裁判」平均，兼顾可复现与主观质量
    if judge_ans is not None:
        answer_score = round(0.5 * rule_ans + 0.5 * judge_ans, 4)
    else:
        answer_score = round(rule_ans, 4)

    # —— ③ 忠实度（规则 + 可选 LLM 裁判）——
    rule_faith = rule_faithfulness_score(answer_text, sources)
    judge_faith = (
        llm_judge_faithfulness(answer_text, sources) if JUDGE_ENABLED else None
    )
    if judge_faith is not None:
        faith_score = round(0.5 * rule_faith + 0.5 * judge_faith, 4)
    else:
        faith_score = round(rule_faith, 4)

    # —— 复用 eval_rag 的检索指标（all-hit / MRR / rank@k）——
    try:
        docs = await retrieve_with_scores(
            question, kb_ids=kb_ids, top_k=top_k, use_cache=False
        )
        texts = [d.page_content for d, _ in docs]
        rm = compute_retrieval_metrics(texts, kws) if kws else {
            "all_hit": None, "any_hit": None, "hit_kws": [], "first_rank": 0
        }
    except Exception as e:
        rm = {"all_hit": None, "any_hit": None, "hit_kws": [], "first_rank": 0, "error": str(e)}

    return {
        "question": question,
        "multi_turn": multi_turn,
        "expected_tools": expected_tools,
        "used_sql": used_sql,
        "retrieval_used": retrieval_used,
        "tool_results": tool_results,
        "tool_score": round(tool_score, 4),
        "src_hit_rate": round(src_hit_rate, 4),
        "expected_src": expected_src,
        "src_hit": src_hit,
        "expected_kw": kws,
        "answer_len": len(answer_text),
        "answer_excerpt": answer_text[:200],
        "answer_score": answer_score,
        "answer_rule": round(rule_ans, 4),
        "answer_judge": (round(judge_ans, 4) if judge_ans is not None else None),
        "faith_score": faith_score,
        "faith_rule": round(rule_faith, 4),
        "faith_judge": (round(judge_faith, 4) if judge_faith is not None else None),
        "retrieval_metrics": rm,
    }


# ===================== 汇总与报告 =====================
def _mean(vals):
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else 0.0


async def evaluate_all(cases: list, top_k: int) -> dict:
    from eval_rag import compute_retrieval_metrics  # 复用，禁止重写

    results = []
    blockers = []
    for i, case in enumerate(cases):
        try:
            r = await run_case(case, top_k, compute_retrieval_metrics)
        except Exception as e:
            # 链路执行失败（多为依赖/DB 缺失）：记 blocker，不中断整体
            blockers.append(f"case#{i} [{case.get(F_QUESTION, '')[:24]}]: {e}")
            r = {"question": case.get(F_QUESTION, ""), "error": str(e)}
        results.append(r)

    ans_scores = [r.get("answer_score") for r in results if "answer_score" in r]
    tool_scores = [r.get("tool_score") for r in results if "tool_score" in r]
    faith_scores = [r.get("faith_score") for r in results if "faith_score" in r]
    all_hits = [
        r["retrieval_metrics"].get("all_hit")
        for r in results
        if r.get("retrieval_metrics", {}).get("all_hit") is not None
    ]

    ans_mean = _mean(ans_scores)
    tool_mean = _mean(tool_scores)
    faith_mean = _mean(faith_scores)
    retrieval_all_hit_rate = (sum(1 for x in all_hits if x) / len(all_hits)) if all_hits else None

    answer_pass = ans_mean >= ANSWER_ACCURACY_MIN
    tool_pass = tool_mean >= TOOL_ACCURACY_MIN

    summary = {
        "total_cases": len(cases),
        "ran_cases": len(ans_scores),
        "answer_accuracy_mean": round(ans_mean, 4),
        "answer_accuracy_min": ANSWER_ACCURACY_MIN,
        "answer_pass": answer_pass,
        "tool_accuracy_mean": round(tool_mean, 4),
        "tool_accuracy_min": TOOL_ACCURACY_MIN,
        "tool_pass": tool_pass,
        "faithfulness_mean": round(faith_mean, 4),
        "retrieval_all_hit_rate(reused)": (
            round(retrieval_all_hit_rate, 4) if retrieval_all_hit_rate is not None else None
        ),
        "reached_thresholds": answer_pass and tool_pass,
        "blockers": blockers,
    }
    return {"summary": summary, "cases": results}


def print_report(report: dict):
    s = report["summary"]
    print("\n========== Agent 端到端评估汇总 ==========")
    print(f"评测条数: {s['ran_cases']}/{s['total_cases']}")
    print(f"答案正确率均值: {s['answer_accuracy_mean']}  (阈值≥{s['answer_accuracy_min']})  -> {'达标✓' if s['answer_pass'] else '未达标✗'}")
    print(f"工具调用准确率均值: {s['tool_accuracy_mean']}  (阈值≥{s['tool_accuracy_min']})  -> {'达标✓' if s['tool_pass'] else '未达标✗'}")
    print(f"忠实度均值: {s['faithfulness_mean']}")
    print(f"检索 all-hit 率(复用): {s['retrieval_all_hit_rate(reused)']}")
    print(f"整体是否达上线阈值: {'是✓' if s['reached_thresholds'] else '否✗'}")
    if s["blockers"]:
        print("\n-- 阻塞点（链路执行失败，多为依赖/DB/KB 未配置）--")
        for b in s["blockers"]:
            print("  ! " + b)
    print("\n-- 逐条明细 --")
    for i, c in enumerate(report["cases"]):
        if "error" in c:
            print(f"  #{i} ✗ {c['question'][:28]}  错误: {c['error'][:80]}")
            continue
        print(
            f"  #{i} {c['question'][:26]} | 答:{c['answer_score']} "
            f"(规{c['answer_rule']}/裁{c['answer_judge']}) | 工具:{c['tool_score']} "
            f"{c['tool_results']} | 忠:{c['faith_score']} | SQL:{c['used_sql']}"
        )


# ===================== 入口 =====================
async def main_async(args):
    with open(EVAL_SET_PATH, encoding="utf-8") as f:
        cases = json.load(f)

    if args.case is not None:
        cases = [cases[args.case]]

    if args.no_judge:
        global JUDGE_ENABLED
        JUDGE_ENABLED = False

    report = await evaluate_all(cases, args.top_k)

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    if not args.quiet:
        print_report(report)
    print(f"\n报告已写入: {REPORT_PATH}")


def main():
    parser = argparse.ArgumentParser(description="Agent 端到端评估")
    parser.add_argument("--case", type=int, default=None, help="仅评测第 N 条（0-based），用于 smoke")
    parser.add_argument("--top-k", type=int, default=TOP_K)
    parser.add_argument("--no-judge", action="store_true", help="关闭 LLM 裁判，纯规则打分")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
