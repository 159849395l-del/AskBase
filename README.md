# 知识库问答系统

> ⚠️ **声明**：本项目为作者**个人练手使用**的示例项目，仅用于学习与技术验证，不保证生产可用性，请勿直接用于正式业务环境。

基于 **LangChain** 框架开发的知识库问答系统。支持**文档型知识库**（RAG 向量检索）与**数据库型知识库**（Text-to-SQL 实时查询）双链路问答，内置**大模型库管理**（多模型配置）、**AI 智能工具**（内置技能 + MCP 扩展）与**多阶段网页爬虫**，多用户多会话、流式对话、引用溯源与 SQL 语句展示。

## 技术栈

| 层级 | 技术 |
|------|------|
| 大语言模型 | DeepSeek / 百炼等任意 OpenAI 兼容端点（支持大模型库多模型配置与按需切换） |
| 嵌入模型 | 阿里云百炼 text-embedding-v3（OpenAI 兼容端点） |
| RAG 框架 | LangChain + LangChain-Community |
| 检索增强 | Chroma 向量 + BM25 混合检索（RRF 融合）、重排（BM25 / 百炼 gte-rerank）、上下文压缩 |
| 后端框架 | FastAPI (Python) |
| 前端框架 | React 18 + TypeScript + Vite |
| UI 组件库 | Ant Design 5 |
| 向量数据库 | ChromaDB |
| 关系数据库 | SQLite（系统库）+ MySQL（爬虫/业务库） |
| 认证 | JWT + bcrypt |

## 功能特性

- **三种知识库类型**：文档集（文档+问答）、数据库型（连接 MySQL 表 + 表字段描述 + 知识点）、混合挂载
- **数据库 Text-to-SQL 问答**：用户自然语言 → LLM 生成只读 SQL → 执行 → 基于真实数据回答（表结构双重告知：知识库自动拉取字段注释 + 智能体提示词补充业务规则）
- **大模型库管理**：系统内置多模型配置（默认模型、启停、按智能体指定），支持 DeepSeek / 百炼等 OpenAI 兼容服务混用
- **AI 智能工具（内置技能）**：联网搜索（Exa → 百度 → Bing 三级回退）、知识库检索、数学计算、获取当前时间等，智能体可挂载任意组合，回答时自动调用
- **对话三路检索**：文档知识库向量检索 + 数据库知识点向量检索 + （挂载 B 类知识库时）Text-to-SQL 查实时库，三路结果合并为参考文档
- **智能体（Agent）**：挂载多个知识库与工具，自定义 system prompt（表名/字段规则/输出格式/降级话术）
- **网页爬虫采集**：多阶段智能爬虫（规划→发现→抓取→LLM 提取→校验→聚合），支持**定时调度**、URL 规范化去重、列表页自动轮询刷新
- **数据源管理**：MySQL 连接管理（密码加密存储）
- **文档 RAG 问答**：TXT/MD/PDF/DOCX 上传索引，流式 SSE 回答 + 引用来源折叠展示（文档片段 / FAQ / SQL 语句）
- **管理员后台**：知识库/智能体/大模型/工具/数据源/爬虫/用户管理
- **用户管理**：创建用户、启用/禁用、重置密码、角色分配
- 多用户多会话管理、历史对话持久化、Markdown 渲染、上下文压缩

## 会话问答链路

```
用户提问
  ├─ 路 1  文档型知识库（文档 / 问答） → 向量 + BM25 混合检索 TopK
  ├─ 路 2  数据库型知识库（知识点 / FAQ）→ 向量检索 TopK
  ├─ 路 3  挂载了 B 类数据库知识库时 → LLM 依据表结构生成只读 SQL → 执行真实查询
  └─ 智能体挂载了工具时 → 时效类问题自动调用（联网搜索 / 计算等）
              ↓
  三路结果合并为【参考文档】→ 按智能体提示词格式输出
  前端展示答案 + "最匹配的 N 个来源"（SQL 语句 / 文档片段 / 引用）
```

> 约束：一个智能体最多挂载 **1 个数据库型（B 类）知识库**（避免 SQL 目标库不明确），文档型（A 类）不限数量。

## 内置技能与外部服务

### 内置技能（已随仓库提交，开箱即用）

智能体在编辑页勾选技能即可启用，问答时遇到对应场景自动调用：

