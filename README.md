# 电商 RAG 知识库问答系统

基于 **LangChain** 框架开发的企业级 RAG（检索增强生成）知识库问答系统，面向电商商品信息场景，支持多用户多会话、流式对话、引用溯源。

## 技术栈

| 层级 | 技术 |
|------|------|
| 大语言模型 | DeepSeek API（OpenAI 兼容端点，可换百炼 qwen 等任意兼容服务） |
| 嵌入模型 | 阿里云百炼 text-embedding-v3（OpenAI 兼容端点） |
| RAG 框架 | LangChain + LangChain-Community |
| 后端框架 | FastAPI (Python) |
| 前端框架 | React 18 + TypeScript + Vite |
| UI 组件库 | Ant Design 5 |
| 向量数据库 | ChromaDB |
| 关系数据库 | SQLite |
| 认证 | JWT + bcrypt |

## 功能特性

- 知识库文档上传与管理（支持 TXT/MD/PDF/DOCX/CSV/XLSX）
- 流式 RAG 问答（SSE 实时推送）
- 引用来源展示（知识库片段追溯）
- 多用户多会话管理
- 历史对话持久化与恢复
- 用户注册/登录/修改密码
- 管理员权限隔离（仅 admin 可管理知识库）
- Markdown 渲染（支持表格产品对比）

## 快速启动

### 前置要求

- Python 3.10+
- Node.js 18+
- 阿里云百炼 API Key（[开通地址](https://bailian.console.aliyun.com/)）

### 1. 配置 API Key

编辑 `backend/.env`，填入两个 API Key（LLM 与 Embedding 可来自不同供应商）：

```env
# LLM — DeepSeek（https://platform.deepseek.com 申请）
LLM_API_KEY=sk-your-deepseek-api-key-here
LLM_API_BASE=https://api.deepseek.com
LLM_MODEL=deepseek-chat

# Embedding — 阿里云百炼（https://bailian.console.aliyun.com 申请通用 sk- key）
EMBEDDING_API_KEY=sk-your-dashscope-api-key-here
EMBEDDING_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
EMBEDDING_MODEL=text-embedding-v3
```

如需改用百炼 qwen 做 LLM，把 `LLM_API_BASE` 改为 `https://dashscope.aliyuncs.com/compatible-mode/v1`、`LLM_MODEL` 改为 `qwen-plus` 即可。

### 2. 一键启动 (Windows)

双击运行 `start.bat`，脚本会自动：
1. 创建 Python 虚拟环境并安装依赖
2. 安装前端 npm 依赖
3. 启动后端 (http://localhost:8000) 和前端 (http://localhost:5173)

### 3. 手动启动

**后端：**
```bash
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**前端：**
```bash
cd frontend
npm install
npm run dev
```

### 4. 访问系统

- 前端页面：http://localhost:5173
- API 文档：http://localhost:8000/docs
- 管理员账号：`admin` / `123456`

## 使用指南

1. 用 admin 账号登录 → 进入「知识库管理」→ 上传电商商品文档
2. 等待文档处理完成（状态变为"已索引"）
3. 进入「我的会话」→ 新建会话 → 开始提问
4. 回答会引用知识库来源，点击可查看原文片段
5. 普通用户注册后只能进行问答，无法访问知识库管理

## 项目结构

```
├── backend/            # FastAPI 后端
│   ├── app/
│   │   ├── api/        # API 路由
│   │   ├── models/     # ORM 模型
│   │   ├── schemas/    # Pydantic 模型
│   │   ├── services/   # 业务逻辑
│   │   ├── rag/        # RAG 管道组件
│   │   └── core/       # 安全与依赖
│   └── data/           # 运行时数据
├── frontend/           # React 前端
│   └── src/
│       ├── pages/      # 页面组件
│       ├── components/ # 可复用组件
│       ├── store/      # Zustand 状态
│       └── api/        # API 客户端
├── data/products/      # 示例电商商品数据
└── start.bat           # 一键启动脚本
```

## API 概览

| 端点 | 方法 | 说明 | 权限 |
|------|------|------|------|
| `/api/auth/register` | POST | 用户注册 | 公开 |
| `/api/auth/login` | POST | 用户登录 | 公开 |
| `/api/auth/me` | GET | 当前用户信息 | 登录 |
| `/api/auth/change-password` | PUT | 修改密码 | 登录 |
| `/api/conversations` | GET/POST | 会话列表/新建 | 登录 |
| `/api/conversations/{id}` | GET/DELETE/PATCH | 会话操作 | 所有者 |
| `/api/conversations/{id}/messages` | POST | SSE 流式问答 | 所有者 |
| `/api/kb/documents` | GET/POST | 文档列表/上传 | admin |
| `/api/kb/documents/{id}` | GET/DELETE | 文档详情/删除 | admin |
| `/api/kb/stats` | GET | KB 统计 | admin |
| `/api/kb/reindex` | POST | 重建索引 | admin |
| `/api/health` | GET | 健康检查 | 公开 |
