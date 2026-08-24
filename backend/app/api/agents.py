"""
智能体管理 API — 列表/详情/创建/更新/删除（CRUD）
- 列表、详情：登录用户可用
- 增删改：仅管理员
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional

from app.database import get_db
from app.core.dependencies import get_current_user, get_admin_user
from app.models.user import User
from app.models.agent import Agent, AgentKnowledgeBase
from app.models.knowledge_document import KnowledgeDocument
from app.schemas.agent import AgentItem, AgentDetail, AgentCreate, AgentUpdate

router = APIRouter(prefix="/api/agents", tags=["智能体"])


async def _to_item(agent: Agent, kb_ids: List[int]) -> AgentItem:
    return AgentItem(
        id=agent.id,
        name=agent.name,
        description=agent.description,
        icon=agent.icon,
        welcome_message=agent.welcome_message,
        is_active=agent.is_active,
        is_hidden=agent.is_hidden,
        sort_order=agent.sort_order,
        created_at=agent.created_at,
        kb_ids=kb_ids,
    )


async def _to_detail(agent: Agent, kb_ids: List[int]) -> AgentDetail:
    item = await _to_item(agent, kb_ids)
    return AgentDetail(**item.model_dump(), system_prompt=agent.system_prompt, updated_at=agent.updated_at)


@router.get("", response_model=List[AgentItem])
async def list_agents(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """列出智能体（按排序）；普通用户只看未隐藏且启用的，管理员看全部（含隐藏/停用）"""
    q = select(Agent)
    if current_user.role != "admin":
        q = q.where(Agent.is_active == True, Agent.is_hidden == False)
    q = q.order_by(Agent.sort_order.asc(), Agent.id.asc())
    result = await db.execute(q)
    agents = result.scalars().all()
    items: List[AgentItem] = []
    for a in agents:
        # 取关联的 kb_doc_id
        kb_ids = [row[0] for row in (await db.execute(
            select(AgentKnowledgeBase.kb_id).where(AgentKnowledgeBase.agent_id == a.id)
        )).all()]
        items.append(await _to_item(a, kb_ids))
    return items


@router.get("/{agent_id}", response_model=AgentDetail)
async def get_agent(
    agent_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """智能体详情（admin 可见 system_prompt；普通用户不暴露提示词，且隐藏的智能体视为不存在）"""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if agent is None or (current_user.role != "admin" and (agent.is_hidden or not agent.is_active)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="智能体不存在")
    kb_ids = [row[0] for row in (await db.execute(
        select(AgentKnowledgeBase.kb_id).where(AgentKnowledgeBase.agent_id == agent_id)
    )).all()]
    detail = await _to_detail(agent, kb_ids)
    if current_user.role != "admin":
        detail.system_prompt = ""
    return detail


def _sanitize_html(value: str) -> str:
    """剥离 HTML/脚本标签，防止恶意内容进入展示层（XSS 兜底）"""
    import re as _re
    if not value:
        return value
    return _re.sub(r"<[^>]*>", "", value)


async def _ensure_name_unique(db: AsyncSession, name: str, exclude_agent_id: int | None = None) -> None:
    """校验智能体名称唯一（排除 exclude_agent_id，用于更新自身）"""
    q = select(Agent).where(Agent.name == name.strip())
    if exclude_agent_id is not None:
        q = q.where(Agent.id != exclude_agent_id)
    existing = (await db.execute(q)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"智能体名称「{name}」已存在，请使用其他名称")


async def _validate_kb_ids(db: AsyncSession, kb_ids: List[int]) -> None:
    """校验知识库存在 + 数据库型（B 类）KB 最多挂载 1 个"""
    from app.models.knowledge_base import KnowledgeBase

    if not kb_ids:
        return
    kbs = (
        await db.execute(select(KnowledgeBase).where(KnowledgeBase.id.in_(kb_ids)))
    ).scalars().all()
    existing_ids = {kb.id for kb in kbs}
    missing = [x for x in kb_ids if x not in existing_ids]
    if missing:
        raise HTTPException(status_code=400, detail=f"知识库不存在: {missing}")
    db_kbs = [kb for kb in kbs if kb.type == "database"]
    if len(db_kbs) > 1:
        names = "、".join(kb.name for kb in db_kbs)
        raise HTTPException(
            status_code=400,
            detail=f"最多只能挂载 1 个数据库型知识库（当前选了 {len(db_kbs)} 个：{names}），"
                   "否则 SQL 不知道查哪个库/表，请保留 1 个",
        )


@router.post("", response_model=AgentDetail)
async def create_agent(
    body: AgentCreate,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
):
    """创建智能体（仅管理员）"""
    # 校验 kb_ids 都存在 + 数据库型 ≤ 1
    await _validate_kb_ids(db, body.kb_ids)

    # 名称唯一性校验
    await _ensure_name_unique(db, body.name, exclude_agent_id=None)

    agent = Agent(
        name=_sanitize_html(body.name),
        description=_sanitize_html(body.description),
        icon=_sanitize_html(body.icon),
        welcome_message=_sanitize_html(body.welcome_message),
        system_prompt=body.system_prompt,
        is_active=body.is_active,
        sort_order=body.sort_order,
        created_by=admin_user.id,
    )
    db.add(agent)
    await db.flush()
    for kid in body.kb_ids:
        db.add(AgentKnowledgeBase(agent_id=agent.id, kb_id=kid))
    await db.flush()
    return await _to_detail(agent, list(body.kb_ids))


@router.put("/{agent_id}", response_model=AgentDetail)
async def update_agent(
    agent_id: int,
    body: AgentUpdate,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
):
    """更新智能体（仅管理员）"""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="智能体不存在")

    data = body.model_dump(exclude_unset=True)
    kb_ids_update = data.pop("kb_ids", None)
    # 名称唯一性校验（排除自身）
    if "name" in data:
        data["name"] = _sanitize_html(data["name"])
        await _ensure_name_unique(db, data["name"], exclude_agent_id=agent_id)
    # 文本字段剥离 HTML 标签（XSS 兜底）
    for k in ("description", "icon", "welcome_message"):
        if k in data and data[k]:
            data[k] = _sanitize_html(data[k])
    for k, v in data.items():
        setattr(agent, k, v)

    if kb_ids_update is not None:
        # 全量替换
        await _validate_kb_ids(db, kb_ids_update)
        # 删旧关联
        old = await db.execute(
            select(AgentKnowledgeBase).where(AgentKnowledgeBase.agent_id == agent_id)
        )
        for row in old.scalars().all():
            await db.delete(row)
        # 加新关联
        for kid in kb_ids_update:
            db.add(AgentKnowledgeBase(agent_id=agent_id, kb_id=kid))

    await db.flush()
    # 取最新 kb_ids
    kb_ids = [row[0] for row in (await db.execute(
        select(AgentKnowledgeBase.kb_id).where(AgentKnowledgeBase.agent_id == agent_id)
    )).all()]
    return await _to_detail(agent, kb_ids)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: int,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
):
    """删除智能体（仅管理员；级联删除关联，会话的 agent_id 置 NULL）"""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="智能体不存在")
    await db.delete(agent)
    await db.flush()


@router.post("/{agent_id}/conversation")
async def get_or_create_agent_conversation(
    agent_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户对该智能体的会话（每个用户×智能体只保持一个，复用最近一次），没有则创建"""
    from sqlalchemy import desc
    from app.models.conversation import Conversation

    agent = (await db.execute(select(Agent).where(Agent.id == agent_id))).scalar_one_or_none()
    # 普通用户：隐藏或停用的智能体视为不存在；管理员不受限
    if agent is None or not agent.is_active or (current_user.role != "admin" and agent.is_hidden):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="智能体不存在或未启用")

    # 查找该用户对该智能体的激活会话（最近更新的）
    conv = (await db.execute(
        select(Conversation)
        .where(
            Conversation.user_id == current_user.id,
            Conversation.agent_id == agent_id,
            Conversation.is_active == True,
        )
        .order_by(desc(Conversation.updated_at))
        .limit(1)
    )).scalar_one_or_none()

    if conv is None:
        conv = Conversation(user_id=current_user.id, agent_id=agent_id, title=agent.name)
        db.add(conv)
        await db.flush()

    return {
        "id": conv.id,
        "title": conv.title,
        "agent_id": conv.agent_id,
        "is_active": conv.is_active,
        "created_at": conv.created_at,
        "updated_at": conv.updated_at,
    }


