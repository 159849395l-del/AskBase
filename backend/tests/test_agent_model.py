"""测试智能体必须绑定模型 —— 不再有「系统默认」这一说

seam：schema 校验（纯函数）+ 直接调用端点函数 + 临时文件库
"""

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api.agents import create_agent, update_agent
from app.models.agent import Agent
from app.models.llm_model import LLMModel
from app.schemas.agent import AgentCreate, AgentUpdate


def _add(factory, *rows):
    async def _run():
        async with factory() as db:
            for r in rows:
                db.add(r)
            await db.commit()

    asyncio.run(_run())


def _model(model_id=1, name="测试模型", is_active=True):
    return LLMModel(
        id=model_id, name=name, provider="custom", model_id="deepseek-chat",
        base_url="https://api.deepseek.com", is_active=is_active,
    )


def _agent(agent_id=1, model_id=1):
    return Agent(id=agent_id, name="测试智能体", created_by=1, model_id=model_id)


class TestSchemaRequiresModel:
    """创建智能体时模型是必填项"""

    def test_不传模型_被拒绝(self):
        """场景：只给名字 → 校验不通过，不可能造出没有模型的智能体"""
        with pytest.raises(ValidationError):
            AgentCreate(name="没有模型的智能体")

    def test_传模型_通过(self):
        """场景：带上模型 → 正常构造"""
        assert AgentCreate(name="有模型的智能体", model_id=3).model_id == 3


class TestEndpointChecksModel:
    """端点还要确认模型真实可用"""

    def test_模型不存在_拒绝创建(self, usage_db):
        """场景：绑一个不存在的模型 id → 400"""
        async def _call():
            async with usage_db() as db:
                await create_agent(
                    AgentCreate(name="绑定幽灵模型", model_id=999),
                    db=db,
                    admin_user=SimpleNamespace(id=1),
                )

        with pytest.raises(HTTPException) as exc:
            asyncio.run(_call())
        assert exc.value.status_code == 400
        assert "不存在" in exc.value.detail

    def test_模型已停用_拒绝创建(self, usage_db):
        """场景：绑一个已停用的模型 → 400（避免选到跑不通的模型）"""
        _add(usage_db, _model(model_id=2, name="停用的模型", is_active=False))

        async def _call():
            async with usage_db() as db:
                await create_agent(
                    AgentCreate(name="绑定停用模型", model_id=2),
                    db=db,
                    admin_user=SimpleNamespace(id=1),
                )

        with pytest.raises(HTTPException) as exc:
            asyncio.run(_call())
        assert exc.value.status_code == 400
        assert "已停用" in exc.value.detail


class TestUpdateCannotClearModel:
    """更新时不允许把模型清空"""

    def test_显式传null_拒绝(self, usage_db):
        """场景：模型下拉被清空后提交 → 400，而不是退回系统默认"""
        _add(usage_db, _model(), _agent())

        async def _call():
            async with usage_db() as db:
                await update_agent(
                    1, AgentUpdate(model_id=None), db=db,
                    admin_user=SimpleNamespace(id=1),
                )

        with pytest.raises(HTTPException) as exc:
            asyncio.run(_call())
        assert exc.value.status_code == 400
        assert "不支持清空" in exc.value.detail

    def test_不传模型_保持原值不变(self, usage_db):
        """场景：只改名字 → 模型不受影响（局部更新语义不变）"""
        _add(usage_db, _model(), _agent(model_id=1))

        async def _call():
            async with usage_db() as db:
                await update_agent(
                    1, AgentUpdate(name="改了名字"), db=db,
                    admin_user=SimpleNamespace(id=1),
                )
                # 直接调用端点时没有 get_db 依赖的退出提交，需要显式落库
                await db.commit()

        asyncio.run(_call())

        async def _read():
            async with usage_db() as db:
                from sqlalchemy import select

                return (
                    await db.execute(select(Agent).where(Agent.id == 1))
                ).scalar_one()

        agent = asyncio.run(_read())
        assert agent.name == "改了名字"
        assert agent.model_id == 1
