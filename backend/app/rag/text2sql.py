"""Text-to-SQL 执行模块 — B 类（数据库型）知识库的"查数据"链路

流程：加载表/字段描述（db_tables + db_table_fields，含人工描述）→ 组装 DDL 文本
→ 调 LLM 生成 SELECT → 只读安全校验 → PyMySQL 执行 → 结果格式化为文本。

安全约束（硬性）：
- 只允许 SELECT / SHOW / DESCRIBE / EXPLAIN 开头
- 禁止多语句（; 分号）、禁止写操作关键词（INSERT/UPDATE/DELETE/DROP/ALTER/...）
- 结果集最多 MAX_ROWS 行，单字段最多 MAX_FIELD_CHARS 字符，防止大结果撑爆上下文
"""

from typing import Any, Dict, List, Optional, Tuple
import re
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.knowledge_base import KnowledgeBase
from app.models.data_source import DataSource
from app.models.db_table import DBTable, DBTableField
from app.utils.crypto import decrypt_password
from app.rag.chain import get_llm

MAX_ROWS = 100
MAX_FIELD_CHARS = 500
MAX_SQL_LEN = 1000

# 只读白名单：允许出现在语句最前的动词
_READONLY_PREFIX = re.compile(r"^\s*(SELECT|SHOW|DESCRIBE|DESC|EXPLAIN)\b", re.IGNORECASE)
# 写操作/危险关键词（任意位置出现即拒绝）
_DANGEROUS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|RENAME|GRANT|REVOKE|"
    r"REPLACE|MERGE|INTO\s+OUTFILE|LOAD\s+DATA|SELECT\s+INTO\s+OUTFILE|"
    r"SLEEP|BENCHMARK|GET_LOCK|RELEASE_LOCK)\b",
    re.IGNORECASE,
)
# 多条语句（; 后跟内容）拒绝
_MULTI_STMT = re.compile(r";\s*\S")


def build_schema_ddl(tables: List[Tuple[DBTable, List[DBTableField]]]) -> str:
    """由表/字段记录生成 DDL 描述文本（供 LLM 理解表结构）

    只包含 is_required=True 且未软删除的表/字段；字段描述优先人工填写的
    field_comment（源库注释已默认预填）。
    """
    lines = []
    for table, fields in tables:
        lines.append(f"CREATE TABLE `{table.table_name}` (")
        lines.append(f"  -- 表说明: {table.table_comment or '(无)'}")
        for f in fields:
            comment = f.field_comment.strip()
            if comment:
                lines.append(f"  `{f.field_name}` {f.field_type} -- {comment}")
            else:
                lines.append(f"  `{f.field_name}` {f.field_type}")
        lines.append(");")
    return "\n".join(lines)


async def load_schema(db: AsyncSession, kb: KnowledgeBase) -> str:
    """从 db_tables / db_table_fields 加载启用表/字段并生成 DDL 文本"""
    tables = (
        await db.execute(
            select(DBTable)
            .where(DBTable.kb_id == kb.id, DBTable.status == "normal", DBTable.is_required == True)
            .order_by(DBTable.id.asc())
        )
    ).scalars().all()
    items = []
    for t in tables:
        fields = (
            await db.execute(
                select(DBTableField)
                .where(
                    DBTableField.db_table_id == t.id,
                    DBTableField.deleted_flag == False,
                    DBTableField.is_required == True,
                )
                .order_by(DBTableField.id.asc())
            )
        ).scalars().all()
        if fields:
            items.append((t, list(fields)))
    return build_schema_ddl(items)


