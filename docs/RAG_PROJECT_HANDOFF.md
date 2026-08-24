# RAG 项目交接文档（供接手开发快速上手）

> 项目路径：`D:\claude_test\LangChainRAG项目`
> 文档时间：2026-08-21
> 本文档写给接手的开发者/AI，重点是**了解现状、理解当前正在解决的问题（智能体化改造）、快速定位代码**。

---

## 1. 项目简介

基于 **LangChain + ChromaDB** 的企业级 RAG（检索增强生成）知识库问答系统。
- 知识来源有两条途径：**① 管理员上传文档**（TXT/MD/PDF/DOCX/CSV/XLSX）；**② 外部爬虫（ai_crawl 项目）爬取结果**（通过桥接脚本灌入同一个向量库）
- 支持多用户、管理员/普通用户角色隔离、SSE 流式问答、引用溯源
- 正在进行一次重大改造：**把"普通会话"升级为"专属智能体"**（见第 8 节，当前工作重点）

## 2. 技术栈

| 层 | 技术 |
|---|---|
| LLM | DeepSeek（OpenAI 兼容端点 `https://api.deepseek.com`，模型 `deepseek-chat`） |
| Embedding | 阿里云百炼 `text-embedding-v3`（`https://dashscope.aliyuncs.com/compatible-mode/v1`） |
| RAG 框架 | LangChain + LangChain-Community（rank_bm25 做 BM25 混合检索） |
| 后端 | FastAPI（Python 3.10+，异步 SQLAlchemy 2.0） |
| 向量库 | ChromaDB（本地持久化 `./data/chromadb`，collection 名 `ecommerce_kb`） |
| 关系库 | SQLite（`./data/app.db`，async + aiosqlite，WAL 模式） |
| 前端 | React 18 + TypeScript + Vite 6 + Ant Design 5 + Zustand |
| 认证 | JWT + bcrypt（admin/user 角色） |

**运行端口**：后端 `8000`，前端 `5175`（注意：前端原为 5173，与 ai_crawl 冲突后改为 5175，`vite.config.ts` / `backend/.env` CORS / `start.bat` 三处一致）。

## 3. 快速启动

```bash
# 后端（须在 backend 目录，加载 backend/.env）
cd "D:\claude_test\LangChainRAG项目\backend"
venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 前端
cd "D:\claude_test\LangChainRAG项目\frontend"
npm run dev   # http://localhost:5175
```

- 管理员账号：`admin / 123456`（启动时自动种子创建）
- 首次启动自动建表（`Base.metadata.create_all`）+ 兼容迁移（见 8.2 的 ALTER TABLE 说明）
- 数据库/向量库位于 `backend/data/`（app.db、chromadb/、uploads/）

## 4. 目录结构