| 技能 | 触发场景 | 说明 |
|------|----------|------|
| 联网搜索 | 价格/新闻/实时数据/最新动态 | 答案级搜索（Exa）优先，逐级回退百度 → Bing |
| 数学计算 | 四则/科学计算 | 本地执行，无需外部服务 |
| 获取当前时间 | 时间/日期类问题 | 本地执行 |
| 知识库检索 | 需要精确引用时 | 限定在智能体挂载的知识库范围内检索 |

新增技能：在 `backend/app/skills/handlers.py` 实现逻辑 → `registry.py` 注册 → 重启后端，界面即可为智能体勾选。

### 联网搜索的 Key 配置

- **Exa（推荐）**：在 https://exa.ai 注册 → Dashboard → API Keys 生成，填入 `backend/.env`：
  ```env
  EXA_API_KEY=你的-exa-key
  ```
  填了之后搜索优先返回 Exa 整理好的综合答案（质量最高）。
- **不填也可以**：自动回退到 百度 → Bing 网页搜索，无需任何 key。

### MCP 服务（进度说明）

后端已支持把 MCP 服务的工具挂载给智能体调用（工具名自动加 `mcp<服务id>_` 前缀避免跨服务重名，失效引用自动跳过）。但**管理界面目前只读展示 MCP 服务与工具列表，尚未提供"新增 MCP 服务"的界面入口**。

如需接入新的 MCP 服务，当前需要直接向数据库 `mcp_servers` 表注册一条配置：`name` + `transport`（`stdio`：填 `command`/`args`/`env`；`sse`：填 `url`），回到 AI 工具页点"刷新"拉取工具清单，即可在智能体上勾选使用。后续版本会补管理界面入口。

## 近期主要更新

- **大模型库模块**：管理多套 LLM 配置，智能体/会话可按需选模型；`.env` 中的模型自动同步入库作为兜底
- **AI 智能工具（内置技能）**：Web 搜索改 Exa Answer 优先（质量差时回退百度/Bing），修复工具参数解析 bug（LangChain tool_calls 结构与 OpenAI 原始格式不同导致带参工具恒空参）
- **技能挂载修复**：挂工具的智能体在知识库检不到结果时不再短路（原逻辑直接跳过 LLM/工具），新增带工具专用的放宽规则
- **爬虫定时调度**：后台调度器按 `run_time` + `interval_days` 周期触发任务（此前只有 CRUD，配置后从不执行）；修复 MySQL TIME 列被 ORM 读成 timedelta 导致的解析失败
- **URL 去重增强**：新增 canonical_url 归一化（去跟踪参数/协议统一/query 排序），修复同文因 URL 变体重复提取的问题
- **上下文压缩**：长会话自动压缩历史，控制 token 消耗
- **检索与问答**：BM25 混合检索（jieba 分词）、重排器、查询改写、缓存开关
- **启动脚本重构**：依赖指纹自动重装、端口健康检查、清理 uvicorn `--reload` 残留的孤儿进程（此前占住 8000 导致起不来）、`init_all.py` 一键建库
- **接口对齐**：前端 `interval_days` 驼峰/下划线不一致导致的定时间隔失效等修复

> 以上为仓库当前 commit 对应内容，详细的逐条修复记录见 git 提交历史。

## 快速启动

### 前置要求

- Python 3.11（推荐版本，依赖已按 3.11 锁定）
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

# 爬虫 MySQL（数据库型知识库与爬虫任务；不配则爬虫/库表功能不可用）
CRAWLER_DB_HOST=127.0.0.1
CRAWLER_DB_PORT=3306
CRAWLER_DB_USER=root
CRAWLER_DB_PASSWORD=change-me
CRAWLER_DB_NAME=ai_crawl

# 联网搜索（可选）：去 https://exa.ai 注册拿 key；不填自动回退百度/Bing
EXA_API_KEY=
```

### 2. 一键启动 (Windows)

双击运行 `start.bat`，脚本会依次完成：检查 Python/Node → 建 venv 并装依赖 → 装 npm 包 →
清理上次残留进程 → 初始化数据库（建表 + 建管理员）→ 启动前后端并等端口就绪。

```bat
start.bat              :: 正常启动
start.bat --reinstall  :: 强制重装 Python 依赖（改过 requirements.txt 时用）
stop.bat               :: 停止前后端，释放 8000 / 5175
```

依赖是否重装由 `backend/venv/deps.md5` 里的 requirements.txt 指纹决定，内容变了会自动重装。

### 3. 手动启动

**后端：**
```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
venv\Scripts\python.exe scripts\init_all.py   # 建表 + 建管理员账号
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**前端：**
```bash
cd frontend
npm install
npm run dev
```

### 4. 访问系统

