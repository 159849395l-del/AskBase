"""测试工具执行器：来源归一化 + 全局编号

seam：temp_db 夹具（临时文件 SQLite）里放一条真实 Skill 行，把 handler 换成
假实现或直接复用真实的 web_search，驱动**真实的 run_tool_calls**，
只在它返回的结构与「给模型看的文本」上断言。

要守的规矩：给模型看的文本里的来源编号，必须与最终来源面板的编号是同一套。
"""

import asyncio

import pytest

from app.models.skill import Skill
from app.schemas.agent import AgentToolRef
from app.skills import handlers as handlers_module
from app.skills.executor import (
    execute_tool_call,
    normalize_tool_result,
    run_tool_calls,
)


WEB_SOURCES = [
    {
        "kind": "web",
        "title": "国务院通知",
        "url": "https://a.example/1",
        "filename": "国务院通知",
        "chunk_text": "通知正文",
    },
    {
        "kind": "web",
        "title": "日历网",
        "url": "https://b.example/2",
        "filename": "日历网",
        "chunk_text": "日历正文",
    },
]

EXA_PAYLOAD = {
    "answer": "春节放假 9 天。[1]",
    "citations": [{"title": "国务院通知", "url": "https://a.example/1", "text": "通知正文"}],
}


def _seed_skill(factory, name="web_search", handler="web_search"):
    """建一条真实 Skill 行（handler 名要对上注册表里的 key）"""

    async def _go():
        async with factory() as db:
            s = Skill(name=name, title=name, description="", handler=handler, is_active=True)
            db.add(s)
            await db.commit()
            await db.refresh(s)
            return s.id

    return asyncio.run(_go())


def _call(factory, skill_id, tool_calls, source_offset=0, name="web_search"):
    async def _go():
        async with factory() as db:
            ref = AgentToolRef(tool_type="skill", tool_ref_id=skill_id)
            return await run_tool_calls(db, tool_calls, {name: ref}, source_offset=source_offset)

    return asyncio.run(_go())


def _one(args=None, call_id="call_1", name="web_search"):
    return [{"id": call_id, "name": name, "args": args or {"query": "x"}}]


def _fake_handler(text, sources):
    async def _h(args):
        return text, sources

    return _h


class TestNormalizeToolResult:
    """处理函数两种返回形态都要能吃下"""

    def test_纯文本_来源为空(self):
        """场景：老形态（只返回字符串）→ 行为不变，来源为空"""
        assert normalize_tool_result("现在是 10:00") == ("现在是 10:00", [])

    def test_文本加来源_原样返回(self):
        """场景：新形态 (text, sources) → 文本与来源都保留"""
        assert normalize_tool_result(("答案 [1]", WEB_SOURCES)) == ("答案 [1]", WEB_SOURCES)

    def test_来源为None_视为空列表(self):
        """场景：工具声明了来源位但没填 → 当作没有来源，不炸"""
        assert normalize_tool_result(("纯文本", None)) == ("纯文本", [])

    def test_来源里的非字典项被丢弃(self):
        """场景：来源列表混入脏数据 → 只保留可用项"""
        text, sources = normalize_tool_result(("文本", ["https://a.example", WEB_SOURCES[0]]))

        assert text == "文本"
        assert sources == [WEB_SOURCES[0]]

    def test_非字符串非元组_转成文本(self):
        """场景：handler 返回意外类型 → 退化成文本，不抛异常"""
        assert normalize_tool_result(123) == ("123", [])