```
backend/
├── app/
│   ├── main.py            # 入口：CORS、路由注册、lifespan（建表+迁移+种子admin）
│   ├── config.py          # Pydantic Settings，全部可被 backend/.env 覆盖
│   ├── database.py        # async engine / session / init_db
│   ├── api/
│   │   ├── auth.py        # 注册/登录/改密（OAuth2 表单登录，不是 JSON）
│   │   ├── conversations.py  # 会话 CRUD（支持 agent_id 创建）
│   │   ├── chat.py        # SSE 流式问答（核心，见 7.3）
│   │   ├── kb.py          # 知识文档 CRUD/上传/统计/检索调试
│   │   ├── agents.py      # ★新增：智能体 CRUD + /test 预览端点
│   │   └── system.py      # 健康检查、品类列表
│   ├── models/            # SQLAlchemy：user/conversation/message/knowledge_document/agent(新)
│   ├── schemas/           # Pydantic：对应模型 + agent.py(新)
│   ├── services/          # auth/conversation/kb/rag_service（摄入与重建）
│   ├── rag/               # RAG 管道（重点目录，见 7）
│   └── core/              # security(JWT) / dependencies(get_current_user, get_admin_user)
├── scripts/
│   ├── ingest_from_aicrawl.py  # ★ai_crawl → ChromaDB 桥接脚本（可幂等重跑）
│   └── query_scope.py          # kb_doc_id 作用域检索调试
├── data/                  # 运行时数据（app.db / chromadb / uploads）
└── .env                   # 密钥与全部可调参数（勿提交，含 LLM/EMBEDDING key）

frontend/src/
├── App.tsx                # 路由（/chat /admin/agents /admin/agents/:id/edit /admin/kb /profile）
├── api/                   # axios client（自动带 JWT）+ 各资源 API；agent.ts 的 testAgentStream 用原生 fetch(SSE)
├── store/                 # Zustand：authStore(用户/角色) chatStore(会话/消息/activeAgentId)
├── pages/
│   ├── ChatPage.tsx       # ★改造：无会话=智能体卡片入口；会话内=欢迎语+聊天
│   ├── AgentListPage.tsx  # ★新增：管理员智能体卡片列表
│   ├── AgentEditPage.tsx  # ★新增：左表单右实时预览（图2）
│   ├── KnowledgeBasePage.tsx  # 知识库管理（admin）
│   └── ...
├── components/layout/     # AppLayout(侧边栏/菜单) ConversationList(会话列表，一行标题+查看更多6条)
└── types/                 # chat.ts(会话加了 agent_id) agent.ts(新增)
```

## 5. 数据模型（6 张表）

| 表 | 说明 | 关键字段 |
|---|---|---|
| `users` | 用户 | id, username, role("admin"/"user"), is_active |
| `conversations` | 会话 | id, user_id, **agent_id(新增,可空,外键 agents ON DELETE SET NULL)**, title, is_active |
| `messages` | 消息 | id, conversation_id, role(user/assistant), content, sources(JSON), token_count |
| `knowledge_documents` | 知识文档 | id, filename, file_type, chunk_count, status(processing/indexed/failed), product_category, uploaded_by |
| `agents` | **★新增：智能体** | id, name, description, icon, welcome_message, system_prompt, is_active, sort_order, created_by |
| `agent_knowledge_bases` | **★新增：智能体↔知识文档多对多** | agent_id(PK), kb_doc_id(PK) |

关系：
- `conversations.agent_id → agents.id`（会话归属智能体，删除智能体时置 NULL）
- `Agent ↔ KnowledgeDocument` 多对多（`secondary="agent_knowledge_bases"`）
- 知识文档删除会连带清 ChromaDB 向量（按 `kb_doc_id` metadata 过滤），**桥接灌入的外部文档无磁盘文件，rebuild_index 会跳过它们**（保护爬取数据）

## 6. API 清单

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| POST | /api/auth/register | 注册（body: username/password/confirm_password） | 公开 |
| POST | /api/auth/login | 登录（**form-data**，非 JSON；返回 access_token） | 公开 |
| GET | /api/conversations | 会话列表 | 登录 |
| POST | /api/conversations | 新建会话（body 可带 `agent_id`，标题自动用 agent 名） | 登录 |
| GET/PATCH/DELETE | /api/conversations/{id} | 会话详情/改名/删除 | 所有者 |
| POST | /api/conversations/{id}/messages | **SSE 流式问答**（见 7.3） | 所有者 |
| GET/POST | /api/kb/documents | 文档列表/上传 | admin |
| GET/DELETE | /api/kb/documents/{id} | 文档详情/删除 | admin |
| GET | /api/kb/stats | 知识库统计 | admin |
| POST | /api/kb/reindex | 重建索引 | admin |
| GET | /api/kb/search?q= | 检索调试（可带 kb_doc_ids） | admin |
| **GET** | **/api/agents** | 智能体列表（登录用户可见） | 登录 |
| **GET** | **/api/agents/{id}** | 智能体详情（含 system_prompt/kb_doc_ids） | 登录 |
| **POST/PUT/DELETE** | **/api/agents[/{id}]** | 智能体 CRUD | **admin** |
| **POST** | **/api/agents/test** | 智能体草稿实时问答（SSE，不落库，编辑页预览用） | **admin** |
| GET | /api/categories | 品类列表 | 公开 |
| GET | /api/health | 健康检查 | 公开 |

