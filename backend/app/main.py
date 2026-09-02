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
from app.api.agents import router as agents_router
from app.api.data_sources import router as data_sources_router
from app.api.knowledge_bases import router as knowledge_bases_router
from app.api.kb_tables import router as kb_tables_router
from app.crawler.api.tasks import router as crawler_tasks_router
from app.crawler.api.results import router as crawler_results_router
from app.crawler.api.schedule import router as crawler_schedule_router
from app.api.admin_users import router as admin_users_router
from app.api.models import router as models_router
from app.api.skills import router as skills_router
from app.api.mcp_servers import router as mcp_servers_router

# 新表依赖：确保 ORM 注册表包含 llm_models / skills / mcp_servers / agent_tools
from app.models.llm_model import LLMModel  # noqa: F401
from app.models.skill import Skill  # noqa: F401
from app.models.mcp_server import MCPServer  # noqa: F401
from app.models.agent import AgentTool  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期 — 启动时初始化数据库和种子数据"""
    from app.database import async_session_factory, engine
    from app.services.auth_service import seed_admin
    from sqlalchemy import text

    print(f"[Startup] 启动 {settings.APP_NAME} v{settings.APP_VERSION}")

    # 初始化数据库表（新模型首次启动自动建表）
    await init_db()

    # 兼容迁移：给已有 conversations 表加 agent_id 列（SQLite 重复 ADD COLUMN 会报错，吞掉）
    async with engine.begin() as conn:
        try:
            await conn.execute(text(
                "ALTER TABLE conversations ADD COLUMN agent_id INTEGER REFERENCES agents(id) ON DELETE SET NULL"
            ))
            print("[Startup] 已给 conversations 表添加 agent_id 列")
        except Exception as e:
            # 已存在该列（duplicate column name）等情况都跳过
            if "duplicate column" not in str(e).lower():
                raise

        # 智能体名称唯一索引（已有重复数据时创建会失败，需先人工清理）
        try:
            await conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_agents_name ON agents (name)"))
            print("[Startup] 已创建智能体名称唯一索引 uq_agents_name")
        except Exception as e:
            print(f"[Startup] 警告：创建智能体名称唯一索引失败：{e}")

        # 兼容迁移：agents 表加 is_hidden 列（对用户隐藏开关）
        try:
            await conn.execute(text("ALTER TABLE agents ADD COLUMN is_hidden BOOLEAN NOT NULL DEFAULT 0"))
            print("[Startup] 已给 agents 表添加 is_hidden 列")
        except Exception as e:
            if "duplicate column" not in str(e).lower():
                raise

        # 兼容迁移：knowledge_documents 表加 kb_id 列（归属知识库；历史数据保持 NULL 待迁移）
        try:
            await conn.execute(text(
                "ALTER TABLE knowledge_documents ADD COLUMN kb_id INTEGER REFERENCES knowledge_bases(id)"
            ))
            print("[Startup] 已给 knowledge_documents 表添加 kb_id 列")
        except Exception as e:
            if "duplicate column" not in str(e).lower():
                raise

        # 兼容迁移：agents 表加 model_id 列（绑定大模型，NULL=系统默认）
        try:
            await conn.execute(text(
                "ALTER TABLE agents ADD COLUMN model_id INTEGER REFERENCES llm_models(id) ON DELETE SET NULL"
            ))
            print("[Startup] 已给 agents 表添加 model_id 列")
        except Exception as e:
            if "duplicate column" not in str(e).lower():
                raise

    # 种子管理员账户 + 内置 Skill
    async with async_session_factory() as session:
        await seed_admin(session)
        try:
            from app.skills.registry import ensure_builtin_skills

            created = await ensure_builtin_skills(session)
            if created:
                print(f"[Startup] 已写入 {created} 个内置 Skill")
        except Exception as e:
            print(f"[Startup] 警告：内置 Skill 初始化失败：{e}")

        # 把 .env 里的 LLM 配置同步成一条可选模型（幂等；不设为默认，
        # 未指定模型时仍走 .env 兜底，老行为完全不变）
        try:
            from app.services.llm_model_service import sync_env_model

            synced = await sync_env_model(session)
            if synced:
                print(f"[Startup] 已同步 .env 模型到模型库：{synced.name}（默认仍由 .env 兜底）")
        except Exception as e:
            print(f"[Startup] 警告：.env 模型同步失败：{e}")

        await session.commit()

    # 启动爬虫定时调度器（常驻后台循环；服务关闭时随事件循环结束）
    scheduler_task = None
    try:
        import asyncio as _asyncio

        from app.crawler.scheduler import scheduler_loop

        scheduler_task = _asyncio.create_task(scheduler_loop())
        print("[Startup] 爬虫定时调度器已启动（每 20 秒扫描）")
    except Exception as e:
        print(f"[Startup] 警告：爬虫定时调度器启动失败：{e}")

    print(f"[Startup] 服务已就绪，LLM 模型: {settings.LLM_MODEL}")
    yield
    if scheduler_task is not None:
        scheduler_task.cancel()
        print("[Shutdown] 爬虫定时调度器已停止")
    print("[Shutdown] 服务关闭")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="基于 LangChain 的知识库问答系统（文档 RAG + 数据库 Text-to-SQL）",
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
app.include_router(agents_router)
app.include_router(data_sources_router)
app.include_router(knowledge_bases_router)
app.include_router(kb_tables_router)
app.include_router(crawler_tasks_router)
app.include_router(crawler_results_router)
app.include_router(crawler_schedule_router)
app.include_router(admin_users_router)
app.include_router(models_router)
app.include_router(skills_router)
app.include_router(mcp_servers_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
