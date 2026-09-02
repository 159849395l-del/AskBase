# 新增「大模型库」与「AI 智能工具」模块方案

> 目标：把当前硬编码在 `.env` 里的 LLM 配置，升级为后台可配置的「大模型库」；同时新增「AI 智能工具」模块，先支持内部 Skill，再支持外部 MCP 服务。智能体可像挂载知识库一样挂载模型和工具。

## 实现状态（阶段 A / B / C 均已完成，代码未提交 git）

| 阶段 | 状态 | 说明 |
|------|------|------|
| A 大模型库 | 已完成 | 后端 CRUD + 连通测试 + 设为默认；前端管理页；智能体可绑定模型 |
| B 内部 Skill | 已完成 | 内置 4 个工具（web_search / kb_search / get_current_time / calculator）；对话链路支持 function calling |
| C MCP 服务 | 已完成 | stdio / SSE 两种传输，工具发现与缓存；前端卡片管理 |

**尚未实测**：真实 LLM 下的工具触发链路、真实 MCP server 连接（需本地启动后端验证）。
**依赖坑**：`mcp` 必须锁 `1.9.4`。装 2.x 会把 starlette 升到 1.6.0，与 `fastapi==0.115.6` 冲突。backend 环境执行 `pip install mcp==1.9.4`。

---

## 一、参考方案速览

| 平台 | 模型库做法 | 工具/插件做法 | 可借鉴点 |
|------|-----------|--------------|---------|
| **WorkBuddy** | `~/.workbuddy/models.json`，字段：id/name/vendor/url/apiKey/supportsToolCall/supportsImages | `mcp.json` 配置 server：`command/args/env`，UI 以 connector 卡片展示 | 模型与工具配置分离；MCP 按 server 卡片管理 |
| **Dify** | 模型供应商（provider）= 一个账号连接；其下挂多个 model；字段：provider_name/api_key/base_url/models | 工具分内置（web search / code exec）和外接 API；Agent 可选启用工具 | provider + model 两级抽象；工具可开关、按 agent 启用 |
| **MCP 官方** | - | server 暴露 tools/list、tools/call；传输分 stdio / streamable HTTP；工具用 JSON Schema 描述参数 | 把外部能力统一抽象为 tool name + inputSchema |
| **DeepSeek Harness / 通用** | 仅配置 api_key + model + base_url，无多 provider | 多为 function calling 框架内部 tool | 保持 OpenAI 兼容调用即可 |

**我们的取舍**：
- 模型库 = **平铺模型列表**（类似 WorkBuddy models.json，但入库），一条记录就是一个可用模型，带厂商标签。
- AI 智能工具 = **内部 Skill + 外部 MCP** 两层：
  - 内部 Skill：本项目自己实现的 Python 函数工具（联网搜索、知识库检索、发送邮件等）。
  - 外部 MCP：按 MCP 规范连接 stdio/SSE 服务，动态发现工具。

---

## 二、总体架构

```
┌─────────────────────────────────────────────────────────────┐
│                        前端 React (Ant Design 5)              │
│  ┌──────────────┐  ┌──────────────────────────────────────┐  │
│  │ 大模型库管理  │  │ AI 智能工具管理                       │  │
│  │ (表格+弹窗)   │  │ Tab1 内部工具 | Tab2 MCP 服务        │  │
│  └──────────────┘  │ (卡片网格 + 新增/编辑抽屉)            │  │
│                    └──────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI 后端                             │
│  /api/models          /api/skills        /api/mcp-servers     │
│  /api/agents/{id}/models                /api/agents/{id}/tools│
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
  ┌──────────┐        ┌──────────────┐        ┌─────────────┐
  │ LLM 调用层│        │ 内部 Skill   │        │ MCP Client  │
  │ ChatOpenAI│        │ Python func  │        │ stdio/SSE   │
  └──────────┘        └──────────────┘        └─────────────┘
```

**关键改动**：
- `app/config.py` 保留 `.env` 作为**系统默认模型**（兜底/回退）。
- `rag/chain.py` 的 `get_llm()` 改为按 `model_id` 从「大模型库」取配置；若未取到则回退 `.env`。
- `agents` 表新增 `model_id`（可选）和工具关联；会话链路按 agent 配置选择模型和工具。

---

## 三、数据库设计

