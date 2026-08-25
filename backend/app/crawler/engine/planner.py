"""PlannerAgent — LLM 解析任务描述，产出 schema 与执行计划"""
import json
import time
from datetime import datetime
from app.crawler.models import CrawlTask, AgentLog, TaskStatus, get_crawler_session_factory
from app.crawler.sse_publisher import publish_agent_log
from app.config import settings
import openai

PLANNER_SYSTEM_PROMPT = """\u4f60\u662f\u722c\u866b\u4efb\u52a1\u89c4\u5212\u5668\u3002\u6839\u636e\u7528\u6237\u7684\u4efb\u52a1\u63cf\u8ff0\u8f93\u51fa JSON \u5bf9\u8c61\uff0c\u683c\u5f0f\uff1a
{
  "title": "\u4efb\u52a1\u6807\u9898",
  "schema": {
    "fields": [{"name":"\u5b57\u6bb5\u540d","type":"string|number|date|array","description":"\u5b57\u6bb5\u8bf4\u660e","required":true|false}],
    "dedup_keys": ["\u7528\u4e8e\u53bb\u91cd\u7684\u5b57\u6bb5\u540d"]
  },
  "seed_hint": ["\u5efa\u8bae\u7684\u79cd\u5b50 URL"],
  "same_domain_only": true,
  "max_depth_hint": 2,
  "crawl_mode_hint": "STATIC|JS"
}
\u89c4\u5219\uff1a
1. \u5b57\u6bb5 name \u5fc5\u987b\u4f7f\u7528\u82f1\u6587 snake_case\uff0cdescription \u7528\u4e2d\u6587\u8bf4\u660e\u542b\u4e49
2. \u5b57\u6bb5\u6570 2-15 \u4e2a\uff1b\u53ea\u63d0\u53d6\u7528\u6237\u660e\u786e\u63d0\u5230\u7684\u5b57\u6bb5
3. \u3010\u7edf\u4e00\u547d\u540d\u3011\u6587\u7ae0/\u65b0\u95fb\u7c7b\u4efb\u52a1\uff0c\u5b57\u6bb5\u540d\u5fc5\u987b\u56fa\u5b9a\u7528\uff1a
   - \u6807\u9898 \u2192 title
   - \u6b63\u6587\u5185\u5bb9 \u2192 content
   - \u53d1\u5e03\u65f6\u95f4/\u65e5\u671f \u2192 publish_date\uff08type: date\uff0c\u8f93\u51fa ISO \u65e5\u671f\u5982 2026-07-28\uff09
   - \u94fe\u63a5 \u2192 url
   \u7981\u6b62\u4f7f\u7528 publish_time\u3001published_at\u3001\u65e5\u671f\u3001\u53d1\u5e03\u65e5\u671f \u7b49\u5176\u4ed6\u5b57\u6bb5\u540d
4. \u6587\u7ae0\u7c7b\u4efb\u52a1 dedup_keys \u7528 ["url"]\uff08\u6ca1\u6709 url \u5b57\u6bb5\u65f6\u7528 ["title"]\uff09
5. \u53ea\u8f93\u51fa JSON\uff0c\u4e0d\u8981\u8f93\u51fa\u5176\u4ed6\u6587\u5b57"""


def default_schema() -> dict:
    return {"fields": [{"name":"title","type":"string","description":"\u6807\u9898","required":True},{"name":"content","type":"string","description":"\u6b63\u6587\u5185\u5bb9","required":False},{"name":"publish_date","type":"date","description":"\u53d1\u5e03\u65f6\u95f4","required":False},{"name":"url","type":"string","description":"\u6765\u6e90\u94fe\u63a5","required":False}],"dedup_keys":["title"]}


async def execute_planning(task_id: int):
    factory = get_crawler_session_factory()
    async with factory() as db:
        task = await db.get(CrawlTask, task_id)
        if not task or task.status != TaskStatus.PLANNING.value:
            return None
        start_ms = int(time.time() * 1000)
        log = AgentLog(task_id=task_id, agent="PLANNER", stage="understand", status="RUNNING", started_at=datetime.now())
        db.add(log)
        schema = None
        plan = None
        tokens = 0
        try:
            client = openai.AsyncOpenAI(api_key=settings.LLM_API_KEY, base_url=settings.LLM_API_BASE)
            resp = await client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=[{"role":"system","content":PLANNER_SYSTEM_PROMPT},{"role":"user","content":f"\u4efb\u52a1\u63cf\u8ff0\uff1a{task.description}"}],
                temperature=0.1, response_format={"type":"json_object"},
            )
            content = resp.choices[0].message.content
            tokens = resp.usage.total_tokens if resp.usage else 0
            parsed = json.loads(content)
            parsed_schema = parsed.get("schema")
            if not isinstance(parsed_schema, dict) or not parsed_schema.get("fields"):
                # LLM 未给出有效字段（任务描述太简略等）时回退默认 schema，避免空 schema 抽不出任何数据
                schema = default_schema()
                plan = {**parsed, "schema": schema}
            else:
                schema = parsed_schema
                plan = parsed
        except Exception as e:
            print(f"[Planner] LLM \u8c03\u7528\u5931\u8d25\uff0c\u964d\u7ea7\u9ed8\u8ba4 schema: {e}")
            schema = default_schema()
            plan = {"title": task.title, "same_domain_only": task.same_domain_only, "max_depth_hint": task.max_depth, "crawl_mode_hint": "STATIC"}
        task.schema_json = schema
        task.plan_json = plan
        await db.flush()
        await db.commit()
        log2 = AgentLog(task_id=task_id, agent="PLANNER", stage="understand", status="SUCCESS", cost_tokens=tokens, duration_ms=int(time.time()*1000-start_ms), started_at=datetime.now(), finished_at=datetime.now())
        db.add(log2)
        await db.commit()
        await publish_agent_log(task_id, "PLANNER", "SUCCESS", "understand", tokens)
        print(f"[Planner] Task {task_id} planned: schema fields={len(schema.get('fields', []))}")
        return None
