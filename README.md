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
- **微信公众号采集**：适配公众号文章页（正文、标题、发布时间专属解析），可识别并拦截微信验证码页，避免空壳页污染数据（能力边界见下方专节）
- **数据源管理**：MySQL 连接管理（密码加密存储）
- **文档 RAG 问答**：TXT/MD/PDF/DOCX 上传索引，流式 SSE 回答 + 引用来源折叠展示。来源分四类：知识库片段（doc）、生成查询（sql）、库返回结果（db_result）、联网搜索到的网页（web）
- **引用来源可信**：正文里的 `[来源N]` 与来源面板里的「来源N」共用一套编号（编号 = 在来源列表中的位置，知识库来源在前、网页来源在后）。所有来源各有标题可读，网页来源带可点击链接；工具调用过程随消息留痕，刷新页面后仍可查看
- **用量统计**：管理员可按时间范围与智能体查看真实 token 消耗、问答次数、模型调用次数，含日/月/年趋势图与按智能体明细排行
- **管理员后台**：知识库/智能体/大模型/工具/数据源/爬虫/用户/用量统计管理
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
  前端展示答案 + "最匹配的 N 个来源"（SQL 语句 / 文档片段 / 网页链接）+ 工具调用留痕
```

> 约束：一个智能体最多挂载 **1 个数据库型（B 类）知识库**（避免 SQL 目标库不明确），文档型（A 类）不限数量。

### 来源编号规则

编号只有一个来源：**该来源在来源列表中的位置**。知识库来源排在前面，工具带出的网页来源接在后面，因此正文里的 `[来源N]` 与面板上的「来源N」必然是同一条。

外部服务自带的编号（例如 Exa 答案正文里的 `[1]`）不算数，进入模型前会被统一改写；拿不到结构化来源的工具（如外部服务只返回纯文本的 MCP 工具）不产生任何来源条目，宁可不给来源也不给假来源。

## 用量统计

管理员侧边栏的「用量统计」页，回答「这套系统花了多少、哪个智能体最贵」：

- **范围**：时间区间 + 粒度（日 / 月 / 年）+ 可选的智能体作用域（整页联动）
- **内容**：5 张汇总卡 → token 趋势折线（输入 / 输出）+ 调用次数柱状 → 按智能体明细排行
- **口径**（页面上也有一行说明）：
  - **问答次数** = 用户发起的一次提问，一次提问只算一次（检索无结果、根本没调模型的提问不算）
  - **模型调用次数** = 实际发生的模型调用次数。一次提问背后往往不止一次：查询改写、上下文压缩、Text-to-SQL、工具多轮都会各自产生调用，因此通常大于问答次数
  - 两个数字**只统计模型服务返回的真实用量**；端点没返回用量时按字符推算的「估算用量」与失败调用会留在流水表里备查，但**不进任何统计数字**

采集是旁路写入、全程吞异常，写入失败不影响问答返回。用量流水表**只增不改**（这是账单的事实来源，删除智能体或会话不会抹掉历史归属），决策记录见 `docs/adr/0001-usage-log-append-only.md`。

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

- **Token 用量统计模块**：新增只增不改的用量流水表与管理员统计页（汇总卡 / 日·月·年趋势图 / 按智能体明细排行 / 作用域下钻），6 处埋点覆盖主回答、工具轮、查询改写、上下文压缩、Text-to-SQL 与智能体配置测试；报表只统计模型服务确认的真实用量，估算与失败调用落库但不进统计
- **引用来源可信化**：联网搜索找到的网页成为一等来源（标题可点、链接可点），正文 `[来源N]` 与来源面板统一编号（编号 = 在列表中的位置），工具结果里外部服务自带的 `[1][2]` 在进入模型前被改写，工具调用过程随助手消息落库、刷新页面后仍可查看
- **智能体必须绑定模型**：去掉「系统默认」这个隐式选项，每个智能体都要显式指定所用模型
- **测试补齐**：修复前端 vitest 未配置 `setupFiles` 导致的 10 条既有失败；新增两个真实链路验收脚本（见「测试」一节）
- **大模型库模块**：管理多套 LLM 配置，智能体/会话可按需选模型；`.env` 中的模型自动同步入库作为兜底
- **AI 智能工具（内置技能）**：Web 搜索改 Exa Answer 优先（质量差时回退百度/Bing），修复工具参数解析 bug（LangChain tool_calls 结构与 OpenAI 原始格式不同导致带参工具恒空参）
- **技能挂载修复**：挂工具的智能体在知识库检不到结果时不再短路（原逻辑直接跳过 LLM/工具），新增带工具专用的放宽规则
- **爬虫定时调度**：后台调度器按 `run_time` + `interval_days` 周期触发任务（此前只有 CRUD，配置后从不执行）；修复 MySQL TIME 列被 ORM 读成 timedelta 导致的解析失败
- **URL 去重增强**：新增 canonical_url 归一化（去跟踪参数/协议统一/query 排序），修复同文因 URL 变体重复提取的问题
- **上下文压缩**：长会话自动压缩历史，控制 token 消耗
- **检索与问答**：BM25 混合检索（jieba 分词）、重排器、查询改写、缓存开关
- **启动脚本重构**：依赖指纹自动重装、端口健康检查、清理 uvicorn `--reload` 残留的孤儿进程（此前占住 8000 导致起不来）、`init_all.py` 一键建库
- **接口对齐**：前端 `interval_days` 驼峰/下划线不一致导致的定时间隔失效等修复
- **微信公众号文章采集**：正文锁定 `#js_content`、标题取 `og:title`、发布时间从页面 `var ct` 时间戳解析；新增验证码页 / 空壳页识别，避免 17KB 的拦截空壳页被当作正常文章入库
- **爬虫配置加载修复**：`crawler/config.py` 补 `load_dotenv`。此前 `.env` 只被 pydantic-settings 读进 Settings 对象、并未写入 `os.environ`，而爬虫模块用 `os.getenv` 取值，导致数据库密码读成空、MySQL 拒绝连接（表现为爬虫任务列表接口 500）
- **抽取信息补全**：`CrawlPage` 原本没有 title 字段，cleaner 抽出的标题被直接丢弃，导致单篇文章的标题由模型从正文首句猜测、发布时间恒为 null；现随正文一并传入提示词

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

