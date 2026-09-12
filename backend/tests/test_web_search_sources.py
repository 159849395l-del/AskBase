"""测试联网搜索工具把「网页来源」结构化地带出来

seam（沿用仓库既有约定）：用 fake_http 夹具替换 handlers 模块级的 httpx，
用预置响应驱动**真实的解析逻辑**，不联网、不依赖外部服务。

契约：处理函数返回 (给模型看的文本, 结构化来源列表)；
文本里的 [N] 指代 sources[N-1]，由执行器统一改写成全局编号。
"""

import asyncio

from app.skills.handlers import web_search


EXA_PAYLOAD = {
    "answer": "2026 年春节放假 9 天。[1]",
    "citations": [
        {
            "title": "国务院办公厅关于2026年部分节假日安排的通知",
            "url": "https://www.gov.cn/zhengce/content_7047091.htm",
            "publishedDate": "2025-11-04T00:00:00.000Z",
            "author": "国务院办公厅",
        },
        {
            "title": "2026年放假安排日历",
            "url": "https://rili.example.com/2026",
            "publishedDate": None,
        },
    ],
}

BAIDU_HTML = (
    '<div><h3 class="t"><a href="http://www.baidu.com/link?url=aaa">百度结果一</a></h3>'
    '<h3 class="t"><a href="http://www.baidu.com/link?url=bbb">百度结果二</a></h3></div>'
)

# 反爬页：百度会返回「安全验证」，触发回退
BAIDU_BLOCKED_HTML = "<html><title>百度安全验证</title></html>"

BING_HTML = (
    '<ol><li class="b_algo"><h2><a href="https://example.com/a">示例标题一</a></h2>'
    "<p>示例摘要一</p></li></ol>"
)


def _search(query="今天有什么新闻", **kwargs):
    return asyncio.run(web_search({"query": query, **kwargs}))


def _plain_page(fake_http):
    """网页正文抓取：非 html 内容直接放弃，避免测试依赖正文清洗器"""
    return fake_http.Response(text="", content_type="application/octet-stream")


class TestExaPath:
    """Exa Answer 路径：引用列表不能再被丢掉"""

    def test_引用被结构化带出(self, fake_http):
        """场景：Exa 返回 answer + citations → 两者都要回来"""
        fake_http({"api.exa.ai/answer": fake_http.Response(payload=EXA_PAYLOAD)})

        text, sources = _search("2026年春节放假安排")

        assert "2026 年春节放假 9 天" in text
        assert len(sources) == 2
        assert sources[0]["kind"] == "web"
        assert sources[0]["title"] == "国务院办公厅关于2026年部分节假日安排的通知"
        assert sources[0]["url"] == "https://www.gov.cn/zhengce/content_7047091.htm"
        assert sources[0]["published"].startswith("2025-11-04")

    def test_没有引用时_来源为空(self, fake_http):
        """场景：Exa 只回了 answer、没有 citations → 文本照常，来源为空"""
        fake_http({"api.exa.ai/answer": fake_http.Response(payload={"answer": "只有答案"})})

        text, sources = _search("随便问问")

        assert "只有答案" in text
        assert sources == []

    def test_未配置key_不走Exa(self, fake_http, monkeypatch):
        """场景：没有 EXA_API_KEY → 直接走搜索回退，不去请求 Exa"""
        monkeypatch.setattr("app.config.settings.EXA_API_KEY", "")
        fake_http(
            {
                "www.baidu.com/s": fake_http.Response(text=BAIDU_HTML, content_type="text/html"),
                "link?url=": _plain_page(fake_http),
            }
        )

        _, sources = _search("随便问问")

        assert [s["title"] for s in sources] == ["百度结果一", "百度结果二"]


class TestFallbackPath:
    """百度 / Bing 回退路径：结果本身就要成为来源"""

    def test_百度结果成为网页来源(self, fake_http, monkeypatch):
        """场景：百度返回若干条结果 → 每条都是一个可点击来源"""
        monkeypatch.setattr("app.config.settings.EXA_API_KEY", "")
        fake_http(
            {
                "www.baidu.com/s": fake_http.Response(text=BAIDU_HTML, content_type="text/html"),
                "link?url=": _plain_page(fake_http),
            }
        )

        text, sources = _search("今天有什么新闻")

        assert len(sources) == 2
        assert sources[0]["url"] == "http://www.baidu.com/link?url=aaa"
        assert sources[1]["title"] == "百度结果二"
        assert all(s["kind"] == "web" for s in sources)
        assert "百度结果一" in text

    def test_百度被反爬_回退Bing且来源来自Bing(self, fake_http, monkeypatch):
        """场景：百度命中安全验证 → 换 Bing，来源必须是 Bing 的结果"""
        monkeypatch.setattr("app.config.settings.EXA_API_KEY", "")
        fake_http(
            {
                "www.baidu.com/s": fake_http.Response(text=BAIDU_BLOCKED_HTML, content_type="text/html"),
                "cn.bing.com/search": fake_http.Response(text=BING_HTML, content_type="text/html"),
                "example.com/a": _plain_page(fake_http),
            }
        )

        _, sources = _search("今天有什么新闻")

        assert [s["title"] for s in sources] == ["示例标题一"]
        assert sources[0]["url"] == "https://example.com/a"


class TestDegenerateInputs:
    """没有来源的路径不能凭空造出来源"""

    def test_缺少关键词(self):
        """场景：query 为空 → 返回可读错误，来源为空"""
        text, sources = _search("   ")

        assert "缺少搜索关键词" in text
        assert sources == []

    def test_搜索无结果(self, fake_http, monkeypatch):
        """场景：所有搜索源都没结果 → 提示换关键词，来源为空"""
        monkeypatch.setattr("app.config.settings.EXA_API_KEY", "")
        fake_http(
            {
                "www.baidu.com/s": fake_http.Response(text=BAIDU_BLOCKED_HTML, content_type="text/html"),
                "cn.bing.com/search": fake_http.Response(text="<html></html>", content_type="text/html"),
            }
        )

        text, sources = _search("一个查不到的词")

        assert "未找到" in text
        assert sources == []
