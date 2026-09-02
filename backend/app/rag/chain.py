"""
LangChain RAG 链 — ChatOpenAI + 百炼 MaaS 端点
"""

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from sqlalchemy import select
from app.config import settings
from app.rag.retriever import retrieve_with_scores
from app.rag.query_rewriter import rewrite_query
from app.rag.context_compressor import compress_history
from app.services.llm_factory import resolve_llm
from app.schemas.agent import AgentToolRef
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

# 挂载工具时的规则：放宽"只用参考文档"，允许调用工具获取实时/外部信息
RAG_RULES_WITH_TOOLS = """【必须遵守的规则】
1. 涉及时效性信息的问题（当前时间/日期、价格行情、新闻事件、实时数据、天气、政策、最新动态等），你必须调用合适的工具去获取，禁止凭内部记忆或主观推断作答；知识库和工具都拿不到时才如实说明
2. 你可以调用下方授权的工具（获取当前时间、联网搜索、知识库检索、数学计算）。工具返回结果可信，请优先结合工具结果和参考文档回答
3. 禁止编造。参考文档和工具都无法获取的信息，请如实说明无法获取
4. 回答时请引用文档中的具体内容，并在末尾标明引用来源编号
5. 如果涉及价格、库存等时效性信息，请提醒用户以实际页面为准
6. 使用中文回答，保持专业、友好的语气
7. 对于对比类问题，请用表格形式呈现差异"""

# 默认智能体提示词（未配置自定义提示词时使用）
SYSTEM_PROMPT = """你是一个知识库问答助手。你的职责是基于知识库中提供的参考文档，准确回答用户的问题。

""" + RAG_RULES + """

【参考文档】
{context}"""

