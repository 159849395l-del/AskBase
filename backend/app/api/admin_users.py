"""管理员：用户管理 API — 列表/创建/编辑/启用禁用/重置密码/删除"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel, Field, field_validator
import re

from app.database import get_db
from app.models.user import User
from app.core.dependencies import get_admin_user
from app.core.security import hash_password
from app.services.auth_service import register_user

router = APIRouter(prefix="/api/admin/users", tags=["用户管理"])


# ---------- Schemas ----------

class AdminUserItem(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    created_at: str

    class Config:
        from_attributes = True


class AdminUserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    password: str = Field(..., min_length=6, max_length=128, description="初始密码")
    role: str = Field("user", description="角色：admin / user")

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z0-9_]+$", v):
            raise ValueError("用户名只能包含字母、数字和下划线")
        return v

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in ("admin", "user"):
            raise ValueError("角色只能是 admin 或 user")
        return v


class AdminUserUpdate(BaseModel):
    role: str | None = Field(None, description="角色：admin / user")
    is_active: bool | None = Field(None, description="启用/禁用")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v):
        if v is not None and v not in ("admin", "user"):
            raise ValueError("角色只能是 admin 或 user")
        return v


class AdminResetPassword(BaseModel):
    new_password: str = Field(..., min_length=6, max_length=128, description="新密码")


# ---------- Helpers ----------

async def _get_user(db: AsyncSession, user_id: int) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(404, detail="用户不存在")
    return user


# ---------- API ----------

@router.get("", response_model=list[AdminUserItem])
async def list_admin_users(
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """用户列表（全部字段，含启用状态）"""
    result = await db.execute(select(User).order_by(User.id.asc()))
    return list(result.scalars().all())


@router.post("", response_model=AdminUserItem, status_code=201)
async def create_admin_user(
    req: AdminUserCreate,
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """创建用户（可指定角色）"""
    exists = await db.scalar(select(User).where(User.username == req.username))
    if exists is not None:
        raise HTTPException(409, detail="用户名已存在")
    user = User(
        username=req.username,
        password_hash=hash_password(req.password),
        role=req.role,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


@router.put("/{user_id}", response_model=AdminUserItem)
async def update_admin_user(
    user_id: int,
    req: AdminUserUpdate,
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """编辑用户（角色/启用状态）"""
    user = await _get_user(db, user_id)
    # 自我保护：不能禁用/降级自己
    if user.id == admin_user.id and (req.is_active is False or req.role == "user"):
        raise HTTPException(400, detail="不能对自己的账户执行此操作")
    # 最后一个 admin 保护：把唯一 admin 降为 user 时拒绝
    if user.role == "admin" and req.role == "user":
        admin_count = await db.scalar(select(func.count()).select_from(User).where(User.role == "admin", User.is_active == True))
        if (admin_count or 0) <= 1:
            raise HTTPException(400, detail="系统至少需要保留一个启用的管理员")
    if req.role is not None:
        user.role = req.role
    if req.is_active is not None:
        user.is_active = req.is_active
    await db.flush()
    await db.refresh(user)
    return user


@router.put("/{user_id}/password", response_model=dict)
async def reset_user_password(
    user_id: int,
    req: AdminResetPassword,
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """重置用户密码（管理员操作，无需旧密码）"""
    user = await _get_user(db, user_id)
    user.password_hash = hash_password(req.new_password)
    await db.flush()
    return {"message": f"已重置用户「{user.username}」的密码"}


@router.delete("/{user_id}", response_model=dict)
async def delete_admin_user(
    user_id: int,
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """删除用户（连带其会话/文档）"""
    if user_id == admin_user.id:
        raise HTTPException(400, detail="不能删除自己的账户")
    user = await _get_user(db, user_id)
    if user.role == "admin":
        admin_count = await db.scalar(select(func.count()).select_from(User).where(User.role == "admin"))
        if (admin_count or 0) <= 1:
            raise HTTPException(400, detail="不能删除最后一个管理员")
    await db.delete(user)
    await db.flush()
    return {"message": f"已删除用户「{user.username}」"}
