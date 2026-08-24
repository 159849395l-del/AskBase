"""
查询改写模块 — 结合聊天历史消解指代/省略，生成完整自包含的检索问题

零新依赖：仅复用 chain.get_llm()，通过函数内 import 避免与 chain.py 循环导入。
"""

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from app.config import settings


REWRITE_SYSTEM_PROMPT = """你是一个查询改写助手。仅当聊天历史中存在指代或省略时，将用户问题改写为完整自包含的表述，使检索能独立理解；否则原样输出用户问题。只输出改写后的问题，不要解释。"""


def build_rewrite_messages(question: str, chat_history: list) -> list:
    """构建改写用消息列表：系统提示 + 最近 CHAT_HISTORY_WINDOW 条历史 + 当前问题（纯函数）"""
    msgs = [SystemMessage(content=REWRITE_SYSTEM_PROMPT)]
    if chat_history:
        for role, content in chat_history[-settings.CHAT_HISTORY_WINDOW:]:
            if role == "human":
                msgs.append(HumanMessage(content=content))
            else:
                msgs.append(AIMessage(content=content))
    msgs.append(HumanMessage(content=question))
    return msgs


async def rewrite_query(question: str, chat_history: list) -> str:
    """调用 LLM 改写问题；任何异常打印日志并返回原问题（回退保底，不中断链路）"""
    try:
        # 函数内 import，避免与 chain.py 循环导入
        from app.rag.chain import get_llm

        messages = build_rewrite_messages(question, chat_history)
        response = await get_llm().ainvoke(messages)
        rewritten = response.content.strip()
        return rewritten if rewritten else question
    except Exception as e:
        print(f"[QueryRewrite] 改写异常，回退原问题: {e}")
        return question