### 3.1 大模型库表 `llm_models`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | |
| name | VARCHAR(100) | 显示名，如「DeepSeek V3」 |
| provider | VARCHAR(50) | 厂商：deepseek / volcengine / openai / aliyun / local 等 |
| model_id | VARCHAR(100) | 真实模型 ID，如 `deepseek-v3-250324` |
| base_url | VARCHAR(255) | OpenAI 兼容 endpoint，如 `https://ark.cn-beijing.volces.com/api/v3` |
| api_key_encrypted | VARCHAR(512) | Fernet 加密存储 |
| is_active | BOOLEAN | 是否启用 |
| is_vision | BOOLEAN | 是否视觉模型 |
| supports_tool_call | BOOLEAN | 是否支持 function calling（影响工具调用方式） |
| max_tokens | INTEGER nullable | 最大输出 token |
| temperature | FLOAT | 默认温度 |
| is_default | BOOLEAN | 是否系统默认（唯一） |
| created_at / updated_at | VARCHAR(30) | |

**约束**：`provider + model_id` 联合唯一；只有一个 `is_default=true`。

### 3.2 内部 Skill 表 `skills`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | |
| name | VARCHAR(100) | 工具名（英文，LLM 可见），如 `web_search` |
| title | VARCHAR(100) | 显示标题，如「联网搜索互联网最新信息」 |
| description | TEXT | 工具描述，给 LLM 看 |
| icon | VARCHAR(50) | emoji 或 antd icon 名 |
| handler | VARCHAR(100) | 后端注册的处理函数路径/标识 |
| input_schema | TEXT (JSON) | JSON Schema 参数定义 |
| is_active | BOOLEAN | |
| is_builtin | BOOLEAN | 是否内置（内置不可删） |
| sort_order | INTEGER | |
| created_at / updated_at | VARCHAR(30) | |

### 3.3 MCP 服务表 `mcp_servers`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | |
| name | VARCHAR(100) | 显示名 |
| transport | VARCHAR(20) | `stdio` / `sse` |
| command | VARCHAR(255) nullable | stdio 命令，如 `npx` |
| args | TEXT (JSON) nullable | stdio 参数数组 |
| env | TEXT (JSON) nullable | 环境变量 |
| url | VARCHAR(255) nullable | SSE 地址 |
| is_active | BOOLEAN | |
| tools_cache | TEXT (JSON) nullable | 上次发现的工具列表（tools/list 结果） |
| tools_cached_at | VARCHAR(30) nullable | |
| created_at / updated_at | VARCHAR(30) | |

### 3.4 智能体扩展

- `agents` 表新增 `model_id`（INTEGER FK → llm_models.id，nullable）。
- 新建关联表 `agent_tools`：`agent_id + tool_type + tool_ref_id + enabled`。
  - `tool_type`: `skill` | `mcp_tool`
  - `tool_ref_id`: skill.id 或 MCP 工具 name（在 mcp_server.tools_cache 里找）
  - 这样内部 Skill 与 MCP 工具可混合挂载。

---

## 四、后端 API 设计

### 4.1 大模型库 `/api/models`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/models` | 列表（admin 看全部，普通用户只看启用） |
| POST | `/api/models` | 新增 |
| GET | `/api/models/{id}` | 详情 |
| PUT | `/api/models/{id}` | 更新 |
| DELETE | `/api/models/{id}` | 删除（检查是否被 agent 引用） |
| POST | `/api/models/{id}/test` | 连通测试：发一条简单 chat.completions 验证 |
| POST | `/api/models/{id}/set-default` | 设为默认模型 |

新增 schema 文件：`schemas/llm_model.py`
新增 service：`services/llm_model_service.py`
新增 model：`models/llm_model.py`

### 4.2 内部 Skill `/api/skills`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/skills` | 列表 |
| POST | `/api/skills` | 新增 |
| PUT | `/api/skills/{id}` | 更新 |
| DELETE | `/api/skills/{id}` | 删除（内置不可删） |

新增 schema：`schemas/skill.py`
新增 model：`models/skill.py`

### 4.3 MCP 服务 `/api/mcp-servers`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/mcp-servers` | 列表 |
| POST | `/api/mcp-servers` | 新增 |
| GET | `/api/mcp-servers/{id}` | 详情 |
| PUT | `/api/mcp-servers/{id}` | 更新 |
| DELETE | `/api/mcp-servers/{id}` | 删除 |
| POST | `/api/mcp-servers/{id}/discover` | 触发 tools/list，缓存结果 |
| POST | `/api/mcp-servers/{id}/tools/{tool_name}/call` | 管理员测试调用 |