## 7. 核心链路（RAG 管道，`backend/app/rag/`）

### 7.1 摄入链路（文档/爬取 → ChromaDB）
上传：`kb.py` → `rag_service.ingest_document` → `loader.load_document`（文件解析）→ `splitter.get_text_splitter`（中文感知切分，800字/100重叠）→ 元数据打标（`kb_doc_id`/`chunk_hash`/`source`）→ **按 chunk_hash 去重（幂等）** → 每批 **10 条**（百炼 embedding 单批上限）`vectorstore.add_documents` → 更新 knowledge_documents 状态。
桥接：`scripts/ingest_from_aicrawl.py` 直读 ai_crawl 的 MySQL（t_result VALID）→ 拼 Document（标题+正文/字段）→ 复用上面同一套 splitter/vectorstore → 按爬取任务登记一条 KnowledgeDocument（文件名 `任务标题 〔#task_id〕`）→ 支持 `--task-id` / `--dry-run` / 幂等重跑。

### 7.2 检索链路（`retriever.py`）
`retrieve_with_scores(query, product_category, kb_doc_ids, top_k, ...)`：
1. 缓存查询（`_cache_key` 含 kb_doc_ids）
2. 向量路：`vectorstore.similarity_search_with_relevance_scores`，`filter` 支持 `{"kb_doc_id": {"$in": [...]}}` 或 `{"product_category": ...}`；按 `score >= RETRIEVAL_SCORE_THRESHOLD`（默认 0.3）过滤
3. BM25 路（`bm25_index.py`）：**懒加载**——首次查询从 ChromaDB 全量构建，增删文档后 `invalidate_bm25_index()` 触发重建；`_is_real_hit` 用词频判断真实命中（BM25Plus 小语料不塌缩）
4. RRF 融合（`fusion.py`）→ 可选重排（默认关）→ 展示分数

### 7.3 问答链路（`api/chat.py` + `rag/chain.py`）
```
POST /conversations/{id}/messages
  → 校验归属 → 载入历史(窗口10) → 存用户消息 → 首条自动命名
  → 【智能体注入】若 conv.agent_id 有值：加载 Agent.system_prompt + 关联 kb_doc_ids（空列表转 None=全库）
  → stream_rag_response(question, history, product_category, kb_doc_ids, system_prompt)
     → 查询改写(QUERY_REWRITE_ENABLED，默认关) → 7.2 检索 → 空结果兜底 no_results
     → format_docs_with_sources（[来源N: label] 前缀拼接 context）
     → _build_messages(system_prompt, RAG_RULES, context) → ChatOpenAI 流式 → SSE 事件(token/sources/no_results/done)
  → done 时用独立 DB 会话落库 assistant 消息
```

**提示词结构（`chain.py`，8-21 重构，重要）**：
```python
RAG_RULES = """【必须遵守的规则】只根据参考文档回答/不得编造/引用来源编号/…"""  # 硬规则，所有智能体强制
SYSTEM_PROMPT = "你是一个知识库问答助手…" + RAG_RULES + "【参考文档】{context}"  # 默认

# 自定义 system_prompt（智能体的）作为【角色设定】追加在规则前，规则始终保留：
system_content = agent.system_prompt + "\n\n" + RAG_RULES + "\n\n【参考文档】\n" + context
```

## 8. ★当前正在解决的问题：智能体化改造（重点）

**目标**：把"普通会话"升级为"专属智能体"——管理员创建智能体（自定义名称/简介/图标/欢迎语/**系统提示词**/关联知识库），用户端看到一个个智能体卡片，点进去是专属会话；用户看不到提示词与知识库配置。样式参考：卡片网格列表（admin 页）、左编辑右预览（编辑页）、纯聊天入口（用户页）。

### 8.1 已完成（2026-08-20 ~ 08-21，全部可运行）

