"""大模型库服务 — CRUD + API Key 加解密 + 连通性测试 + 默认模型维护"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from fastapi import HTTPException, status
import asyncio
import time

from app.models.llm_model import LLMModel
from app.schemas.llm_model import (
    LLMModelCreate,
    LLMModelUpdate,
    LLMModelItem,
    ModelTestResponse,
)
from app.utils.crypto import encrypt_password, decrypt_password

# base_url 关键字 → provider 标识（用于迁移 .env 配置时自动识别厂商）
_PROVIDER_BY_URL = [
    ("api.deepseek.com", "deepseek"),
    ("volces.com", "volcengine"),
    ("dashscope", "aliyun"),
    ("api.openai.com", "openai"),
    ("moonshot", "moonshot"),
    ("bigmodel.cn", "zhipu"),
    ("localhost:11434", "local"),
]


def _infer_provider(base_url: str) -> str:
    url = (base_url or "").lower()
    for keyword, provider in _PROVIDER_BY_URL:
        if keyword in url:
            return provider
    return "custom"


async def sync_env_model(db: AsyncSession) -> Optional[LLMModelItem]:
    """把 .env 里的 LLM_* 配置同步成一条模型记录（幂等）

    - 只在同 (provider, model_id) 不存在时插入，不覆盖用户后续修改
    - **不设为默认**：is_default 保持 False，未指定模型时仍走 .env 兜底，行为不变
    - 目的：让原本硬编码的模型出现在大模型库里，可被智能体显式选择
    """
    from app.config import settings

    model_id = (settings.LLM_MODEL or "").strip()
    base_url = (settings.LLM_API_BASE or "").strip().rstrip("/")
    if not model_id or not base_url:
        return None

    provider = _infer_provider(base_url)
    existing = (
        await db.execute(
            select(LLMModel).where(
                LLMModel.provider == provider, LLMModel.model_id == model_id
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return None

    m = LLMModel(
        name=f"{model_id}（来自 .env）",
        provider=provider,
        model_id=model_id,
        base_url=base_url,
        api_key_encrypted=encrypt_password(settings.LLM_API_KEY) if settings.LLM_API_KEY else None,
        is_active=True,
        is_vision=False,
        supports_tool_call=False,
        temperature=settings.LLM_TEMPERATURE,
        is_default=False,
    )
    db.add(m)
    await db.flush()
    await db.refresh(m)
    return LLMModelItem.model_validate(m)


async def list_models(db: AsyncSession, only_active: bool = False) -> List[LLMModelItem]:
    """列出模型（按排序 + id）"""
    q = select(LLMModel)
    if only_active:
        q = q.where(LLMModel.is_active == True)  # noqa: E712
    q = q.order_by(LLMModel.sort_order.asc(), LLMModel.id.asc())
    result = await db.execute(q)
    return [LLMModelItem.model_validate(m) for m in result.scalars().all()]


async def get_model(db: AsyncSession, model_id: int) -> LLMModel:
    """取模型 ORM 对象（不存在抛 404）"""
    result = await db.execute(select(LLMModel).where(LLMModel.id == model_id))
    m = result.scalar_one_or_none()
    if m is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="模型不存在")
    return m


async def create_model(db: AsyncSession, body: LLMModelCreate) -> LLMModelItem:
    """创建模型；provider+model_id 唯一校验"""
    await _ensure_unique(db, body.provider, body.model_id, exclude_id=None)

    m = LLMModel(
        name=body.name.strip(),
        provider=body.provider or "custom",
        model_id=body.model_id.strip(),
        base_url=body.base_url.strip().rstrip("/"),
        api_key_encrypted=encrypt_password(body.api_key) if body.api_key else None,
        is_active=body.is_active,
        is_vision=body.is_vision,
        supports_tool_call=body.supports_tool_call,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
        sort_order=body.sort_order,
        is_default=False,  # 是否默认统一走 _apply_default 处理
    )
    db.add(m)
    await db.flush()
    if body.is_default:
        await _apply_default(db, m.id)
    await db.refresh(m)
    return LLMModelItem.model_validate(m)


async def update_model(db: AsyncSession, model_id: int, body: LLMModelUpdate) -> LLMModelItem:
    """更新模型（部分字段）"""
    m = await get_model(db, model_id)
    data = body.model_dump(exclude_unset=True)
    api_key = data.pop("api_key", None)
    is_default = data.pop("is_default", None)

    if "provider" in data or "model_id" in data:
        new_provider = data.get("provider") or m.provider
        new_model_id = data.get("model_id") or m.model_id
        await _ensure_unique(db, new_provider, new_model_id, exclude_id=model_id)

    if "base_url" in data and data["base_url"]:
        data["base_url"] = data["base_url"].strip().rstrip("/")
    if "model_id" in data and data["model_id"]:
        data["model_id"] = data["model_id"].strip()

    for k, v in data.items():
        setattr(m, k, v)

    # 密钥：显式传了非空字符串才更新
    if api_key:
        m.api_key_encrypted = encrypt_password(api_key)

    await db.flush()
    if is_default:
        await _apply_default(db, model_id)
    await db.refresh(m)
    return LLMModelItem.model_validate(m)


async def delete_model(db: AsyncSession, model_id: int) -> None:
    """删除模型；被引用的智能体会自动置空 model_id（由 FK ondelete=SET NULL 处理，此处手动兜底）"""
    m = await get_model(db, model_id)
    from app.models.agent import Agent

    # 手动兜底：把引用该模型的智能体 model_id 置 NULL
    agents = (
        await db.execute(select(Agent).where(Agent.model_id == model_id))
    ).scalars().all()
    for a in agents:
        a.model_id = None
    await db.flush()

    await db.delete(m)
    await db.flush()


async def set_default_model(db: AsyncSession, model_id: int) -> LLMModelItem:
    """设为系统默认模型（同时取消其它默认）"""
    m = await get_model(db, model_id)
    await _apply_default(db, model_id)
    await db.refresh(m)
    return LLMModelItem.model_validate(m)


async def _apply_default(db: AsyncSession, target_id: int) -> None:
    """把 target_id 设为唯一默认模型"""
    result = await db.execute(select(LLMModel))
    for m in result.scalars().all():
        m.is_default = (m.id == target_id)
    await db.flush()


async def _ensure_unique(
    db: AsyncSession, provider: str, model_id: str, exclude_id: Optional[int]
) -> None:
    """provider + model_id 唯一（排除自身）"""
    q = select(LLMModel).where(
        LLMModel.provider == provider, LLMModel.model_id == model_id.strip()
    )
    if exclude_id is not None:
        q = q.where(LLMModel.id != exclude_id)
    existing = (await db.execute(q)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=f"厂商「{provider}」下已存在模型 ID「{model_id}」，请勿重复添加",
        )


# ---------- 连通性测试 ----------


def _test_model_sync(base_url: str, api_key: str, model_id: str) -> ModelTestResponse:
    """同步执行模型连通测试（调用方负责 to_thread 包装）"""
    from openai import OpenAI

    start = time.perf_counter()
    try:
        client = OpenAI(base_url=base_url, api_key=api_key or "sk-test", timeout=30.0)
        resp = client.chat.completions.create(
            model=model_id,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=16,
            stream=False,
        )
        text = (resp.choices[0].message.content or "").strip()
        latency_ms = int((time.perf_counter() - start) * 1000)
        preview = text[:40].replace("\n", " ")
        return ModelTestResponse(
            success=True,
            message=f"连通正常（{latency_ms}ms）" + (f"，回复：{preview}" if preview else ""),
            latency_ms=latency_ms,
        )
    except Exception as e:
        latency_ms = int((time.perf_counter() - start) * 1000)
        detail = str(e).replace("\n", " ")
        if len(detail) > 300:
            detail = detail[:300] + "..."
        return ModelTestResponse(success=False, message=detail, latency_ms=latency_ms)


async def test_model(
    base_url: str, api_key: str, model_id: str
) -> ModelTestResponse:
    """异步包装的模型连通测试"""
    return await asyncio.to_thread(_test_model_sync, base_url, api_key or "", model_id)


async def test_saved_model(db: AsyncSession, model_id: int) -> ModelTestResponse:
    """用已保存的模型配置测试连通（解密密钥）"""
    m = await get_model(db, model_id)
    return await test_model(
        base_url=m.base_url,
        api_key=decrypt_password(m.api_key_encrypted or ""),
        model_id=m.model_id,
    )
