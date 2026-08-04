---
name: security-audit
description: 安全审计：检查敏感信息泄露、SQL注入、JWT认证、API安全、Web安全等（FastAPI + React 前后端项目）
---

## 代码安全审计

对项目代码进行全面安全检查，发现潜在的安全隐患并给出修复建议。

## 项目安全上下文

- **后端**：FastAPI (Python) + SQLAlchemy + SQLite + JWT认证
- **前端**：React 18 + TypeScript (SPA)
- **LLM**：阿里云百炼 DashScope API
- **部署**：本地开发 / 单机部署，非公网暴露

---

## 六大检查维度

### 维度 1：敏感信息泄露

**检查代码中是否硬编码了敏感信息**

检查项：
- 密码明文（`password = "123456"`）
- API 密钥 / Token（`DASHSCOPE_API_KEY = "sk-xxx"`）
- JWT 密钥（`JWT_SECRET = "xxx"`）
- 数据库连接字符串含密码
- 管理员密码硬编码

检查方式（搜索关键词）：
```
password, secret, token, apiKey, api_key, DASHSCOPE_API_KEY,
JWT_SECRET, privateKey, private_key, salt, passwd, pwd, auth
```

### 维度 2：SQL 注入风险

**检查 SQLAlchemy 使用是否存在注入漏洞**

检查项：
- 是否使用字符串拼接构造 SQL（`f"SELECT * FROM users WHERE name='{input}'"`）
- 是否使用 SQLAlchemy 参数化查询（`select(User).where(User.name == input)`）
- 原生 SQL 是否用了 `text()` + 参数绑定
- 动态 ORDER BY / GROUP BY 是否有白名单校验

危险示例：
```python
# ❌ SQL 注入风险
query = f"SELECT * FROM users WHERE username = '{username}'"
result = await db.execute(text(query))
```

安全示例：
```python
# ✅ SQLAlchemy 参数化查询
result = await db.execute(select(User).where(User.username == username))
```

### 维度 3：JWT 与认证安全

**检查认证机制的安全性**

检查项：
- JWT_SECRET 是否足够随机和长
- JWT 过期时间是否合理
- token 是否通过 Authorization header 传递（非 URL）
- 密码哈希是否使用 bcrypt
- 是否有角色权限校验（admin vs user）
- 前端 localStorage 存储 token 的安全性（XSS风险）

### 维度 4：Web API 安全（FastAPI）

**检查 FastAPI 后端的 Web 安全配置**

检查项：
- CORS 配置是否过于宽松（`allow_origins=["*"]`）
- 是否有请求频率限制（rate limiting）
- 错误响应是否泄露了内部信息（stack trace、数据库结构）
- 文件上传是否有大小和类型校验
- 是否有路径遍历风险（文件路径拼接）
- SSE 端点是否有认证

### 维度 5：LangChain / RAG 安全

**检查 RAG 管道的安全性**

检查项：
- 用户输入是否直接拼入 LLM prompt
- 是否有 prompt injection 防护
- 知识库文档内容是否信任（可能含恶意内容）
- ChromaDB 数据目录权限
- LLM API Key 是否安全存储
- 检索结果是否有数量限制（防止 DoS）

### 维度 6：其它常见安全隐患

| 检查项 | 风险说明 | 检查方式 |
|--------|---------|---------|
| **XSS 跨站脚本** | React `dangerouslySetInnerHTML` 直接插入用户输入 | 搜索 `dangerouslySetInnerHTML` |
| **不安全的随机数** | `Math.random()` / `random.random()` 用于安全场景 | 搜索 `Math.random()`、`random.random()` |
| **eval 动态执行** | `eval()` / `new Function()` / `exec()` 执行用户输入 | 搜索 `eval(`、`exec(` |
| **localStorage 敏感数据** | token 存在 localStorage 中 | 检查 authStore.ts |
| **无输入校验** | 用户输入未校验类型、长度、范围 | 检查 Pydantic models + 前端表单 |
| **console.log 泄露** | 打印了 API Key、用户数据到控制台 | 搜索 `console.log(`、`print(` |
| **依赖漏洞** | `package.json` / `requirements.txt` 中的依赖有已知漏洞 | 检查 `npm audit` / `pip audit` |
| **硬编码 URL/端口** | 内网地址暴露 | 搜索 `http://`、`localhost` |
| **.env 提交到 Git** | .env 文件被提交到版本控制 | 检查 `.gitignore` |

---

## 执行流程

### 步骤 1：确定审计范围

- 用户指定文件 → 审计该文件
- 用户未指定 → 审计 `backend/app/` + `frontend/src/` + 配置文件
- 同时检查 `.gitignore` 是否忽略了 `.env`、`data/` 等敏感路径

### 步骤 2：逐维度检查

```
1. 搜索敏感关键词（password, secret, token, key, apiKey 等）
2. 搜索 SQL 注入模式（字符串拼接 SQL）
3. 检查 JWT 配置和认证逻辑
4. 检查 CORS、文件上传、错误处理
5. 检查 RAG 管道安全
6. 搜索其他风险模式（eval, XSS, console.log 等）
```

### 步骤 3：输出审计报告

```
========== 安全审计报告 ==========

📁 审计范围：backend/app/ + frontend/src/
📝 检查项目：XX 项
🔴 高危：X 个
🟡 中危：X 个
🟢 低危：X 个
⚪ 信息：X 个

====================================
风险等级说明：
  🔴 高危 — 必须立即修复，可能导致数据泄露或被攻击
  🟡 中危 — 建议尽快修复，存在潜在风险
  🟢 低危 — 最佳实践建议，暂无直接危害
  ⚪ 信息 — 值得关注，但非安全问题
====================================

———— 🔴 高危问题 ————
[问题详细列表，含位置、风险说明、修复代码]

———— 总结 ————
安全评分：XX / 100
```

---

## 重要原则

- 检查时**只读不写**，不要修改任何文件
- 对每个问题给出**风险等级**和**具体修复代码**
- 如果项目使用了参数化查询和 bcrypt 密码哈希，要**表扬**
- 考虑项目的实际情况（毕设项目，本地部署，非生产环境）
- RAG 管道的安全重点是 prompt injection 和 API key 保护
