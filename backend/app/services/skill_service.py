"""内部 Skill 服务 — CRUD + 内置工具种子 + 测试调用"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from fastapi import HTTPException, status
import json

from app.models.skill import Skill
from app.schemas.skill import (
    SkillCreate,
    SkillUpdate,
    SkillItem,
    SkillTestResponse,
)
from app.skills.registry import get_handler


def _parse_schema(skill: Skill) -> dict:
    try:
        return json.loads(skill.input_schema) if skill.input_schema else {}
    except Exception:
        return {"type": "object", "properties": {}}


def _to_item(skill: Skill) -> SkillItem:
    return SkillItem(
        id=skill.id,
        name=skill.name,
        title=skill.title,
        description=skill.description,
        icon=skill.icon,
        handler=skill.handler,
        input_schema=_parse_schema(skill),
        is_active=skill.is_active,
        is_builtin=skill.is_builtin,
        is_dangerous=skill.is_dangerous,
        sort_order=skill.sort_order,
        created_at=skill.created_at,
        updated_at=skill.updated_at,
    )


async def list_skills(db: AsyncSession) -> List[SkillItem]:
    result = await db.execute(
        select(Skill).order_by(Skill.sort_order.asc(), Skill.id.asc())
    )
    return [_to_item(s) for s in result.scalars().all()]


async def get_skill(db: AsyncSession, skill_id: int) -> Skill:
    result = await db.execute(select(Skill).where(Skill.id == skill_id))
    s = result.scalar_one_or_none()
    if s is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工具不存在")
    return s


async def create_skill(db: AsyncSession, body: SkillCreate) -> SkillItem:
    await _ensure_name_unique(db, body.name, exclude_id=None)
    s = Skill(
        name=body.name.strip(),
        title=body.title.strip(),
        description=body.description or "",
        icon=body.icon or "🔧",
        handler=body.handler or body.name.strip(),
        input_schema=json.dumps(body.input_schema, ensure_ascii=False),
        is_active=body.is_active,
        is_builtin=False,
        is_dangerous=body.is_dangerous,
        sort_order=body.sort_order,
    )
    db.add(s)
    await db.flush()
    await db.refresh(s)
    return _to_item(s)


async def update_skill(db: AsyncSession, skill_id: int, body: SkillUpdate) -> SkillItem:
    s = await get_skill(db, skill_id)
    data = body.model_dump(exclude_unset=True)
    if "name" in data and data["name"]:
        data["name"] = data["name"].strip()
        await _ensure_name_unique(db, data["name"], exclude_id=skill_id)
    if "input_schema" in data:
        data["input_schema"] = json.dumps(data["input_schema"] or {}, ensure_ascii=False)
    for k, v in data.items():
        setattr(s, k, v)
    await db.flush()
    await db.refresh(s)
    return _to_item(s)


async def delete_skill(db: AsyncSession, skill_id: int) -> None:
    s = await get_skill(db, skill_id)
    if s.is_builtin:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="内置工具不可删除，可改为停用")
    await db.delete(s)
    await db.flush()


async def _ensure_name_unique(db: AsyncSession, name: str, exclude_id) -> None:
    q = select(Skill).where(Skill.name == name.strip())
    if exclude_id is not None:
        q = q.where(Skill.id != exclude_id)
    existing = (await db.execute(q)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"工具名「{name}」已存在")


async def test_skill(
    db: AsyncSession, skill_id: int, arguments: dict
) -> SkillTestResponse:
    """管理员测试调用 Skill（不经过 LLM）"""
    s = await get_skill(db, skill_id)
    handler = get_handler(s.handler or s.name)
    if handler is None:
        return SkillTestResponse(
            success=False,
            message="该工具没有可执行的处理函数（自定义工具暂不支持执行）",
        )
    try:
        result = await handler(arguments or {})
        return SkillTestResponse(success=True, result=str(result))
    except Exception as e:
        return SkillTestResponse(success=False, message=str(e)[:500])
