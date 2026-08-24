"""VerifierAgent — 去重 + 必填字段校验"""
import json
import time
from datetime import datetime
from sqlalchemy import select
from app.crawler.models import CrawlTask, CrawlResult, AgentLog, TaskStatus, get_crawler_session_factory
from app.crawler.utils import safe_json
from app.crawler.sse_publisher import publish_agent_log


async def execute_verifying(task_id: int):
    start_ms = int(time.time() * 1000)
    factory = get_crawler_session_factory()
    async with factory() as db:
        log = AgentLog(task_id=task_id, agent="VERIFIER", stage="dedup", status="RUNNING", started_at=datetime.now())
        db.add(log)
        task = await db.get(CrawlTask, task_id)
        if not task: return None
        required = _required_fields(task)
        results = (await db.execute(select(CrawlResult).where(CrawlResult.task_id == task_id, CrawlResult.status == "VALID").order_by(CrawlResult.id.asc()))).scalars().all()
        seen = {}; valid=0; duplicate=0; invalid=0
        for r in results:
            data = r.data_json if isinstance(r.data_json, dict) else (json.loads(r.data_json) if r.data_json else {})
            if not isinstance(data, dict):
                r.status = "INVALID"; invalid+=1; continue
            if _missing_required(data, required):
                r.status = "INVALID"; invalid+=1; continue
            first = seen.get(r.record_hash)
            if first is not None:
                r.status = "DUPLICATE"; r.source_url = first.url; duplicate+=1
            else:
                seen[r.record_hash] = r; valid+=1
        await db.flush()
        await db.commit()
        task = await db.get(CrawlTask, task_id)
        if task:
            stats = safe_json(task.stats_json) or {}
            stats["valid"] = valid; stats["invalid"] = stats.get("invalid",0) + invalid
            task.stats_json = stats; await db.flush()
        log2 = AgentLog(task_id=task_id, agent="VERIFIER", stage="dedup", status="SUCCESS", duration_ms=int(time.time()*1000-start_ms), started_at=datetime.now(), finished_at=datetime.now())
        db.add(log2)
        await db.commit()
        await publish_agent_log(task_id, "VERIFIER", "SUCCESS", "dedup", 0)
        print(f"[Verifier] Task {task_id}: {valid} valid, {duplicate} duplicate, {invalid} invalid")
        return None


def _required_fields(task):
    try:
        schema = safe_json(task.schema_json) or {}
        if not isinstance(schema, dict):
            return []
        return [f["name"] for f in schema.get("fields",[]) if isinstance(f, dict) and f.get("required")]
    except: return []


def _missing_required(data, required):
    """所有必填字段都非空才不算缺；任一必填字段为空即 missing"""
    if not required:
        return False
    for field in required:
        v = data.get(field)
        if v is None or str(v).strip() == "":
            return True
    return False