**后端**：
- `models/agent.py`：Agent + AgentKnowledgeBase 关联表
- `schemas/agent.py`：AgentItem/AgentDetail/AgentCreate/AgentUpdate
- `api/agents.py`：CRUD（GET 登录可见；写操作 admin）+ `POST /test` 预览端点（流式、不落库）
- `api/conversations.py`：创建会话支持 `agent_id`，标题自动用 agent 名
- `api/chat.py`：按 conv.agent_id 注入 system_prompt + kb_doc_ids（**空列表转 None，否则检索永远为空**）
- `rag/chain.py`：RAG_RULES 硬规则拆分，自定义提示词只作角色设定（防 LLM 幻觉）
- `main.py` lifespan：启动自动 `ALTER TABLE conversations ADD COLUMN agent_id …`（SQLite 兼容迁移，try/except 吞重复列错误）

**前端**：
- `pages/AgentListPage.tsx`：管理员卡片列表（新建/编辑/删除）
- `pages/AgentEditPage.tsx`：左表单（名称/简介/图标选择/欢迎语/提示词/知识库多选/排序/启用）+ 右实时聊天预览（调 `/api/agents/test`）
- `pages/ChatPage.tsx`：无会话=智能体卡片入口（所有人）；会话内绑定 agent 显示欢迎语；仅管理员+非agent会话显示品类/知识库选择器
- `store/chatStore.ts`：+activeAgentId、createNewConversation(agentId?)
- `api/agent.ts`、`types/agent.ts`、`App.tsx` 路由（/admin/agents 等）、`AppLayout.tsx` 菜单（智能体管理）
- `ConversationList.tsx`：每条一行标题、默认 6 条、查看更多展开（前一轮会话侧边栏优化）

### 8.2 关键设计决策
1. **向后兼容**：`agent_id` 可空；旧会话（无 agent）仍用默认 SYSTEM_PROMPT + 全局检索，管理员在普通会话仍可用品类/知识库选择器
2. **提示词安全**：自定义提示词永远追加 RAG_RULES 硬规则（实测防止了 LLM 答"2025年7000人"而忽略资料里"2026年8741人"的幻觉）
3. **知识库隔离**：智能体勾选的 kb_doc_ids 作为检索 filter；不勾选 = None = 全库检索
4. **删除语义**：删智能体 → 会话 agent_id 置 NULL（会话保留）；删知识文档 → 连带清 Chroma 向量
5. **预览不落库**：编辑页测试走 `/api/agents/test`，与真实问答同链路但跳过消息持久化

### 8.3 建议的下一步（供接手者参考，未定稿）
- 智能体卡片可加"最近会话数/使用量"统计展示
- 用户端智能体入口可支持按分类/搜索过滤
- 可考虑让智能体支持多轮人设（system_prompt 之外再给 few-shot 示例）
- 会话列表（ConversationList）可增加按 agent 过滤

## 9. 已知坑与经验（重要，省得重新踩）

1. **百炼 embedding 单批上限 10**：`vectorstore.add_documents` 必须按 10 分批，否则 400
2. **Chroma 查询语法**：`get(where={"kb_doc_id": X})` 只能单字段平铺；多条件需取 `include=["metadatas"]` 后在 Python 侧过滤；`collection.update(ids, metadatas)` 只更新元数据不重嵌
3. **BM25 懒加载 + 失效**：摄入/删除文档后必须 `invalidate_bm25_index()`（ingest/delete 已内置），否则检索用的还是旧索引
4. **SQLite 迁移**：`create_all` 不会给已有表加列，需手动 ALTER（main.py lifespan 已做）；重复执行会报 duplicate column，需 try/except
5. **LLM key 相关**：官方端点模型名是 `deepseek-chat`（`deepseek-v4-flash` 是火山方舟的，官方 API 不存在）；key 失效会 401/402，问答报错时先查 key
6. **登录接口是 form-data**（OAuth2），不是 JSON body
7. **`kb_doc_ids=[]` 语义**：空列表会导致 Chroma filter `$in: []` 返回空 → 必须转 `None`（全库），chat.py/agents.py 已处理
8. **SQLite WAL + 长超时**：database.py 已配置 timeout=30 + WAL，避免并发锁
9. **Windows 路径**：mysqld 桥接脚本用 `D:\dev\mysql-8.0.31-winx64`；MySQL 连接用 `127.0.0.1`（localhost 会解析成 ::1 被拒）+ `ssl_disabled=True`
10. **前端端口**：5175（vite.config.ts、backend/.env CORS_ORIGINS、start.bat 三处需一致）

