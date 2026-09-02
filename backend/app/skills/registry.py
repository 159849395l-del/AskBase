"""Skill 注册表 — 内置工具定义 + 数据库种子

启动时调用 `ensure_builtin_skills(db)`，把内置工具写入 skills 表（已存在则跳过）。
执行时调用 `get_handler(name)` 拿到处理函数。
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Callable, Optional

from app.models.skill import Skill
from app.skills import handlers


# 内置工具定义：name 与 handlers.HANDLERS 的 key 一致
BUILTIN_SKILLS = [
    {
        "name": "web_search",
        "title": "联网搜索互联网最新信息",
        "description": "根据关键词搜索互联网上的最新信息，返回摘要与来源链接。适合回答时效性问题、新闻、实时数据。参数：query（搜索关键词，必填）。",
        "icon": "🌐",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_current_time",
        "title": "获取当前时间",
        "description": "获取当前日期和时间。当用户问及今天、现在、当前时间时使用。参数：format（可选，strftime 格式）。",
        "icon": "🕐",
        "input_schema": {
            "type": "object",
            "properties": {
                "format": {"type": "string", "description": "时间格式，默认 %Y-%m-%d %H:%M:%S"},
            },
        },
    },
    {
        "name": "calculator",
        "title": "数学计算",
        "description": "计算数学表达式，支持加减乘除、取模、幂运算和括号。参数：expression（表达式字符串，必填）。",
        "icon": "🧮",
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "数学表达式，如 (12+8)*3/2"},
            },
            "required": ["expression"],
        },
    },
]


def get_handler(name: str) -> Optional[Callable]:
    """按工具名取处理函数（只返回内置 handler；自定义 skill 暂无可执行实现）"""
    return handlers.HANDLERS.get(name)


async def ensure_builtin_skills(db: AsyncSession) -> int:
    """把内置工具写入数据库（已存在同名则跳过）；返回新增数量"""
    import json

    created = 0
    for spec in BUILTIN_SKILLS:
        existing = (
            await db.execute(select(Skill).where(Skill.name == spec["name"]))
        ).scalar_one_or_none()
        if existing is not None:
            continue
        db.add(
            Skill(
                name=spec["name"],
                title=spec["title"],
                description=spec["description"],
                icon=spec["icon"],
                handler=spec["name"],
                input_schema=json.dumps(spec["input_schema"], ensure_ascii=False),
                is_active=True,
                is_builtin=True,
                is_dangerous=False,
            )
        )
        created += 1
    if created:
        await db.flush()
    return created
