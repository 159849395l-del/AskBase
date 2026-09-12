"""引用来源可信化整体验收 — 走真实 HTTP、真实模型与真实联网搜索。

覆盖工单 .scratch/citation-sources/issues/01-trusted-citations.md 的验收点：
1. 联网搜索产生的网页来源出现在答案下方的来源列表里，且带可点击链接
2. 正文里的 [来源N] 都能在来源列表里逐条对上（编号一套、不错位）
3. 工具调用过程在界面上可见（tool_call 事件）
4. 刷新页面（重新拉会话详情）后工具调用与网页来源仍在
5. Exa 不可用时，百度/Bing 回退路径同样能列出来源

用法（先启动后端，:8000 已在跑则直接执行）:
    cd backend
    set PYTHONIOENCODING=utf-8
    venv\Scripts\python.exe scripts/accept_citations.py [API 地址，默认 http://127.0.0.1:8000]

说明:
- 会真实调用模型与搜索引擎各若干次，请在开发环境运行。
- 会新建一个会话（保留在开发库里，便于随后打开聊天页肉眼核对）。
- 任一验收点不通过时以非零退出码结束。
"""

import asyncio
import json
import os
import re
import sys

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("ASKBASE_API", "http://127.0.0.1:8000")
DEMO_AGENT_NAME = "验收演示助手"
QUESTION = "2026年春节放假是从几号到几号？请给出具体日期。"

_results = []


def check(name: str, ok: bool, detail=None) -> None:
    _results.append((bool(ok), name))
    mark = "[PASS]" if ok else "[FAIL]"
    suffix = "  | " + str(detail) if detail is not None else ""
    print("  %s %s%s" % (mark, name, suffix))


def parse_sse(text: str):
    """把 SSE 文本解析成 [(event, data)]"""
    out = []
    for block in text.split("\n\n"):
        if not block.strip():
            continue
        event, data = "", ""
        for line in block.split("\n"):
            if line.startswith("event: "):
                event = line[7:].strip()
            elif line.startswith("data: "):
                data = line[6:].strip()
        if data:
            out.append((event, json.loads(data)))
    return out


def ask(c, h, agent_id):
    """新建会话并向智能体提问，返回 (events, conv_id)"""
    conv = c.post("/api/conversations", headers=h, json={"agent_id": agent_id}).json()
    r = c.post(
        "/api/conversations/%d/messages" % conv["id"],
        headers=h,
        json={"content": QUESTION},
        timeout=300,
    )
    r.raise_for_status()
    return parse_sse(r.text), conv["id"]


def _iter_sources(sources):
    for i, s in enumerate(sources, 1):
        yield i, s