> 修改 `.env` 后必须**重启后端**才会生效：配置在进程启动时读取，`uvicorn --reload` 只监视 `.py` 文件变更，不会因 `.env` 改动而重载。

### 2. 一键启动 (Windows)

双击运行 `start.bat`，脚本会依次完成：检查 Python/Node → 建 venv 并装依赖 → 装 npm 包 →
清理上次残留进程 → 初始化数据库（建表 + 建管理员）→ 启动前后端并等端口就绪。

```bat
start.bat              :: 正常启动
start.bat --reinstall  :: 强制重装 Python 依赖（改过 requirements.txt 时用）
stop.bat               :: 停止前后端，释放 8000 / 5175
```

依赖是否重装由 `backend/venv/deps.md5` 里的 requirements.txt 指纹决定，内容变了会自动重装。

> **前端依赖只在 `frontend/node_modules` 不存在时才会安装。** 如果你是在旧版本上更新代码（`node_modules` 已存在），新增的依赖（如用量统计页用到的图表库 `@ant-design/plots`）不会自动装上，需要手动跑一次 `cd frontend && npm install`。

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
7. **用量统计**：管理员侧边栏 → 用量统计 → 选时间范围与粒度，需要时可再限定到某个智能体

## 微信公众号采集说明

爬虫可以抓公众号文章，但有明确边界，先看这里避免踩坑：

- **单篇文章能抓**：把文章链接作为种子 URL 即可，正文、标题、发布时间都会自动提取。
- **公众号历史文章列表抓不到**：`/mp/profile_ext` 这类入口要求微信客户端登录态，服务端访问只会拿到"请在微信客户端打开链接"。
- **"往期推荐"里的文章链接会被拦**：`/s?__biz=..&mid=..&sn=..` 这种长链会被 302 到微信验证码页（`wappoc_appmsgcaptcha`）。实测更换 User-Agent、添加 Referer、模拟微信内置浏览器、乃至用真实浏览器渲染，全部无法绕过。这类页面会被判为抓取失败并标记 `BLOCKED`，不会写进数据库。
- **想采集多篇请提供短链**：在微信里打开文章 → 右上角「…」→ 复制链接，得到的是 `/s/xxxx` 短链；多个短链用英文逗号分隔填进种子 URL 即可（爬虫支持多种子）。

> 长链验证由微信服务端强制，非程序侧可解。需要批量、稳定的公众号采集，建议改用 RSS 中转方案（如 WeRSS 一类工具扫码登录后产出短链）。

