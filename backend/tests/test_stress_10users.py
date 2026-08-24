"""10 用户并发压力测试 — 真实链路

每个用户独立走完整链路：登录 → 创建会话 → SSE 流式问答（真实调用
DeepSeek LLM + 百炼 embedding）。

前置条件：后端已启动（uvicorn，默认 localhost:8000）。
后端未启动时测试自动跳过（探测端口），不影响普通单测运行。

运行：
  pytest tests/test_stress_10users.py -v
"""

import asyncio
import json
import socket
import statistics
import time

import httpx
import pytest

pytestmark = pytest.mark.stress

BASE_URL = "http://localhost:8000"
USERNAME = "admin"
PASSWORD = "123456"
CONCURRENCY = 10  # 并发用户数
TIMEOUT = httpx.Timeout(connect=10, read=120, write=30, pool=30)

# 每个用户问一个知识库相关的问题（data/products/clothing.md 羽绒服主题）
QUESTIONS = [
    "羽绒服的清洗频率是多少？多久洗一次比较合适？",
    "羽绒服洗完后应该怎么晾干？能暴晒吗？",
    "羽绒服沾了污渍应该怎么局部处理？",
    "羽绒服的羽绒为什么会结块？怎么恢复蓬松？",
    "羽绒服可以机洗吗？洗衣机的洗涤程序怎么选？",
    "羽绒服存放时需要注意什么？能压紧保存吗？",
    "羽绒服的保暖原理是什么？为什么洗多了会不暖？",
    "羽绒服内衬发霉了怎么办？",
    "羽绒服的拉链坏了能修吗？怎么保养拉链？",
    "羽绒服面料起球了怎么处理？",
]


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


async def _run_user(idx: int, stats: list) -> dict:
    result = {
        "user": idx,
        "question": QUESTIONS[idx % len(QUESTIONS)],
        "ok": False,
        "error": None,
        "login_ms": 0.0,
        "conv_ms": 0.0,
        "chat_ms": 0.0,
        "total_ms": 0.0,
        "tokens": 0,
        "sources": 0,
    }
    t0 = time.perf_counter()
    try:
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
            # 1. 登录（OAuth2 form 格式）
            t = time.perf_counter()
            r = await client.post(
                "/api/auth/login",
                data={"username": USERNAME, "password": PASSWORD},
            )
            result["login_ms"] = (time.perf_counter() - t) * 1000
            r.raise_for_status()
            token = r.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            # 2. 创建会话
            t = time.perf_counter()
            r = await client.post(
                "/api/conversations",
                json={"title": f"stress-user-{idx}"},
                headers=headers,
            )
            result["conv_ms"] = (time.perf_counter() - t) * 1000
            r.raise_for_status()
            conv_id = r.json()["id"]

            # 3. SSE 流式问答（完整消费流）
            t = time.perf_counter()
            raw = ""
            async with client.stream(
                "POST",
                f"/api/conversations/{conv_id}/messages",
                json={"content": result["question"]},
                headers=headers,
            ) as resp:
                if resp.status_code != 200:
                    raise RuntimeError(f"chat HTTP {resp.status_code}")
                async for chunk in resp.aiter_bytes():
                    raw += chunk.decode("utf-8", errors="replace")
            result["chat_ms"] = (time.perf_counter() - t) * 1000

            events = _parse_sse(raw)
            for etype, edata in events:
                if etype == "token":
                    result["tokens"] += 1
                elif etype == "sources":
                    result["sources"] = len(json.loads(edata)["sources"])
                elif etype == "error":
                    raise RuntimeError(f"SSE error: {edata}")

            if not any(e[0] == "done" for e in events):
                raise RuntimeError("missing 'done' event")
            if result["tokens"] == 0:
                raise RuntimeError("no tokens streamed")

            result["ok"] = True
    except Exception as e:  # noqa: BLE001 — 压测要捕获所有失败并汇总
        result["error"] = str(e)
    result["total_ms"] = (time.perf_counter() - t0) * 1000
    stats.append(result)
    return result


async def _run_all(stats: list):
    await asyncio.gather(*(_run_user(i, stats) for i in range(CONCURRENCY)))


def test_10_users_concurrent_stress():
    """10 用户并发全链路压测：全部成功且回答完整"""
    if not _backend_up():
        pytest.skip("后端未启动（localhost:8000），跳过压力测试")

    stats: list = []
    asyncio.run(_run_all(stats))

    # 汇总打印
    ok = [s for s in stats if s["ok"]]
    failed = [s for s in stats if not s["ok"]]
    chats = [s["chat_ms"] for s in stats]
    print("\n===== 10 用户并发压测结果 =====")
    print(f"成功: {len(ok)}/{len(stats)}  失败: {len(failed)}")
    for s in sorted(stats, key=lambda x: x["user"]):
        status = "OK " if s["ok"] else "FAIL"
        print(
            f"  user {s['user']:>2} [{status}] "
            f"login={s['login_ms']:7.0f}ms conv={s['conv_ms']:6.0f}ms "
            f"chat={s['chat_ms']:7.0f}ms total={s['total_ms']:7.0f}ms "
            f"tokens={s['tokens']:>3} sources={s['sources']} "
            f"{s['error'] or ''}"
        )
    if chats:
        print(f"\n问答耗时: avg={statistics.mean(chats):.0f}ms "
              f"min={min(chats):.0f}ms max={max(chats):.0f}ms "
              f"p50={statistics.median(chats):.0f}ms")
        total_tokens = sum(s["tokens"] for s in ok)
        print(f"总 token 事件: {total_tokens}  "
              f"总来源数: {sum(s['sources'] for s in ok)}")
        print(f"总墙钟时间: {max(s['total_ms'] for s in stats) / 1000:.1f}s")

    # 断言：全部成功、无异常、回答非空
    assert len(ok) == CONCURRENCY, f"失败用户: {[s['user'] for s in failed]}"
    assert all(s["tokens"] > 0 for s in ok), "存在无回答输出的用户"
    assert statistics.mean(chats) < 60_000, "平均问答耗时超过 60s"