class TestGlobalNumbering:
    """正文编号与来源列表必须是一套编号"""

    def test_工具文本里的编号改写成全局编号(self, temp_db, monkeypatch):
        """场景：工具自己的 [1][2] + 已有 2 条知识库来源 → 改写为 [来源3][来源4]"""
        skill_id = _seed_skill(temp_db)
        monkeypatch.setitem(
            handlers_module.HANDLERS, "web_search", _fake_handler("[1] 甲\n[2] 乙", WEB_SOURCES)
        )

        results = _call(temp_db, skill_id, _one(), source_offset=2)

        assert "[来源3] 甲" in results[0]["content"]
        assert "[来源4] 乙" in results[0]["content"]

    def test_文末附上可引用的来源清单(self, temp_db, monkeypatch):
        """场景：模型要知道 [来源3] 指向哪个网址 → 结果末尾附清单"""
        skill_id = _seed_skill(temp_db)
        monkeypatch.setitem(
            handlers_module.HANDLERS, "web_search", _fake_handler("[1] 甲", WEB_SOURCES[:1])
        )

        results = _call(temp_db, skill_id, _one(), source_offset=2)

        assert "[来源3: 国务院通知]" in results[0]["content"]
        assert "https://a.example/1" in results[0]["content"]

    def test_超出来源数量的方括号数字不动(self, temp_db, monkeypatch):
        """场景：正文里有年份、序号等方括号数字 → 不许误伤"""
        skill_id = _seed_skill(temp_db)
        monkeypatch.setitem(
            handlers_module.HANDLERS,
            "web_search",
            _fake_handler("截至 [2024] 年，见 [9]；来源 [1]", WEB_SOURCES),
        )

        content = _call(temp_db, skill_id, _one(), source_offset=2)[0]["content"]

        assert "[2024]" in content
        assert "[9]" in content
        assert "[来源3]" in content  # 只有落在来源数量内的才改写

    def test_没有来源时文本原样返回(self, temp_db, monkeypatch):
        """场景：工具没有结构化来源（如取当前时间）→ 不追加清单、不改写"""
        skill_id = _seed_skill(temp_db, name="get_current_time", handler="get_current_time")
        monkeypatch.setitem(
            handlers_module.HANDLERS, "get_current_time", _fake_handler("现在是 [1] 点", [])
        )

        results = _call(
            temp_db, skill_id, _one(name="get_current_time"), source_offset=2,
            name="get_current_time",
        )

        assert results[0]["content"] == "现在是 [1] 点"
        assert results[0]["sources"] == []

    def test_同一轮多个工具调用_编号顺延(self, temp_db, monkeypatch):
        """场景：一轮里调用两个工具 → 第二个的编号接着第一个往下排"""
        skill_id = _seed_skill(temp_db)

        async def _h(args):
            if args.get("query") == "first":
                return "[1] 甲", WEB_SOURCES
            return "[1] 乙", WEB_SOURCES[:1]

        monkeypatch.setitem(handlers_module.HANDLERS, "web_search", _h)
        calls = _one({"query": "first"}, "call_1") + _one({"query": "second"}, "call_2")

        results = _call(temp_db, skill_id, calls, source_offset=2)

        assert "[来源3] 甲" in results[0]["content"]
        assert "[来源5] 乙" in results[1]["content"]
        assert len(results[1]["sources"]) == 1

    def test_没有前置来源时从来源1开始(self, temp_db, monkeypatch):
        """场景：知识库没有来源（纯工具问答）→ 网页来源就是来源1"""
        skill_id = _seed_skill(temp_db)
        monkeypatch.setitem(
            handlers_module.HANDLERS, "web_search", _fake_handler("[1] 甲", WEB_SOURCES[:1])
        )

        results = _call(temp_db, skill_id, _one(), source_offset=0)

        assert "[来源1] 甲" in results[0]["content"]


class TestRealWebSearchThroughExecutor:
    """真实 web_search 走一遍执行器：Exa 的引用要变成可点击来源"""

    def test_exa引用成为全局编号来源(self, temp_db, fake_http):
        """场景：Exa 回了 1 条引用，前面已有 1 条知识库来源 → 它就是来源2"""
        skill_id = _seed_skill(temp_db)
        fake_http({"api.exa.ai/answer": fake_http.Response(payload=EXA_PAYLOAD)})

        results = _call(temp_db, skill_id, _one({"query": "春节放假"}), source_offset=1)

        assert results[0]["sources"][0]["url"] == "https://a.example/1"
        assert "[来源2: 国务院通知]" in results[0]["content"]


class TestExecuteToolCallContract:
    """execute_tool_call 也要按新契约返回 (文本, 来源)"""

    def test_纯文本工具_返回空来源(self, temp_db, monkeypatch):
        """场景：calculator 这类工具只有文本 → 来源为空列表"""
        skill_id = _seed_skill(temp_db, name="calculator", handler="calculator")

        async def _go():
            async with temp_db() as db:
                ref = AgentToolRef(tool_type="skill", tool_ref_id=skill_id)
                return await execute_tool_call(db, ref, {"expression": "1+1"})

        text, sources = asyncio.run(_go())

        assert "2" in text
        assert sources == []

    def test_工具不存在_返回可读错误(self, temp_db):
        """场景：引用的 Skill 已被删除 → 不抛异常，返回可读提示"""

        async def _go():
            async with temp_db() as db:
                ref = AgentToolRef(tool_type="skill", tool_ref_id=999999)
                return await execute_tool_call(db, ref, {})

        text, sources = asyncio.run(_go())

        assert "不存在" in text
        assert sources == []