## 10. 协作项目：ai_crawl（爬虫）

- 路径：`D:\claude_test\ai_crawl`（Spring Boot 后端 8080 + Vue 前端 5173 + MySQL ai_crawl）
- 关系：ai_crawl 抓取 → 正文提取（trafilatura）→ LLM 结构化提取 → MySQL `t_result`（含 data_json/url/status=VALID）→ **桥接脚本** `LangChainRAG项目/backend/scripts/ingest_from_aicrawl.py` 灌入本 rag 的 ChromaDB，成为知识库文档
- 桥接脚本用法：`venv\Scripts\python.exe scripts/ingest_from_aicrawl.py [--task-id N] [--dry-run]`（幂等，可随时重跑）
- 知识点：带"正文内容"字段的爬取任务灌入后问答效果好；只有"标题+链接"的会污染检索（8-20 已清理过一次标题型文档）

## 11. 配置（backend/.env，全部可被 config.py 默认值兜底）

```env
LLM_API_KEY=sk-…                # DeepSeek 官方 key
LLM_API_BASE=https://api.deepseek.com
LLM_MODEL=deepseek-chat
EMBEDDING_API_KEY=sk-…           # 阿里百炼 key
EMBEDDING_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
EMBEDDING_MODEL=text-embedding-v3
DATABASE_URL=sqlite+aiosqlite:///./data/app.db
CHROMA_PERSIST_DIR=./data/chromadb
CHROMA_COLLECTION_NAME=ecommerce_kb
CHUNK_SIZE=300 / CHUNK_OVERLAP=50     # 2026-08-22 调优：小分块 + 语义重排
RETRIEVAL_TOP_K=5 / RETRIEVAL_SCORE_THRESHOLD=0.4   # 阈值仅用于"是否有依据"判定，召回不过滤
RERANK_ENABLED=true / RERANK_MODE=api / RERANK_TOP_N=20 / RERANK_OUTPUT_K=5 / RERANK_MODEL=gte-rerank-v2  # API 语义重排（dashscope SDK，key 复用 EMBEDDING_API_KEY）
CORS_ORIGINS=http://localhost:5175,http://localhost:3000
ADMIN_USERNAME=admin / ADMIN_PASSWORD=123456
# 可选优化（默认关）：HYBRID_ENABLED / QUERY_REWRITE_ENABLED / CACHE_ENABLED
# 检索评估：scripts/eval_rag.py + scripts/eval_set.json（49 条，all-hit 100% / MRR 0.930 / rank@3 98%）
```

## 12. 当前数据状况（2026-08-21）

- 知识文档：14 个（2 个上传示例 + 12 个爬取任务文档），Chroma 总块数 ~289
- 智能体：2 个示例（"招生问答助手"×2：一个无知识库、一个绑定 kb18=task37 正文）
- 测试账号：admin/123456（管理员）、testuser/test123456（普通用户）
- 会话：若干历史会话（含 agent 绑定会话 2022）

## 13. 快速验证清单（改完跑一遍）

1. 启动前后端 → `/api/health` 返回 healthy
2. admin 登录 → GET /api/agents 返回列表 → POST 创建/编辑/删除 正常
3. POST /api/agents/test 带草稿 system_prompt + kb_doc_ids 流式回答且引用资料
4. 普通用户 GET /api/agents 可见、POST 403
5. 前端 /chat 显示智能体卡片 → 点击创建会话 → 欢迎语 → 提问 → SSE 回答 + 来源
6. 知识库上传一个 txt → indexed → 检索命中（若改了摄入链路）