def extract_sql(raw: str) -> str:
    """从 LLM 输出中提取 SQL（去 markdown 代码块、前后注释/说明）"""
    text = raw.strip()
    m = re.search(r"```(?:sql)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if m:
        text = m.group(1).strip()
    # 去掉尾部解释性文字（如 "这条SQL..."），只保留首个完整语句
    text = text.split("\n\n")[0].strip()
    return text[:MAX_SQL_LEN]


def validate_sql(sql: str) -> Tuple[bool, str]:
    """只读安全校验；返回 (是否通过, 错误信息)"""
    if not sql:
        return False, "SQL 为空"
    if len(sql) > MAX_SQL_LEN:
        return False, f"SQL 过长（>{MAX_SQL_LEN} 字符）"
    if not _READONLY_PREFIX.match(sql):
        return False, "只允许 SELECT / SHOW / DESCRIBE / EXPLAIN 查询，已拒绝该语句"
    if _DANGEROUS.search(sql):
        return False, "检测到写操作或危险关键词，已拒绝执行"
    if _MULTI_STMT.search(sql):
        return False, "不支持多语句执行，已拒绝"
    return True, ""


def _format_value(v: Any) -> str:
    if v is None:
        return "NULL"
    s = str(v)
    if len(s) > MAX_FIELD_CHARS:
        return s[:MAX_FIELD_CHARS] + f"...[截断，共{len(s)}字符]"
    return s


def _execute_sql_sync(
    host: str, port: int, database: str, username: str, password: str, sql: str
) -> dict:
    """同步执行 SQL 并格式化结果（调用方负责 to_thread 包装）"""
    import pymysql

    conn = pymysql.connect(
        host=host,
        port=int(port),
        user=username,
        password=password or "",
        database=database,
        connect_timeout=8,
        read_timeout=20,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            if cur.description is None:
                return {"sql": sql, "columns": [], "rows": [], "note": "语句执行成功（无结果集）"}
            columns = [d[0] for d in cur.description]
            rows = []
            for i, row in enumerate(cur.fetchall()):
                if i >= MAX_ROWS:
                    rows.append({"_note": f"...结果超过 {MAX_ROWS} 行，已截断"})
                    break
                rows.append({k: _format_value(v) for k, v in row.items()})
            return {"sql": sql, "columns": columns, "rows": rows}
    finally:
        conn.close()


def format_sql_result(result: dict, max_rows: int = 10) -> str:
    """把查询结果转成给 LLM 的文本（默认最多渲染 10 行，防上下文爆掉）"""
    rows = result.get("rows", [])
    if not rows:
        return result.get("note", "查询无结果")
    lines = []
    for row in rows[:max_rows]:
        if "_note" in row:
            lines.append(row["_note"])
            continue
        parts = [f"{k}={v}" for k, v in row.items()]
        lines.append(" | ".join(parts))
    if len(rows) > max_rows:
        lines.append(f"...(共 {len(rows)} 行，仅展示前 {max_rows} 行)")
    return "\n".join(lines)


async def run_sql_query(
    db: AsyncSession,
    kb: KnowledgeBase,
    question: str,
    system_prompt: str,
) -> Dict[str, Any]:
    """对 B 类知识库执行一次"生成 SQL → 校验 → 执行"链路

    返回：
      {
        "sql": 生成并执行的 SQL（可能为空串=未生成/被拒）,
        "result_text": 查询结果文本（或错误信息）,
        "success": bool,
        "error": 可选错误
      }
    """
    ds = (
        await db.execute(select(DataSource).where(DataSource.id == kb.data_source_id))
    ).scalar_one_or_none()
    if ds is None:
        return {"sql": "", "result_text": "（数据源不存在）", "success": False, "error": "数据源不存在"}

    schema_ddl = await load_schema(db, kb)

    # 组装 SQL 生成 prompt：管理员 system_prompt（含表名/位运算等说明）+ 结构 + 约束
    sql_prompt = f"""你是数据库查询助手。根据下面给出的【数据库表结构】和【使用说明】，把用户问题转化为一条只读 SQL 查询。

【使用说明】
{system_prompt[:4000] if system_prompt else "（无特殊说明）"}

【数据库表结构】
{schema_ddl[:8000]}

【硬性约束】
1. 只能返回 SQL 本身，不要任何解释或 markdown 代码块标记
2. 只能使用 SELECT / SHOW / DESCRIBE / EXPLAIN，严禁任何写操作
3. 严禁使用 select *，只查询问题需要的字段
4. 除非用户明确要求，不要擅自给时间字段添加过滤条件（如 publish_date）
5. 结果只取需要的行数（如 LIMIT 20）
6. 若表结构中无法找到与问题相关的表/字段，返回：NO_RELEVANT_TABLE

【用户问题】
{question}

【SQL】"""

    try:
        llm = get_llm()
        resp = await llm.ainvoke([{"role": "user", "content": sql_prompt}])
        raw_sql = str(resp.content or "").strip()
    except Exception as e:
        return {"sql": "", "result_text": f"（SQL 生成失败：{e}）", "success": False, "error": str(e)}

    if not raw_sql or "NO_RELEVANT_TABLE" in raw_sql.upper():
        return {"sql": "", "result_text": "（无法从现有表结构中匹配到相关内容）", "success": False, "error": "no_relevant_table"}

    sql = extract_sql(raw_sql)
    ok, err = validate_sql(sql)
    if not ok:
        return {"sql": sql, "result_text": f"（SQL 被安全策略拦截：{err}）", "success": False, "error": err}

    try:
        result = await asyncio.to_thread(
            _execute_sql_sync, ds.host, ds.port, kb.database_name, ds.username,
            decrypt_password(ds.password_encrypted or ""), sql,
        )
        return {
            "sql": sql,
            "result_text": format_sql_result(result),
            "success": True,
            "error": None,
        }
    except Exception as e:
        return {"sql": sql, "result_text": f"（SQL 执行失败：{e}）", "success": False, "error": str(e)}
