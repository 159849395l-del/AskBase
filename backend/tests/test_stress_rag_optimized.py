"""RAG 优化冒烟测试 — 真实链路

覆盖新增能力：
1. 品类过滤：带 product_category 的 SSE 问答，断言来源全部属于所选品类
2. 无结果兜底：检索为空时返回兜底文案，不调用 LLM

真实调用 DeepSeek LLM + 百炼 embedding。前置条件：后端已启动
（uvicorn，默认 localhost:8000），未启动时自动跳过。

运行：
  pytest tests/test_stress_rag_optimized.py -v
"""

import asyncio
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

# 知识库真实问题（data/products/clothing.md 羽绒服主题）
CLOTHING_QUESTION = "羽绒服的清洗频率是多少？多久洗一次比较合适？"
# 明显不在知识库中的问题（触发无结果兜底）
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
    """同步包装器：登录 → 建会话 → 发消息 → 返回 SSE 事件"""
    with httpx.Client(base_url=BASE_URL, timeout=TIMEOUT) as client:
        token = _login_token(client)
        headers = {"Authorization": f"Bearer {token}"}
        r = client.post("/api/conversations", json={"title": "rag-opt-smoke"}, headers=headers)
        r.raise_for_status()
        conv_id = r.json()["id"]
        return case(client, headers, conv_id)


def _chat_sse(client: httpx.Client, headers: dict, conv_id: int,
              content: str, category: str = None) -> list:
    """发送消息并完整消费 SSE 流，返回事件列表"""
    body = {"content": content}
    if category:
        body["product_category"] = category
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


def test_category_filtered_qa():
    """品类过滤：带 product_category 问答，来源全部属于所选品类"""
    if not _backend_up():
        pytest.skip("后端未启动（localhost:8000），跳过冒烟测试")

    def case(client, headers, conv_id):
        # 取知识库真实品类（公开端点，管理员/普通用户均可用）
        r = client.get("/api/categories", headers=headers)
        r.raise_for_status()
        categories = r.json().get("categories", [])
        if not categories:
            pytest.skip("知识库暂无品类数据，跳过品类过滤断言")

        category = categories[0]
        events = _chat_sse(client, headers, conv_id, CLOTHING_QUESTION, category)

        # 无 error 事件
        assert not any(e[0] == "error" for e in events), \
            f"SSE 出现 error: {[d for t, d in events if t == 'error']}"
        # 有 done 事件且 token 流非空
        assert any(e[0] == "done" for e in events), "缺少 done 事件"
        tokens = [json.loads(d).get("token", "") for t, d in events if t == "token"]
        assert any(tokens), "无 token 输出"

        # 若返回了来源，必须全部属于所选品类
        for t, d in events:
            if t == "sources":
                sources = json.loads(d)["sources"]
                for s in sources:
                    assert s.get("product_category") == category, \
                        f"来源品类 {s.get('product_category')} != {category}"

    _run_case(case)


def test_no_results_fallback():
    """无结果兜底：检索为空返回兜底文案，不调 LLM"""
    if not _backend_up():
        pytest.skip("后端未启动（localhost:8000），跳过冒烟测试")

    def case(client, headers, conv_id):
        events = _chat_sse(client, headers, conv_id, UNKNOWN_QUESTION)

        assert not any(e[0] == "error" for e in events), "不应出现 error 事件"
        # token 全文 == 兜底文案
        tokens = [json.loads(d).get("token", "") for t, d in events if t == "token"]
        assert "".join(tokens) == NO_RESULT_MESSAGE, \
            f"兜底文案不符: {''.join(tokens)[:80]!r}"
        # done 事件存在且 token_count == 兜底文案长度（SSE 层不携带 full_response）
        done = [json.loads(d) for t, d in events if t == "done"]
        assert done and done[0].get("token_count") == len(NO_RESULT_MESSAGE)
        # 不应出现 sources（无检索结果）
        assert not any(t == "sources" for t, _ in events)

    _run_case(case)