# ---------- 智能体测试（编辑页右侧预览用，不落库） ----------

from pydantic import BaseModel, Field
from fastapi.responses import StreamingResponse
from app.rag.chain import stream_rag_response
import json


class AgentTestRequest(BaseModel):
    question: str = Field(..., min_length=1)
    system_prompt: Optional[str] = None
    kb_ids: List[int] = Field(default_factory=list)
    history: List[List[str]] = Field(default_factory=list, description='[["human","问题"],["ai","回答"]]')


@router.post("/test")
async def test_agent(
    body: AgentTestRequest,
    admin_user: User = Depends(get_admin_user),
):
    """测试智能体配置（仅管理员）：用当前草稿的 system_prompt + kb_ids 直接问答，SSE 流式返回，不落库"""
    history = [(h[0], h[1]) for h in body.history if len(h) == 2]

    async def event_stream():
        try:
            async for event in stream_rag_response(
                body.question,
                history,
                kb_ids=body.kb_ids or None,
                system_prompt=body.system_prompt,
            ):
                if event["type"] == "token":
                    yield f"event: token\ndata: {json.dumps({'token': event['content']}, ensure_ascii=False)}\n\n"
                elif event["type"] == "sources":
                    yield f"event: sources\ndata: {json.dumps({'sources': event['sources']}, ensure_ascii=False)}\n\n"
                elif event["type"] == "no_results":
                    yield f"event: no_results\ndata: {json.dumps({'message': event['message']}, ensure_ascii=False)}\n\n"
                elif event["type"] == "done":
                    yield f"event: done\ndata: {json.dumps({'token_count': len(event.get('full_response', ''))}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )