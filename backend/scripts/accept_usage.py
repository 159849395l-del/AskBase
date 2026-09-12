"""用量统计整体验收脚本 — 走真实 HTTP 与真实模型，逐条核对用量统计的验收点。

覆盖：采集链路（真实用量/短路不记账）、双计数口径、按智能体明细、
日/月/年维度与补零、整页作用域下钻。

用法（先启动后端）:
    cd backend
    venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
    # 另开一个终端（中文输出需要 UTF-8）
    set PYTHONIOENCODING=utf-8
    venv\Scripts\python.exe scripts/accept_usage.py [API 地址，默认 http://127.0.0.1:8000]

说明:
- 会真实调用模型若干次（约 4~6 次），请在开发环境运行。
- 会创建/复用一个名为「验收演示助手」的智能体，并新建一个会话；
  这些数据会保留在开发库里，方便随后打开「用量统计」页面肉眼核对。
- 任一验收点不通过时以非零退出码结束，可直接作为人工回归的闸门。
"""

import json
import os
import sqlite3
import sys

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("ASKBASE_API", "http://127.0.0.1:8000")
DEMO_AGENT_NAME = "验收演示助手"
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "app.db")

_results = []


def check(name: str, ok: bool, detail=None) -> None:
    _results.append((bool(ok), name))
    mark = "[PASS]" if ok else "[FAIL]"
    suffix = "  | " + str(detail) if detail is not None else ""
    print("  %s %s%s" % (mark, name, suffix))