## 项目结构

```
├── backend/
│   ├── app/
│   │   ├── api/            # API 路由（认证/会话/知识库/智能体/大模型/工具/数据源/爬虫/用量统计）
│   │   ├── crawler/        # 多智能体爬虫引擎 + 定时调度器（planner/discovery/crawler/extractor/verifier）
│   │   ├── skills/         # 内置工具技能（handlers 实现 / registry 注册 / executor 执行循环与来源编号）
│   │   ├── rag/            # RAG 管道（检索/混合检索/重排/上下文压缩）+ Text-to-SQL
│   │   ├── models/         # ORM 模型
│   │   ├── schemas/        # Pydantic 模型
│   │   ├── services/       # 业务逻辑（含用量采集 usage_service）
│   │   └── core/           # 安全与依赖
│   ├── scripts/            # init_all.py 建库、accept_*.py 真实链路验收、eval_*.py 评测
│   ├── tests/              # pytest 用例
│   └── data/               # SQLite 运行时数据（已 gitignore，不入库）
├── frontend/               # React 前端
│   └── src/
│       ├── pages/          # 页面组件（含用户管理/爬虫/大模型库/AI工具/用量统计等）
│       ├── components/     # 可复用组件
│       ├── store/          # Zustand 状态
│       └── api/            # API 客户端
├── CONTEXT.md              # 领域词汇表（钉住易混概念，如问答次数 vs 模型调用次数）
├── docs/adr/               # 架构决策记录
├── docs/agents/            # 工程协作约定（issue tracker / triage / domain docs）
├── start.bat               # 一键启动（含依赖自检、清残留进程、建库、健康检查）
└── stop.bat                # 停止前后端（清理逻辑已内联，不再需要 ps1 文件）
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
| `/api/admin/usage/overview` | 用量汇总 + 按智能体明细 | admin |
| `/api/admin/usage/timeseries` | 用量时间序列（日/月/年） | admin |
| `/api/crawler/tasks` | 爬虫任务管理 | admin |
| `/api/health` | 健康检查 | 公开 |

## 测试

```bash
# 后端（在 backend/ 下，用仓库自己的 venv）
backend/venv/Scripts/python.exe -m pytest tests/ -q --ignore=tests/load

# 前端（在 frontend/ 下）
npm run test          # vitest
npm run build         # 含 tsc -b 类型检查
```

另有两个**走真实链路**的整体验收脚本，会真实调用模型与搜索引擎，需要后端已在 `:8000` 运行、且模型 Key 有余额：

```bash
backend/venv/Scripts/python.exe backend/scripts/accept_usage.py      # 用量统计验收
backend/venv/Scripts/python.exe backend/scripts/accept_citations.py  # 引用来源验收
```

`accept_citations.py` 依赖 `accept_usage.py` 先跑一次建出来的演示智能体。两者都会把验证用的会话留在开发库里，末尾打印会话 id 便于在页面上肉眼核对。

> `tests/test_stress_rag_optimized.py` 标了 `stress`：后端没启动时自动跳过。后端在跑时它会真的发问，其中作用域用例需要开发库里存在「已入库文档的文档型知识库」，否则跳过 —— **跳过不等于通过**。

## 已知边界

这些是有意为之的边界，不是待修的 bug，用之前先知道：

- **联网搜索的网页来源可以点开，但正文里的 `[来源N]` 是纯文本**，没有做成锚点跳转；编号是用来跟下方来源列表对照的。
- **MCP 工具不产生来源条目**。它由外部服务返回纯文本，拿不到结构化来源，宁可不给来源也不给假来源；因此它自带的 `[N]` 编号无法与本站编号对齐，只有 `[来源N]` 这一种编号可信。
- **用量统计不做金额折算**（模型库没有单价字段），只统计 token 数量；升级前的历史问答也不回溯计入（旧 `token_count` 存的是字符数）。
- **用量统计的作用域下拉取自智能体列表**，因此已被删除但仍有历史用量的智能体无法单独下钻 —— 它们在「全部」视图的明细里仍然可见、也不会丢。
- **命中「知识库中未找到资料」的提问不计入问答次数**，但这次提问若已发生内部调用（如查询改写），那部分消耗会照实记账，以便总消费口径准确。
- **检索为空且未挂工具时会短路**，直接返回兜底文案，不调用模型、不产生流水。

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