SYSTEM_PROMPT_WITH_TOOLS = """你是一个智能问答助手。你的职责是基于参考文档、数据库查询结果和工具返回结果，准确回答用户的问题。

""" + RAG_RULES_WITH_TOOLS + """

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


def get_llm(model_id: Optional[int] = None) -> ChatOpenAI:
    """ChatOpenAI -> 大模型库 / .env 兜底

    - 传 model_id：从大模型库取配置（失败自动回退 .env）
    - 不传：优先库内默认模型，其次 .env
    注：本函数是同步上下文的便捷入口，异步链路请用 services.llm_factory.resolve_llm。
    """
    from app.services.llm_factory import resolve_llm_sync

    if model_id is None:
        # 未指定时沿用旧行为（.env），避免同步上下文里额外开事件循环
        return ChatOpenAI(
            model=settings.LLM_MODEL,
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_API_BASE,
            temperature=settings.LLM_TEMPERATURE,
            streaming=True,
        )
    return resolve_llm_sync(model_id, streaming=True)


def _build_messages(context: str, question: str, chat_history: list, system_prompt: str = None, compressed_summary: str = None, tool_note: str = None, rules: str = None) -> list:
    """构造消息列表：自定义 system_prompt 作为角色设定追加，硬性规则始终保留。

    若 compressed_summary 不为空（上下文压缩生效），将其作为独立系统消息插入到
    "系统提示/RAG_RULES" 与 "近期原文历史" 之间，拼接顺序为：
        [角色 system_prompt, RAG_RULES, 摘要(若有), 近期原文历史, 当前问题]
    当 compressed_summary 为 None 时，行为与原 10 轮滑动窗口完全一致（降级）。
    rules 参数允许挂工具时替换为 RAG_RULES_WITH_TOOLS（默认 RAG_RULES）。
    """
    rules = rules or RAG_RULES
    extra = ("\n\n" + tool_note.strip()) if tool_note else ""
    if system_prompt and system_prompt.strip():
        system_content = (
            system_prompt.strip()
            + extra
            + "\n\n"
            + rules
            + "\n\n【参考文档】\n"
            + context
        )
    else:
        if rules is RAG_RULES_WITH_TOOLS:
            system_content = SYSTEM_PROMPT_WITH_TOOLS.format(context=context) + (extra if extra else "")
        else:
            system_content = SYSTEM_PROMPT.format(context=context) + (extra if extra else "")
    msgs = [SystemMessage(content=system_content)]
    if compressed_summary:
        msgs.append(SystemMessage(content="【对话历史摘要】\n" + compressed_summary))
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
    model_id: Optional[int] = None,
) -> dict:
    docs_with_scores = await retrieve_with_scores(
        question, kb_doc_ids=kb_doc_ids, kb_ids=kb_ids
    )
    max_score = max((s for _, s in docs_with_scores), default=0.0)
    if not docs_with_scores or max_score < settings.RETRIEVAL_SCORE_THRESHOLD:
        return {"response": NO_RESULT_MESSAGE, "sources": []}
    context, sources = format_docs_with_sources(docs_with_scores)
    llm = await resolve_llm(model_id)
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
    conv_id: Optional[int] = None,
    last_msg_id: Optional[int] = None,
    model_id: Optional[int] = None,
    tools: Optional[List[AgentToolRef]] = None,
) -> AsyncIterator[Dict[str, Any]]:
    # 有历史时绕过检索缓存，避免改写查询与裸查询串台
    history = chat_history or []
    use_cache = not history
    tool_refs = [t for t in (tools or []) if t.enabled]

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

    # 无依据兜底（阈值语义）：完全没有检索结果 + 没有 SQL 结果时
    max_score = max((s for _, s in docs_with_scores), default=0.0)
    has_docs = bool(docs_with_scores) and max_score >= settings.RETRIEVAL_SCORE_THRESHOLD
    if not has_docs and not sql_result:
        if not tool_refs:
            # 没有可用依据也没有工具：返回固定提示，不浪费 LLM
            for evt in build_no_result_events():
                yield evt
            return
        # 挂了工具（如获取当前时间 / 联网搜索）：不短路，把是否调工具的
        # 判断权交给模型——时效类问题应由工具给出答案而非知识库
        context = ""
    else:
        docs_context, doc_sources = format_docs_with_sources(docs_with_scores)
        context_parts.append(docs_context)
        sources.extend(doc_sources)
        context = "\n\n".join(p for p in context_parts if p)
    llm = await resolve_llm(model_id)
    # 上下文压缩：将较早历史压成摘要，近期原文保持高保真。
    # 任何异常/未达阈值时 compress_history 静默降级，返回 (None, history)，
    # 此时 _build_messages 行为与原始 10 轮滑动窗口完全一致。
    compressed_summary, compressed_history = await compress_history(
        history, conv_id=conv_id, last_msg_id=last_msg_id
    )
    # 挂载工具时放宽"只用参考文档"的约束，并说明工具使用原则
    tool_note = None
    rules = RAG_RULES
    if tool_refs:
        rules = RAG_RULES_WITH_TOOLS
        tool_note = (
            "【工具使用规则】\n"
            "1. 你被授权使用若干工具。当参考文档不足以回答，或问题涉及时效信息、实时计算、外部知识时，调用合适的工具。\n"
            "2. 工具返回的结果可以信任，回答时请基于工具结果，并说明信息来源。\n"
            "3. 不需要工具时不要调用，直接根据参考文档回答。"
        )
    messages = _build_messages(
        context, question, compressed_history, system_prompt=system_prompt,
        compressed_summary=compressed_summary, tool_note=tool_note, rules=rules,
    )

    # ---------- 工具调用（挂载了工具且模型支持时才启用） ----------
    if tool_refs:
        tool_events, tool_messages = await _maybe_run_tools(
            llm, messages, tool_refs, kb_ids=kb_ids
        )
        for evt in tool_events:
            yield evt
        if tool_messages:
            messages = messages + tool_messages

    full_response = ""
    async for chunk in llm.astream(messages):
        if chunk.content:
            full_response += chunk.content
            yield {"type": "token", "content": chunk.content}

    yield {"type": "sources", "sources": sources}
    yield {"type": "done", "full_response": full_response}


async def _maybe_run_tools(llm, messages: list, tool_refs: list, kb_ids=None):
    """工具多轮调用循环：模型判断是否调用 → 执行 → 结果回填 → 再问，最多 3 轮。

    部分模型偶发发出空参数 / 参数不全的 tool_call（如 web_search 缺 query），
    把工具执行结果（含"缺少参数"错误）回填后让模型在下一轮修正或直接作答，
    避免"调用了一次失败就放弃"。
    返回 (sse_events, tool_messages)。任何异常都静默降级为「不使用工具」。
    """
    from langchain_core.messages import AIMessage, ToolMessage
    from app.database import async_session_factory
    from app.skills.executor import build_tool_specs, run_tool_calls

    max_rounds = 3
    events: list = []
    tool_messages: list = []
    try:
        async with async_session_factory() as db:
            specs, name_map = await build_tool_specs(db, tool_refs)
            if not specs:
                return [], []
            llm_with_tools = llm.bind_tools(specs)
            # 记录每个工具调用真实的 name+args（给 LLM 看第二轮历史时用）
            call_records: list = []
            for _round in range(max_rounds):
                ai_msg = await llm_with_tools.ainvoke(messages + tool_messages)
                tool_calls = getattr(ai_msg, "tool_calls", None) or []
                if not tool_calls:
                    break  # 模型不再调用工具（可能已直接给出答案）
                results = await run_tool_calls(db, tool_calls, name_map, kb_ids=kb_ids)
                call_records.extend(results)
                for r in results:
                    events.append({
                        "type": "tool_call",
                        "name": r["name"],
                        "content": r["content"][:500],
                    })
                # 本轮 AI 的工具调用请求 + 各工具结果，作为历史追加给下一轮
                tool_messages.append(
                    AIMessage(
                        content=ai_msg.content or "",
                        tool_calls=[
                            {
                                "name": c.get("name", ""),
                                "args": c.get("args", {}) or {},
                                "id": c.get("id") or c.get("name", ""),
                                "type": "tool_call",
                            }
                            for c in tool_calls
                        ],
                    )
                )
                for r in results:
                    tool_messages.append(
                        ToolMessage(content=r["content"], tool_call_id=r["tool_call_id"])
                    )
    except Exception as e:
        print(f"[chain] 工具调用失败，降级为不调用工具：{e}")
        return [], []

    return events, tool_messages
