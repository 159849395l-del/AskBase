"""
LangChain RAG 链 — ChatOpenAI + 百炼 MaaS 端点
"""

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from sqlalchemy import select
from app.config import settings
from app.rag.retriever import retrieve_with_scores
from app.rag.query_rewriter import rewrite_query
from typing import AsyncIterator, Optional, Dict, Any, List


NO_RESULT_MESSAGE = "知识库中未找到相关资料，请尝试更换关键词或咨询管理员。"


def build_no_result_events() -> list:
    """构建检索为空时的 SSE 事件序列（不调用 LLM，纯函数）"""
    return [
        {"type": "no_results", "message": NO_RESULT_MESSAGE},
        {"type": "token", "content": NO_RESULT_MESSAGE},
        {"type": "done", "full_response": NO_RESULT_MESSAGE},
    ]


# 硬性规则（所有智能体都必须遵守，无论自定义提示词怎么写）
RAG_RULES = """【必须遵守的规则】
1. 只根据下面的【参考文档】内容回答问题，不要使用外部知识，不要编造
2. 如果参考文档中没有相关信息，请诚实地说"根据现有知识库资料，我无法找到相关信息"
3. 回答时请引用文档中的具体内容，并在末尾标明引用来源编号
4. 如果涉及价格、库存等时效性信息，请提醒用户以实际页面为准
5. 使用中文回答，保持专业、友好的语气
6. 对于对比类问题，请用表格形式呈现差异"""

# 默认智能体提示词（未配置自定义提示词时使用）
SYSTEM_PROMPT = """你是一个知识库问答助手。你的职责是基于知识库中提供的参考文档，准确回答用户的问题。

""" + RAG_RULES + """

【参考文档】
{context}"""


def _source_label(meta: dict) -> str:
    """来源标签：上传文件用 filename，爬取内容回退到 source(URL)/title"""
    return meta.get("filename") or meta.get("source") or meta.get("title") or "未知文件"


def format_docs_with_sources(docs_with_scores: list) -> tuple:
    """Format retrieved docs into context string + sources list"""
    context_parts = []
    sources = []
    for i, (doc, score) in enumerate(docs_with_scores):
        label = _source_label(doc.metadata)
        source_label = f"[来源{i + 1}: {label}]"
        context_parts.append(f"{source_label}\n{doc.page_content}")
        sources.append({
            "filename": label,
            "source": doc.metadata.get("source", ""),
            "chunk_text": doc.page_content[:300],
            "similarity_score": round(score, 4),
            "score_type": doc.metadata.get("_score_type", "vector"),
            "chunk_index": doc.metadata.get("chunk_index", 0),
        })
    return "\n\n".join(context_parts), sources


def get_llm() -> ChatOpenAI:
    """ChatOpenAI -> 任意 OpenAI 兼容端点（默认 DeepSeek）"""
    return ChatOpenAI(
        model=settings.LLM_MODEL,
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_API_BASE,
        temperature=settings.LLM_TEMPERATURE,
        streaming=True,
    )


def _build_messages(context: str, question: str, chat_history: list, system_prompt: str = None) -> list:
    """构造消息列表：自定义 system_prompt 作为角色设定追加，硬性规则始终保留"""
    if system_prompt and system_prompt.strip():
        system_content = (
            system_prompt.strip()
            + "\n\n"
            + RAG_RULES
            + "\n\n【参考文档】\n"
            + context
        )
    else:
        system_content = SYSTEM_PROMPT.format(context=context)
    msgs = [SystemMessage(content=system_content)]
    if chat_history:
        for role, content in chat_history[-settings.CHAT_HISTORY_WINDOW:]:
            if role == "human":
                msgs.append(HumanMessage(content=content))
            else:
                msgs.append(AIMessage(content=content))
    msgs.append(HumanMessage(content=question))
    return msgs


async def generate_rag_response(
    question: str,
    chat_history: Optional[list] = None,
    kb_doc_ids: Optional[List[int]] = None,
    kb_ids: Optional[List[int]] = None,
    system_prompt: Optional[str] = None,
) -> dict:
    docs_with_scores = await retrieve_with_scores(
        question, kb_doc_ids=kb_doc_ids, kb_ids=kb_ids
    )
    max_score = max((s for _, s in docs_with_scores), default=0.0)
    if not docs_with_scores or max_score < settings.RETRIEVAL_SCORE_THRESHOLD:
        return {"response": NO_RESULT_MESSAGE, "sources": []}
    context, sources = format_docs_with_sources(docs_with_scores)
    llm = get_llm()
    messages = _build_messages(context, question, chat_history or [], system_prompt=system_prompt)
    response = await llm.ainvoke(messages)
    return {"answer": response.content, "sources": sources, "context": context}


