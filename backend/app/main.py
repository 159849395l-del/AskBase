"""
FastAPI 应用入口 — 注册路由、中间件、生命周期事件
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.config import settings
from app.database import init_db
from app.api.auth import router as auth_router
from app.api.conversations import router as conversations_router
from app.api.chat import router as chat_router
from app.api.kb import router as kb_router
from app.api.system import router as system_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期 — 启动时初始化数据库和种子数据"""
    from app.database import async_session_factory
    from app.services.auth_service import seed_admin

    print(f"[Startup] 启动 {settings.APP_NAME} v{settings.APP_VERSION}")

    # 初始化数据库表
    await init_db()

    # 种子管理员账户
    async with async_session_factory() as session:
        await seed_admin(session)
        await session.commit()

    print(f"[Startup] 服务已就绪，LLM 模型: {settings.LLM_MODEL}")
    yield
    print("[Shutdown] 服务关闭")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="基于 LangChain 的电商 RAG 企业级知识库问答系统",
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth_router)
app.include_router(conversations_router)
app.include_router(chat_router)
app.include_router(kb_router)
app.include_router(system_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