新增：`schemas/mcp_server.py`、`models/mcp_server.py`、`services/mcp_service.py`

### 4.4 智能体挂载模型与工具

在现有 `/api/agents` 上扩展：
- `AgentCreate` / `AgentUpdate` 增加 `model_id: int | None` 和 `tools: List[AgentToolRef]`。
- `AgentDetail` / `AgentItem` 返回 `model: LLMModelItem | None` 和 `tools: List[AgentToolItem]`。

新增关联表：`models/agent.py` 里补 `AgentTool`。

### 4.5 对话链路集成

修改点：
- `rag/chain.py`：`get_llm(model_id=None)` 根据 `model_id` 从库取配置，构造 `ChatOpenAI`；失败回退 `.env`。
- `stream_rag_response` 增加 `model_id` 参数。
- `api/chat.py` 发消息时，从 agent 读 `model_id` 并传入。
- 工具调用：先实现**内部 Skill** 的 function calling。模型必须 `supports_tool_call=true` 才启用工具。
  - 在 `stream_rag_response` 中，如 agent 挂载了工具，用 `ChatOpenAI.bind_tools(tools)` 触发工具调用。
  - 工具执行器根据 `tool_type` 路由到 skill handler 或 mcp client。
  - 工具结果再送回 LLM 生成最终回答。

---

## 五、前端页面设计

### 5.1 大模型库管理（参考截图 1/2）

- 页面路径：`/admin/models`
- 布局：表格 + 右上角「新增」按钮，与数据源管理一致。
- 表格列：状态（启用绿点）、厂商标签、模型名、模型 ID、接口地址、是否视觉模型、创建时间、操作（编辑/删除）。
- 弹窗表单字段：
  - 厂商名称（下拉：深度求索 / 字节豆包 / OpenAI / 阿里云 / 本地 / 自定义）
  - 模型名称（显示名）
  - 模型 ID（真实 ID）
  - 模型状态（启用/停用）
  - 接口地址
  - API Key（密码框，加密存储，编辑时不回显）
  - 是否视觉模型（下拉：是/否）
  - 是否支持工具调用（下拉）
  - 默认温度、最大 token（可选）
- 弹窗底部：检测连通按钮 + 取消 + 确定。

### 5.2 AI 智能工具管理（参考截图 3/4）

- 页面路径：`/admin/tools`
- 布局：Tabs ——「内部工具」「MCP 服务」。
- **内部工具 Tab**：
  - 卡片网格，每个卡片：图标、标题、描述、启用状态点、右上角菜单（编辑/删除）。
  - 首个卡片为「新增工具」。
  - 点击卡片进入编辑抽屉：名称/标题/描述/icon/参数 schema/启用状态/处理函数选择。
- **MCP 服务 Tab**：
  - 同样卡片网格。
  - 卡片显示：服务名、transport 标签、已发现工具数、启用状态。
  - 新增/编辑抽屉：transport 选择 → 显示 command/args/env 或 url；保存后触发「发现工具」。
  - 抽屉内二级列表展示该服务下的工具，可单独启用/禁用。

### 5.3 智能体编辑页扩展

- 在现有「挂载知识库」区域下方新增：
  - **选择模型**：下拉选择大模型库中启用的模型；不选则走系统默认。
  - **启用工具**：多选框/穿梭框，列出内部 Skill + MCP 工具；支持开关。
- 测试智能体 `/api/agents/test` 同样传入 `model_id` 和 `tools`。

### 5.4 菜单注册

`AppLayout.tsx` 管理员菜单新增：
- 「大模型库管理」→ `/admin/models`
- 「AI 智能工具」→ `/admin/tools`

`App.tsx` 增加对应受保护路由。

---

## 六、关键集成点

1. **模型回退策略**：后台未配置任何模型时，仍用 `.env` 里的 `LLM_API_KEY/LLM_API_BASE/LLM_MODEL` 兜底，保证旧用户不中断。
2. **Agent 默认模型**：`agents.model_id` 为 NULL 时，使用「大模型库」中 `is_default=true` 的模型；再空则回退 `.env`。
3. **工具调用安全**：
   - 所有 skill handler 默认**只读/安全**；写操作 skill 必须显式声明 `destructive=true`，前端调用前弹确认。
   - MCP server 由管理员配置，本系统只作为 client 调用；敏感工具（写文件、发送消息）默认禁用，需手动启用。
