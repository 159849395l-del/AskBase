"""
LangChain RAG 链 — ChatOpenAI + 百炼 MaaS 端点
"""

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from app.config import settings
from app.rag.retriever import retrieve_with_scores
from typing import AsyncIterator, Optional, Dict, Any


SYSTEM_PROMPT = """你是一个专业的电商产品知识库助手。你的职责是基于提供的产品信息文档，准确回答用户关于产品的问题。

请严格遵守以下规则：
1. 只根据提供的【参考文档】内容回答问题，不要使用外部知识
2. 如果参考文档中没有相关信息，请诚实地说"根据现有产品资料，我无法找到相关信息"，不要编造
3. 回答时请引用具体的产品名称、规格参数，并在末尾标明引用来源编号
4. 如果涉及价格、库存等时效性信息，请提醒用户以实际页面为准
5. 使用中文回答，保持专业、友好的语气
6. 对于产品对比类问题，请用表格形式呈现差异

{context}"""


def format_docs_with_sources(docs_with_scores: list) -> tuple:
    """Format retrieved docs into context string + sources list"""
    context_parts = []
    sources = []
    for i, (doc, score) in enumerate(docs_with_scores):
        source_label = f"[来源{i + 1}: {doc.metadata.get('filename', '未知文件')}]"
        context_parts.append(f"{source_label}\n{doc.page_content}")
        sources.append({
            "filename": doc.metadata.get("filename", "未知文件"),
            "chunk_text": doc.page_content[:300],
            "similarity_score": round(score, 4),
            "chunk_index": doc.metadata.get("chunk_index", 0),
            "product_category": doc.metadata.get("product_category", None),
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


def _build_messages(context: str, question: str, chat_history: list) -> list:
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
    product_category: Optional[str] = None,
) -> dict:
    docs_with_scores = await retrieve_with_scores(question)
    context, sources = format_docs_with_sources(docs_with_scores)
    llm = get_llm()
    messages = _build_messages(context, question, chat_history or [])
    response = await llm.ainvoke(messages)
    return {"answer": response.content, "sources": sources, "context": context}


async def stream_rag_response(
    question: str,
    chat_history: Optional[list] = None,
) -> AsyncIterator[Dict[str, Any]]:
    docs_with_scores = await retrieve_with_scores(question)
    context, sources = format_docs_with_sources(docs_with_scores)
    llm = get_llm()
    messages = _build_messages(context, question, chat_history or [])

    full_response = ""
    async for chunk in llm.astream(messages):
        if chunk.content:
            full_response += chunk.content
            yield {"type": "token", "content": chunk.content}

    yield {"type": "sources", "sources": sources}
    yield {"type": "done", "full_response": full_response}
