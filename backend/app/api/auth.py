"""认证 API"""

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.user import User
from app.core.dependencies import get_current_user, get_admin_user
from app.services.auth_service import register_user, login_user, change_user_password
from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    UserInfo,
    ChangePasswordRequest,
    MessageResponse,
)
from pydantic import BaseModel

router = APIRouter(prefix="/api/auth", tags=["认证"])


class UserBrief(BaseModel):
    """用户简要信息（授权用户下拉用）"""

    id: int
    username: str
    role: str


@router.get("/users", response_model=list[UserBrief])
async def list_users(
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """用户列表（仅管理员，供授权用户选择）"""
    result = await db.execute(select(User).order_by(User.id.asc()))
    return [
        UserBrief(id=u.id, username=u.username, role=u.role)
        for u in result.scalars().all()
    ]


@router.post("/register", response_model=UserInfo, status_code=201)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """用户注册"""
    return await register_user(db, req)


@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """用户登录 — OAuth2 表单格式"""
    return await login_user(db, LoginRequest(username=form_data.username, password=form_data.password))


@router.get("/me", response_model=UserInfo)
async def get_me(current_user: User = Depends(get_current_user)):
    """获取当前登录用户信息"""
    return UserInfo(
        id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        created_at=current_user.created_at,
    )


@router.put("/change-password", response_model=MessageResponse)
async def change_password(
    req: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """修改密码"""
    await change_user_password(db, current_user, req.old_password, req.new_password)
    return MessageResponse(message="密码修改成功")