- 前端页面：http://localhost:5175
- API 文档：http://localhost:8000/docs
- 管理员账号：`admin` / `123456`

## 使用指南

1. **文档型知识库**：登录 admin → 知识库管理 → 新建文档知识库 → 上传文档 → 等待索引
2. **数据库型知识库**：数据源管理 → 配置 MySQL → 知识库绑定数据源与库名 → 同步表结构（字段注释自动预填）→ 勾选"必选"表
3. **大模型库**：大模型库页新增模型配置（选默认模型）；如已在 `.env` 配好 DeepSeek 等，启动时会自动同步入库
4. **智能体**：新建智能体 → 挂载知识库（0/1 个数据库型 + 多个文档型）→ 勾选工具（联网搜索等）→ 写 system prompt（表名、字段规则、输出格式）
5. **爬虫采集**：爬虫管理 → 新建任务（标题/描述写清来源与提取字段）→ 结果自动落库；可设置定时调度按天自动跑
6. **问答**：我的会话 → 选择智能体 → 提问（答案带引用来源 / SQL 展示；时效性问题自动触发联网搜索）

## 项目结构

```
├── backend/
│   ├── app/
│   │   ├── api/            # API 路由（认证/会话/知识库/智能体/大模型/工具/数据源/爬虫）
│   │   ├── crawler/        # 多智能体爬虫引擎 + 定时调度器（planner/discovery/crawler/extractor/verifier）
│   │   ├── skills/         # 内置工具技能（handlers 实现 / registry 注册 / executor 执行循环）
│   │   ├── rag/            # RAG 管道（检索/混合检索/重排/上下文压缩）+ Text-to-SQL
│   │   ├── models/         # ORM 模型
│   │   ├── schemas/        # Pydantic 模型
│   │   ├── services/       # 业务逻辑
│   │   └── core/           # 安全与依赖
│   └── data/               # SQLite 运行时数据
├── frontend/               # React 前端
│   └── src/
│       ├── pages/          # 页面组件（含用户管理/爬虫/大模型库/AI工具等）
│       ├── components/     # 可复用组件
│       ├── store/          # Zustand 状态
│       └── api/            # API 客户端
├── start.bat               # 一键启动（含依赖自检、清残留进程、建库、健康检查）
├── stop.bat                # 停止前后端（清理逻辑已内联，不再需要 ps1 文件）
└── backend/scripts/
    └── init_all.py         # 建表 + 初始化管理员账号（可重复执行）
```

## API 概览

| 端点 | 说明 | 权限 |
|------|------|------|
| `/api/auth/*` | 注册/登录/改密 | 公开/登录 |
| `/api/conversations/*` | 会话与 SSE 问答 | 登录 |
| `/api/kb/*` | 文档知识库管理 | admin |
| `/api/data-sources` | MySQL 数据源管理 | admin |
| `/api/knowledge-bases` | 知识库（文档/数据库）管理 | admin |
| `/api/llm-models` | 大模型库管理 | admin |
| `/api/skills` | 内置工具（技能）管理 | admin |
| `/api/mcp-servers` | MCP 服务管理 | admin |
| `/api/agents` | 智能体管理 | admin |
| `/api/admin/users` | 用户管理（创建/禁用/重置密码/删除） | admin |
| `/api/crawler/tasks` | 爬虫任务管理 | admin |
| `/api/health` | 健康检查 | 公开 |

## 安全与部署须知

本项目为练手示例，**默认配置仅适用于本地开发**，部署到任何可公开访问的环境前务必修改：

- 系统管理员默认账号：`admin` / `123456`（见 `backend/app/config.py`、`backend/app/services/auth_service.py`）
- 爬虫 MySQL 连接不再内置密码，需在 `backend/.env` 配置 `CRAWLER_DB_PASSWORD`（见 `backend/app/crawler/config.py`）

修改方式（推荐用环境变量覆盖，不要直接改源码）：

```env
# backend/.env
ADMIN_PASSWORD=改成强密码
JWT_SECRET=改成随机长字符串
CRAWLER_DB_PASSWORD=改成你的数据库密码
```

其他建议：

- **切勿提交 `backend/.env`**：该文件含真实密钥，已被 `.gitignore` 忽略；如误提交到公开仓库，请立即轮换对应密钥，因为公开历史无法彻底抹除。
- 建议在 GitHub 仓库 **Settings → Security** 开启 **Secret scanning** 与 **Push protection**，防止未来误推密钥。
- 绑定 MySQL 等知识库数据源时，请使用**只读账号**，降低 Text-to-SQL 执行风险。