def main() -> int:
    c = httpx.Client(base_url=BASE, timeout=60)
    token = c.post("/api/auth/login", data={"username": "admin", "password": "123456"}).json()["access_token"]
    h = {"Authorization": "Bearer " + token}

    agents = c.get("/api/agents", headers=h).json()
    agent = next((a for a in agents if a["name"] == DEMO_AGENT_NAME), None)
    if agent is None:
        print("找不到验收智能体 %s，请先跑一次 accept_usage.py" % DEMO_AGENT_NAME)
        return 1

    print("T1 联网提问：网页来源要出现在来源列表里")
    events, conv_id = ask(c, h, agent["id"])
    kinds = [e for e, _ in events]
    answer = "".join(d.get("token", "") for e, d in events if e == "token")
    tool_calls = [d for e, d in events if e == "tool_call"]
    sources = next((d.get("sources") or [] for e, d in events if e == "sources"), [])

    print("     回答：%s" % answer.replace("\n", " ")[:120])
    print("     事件类型：%s" % sorted(set(kinds)))
    check("发生了工具调用（tool_call 事件）", bool(tool_calls), [t["name"] for t in tool_calls])

    web = [(i, s) for i, s in _iter_sources(sources) if s.get("kind") == "web"]
    check("来源列表里有网页来源", bool(web), "共 %d 条来源，其中网页 %d 条" % (len(sources), len(web)))
    check("网页来源带可点击链接", bool(web) and all(s.get("url", "").startswith("http") for _, s in web))
    check("网页来源带标题", bool(web) and all(s.get("title") for _, s in web))

    print("T2 编号一一对应：正文 [来源N] ↔ 列表第 N 条")
    # 模型偶发写成全角【来源N】—— 那是同一个编号，只是括号全角，不能判失败
    cited = sorted({int(n) for n in re.findall(r"[\[【]来源\s*(\d+)[\]】]", answer)})
    loose = sorted({int(n) for n in re.findall(r"[\[【](\d+)[\]】]", answer)})
    check("正文引用了统一编号", bool(cited), "引用编号 %s" % cited)
    check(
        "引用的编号都落在来源列表范围内",
        bool(cited) and max(cited) <= len(sources),
        "引用 %s / 共 %d 条来源" % (cited, len(sources)),
    )
    # 逐条落到具体来源上：编号能对上一条「有标题、网页还带链接」的来源，才算真对上
    mapped = []
    for n in cited:
        s = sources[n - 1] if 1 <= n <= len(sources) else {}
        label = s.get("title") or s.get("filename") or ""
        usable = bool(label) and (s.get("kind") != "web" or str(s.get("url", "")).startswith("http"))
        mapped.append((n, label, usable))
        print("     [来源%d] → [%s] %s%s" % (
            n, s.get("kind") or "doc", label or "（空白来源）", "" if usable else "  ← 不可用"
        ))
    check(
        "每个引用都落到一条可展示的来源（标题非空，网页带链接）",
        bool(cited) and all(usable for _, _, usable in mapped),
    )
    check(
        "来源之间没有重复项（同一编号只对应一条）",
        len(sources) == len({(s.get("kind"), s.get("title") or s.get("filename"), s.get("url")) for s in sources}),
    )
    if loose:
        print("     [提示] 正文里还有裸编号 %s（非 [来源N] 形式），人工核对一下" % loose)

    print("T3 留痕：刷新后工具调用与来源仍在")
    detail = c.get("/api/conversations/%d" % conv_id, headers=h).json()
    assistant = [m for m in detail["messages"] if m["role"] == "assistant"]
    check("助手消息已落库", bool(assistant))
    if assistant:
        msg = assistant[-1]
        check("落库的 tool_calls 可读回", bool(msg.get("tool_calls")), [t["name"] for t in (msg.get("tool_calls") or [])])
        saved_web = [s for s in (msg.get("sources") or []) if s.get("kind") == "web"]
        check("落库的网页来源可读回", len(saved_web) == len(web), "落库 %d 条 / 流式 %d 条" % (len(saved_web), len(web)))

    print("T4 回退路径：Exa 不可用时百度/Bing 也要给出来源")
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from app.config import settings

    settings.EXA_API_KEY = ""  # 强制走回退
    from app.skills.handlers import web_search

    text, fb_sources = asyncio.run(web_search({"query": QUESTION, "read_pages": 1}))
    check("回退路径拿到了结果", bool(fb_sources), "共 %d 条" % len(fb_sources))
    check("回退来源带链接", bool(fb_sources) and all(s.get("url", "").startswith("http") for s in fb_sources))
    if fb_sources:
        print("     例：%s → %s" % (fb_sources[0]["title"][:30], fb_sources[0]["url"][:70]))
    print("     工具文本末段：%s" % text[-160:].replace("\n", " "))

    failed = [n for ok, n in _results if not ok]
    print("\n验收结果：%d/%d 通过" % (len(_results) - len(failed), len(_results)))
    if failed:
        print("未通过：%s" % "；".join(failed))
        return 1
    print("会话 id=%d，可在聊天页打开核对" % conv_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