def main() -> int:
    c = httpx.Client(base_url=BASE, timeout=300)

    print("T1 走通采集链路")
    r = c.get("/api/admin/usage/overview")
    check("未登录访问统计接口被拒", r.status_code == 401, "HTTP %d" % r.status_code)

    token = c.post("/api/auth/login", data={"username": "admin", "password": "123456"}).json()["access_token"]
    h = {"Authorization": "Bearer " + token}

    # 复用同名演示智能体，避免重复运行时撞上智能体名称唯一索引
    skill = c.get("/api/skills", headers=h).json()[0]
    existing = [a for a in c.get("/api/agents", headers=h).json() if a["name"] == DEMO_AGENT_NAME]
    if existing:
        agent = existing[0]
    else:
        agent = c.post("/api/agents", headers=h, json={
            "name": DEMO_AGENT_NAME,
            "description": "用量统计整体验收用，可随时删除",
            "system_prompt": "你是测试助手，回答务必简短。",
            "tools": [{"tool_type": "skill", "tool_ref_id": skill["id"], "enabled": True}],
        }).json()
    conv = c.post("/api/conversations", headers=h, json={"agent_id": agent["id"]}).json()

    # 挂工具的智能体不会走「无结果短路」，因此会产生真实的主回答与工具轮调用
    token_counts = []
    for q in ["现在几点了？", "再确认一次时间", "最后一次确认"]:
        with c.stream("POST", "/api/conversations/%d/messages" % conv["id"], headers=h,
                      json={"content": q}) as resp:
            events, done = set(), None
            for line in resp.iter_lines():
                if line.startswith("event: "):
                    events.add(line[7:])
                elif line.startswith("data: ") and "done" in events and done is None:
                    done = line[6:]
            token_counts.append((resp.status_code, "done" in events,
                                 json.loads(done)["token_count"] if done else 0))

    check("三次真实问答均成功返回", all(x[0] == 200 and x[1] for x in token_counts))
    check("done 事件带回真实 token（不是字符数）",
          all(x[2] > 0 for x in token_counts), [x[2] for x in token_counts])

    # 没有智能体、也没有命中知识库的提问应当短路，不产生任何流水
    plain = c.post("/api/conversations", headers=h, json={}).json()
    with c.stream("POST", "/api/conversations/%d/messages" % plain["id"], headers=h,
                  json={"content": "你好"}) as resp:
        plain_events = sorted({l[7:] for l in resp.iter_lines() if l.startswith("event: ")})
    check("命中无结果短路时不调用模型", "no_results" in plain_events, plain_events)

    # 智能体配置测试端点的消耗：类型应为 agent_test，且无会话归属
    with c.stream("POST", "/api/agents/test", headers=h,
                  json={"question": "现在几点", "system_prompt": "简短回答",
                        "tools": [{"tool_type": "skill", "tool_ref_id": skill["id"], "enabled": True}]}) as resp:
        for _ in resp.iter_lines():
            pass

    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "select call_type, status, is_estimated, count(*) n from llm_usage_logs group by 1,2,3"
    ).fetchall()
    by_type = {r["call_type"]: r["n"] for r in rows}
    print("     流水分布:", by_type)
    check("一次提问留下多类记录", len(by_type) >= 2)
    check("全部为端点返回的真实用量（无估算行）", all(r["is_estimated"] == 0 for r in rows))
    check("短路提问未产生任何记录",
          con.execute("select count(*) from llm_usage_logs where conversation_id=?",
                      (plain["id"],)).fetchone()[0] == 0)

    print()
    print("T2 双计数口径 / T3 按智能体明细")
    ov = c.get("/api/admin/usage/overview", headers=h).json()
    total = ov["totals"]
    check("问答次数等于本轮提问数", total["requests"] >= 3, total["requests"])
    check("模型调用次数大于问答次数（含内部编排）",
          total["llm_calls"] > total["requests"], "%d > %d" % (total["llm_calls"], total["requests"]))
    check("明细逐列与汇总自洽",
          sum(a["total_tokens"] for a in ov["agents"]) == total["total_tokens"]
          and sum(a["llm_calls"] for a in ov["agents"]) == total["llm_calls"])
    check("明细按总 token 降序",
          [a["total_tokens"] for a in ov["agents"]]
          == sorted([a["total_tokens"] for a in ov["agents"]], reverse=True))
    names = [a["agent_name"] for a in ov["agents"]]
    check("无归属记录归入「未绑定智能体」", "未绑定智能体" in names, names)
    check("演示智能体出现在明细里", DEMO_AGENT_NAME in names, names)

    print()
    print("T4 日/月/年维度与补零")
    for granularity, expected in (("day", 30), ("month", 12), ("year", 5)):
        ts = c.get("/api/admin/usage/timeseries", headers=h, params={"granularity": granularity}).json()
        ov2 = c.get("/api/admin/usage/overview", headers=h, params={"granularity": granularity}).json()
        check("%s 粒度桶数正确" % granularity, len(ts["points"]) == expected, len(ts["points"]))
        check("%s 粒度：两个接口区间一致" % granularity,
              (ts["start"], ts["end"]) == (ov2["start"], ov2["end"]),
              "%s ~ %s" % (ts["start"], ts["end"]))
        check("%s 粒度：序列合计与总览一致" % granularity,
              sum(p["total_tokens"] for p in ts["points"]) == ov2["totals"]["total_tokens"])

    r = c.get("/api/admin/usage/timeseries", headers=h,
              params={"granularity": "day", "start": "2016-01-01", "end": "2026-01-01"})
    check("跨度超上限被明确拒绝",
          r.status_code == 400 and "时间跨度过大" in r.json().get("detail", ""),
          r.json().get("detail"))

    print()
    print("T5 整页作用域下钻")
    scoped = c.get("/api/admin/usage/overview", headers=h,
                   params={"agent_id": agent["id"]}).json()
    row = [a for a in ov["agents"] if a["agent_id"] == agent["id"]]
    check("限定后的合计等于未限定时该行",
          bool(row) and scoped["totals"]["total_tokens"] == row[0]["total_tokens"],
          "%s vs %s" % (scoped["totals"]["total_tokens"], row[0]["total_tokens"] if row else None))
    check("限定后明细只剩该智能体",
          len(scoped["agents"]) == 1 and scoped["agents"][0]["agent_id"] == agent["id"])
    ts_one = c.get("/api/admin/usage/timeseries", headers=h,
                   params={"granularity": "day", "agent_id": agent["id"]}).json()
    check("限定后时间序列只统计该智能体",
          sum(p["total_tokens"] for p in ts_one["points"]) == scoped["totals"]["total_tokens"])
    empty = c.get("/api/admin/usage/overview", headers=h, params={"agent_id": 999999}).json()
    check("限定到无数据的智能体返回全零",
          empty["totals"]["llm_calls"] == 0 and empty["agents"] == [])

    passed = sum(1 for ok, _ in _results if ok)
    print()
    print("=" * 62)
    print("验收结果: %d/%d 通过" % (passed, len(_results)))
    for ok, name in _results:
        if not ok:
            print("  未通过:", name)
    print("保留数据: 智能体 id=%d 会话 id=%d（可在「用量统计」页面核对）"
          % (agent["id"], conv["id"]))
    print("=" * 62)
    return 0 if passed == len(_results) else 1


if __name__ == "__main__":
    sys.exit(main())