4. **密码加密**：沿用现有 `app/utils/crypto.py` 的 Fernet 加密 `api_key_encrypted`。
5. **迁移**：在 `main.py` lifespan 里用 `ALTER TABLE` 兼容新增列；新表由 `init_db()` 自动创建。

---

## 七、实施顺序建议（MVP → 完整）

### 阶段 A：大模型库（1-2 天）
1. 后端：`models/llm_model.py` + `schemas/llm_model.py` + `services/llm_model_service.py` + `api/models.py`。
2. 后端：`rag/chain.py` 改造 `get_llm(model_id)`，支持按模型库构造客户端。
3. 后端：`agents` 表加 `model_id`，API 扩展。
4. 前端：模型管理页面 + 类型/API 文件。
5. 前端：智能体编辑页加「选择模型」。
6. 前端：菜单/路由注册。

### 阶段 B：内部 Skill（1-2 天）
1. 后端：`models/skill.py` + `schemas/skill.py` + `api/skills.py`。
2. 后端：实现 skill handler 注册表（如 `skills/web_search.py`、`skills/kb_search.py`），并内置几个常用工具。
3. 后端：`agent_tools` 关联表，对话链路支持 `bind_tools` + tool executor。
4. 前端：AI 智能工具页面「内部工具」Tab。
5. 前端：智能体编辑页加「启用工具」。

### 阶段 C：MCP 服务（2-3 天）
1. 后端：引入 `mcp` Python SDK（`pip install mcp`），实现 `MCPClient`（stdio/SSE）。
2. 后端：`models/mcp_server.py` + `api/mcp_servers.py` + `services/mcp_service.py`。
3. 后端：MCP 工具发现缓存、调用路由。
4. 前端：AI 智能工具页面「MCP 服务」Tab。

---

## 八、需要确认的问题

1. **模型库是否必须支持非 OpenAI 兼容协议？** 当前项目全部走 `ChatOpenAI`，方案保持 OpenAI 兼容即可。
2. **工具调用是否必须现在就做？** 可以先做「管理 + 挂载」，对话里先不启用 function calling，等 Skill 体系稳定再开。
3. **MCP 优先级**：如果短期用不上外部 MCP，可以先只做内部 Skill，MCP 作为二期。
4. **默认厂商列表**：截图里有「深度求索」「字节豆包」。是否还需要预置 OpenAI / 阿里云 / 硅基流动？

---

## 九、新增文件清单（后端）

```
backend/app/models/llm_model.py
backend/app/models/skill.py
backend/app/models/mcp_server.py
backend/app/schemas/llm_model.py
backend/app/schemas/skill.py
backend/app/schemas/mcp_server.py
backend/app/services/llm_model_service.py
backend/app/services/skill_service.py
backend/app/services/mcp_service.py
backend/app/api/models.py
backend/app/api/skills.py
backend/app/api/mcp_servers.py
backend/app/skills/__init__.py
backend/app/skills/registry.py
backend/app/skills/handlers/web_search.py
backend/app/skills/handlers/kb_search.py
backend/app/mcp/__init__.py
backend/app/mcp/client.py
```

## 十、新增文件清单（前端）

```
frontend/src/types/llmModel.ts
frontend/src/types/skill.ts
frontend/src/types/mcpServer.ts
frontend/src/api/models.ts
frontend/src/api/skills.ts
frontend/src/api/mcpServers.ts
frontend/src/pages/ModelManagePage.tsx
frontend/src/pages/AIToolsPage.tsx
frontend/src/components/skills/SkillCard.tsx
frontend/src/components/skills/MCPServerCard.tsx
frontend/src/components/skills/SkillFormDrawer.tsx
frontend/src/components/skills/MCPServerFormDrawer.tsx
```

---

## 十一、风险与注意

- **API Key 安全**：加密存储、接口不回显、前端密码框；`.env` 里的默认 key 继续保留作为兜底。
- **工具调用幻觉**：LLM 可能乱调工具，需在 system prompt 里加「只在需要时调用工具」约束，并对工具参数做强校验。
- **MCP 进程生命周期**：stdio 类型 MCP server 由后端启动子进程，需确保进程随请求/应用退出而清理，避免僵尸进程。
- **兼容性**：新增表/列通过 `init_db()` + lifespan 内 `ALTER TABLE` 完成，不影响已有数据。
