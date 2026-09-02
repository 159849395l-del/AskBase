"""
Chat / Q&A API — SSE streaming endpoint
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.database import get_db, async_session_factory
from app.models.user import User
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.agent import Agent, AgentKnowledgeBase
from app.core.dependencies import get_current_user
from app.schemas.chat import MessageCreate
from app.rag.chain import stream_rag_response
from app.config import settings
from typing import List
import json

router = APIRouter(prefix="/api/conversations", tags=["聊天"])


async def _load_chat_history(db: AsyncSession, conv_id: int, limit: int = None) -> List:
    """Load recent chat history for context window"""
    limit = limit or settings.CHAT_HISTORY_WINDOW
    q = (
        select(Message)
        .where(Message.conversation_id == conv_id)
        .order_by(desc(Message.created_at))
        .limit(limit)
    )
    result = await db.execute(q)
    messages = list(reversed(result.scalars().all()))
    return [
        ("human" if m.role == "user" else "ai", m.content)
        for m in messages
    ]


async def _load_agent_tools(db: AsyncSession, agent_id: int) -> list:
    """读取智能体挂载且启用的工具（转成 AgentToolRef 列表）"""
    from app.models.agent import AgentTool
    from app.schemas.agent import AgentToolRef

    rows = (
        await db.execute(
            select(AgentTool).where(AgentTool.agent_id == agent_id, AgentTool.enabled == True)  # noqa: E712
        )
    ).scalars().all()
    return [
        AgentToolRef(
            tool_type=r.tool_type,
            tool_ref_id=r.tool_ref_id,
            tool_ref=r.tool_ref,
            enabled=r.enabled,
        )
        for r in rows
    ]


async def _auto_generate_title(question: str) -> str:
    title = question.strip().replace("\n", " ")[:30]
    if len(question.strip()) > 30:
        title += "..."
    return title if title else "新对话"


@router.post("/{conv_id}/messages")
async def send_message(
    conv_id: int,
    body: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Send message and stream answer via SSE"""
    # 1. Validate conversation ownership
    result = await db.execute(select(Conversation).where(Conversation.id == conv_id))
    conv = result.scalar_one_or_none()
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    if conv.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问此会话")

    # 2. Load chat history (must load BEFORE saving user message so it doesn't include itself)
    chat_history = await _load_chat_history(db, conv_id)

    # 2.1 取最近一条消息 id，用于上下文压缩的缓存键（与历史一并稳定）
    last_msg_id = (
        await db.execute(
            select(Message.id)
            .where(Message.conversation_id == conv_id)
            .order_by(desc(Message.created_at))
            .limit(1)
        )
    ).scalar_one_or_none()

    # 3. Save user message + auto-title
    user_msg = Message(conversation_id=conv_id, role="user", content=body.content)
    db.add(user_msg)

    is_first_message = len(chat_history) == 0
    if is_first_message:
        # 智能体存在时，标题用 agent.name；否则自动生成
        if conv.agent_id:
            agent_for_title = (await db.execute(select(Agent).where(Agent.id == conv.agent_id))).scalar_one_or_none()
            if agent_for_title:
                conv.title = agent_for_title.name
        else:
            conv.title = await _auto_generate_title(body.content)
        db.add(conv)

    await db.flush()

    # 4. 智能体注入：会话绑定 agent 时，覆盖 system_prompt 与 kb_doc_ids（向后兼容：未绑定 agent 时沿用请求 body）
    kb_ids_saved = body.kb_ids
    system_prompt_saved = None
    model_id_saved = None
    tools_saved = []
    if conv.agent_id:
        agent = (await db.execute(select(Agent).where(Agent.id == conv.agent_id))).scalar_one_or_none()
        if agent:
            system_prompt_saved = agent.system_prompt
            model_id_saved = agent.model_id
            # 从关联表取所有 kb_doc_id（用 agent 的限定；空列表=不限制,全库检索）
            kb_rows = await db.execute(
                select(AgentKnowledgeBase.kb_id).where(AgentKnowledgeBase.agent_id == agent.id)
            )
            kb_ids_saved = [row[0] for row in kb_rows.all()] or None
            tools_saved = await _load_agent_tools(db, agent.id)

    # 5. SSE generator — uses its own DB session to avoid dependency lifecycle issues
    conv_id_saved = conv_id
    question_saved = body.content
    history_saved = chat_history

    async def event_stream():
        full_response = ""
        sources = []

        try:
            async for event in stream_rag_response(
                question_saved,
                history_saved,
                kb_ids=kb_ids_saved,
                system_prompt=system_prompt_saved,
                conv_id=conv_id_saved,
                last_msg_id=last_msg_id,
                model_id=model_id_saved,
                tools=tools_saved,
            ):
                if event["type"] == "token":
                    full_response += event["content"]
                    yield f"event: token\ndata: {json.dumps({'token': event['content']}, ensure_ascii=False)}\n\n"

                elif event["type"] == "sources":
                    sources = event["sources"]
                    yield f"event: sources\ndata: {json.dumps({'sources': sources}, ensure_ascii=False)}\n\n"

                elif event["type"] == "no_results":
                    # 知识库无结果：转发给前端（区别于正常回答）
                    yield f"event: no_results\ndata: {json.dumps({'message': event['message']}, ensure_ascii=False)}\n\n"

                elif event["type"] == "tool_call":
                    # 工具调用过程：前端可展示"正在调用 XX 工具"
                    yield f"event: tool_call\ndata: {json.dumps({'name': event['name'], 'content': event['content']}, ensure_ascii=False)}\n\n"

                elif event["type"] == "done":
                    # Persist assistant message in a SEPARATE session to guarantee commit
                    async with async_session_factory() as save_db:
                        assistant_msg = Message(
                            conversation_id=conv_id_saved,
                            role="assistant",
                            content=full_response,
                            sources=json.dumps(sources, ensure_ascii=False),
                            token_count=len(full_response),
                        )
                        save_db.add(assistant_msg)
                        await save_db.commit()
                        await save_db.refresh(assistant_msg)
                        msg_id = assistant_msg.id

                    yield f"event: done\ndata: {json.dumps({'message_id': msg_id, 'token_count': len(full_response)}, ensure_ascii=False)}\n\n"

        except Exception as e:
            if full_response:
                async with async_session_factory() as save_db:
                    assistant_msg = Message(
                        conversation_id=conv_id_saved,
                        role="assistant",
                        content=full_response + f"\n\n[回答中断: {str(e)}]",
                        sources=json.dumps(sources, ensure_ascii=False),
                    )
                    save_db.add(assistant_msg)
                    await save_db.commit()

            yield f"event: error\ndata: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
