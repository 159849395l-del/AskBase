"""
认证服务 — 用户注册、登录、密码修改
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status
from app.models.user import User
from app.core.security import hash_password, verify_password, create_access_token
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse, UserInfo


async def register_user(db: AsyncSession, req: RegisterRequest) -> UserInfo:
    """注册新用户（角色默认为 user，admin 只能通过种子数据创建）"""
    # 检查用户名是否已存在
    result = await db.execute(select(User).where(User.username == req.username))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="用户名已存在",
        )

    # 创建用户
    user = User(
        username=req.username,
        password_hash=hash_password(req.password),
        role="user",
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    return UserInfo(
        id=user.id,
        username=user.username,
        role=user.role,
        created_at=user.created_at,
    )


async def login_user(db: AsyncSession, req: LoginRequest) -> TokenResponse:
    """用户登录 — 验证凭据并返回 JWT token"""
    # 查找用户
    result = await db.execute(select(User).where(User.username == req.username))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用",
        )

    # 生成 JWT
    access_token = create_access_token(data={"sub": str(user.id), "role": user.role})

    return TokenResponse(
        access_token=access_token,
        user=UserInfo(
            id=user.id,
            username=user.username,
            role=user.role,
            created_at=user.created_at,
        ),
    )


async def change_user_password(
    db: AsyncSession,
    user: User,
    old_password: str,
    new_password: str,
) -> None:
    """修改用户密码"""
    if not verify_password(old_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="旧密码错误",
        )

    user.password_hash = hash_password(new_password)
    db.add(user)
    await db.flush()


async def seed_admin(db: AsyncSession) -> None:
    """种子管理员账户（admin/123456），仅在不存在时创建"""
    from app.config import settings

    result = await db.execute(select(User).where(User.username == settings.ADMIN_USERNAME))
    existing_admin = result.scalar_one_or_none()
    if existing_admin is None:
        admin = User(
            username=settings.ADMIN_USERNAME,
            password_hash=hash_password(settings.ADMIN_PASSWORD),
            role="admin",
        )
        db.add(admin)
        await db.flush()
        print(f"[Seed] 管理员账户已创建: {settings.ADMIN_USERNAME}")
    else:
        # 确保密码是最新的（如果配置更改了）
        existing_admin.password_hash = hash_password(settings.ADMIN_PASSWORD)
        db.add(existing_admin)
        await db.flush()
        print(f"[Seed] 管理员账户已更新: {settings.ADMIN_USERNAME}")
