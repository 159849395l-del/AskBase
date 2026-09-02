"""
内部 Skill 管理 API — 仅管理员可增删改，登录用户可读启用列表
- CRUD：/api/skills
- 测试调用：POST /api/skills/{id}/test
- 内置工具种子：POST /api/skills/seed-builtin
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.database import get_db
from app.models.user import User
from app.core.dependencies import get_current_user, get_admin_user
from app.schemas.skill import (
    SkillCreate,
    SkillUpdate,
    SkillItem,
    SkillTestRequest,
    SkillTestResponse,
)
from app.schemas.auth import MessageResponse
from app.services import skill_service
from app.skills.registry import ensure_builtin_skills

router = APIRouter(prefix="/api/skills", tags=["AI 智能工具"])


@router.get("", response_model=List[SkillItem])
async def list_skills(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """工具列表（管理员看全部；普通用户只看启用）"""
    items = await skill_service.list_skills(db)
    if current_user.role != "admin":
        items = [i for i in items if i.is_active]
    return items


@router.post("", response_model=SkillItem, status_code=status.HTTP_201_CREATED)
async def create_skill(
    body: SkillCreate,
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """新建工具（仅管理员）"""
    return await skill_service.create_skill(db, body)


@router.post("/seed-builtin", response_model=MessageResponse)
async def seed_builtin(
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """把内置工具写入数据库（已存在则跳过）"""
    created = await ensure_builtin_skills(db)
    return MessageResponse(
        message=f"已新增 {created} 个内置工具" if created else "内置工具已存在，无需重复写入"
    )


@router.get("/{skill_id}", response_model=SkillItem)
async def get_skill(
    skill_id: int,
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """工具详情（仅管理员）"""
    s = await skill_service.get_skill(db, skill_id)
    return skill_service._to_item(s)


@router.put("/{skill_id}", response_model=SkillItem)
async def update_skill(
    skill_id: int,
    body: SkillUpdate,
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """更新工具（仅管理员）"""
    return await skill_service.update_skill(db, skill_id, body)


@router.delete("/{skill_id}", response_model=MessageResponse)
async def delete_skill(
    skill_id: int,
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """删除工具（仅管理员；内置工具不可删）"""
    await skill_service.delete_skill(db, skill_id)
    return MessageResponse(message="工具已删除")


@router.post("/{skill_id}/test", response_model=SkillTestResponse)
async def test_skill(
    skill_id: int,
    body: SkillTestRequest,
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """测试调用工具（仅管理员）"""
    return await skill_service.test_skill(db, skill_id, body.arguments)
