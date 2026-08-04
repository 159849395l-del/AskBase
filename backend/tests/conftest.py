"""pytest 配置文件 — 测试夹具和全局配置"""

import pytest
import os
import sys
import asyncio

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环用于异步测试"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
