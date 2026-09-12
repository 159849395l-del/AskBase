"""RAG 优化冒烟测试 — 真实链路

覆盖单元测试够不着的两个端到端行为：
1. 知识库作用域：带 kb_ids 问答，来源不得越出所选知识库
2. 无结果兜底：检索为空时返回兜底文案，不调用 LLM

真实调用 LLM + 百炼 embedding。前置条件：后端已启动
（uvicorn，默认 localhost:8000），未启动时自动跳过。

运行：
  pytest tests/test_stress_rag_optimized.py -v

历史说明：本文件原有一个「品类过滤」用例，打的是 `GET /api/categories` 与请求体里的
`product_category`。那套按品类字符串过滤的检索已在知识库改造（5aba0c6）中整体换成
按 `kb_ids` 的作用域检索 —— 端点与字段都不存在了，用例随之改写为下面的作用域用例。
"""

import json
import socket

import httpx
import pytest

from app.rag.chain import NO_RESULT_MESSAGE

pytestmark = pytest.mark.stress

BASE_URL = "http://localhost:8000"
USERNAME = "admin"
PASSWORD = "123456"
TIMEOUT = httpx.Timeout(connect=10, read=120, write=30, pool=30)

# 通用问题：不绑定特定知识库，命中与否交给检索，命中才做作用域断言
GENERIC_QUESTION = "这份资料主要讲了什么内容？"
# 明显不在任何知识库中的问题（触发无结果兜底）
UNKNOWN_QUESTION = "量子色动力学中的色荷是什么？"


def _backend_up() -> bool:
    """探测后端是否在运行（不可用则跳过压测，避免挂掉质量门）"""
    try:
        with socket.create_connection(("127.0.0.1", 8000), timeout=2):
            return True
    except OSError:
        return False


def _parse_sse(raw: str):
    """解析 text/event-stream 文本为 [(event_type, data), ...]"""
    events = []
    for block in raw.split("\n\n"):
        if not block.strip():
            continue
        event_type = None
        data_lines = []
        for line in block.splitlines():
            if line.startswith("event:"):
                event_type = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data_lines.append(line[len("data:"):].strip())
        if event_type is not None:
            events.append((event_type, "\n".join(data_lines)))
    return events


def _login_token(client: httpx.Client) -> str:
    """登录并返回 Bearer token"""
    r = client.post("/api/auth/login",
                    data={"username": USERNAME, "password": PASSWORD})
    r.raise_for_status()
    return r.json()["access_token"]


def _run_case(case):
    """同步包装器：登录 → 建会话 → 跑用例 → 删掉这次建的会话

    用完自己收拾：冒烟测试每跑一次就往开发库里塞一条会话，攒着会把「我的会话」淹掉。
    """
    with httpx.Client(base_url=BASE_URL, timeout=TIMEOUT) as client:
        token = _login_token(client)
        headers = {"Authorization": f"Bearer {token}"}
        r = client.post("/api/conversations", json={"title": "rag-opt-smoke"}, headers=headers)
        r.raise_for_status()
        conv_id = r.json()["id"]
        try:
            return case(client, headers, conv_id)
        finally:
            # 清理失败不该把用例结果带偏（比如会话已被别的用例删掉）
            try:
                client.delete(f"/api/conversations/{conv_id}", headers=headers)
            except Exception:
                pass


def _chat_sse(client: httpx.Client, headers: dict, conv_id: int,
              content: str, kb_ids: list = None) -> list:
    """发送消息并完整消费 SSE 流，返回事件列表"""
    body = {"content": content}
    if kb_ids:
        body["kb_ids"] = kb_ids
    with client.stream(
        "POST",
        f"/api/conversations/{conv_id}/messages",
        json=body,
        headers=headers,
    ) as resp:
        if resp.status_code != 200:
            raise RuntimeError(f"chat HTTP {resp.status_code}")
        raw = "".join(c.decode("utf-8", errors="replace") for c in resp.iter_bytes())
    return _parse_sse(raw)


def _tokens_of(events) -> str:
    return "".join(json.loads(d).get("token", "") for t, d in events if t == "token")


