"""LLM 客户端工厂 — 优先用大模型库里的配置，取不到则回退 .env

调用优先级：
1. 显式传入的 model_id 对应的模型
2. 大模型库中 is_default=True 且启用的模型
3. .env 里的 LLM_* 配置（兜底，保证老用户不中断）
"""

from langchain_openai import ChatOpenAI
from sqlalchemy import select
from typing import Optional
import asyncio

from app.config import settings
from app.utils.crypto import decrypt_password


def build_chat_llm(
    base_url: str,
    api_key: str,
    model_id: str,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    streaming: bool = True,
) -> ChatOpenAI:
    """按显式配置构造 ChatOpenAI（纯函数，不查库）"""
    kwargs = {
        "model": model_id,
        "api_key": api_key or "sk-placeholder",
        "base_url": base_url,
        "temperature": settings.LLM_TEMPERATURE if temperature is None else temperature,
        "streaming": streaming,
    }
    if max_tokens:
        kwargs["max_tokens"] = max_tokens
    return ChatOpenAI(**kwargs)


def build_env_llm(streaming: bool = True) -> ChatOpenAI:
    """用 .env 配置构造 ChatOpenAI（兜底路径）"""
    return ChatOpenAI(
        model=settings.LLM_MODEL,
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_API_BASE,
        temperature=settings.LLM_TEMPERATURE,
        streaming=streaming,
    )


def _build_from_orm(model, streaming: bool = True) -> ChatOpenAI:
    """从 ORM 对象构造 ChatOpenAI（解密密钥）"""
    api_key = decrypt_password(model.api_key_encrypted or "")
    return build_chat_llm(
        base_url=model.base_url,
        api_key=api_key,
        model_id=model.model_id,
        temperature=model.temperature,
        max_tokens=model.max_tokens,
        streaming=streaming,
    )


async def resolve_llm(model_id: Optional[int] = None, streaming: bool = True) -> ChatOpenAI:
    """解析 LLM 客户端：model_id → 库内默认 → .env 兜底

    数据库相关异常一律降级到 .env，不让配置问题中断问答。
    """
    if model_id is None:
        # 未指定时先找库内默认模型
        try:
            resolved = await _find_default_model_id()
        except Exception:
            resolved = None
        model_id = resolved

    if model_id is not None:
        try:
            model = await _load_model(model_id)
            if model is not None:
                return _build_from_orm(model, streaming=streaming)
        except Exception as e:
            print(f"[llm_factory] 加载模型 {model_id} 失败，回退 .env 配置：{e}")

    return build_env_llm(streaming=streaming)


async def _find_default_model_id() -> Optional[int]:
    """查库里 is_default 且启用的模型 id（不存在返 None）"""
    from app.database import async_session_factory
    from app.models.llm_model import LLMModel

    async with async_session_factory() as db:
        row = (
            await db.execute(
                select(LLMModel.id)
                .where(LLMModel.is_default == True, LLMModel.is_active == True)  # noqa: E712
                .limit(1)
            )
        ).scalar_one_or_none()
    return row


async def _load_model(model_id: int):
    """按 id 加载模型 ORM（不存在返 None）"""
    from app.database import async_session_factory
    from app.models.llm_model import LLMModel

    async with async_session_factory() as db:
        return (
            await db.execute(select(LLMModel).where(LLMModel.id == model_id))
        ).scalar_one_or_none()


def resolve_llm_sync(model_id: Optional[int] = None, streaming: bool = True) -> ChatOpenAI:
    """同步包装：在非 async 上下文里解析 LLM（内部新建事件循环）"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is not None and loop.is_running():
        # 已在事件循环中：无法同步等待，直接回退 .env
        return build_env_llm(streaming=streaming)
    return asyncio.run(resolve_llm(model_id, streaming=streaming))