async def _resolve_kbs(kb_ids: Optional[List[int]]):
    """解析知识库列表：返回 (文档型/A类 kb_ids, 数据库型/B类 KB 对象或 None)

    在独立 DB 会话中查询（chain 层不持有请求级会话）。
    """
    if not kb_ids:
        return None, None
    from app.database import async_session_factory
    from app.models.knowledge_base import KnowledgeBase

    db_kb = None
    doc_ids = []
    async with async_session_factory() as db:
        kbs = (
            await db.execute(select(KnowledgeBase).where(KnowledgeBase.id.in_(kb_ids)))
        ).scalars().all()
        for kb in kbs:
            if kb.type == "database":
                db_kb = kb
            else:
                doc_ids.append(kb.id)
    return (doc_ids or None), db_kb


def _format_sql_source(sql: str, result_text: str) -> dict:
    """构造 SQL 来源（供前端"最匹配来源"展示，排在最前）"""
    return {
        "kind": "sql",
        "filename": "生成查询",
        "sql": sql,
        "chunk_text": f"{sql}\n\n查询结果:\n{result_text[:800]}",
        "similarity_score": 1.0,
        "score_type": "sql",
        "chunk_index": 0,
    }


async def stream_rag_response(
    question: str,
    chat_history: Optional[list] = None,
    kb_doc_ids: Optional[List[int]] = None,
    kb_ids: Optional[List[int]] = None,
    system_prompt: Optional[str] = None,
) -> AsyncIterator[Dict[str, Any]]:
    # 有历史时绕过检索缓存，避免改写查询与裸查询串台
    history = chat_history or []
    use_cache = not history

    # 查询改写：仅开启且存在历史时执行；检索用改写后问题，回答上下文仍用原问题
    if settings.QUERY_REWRITE_ENABLED and history:
        effective_question = await rewrite_query(question, history)
    else:
        effective_question = question

    # 解析挂载的知识库：A 类（向量检索）+ B 类（数据库查询）
    doc_kb_ids, db_kb = await _resolve_kbs(kb_ids)
    # 兼容旧调用：传 kb_doc_ids 时作为文档维度过滤
    if kb_doc_ids and not kb_ids:
        doc_kb_ids = None  # 走 kb_doc_ids 过滤路径

    # 并行 3 路：路1/路2 向量检索（A 类文档+问答、B 类知识点）+ 路3 SQL 生成执行
    import asyncio as _asyncio

    async def _run_vector():
        return await retrieve_with_scores(
            effective_question,
            kb_doc_ids=kb_doc_ids if (kb_doc_ids and not kb_ids) else None,
            kb_ids=doc_kb_ids,
            use_cache=use_cache,
        )

    sql_result = None
    if db_kb is not None:
        from app.database import async_session_factory
        from app.rag.text2sql import run_sql_query

        async def _run_sql():
            async with async_session_factory() as db:
                return await run_sql_query(db, db_kb, question, system_prompt or "")

        _vec_task = _asyncio.create_task(_run_vector())
        sql_result = await _run_sql()
        docs_with_scores = await _vec_task
    else:
        docs_with_scores = await _run_vector()

    # 合并来源：SQL 来源放最前，其后是向量检索来源（文档/问答/知识点）
    sources = []
    if sql_result and sql_result.get("sql"):
        sources.append(_format_sql_source(sql_result["sql"], sql_result.get("result_text", "")))

    context_parts = []
    if sql_result and sql_result.get("result_text"):
        # SQL 结果作为"参考文档"最前段（管理员 prompt 会规定如何组织回答）
        label = f"[来源{len(sources)}: 数据库查询结果]"
        context_parts.append(f"{label}\n{sql_result['result_text']}")
        sources.append({
            "kind": "db_result",
            "filename": "数据库查询结果",
            "chunk_text": sql_result["result_text"][:800],
            "similarity_score": 1.0,
            "score_type": "sql",
            "chunk_index": 0,
        })

    # 无依据兜底（阈值语义）：完全没有检索结果 + 没有 SQL 结果时，返回固定提示
    max_score = max((s for _, s in docs_with_scores), default=0.0)
    if (not docs_with_scores or max_score < settings.RETRIEVAL_SCORE_THRESHOLD) and not sql_result:
        for evt in build_no_result_events():
            yield evt
        return

    docs_context, doc_sources = format_docs_with_sources(docs_with_scores)
    context_parts.append(docs_context)
    sources.extend(doc_sources)
    context = "\n\n".join(p for p in context_parts if p)
    llm = get_llm()
    messages = _build_messages(context, question, history, system_prompt=system_prompt)

    full_response = ""
    async for chunk in llm.astream(messages):
        if chunk.content:
            full_response += chunk.content
            yield {"type": "token", "content": chunk.content}

    yield {"type": "sources", "sources": sources}
    yield {"type": "done", "full_response": full_response}
