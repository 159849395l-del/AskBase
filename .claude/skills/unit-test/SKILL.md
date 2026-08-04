---
name: unit-test
description: 创建单元测试、执行测试、并生成测试报告（支持 Python 后端 + TypeScript 前端）
---

## 单元测试技能

本技能用于为电商RAG知识库问答系统创建和执行单元测试。项目是前后端分离架构。

### 技术栈

| 端 | 测试框架 | 运行命令 | 测试文件位置 |
|------|---------|---------|-------------|
| 前端 React | Vitest | `npx vitest run` | `frontend/src/**/*.test.{ts,tsx}` |
| 后端 Python | pytest | `python -m pytest backend/tests/ -v` | `backend/tests/test_*.py` |

### 可用命令

| 命令 | 用途 | 目录 |
|------|------|------|
| `npx vitest run` | 运行所有前端测试 | `frontend/` |
| `python -m pytest backend/tests/ -v` | 运行所有后端测试 | `backend/` |

---

## 执行流程

### 步骤 1：确定测试目标

**适合测试的代码优先级**：

| 优先级 | 类型 | 示例 |
|------|------|------|
| 最高 | 纯计算/工具函数 | 文本清洗、文件大小格式化 |
| 高 | 数据转换函数 | RAG 文档格式化、Pydantic schema |
| 中 | API 端点 | FastAPI 路由 |
| 低 | React 组件 | 表单验证、弹窗 |

### 步骤 2：创建测试文件

**Python 后端测试** (`backend/tests/test_xxx.py`)：

```python
import pytest

class TestFormatDocs:
    """格式化检索文档 — 测试套件"""

    def test_正常输入_返回格式化上下文(self):
        """输入: 有效的 Document 列表 → 输出: 格式化字符串+来源列表"""
        pass

    def test_空列表_返回空上下文(self):
        """输入: [] → 输出: ('', [])"""
        pass
```

**TypeScript 前端测试** (`frontend/src/utils/xxx.test.ts`)：

```typescript
import { describe, it, expect } from 'vitest'

describe('formatFileSize — 文件大小格式化', () => {
  it('场景：1024字节 → 输出"1.0 KB"', () => {
    expect(formatFileSize(1024)).toBe('1.0 KB')
  })
  it('边界：0字节 → 输出"0 B"', () => {
    expect(formatFileSize(0)).toBe('0 B')
  })
})
```

### 步骤 3：执行测试

- 前端：`cd frontend && npx vitest run`
- 后端：`cd backend && python -m pytest backend/tests/ -v`

### 步骤 4：生成测试报告

```
========== 单元测试报告 ==========
📁 测试文件：X 个  📝 测试用例：Y 个
✅ 通过：Z  ❌ 失败：W  ⏱️ 耗时：XXXms
==================================
```

---

## 编写测试的原则

- 每个测试只测一个场景，用中文描述
- 覆盖三种情况：**正常**、**边界**（空值、0）、**异常**（非法输入）
- 后端测试用 pytest fixture 管理测试数据
- 测试写完必须立即运行，确认全部通过
