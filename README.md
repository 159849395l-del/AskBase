# 知识库问答系统

基于 **LangChain** 框架开发的知识库问答系统，支持**文档型知识库**（RAG 向量检索）与**数据库型知识库**（Text-to-SQL 实时查询）双链路问答，内置智能体（Agent）与网页爬虫采集，多用户多会话、流式对话、引用溯源。

## 技术栈

| 层级 | 技术 |
|------|------|
| 大语言模型 | DeepSeek API（OpenAI 兼容端点，可换任意兼容服务） |
| 嵌入模型 | 阿里云百炼 text-embedding-v3（OpenAI 兼容端点） |
| RAG 框架 | LangChain + LangChain-Community |
| 后端框架 | FastAPI (Python) |
| 前端框架 | React 18 + TypeScript + Vite |
| UI 组件库 | Ant Design 5 |
| 向量数据库 | ChromaDB |
| 关系数据库 | SQLite（系统库）+ MySQL（爬虫/业务库） |
| 认证 | JWT + bcrypt |

## 功能特性

- **三种知识库类型**：文档集（文档+问答）、数据库型（连接 MySQL 表 + 表字段描述 + 知识点）、混合挂载
- **数据库 Text-to-SQL 问答**：用户自然语言 → LLM 生成只读 SQL → 执行 → 基于真实数据回答
- **智能体（Agent）**：挂载多个知识库，自定义 system prompt（表名/字段规则/输出格式/降级话术）
- **网页爬虫采集**：多阶段智能爬虫（规划→发现→抓取→LLM 提取→校验→聚合），自动翻页、去重、落库
- **数据源管理**：MySQL 连接管理（密码加密存储）
- **文档 RAG 问答**：TXT/MD/PDF/DOCX 上传索引，流式 SSE 回答 + 引用来源展示
- **管理员后台**：知识库/智能体/数据源/爬虫/用户管理
- **用户管理**：创建用户、启用/禁用、重置密码、角色分配
- 多用户多会话管理、历史对话持久化、Markdown 渲染

## 快速启动

### 前置要求

- Python 3.10+
- Node.js 18+
- MySQL 8（可选，用于数据库型知识库与爬虫）
- LLM / Embedding API Key

### 1. 配置 API Key

编辑 `backend/.env`：

```env
# LLM
LLM_API_KEY=sk-your-llm-api-key
LLM_API_BASE=https://api.deepseek.com
LLM_MODEL=deepseek-chat

# Embedding
EMBEDDING_API_KEY=sk-your-dashscope-api-key
EMBEDDING_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
EMBEDDING_MODEL=text-embedding-v3
```

### 2. 一键启动 (Windows)

双击运行 `start.bat`（自动装依赖并启动前后端）。

### 3. 手动启动

**后端：**
```bash
cd backend
python -m venv venv
venv\Scripts\activate
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

1. **文档型知识库**：登录 admin → 知识库管理 → 新建文档知识库 → 上传文档 → 等待索引
2. **数据库型知识库**：数据源管理 → 配置 MySQL → 知识库绑定数据源与库名 → 同步表结构（字段注释自动预填）→ 勾选"必选"表
3. **智能体**：新建智能体 → 挂载知识库 → 写 system prompt（表名、字段规则、输出格式）
4. **爬虫采集**：爬虫管理 → 新建任务（标题/描述写清来源与提取字段）→ 结果自动落库（school_articles）
5. **问答**：我的会话 → 选择智能体 → 提问（答案带引用来源 / SQL 展示）

## 项目结构

```
├── backend/
│   ├── app/
│   │   ├── api/            # API 路由（认证/会话/知识库/智能体/数据源/用户管理）
│   │   ├── crawler/        # 多智能体爬虫引擎（planner/discovery/crawler/extractor/verifier）
│   │   ├── models/         # ORM 模型
│   │   ├── schemas/        # Pydantic 模型
│   │   ├── services/       # 业务逻辑
│   │   ├── rag/            # RAG 管道 + Text-to-SQL
│   │   └── core/           # 安全与依赖
│   └── data/               # SQLite 运行时数据
├── frontend/               # React 前端
│   └── src/
│       ├── pages/          # 页面组件（含用户管理/爬虫管理等）
│       ├── components/     # 可复用组件
│       ├── store/          # Zustand 状态
│       └── api/            # API 客户端
└── start.bat               # 一键启动脚本
```

## API 概览

| 端点 | 说明 | 权限 |
|------|------|------|
| `/api/auth/*` | 注册/登录/改密 | 公开/登录 |
| `/api/conversations/*` | 会话与 SSE 问答 | 登录 |
| `/api/kb/*` | 文档知识库管理 | admin |
| `/api/data-sources` | MySQL 数据源管理 | admin |
| `/api/knowledge-bases` | 知识库（文档/数据库）管理 | admin |
| `/api/agents` | 智能体管理 | admin |
| `/api/admin/users` | 用户管理（创建/禁用/重置密码/删除） | admin |
| `/api/crawler/tasks` | 爬虫任务管理 | admin |
| `/api/health` | 健康检查 | 公开 |