def _sources_of(events) -> list:
    for t, d in events:
        if t == "sources":
            return json.loads(d)["sources"]
    return []


def _assert_model_usable(events) -> None:
    """模型不可用（配额/计费）不是代码问题，跳过而不是误报失败

    不这么做的话，Key 欠费会表现为「SSE 出现 error」，
    看起来像检索链路坏了，实际只是余额没了。
    """
    errors = [json.loads(d).get("error", "") for t, d in events if t == "error"]
    for err in errors:
        if "Insufficient Balance" in err or "402" in err:
            pytest.skip(f"模型 Key 不可用（{err[:80]}），跳过真实链路冒烟")


def _scopable_kb(client: httpx.Client, headers: dict):
    """找一个「已入库文档」的文档型知识库；没有就返回 None

    只挑文档型：数据库型知识库要连外部 MySQL，不该成为本冒烟测试的前置条件。
    """
    r = client.get("/api/knowledge-bases", headers=headers)
    r.raise_for_status()
    candidates = [
        kb for kb in r.json()
        if kb.get("type") == "document" and kb.get("doc_count", 0) > 0
    ]
    return candidates[0] if candidates else None


def _kb_filenames(client: httpx.Client, headers: dict, kb_id: int) -> set:
    """该知识库里所有已入库文档的文件名 —— 来源里出现的名字必须落在这个集合内"""
    r = client.get("/api/kb/documents", headers=headers, params={"kb_id": kb_id, "page_size": 100})
    r.raise_for_status()
    return {d["filename"] for d in r.json()["items"]}


def test_kb_scoped_qa():
    """知识库作用域：带 kb_ids 问答，来源不得越出所选知识库"""
    if not _backend_up():
        pytest.skip("后端未启动（localhost:8000），跳过冒烟测试")

    def case(client, headers, conv_id):
        kb = _scopable_kb(client, headers)
        if kb is None:
            pytest.skip("开发库里没有已入库文档的文档型知识库，跳过作用域断言")

        allowed = _kb_filenames(client, headers, kb["id"])
        events = _chat_sse(client, headers, conv_id, GENERIC_QUESTION, kb_ids=[kb["id"]])

        _assert_model_usable(events)
        assert not any(t == "error" for t, _ in events), \
            f"SSE 出现 error: {[d for t, d in events if t == 'error']}"
        assert any(t == "done" for t, _ in events), "缺少 done 事件"
        assert _tokens_of(events), "无 token 输出"

        sources = _sources_of(events)
        if not sources:
            pytest.skip(f"本次检索未命中「{kb['name']}」的任何片段，作用域无从验证")

        # 作用域的全部意义就在这里：不许漏出所选知识库之外的来源
        outside = [s.get("filename") for s in sources if s.get("filename") not in allowed]
        assert not outside, \
            f"来源越出所选知识库「{kb['name']}」(id={kb['id']}): {outside}；库内文件 {sorted(allowed)}"

    _run_case(case)


def test_no_results_fallback():
    """无结果兜底：检索为空返回兜底文案，且不调 LLM"""
    if not _backend_up():
        pytest.skip("后端未启动（localhost:8000），跳过冒烟测试")

    def case(client, headers, conv_id):
        events = _chat_sse(client, headers, conv_id, UNKNOWN_QUESTION)

        assert not any(t == "error" for t, _ in events), "不应出现 error 事件"
        # token 全文 == 兜底文案
        assert _tokens_of(events) == NO_RESULT_MESSAGE, \
            f"兜底文案不符: {_tokens_of(events)[:80]!r}"
        # 兜底路径根本没调模型，所以没有真实用量 —— 发的是 null，不是估算值，也不是文案长度
        done = [json.loads(d) for t, d in events if t == "done"]
        assert done, "缺少 done 事件"
        assert done[0].get("token_count") is None, \
            f"不调模型的兜底路径不该有 token 数，实得 {done[0].get('token_count')!r}"
        # 不应出现 sources（无检索结果）
        assert not any(t == "sources" for t, _ in events)

    _run_case(case)
