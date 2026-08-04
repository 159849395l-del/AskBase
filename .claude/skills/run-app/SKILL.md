---
name: run-app
description: 启动电商RAG知识库问答系统（开发模式），用于预览和测试
---

## 启动电商RAG知识库问答系统

本项目是 FastAPI + React 前后端分离的 Web 应用。按以下步骤启动开发模式：

### 启动步骤

1. **一键启动（推荐）**
   - 双击运行 `start.bat`
   - 脚本会自动安装依赖、初始化数据库、启动前后端服务

2. **手动启动后端**
   ```bash
   cd backend
   venv\Scripts\activate
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

3. **手动启动前端**
   ```bash
   cd frontend
   npm run dev
   ```

### 验证启动成功

- 后端控制台显示：`Application startup complete. Uvicorn running on http://0.0.0.0:8000`
- 前端控制台显示：`Local: http://localhost:5173/`
- API 文档：http://localhost:8000/docs
- 管理员账号：`admin` / `123456`

### 重要说明

- 后端使用 `--reload` 模式，修改 `backend/app/` 下代码会自动重启
- 前端 Vite 支持热更新，修改 `frontend/src/` 代码浏览器自动刷新
- 数据库文件在 `backend/data/app.db`，ChromiaDB 向量数据在 `backend/data/chromadb/`
- API Key 配置在 `backend/.env`：`LLM_API_KEY`（DeepSeek）、`EMBEDDING_API_KEY`（百炼）

### 常见问题

- **端口占用**：后端 8000、前端 5173，检查是否有其他程序占用
- **依赖缺失**：运行 `start.bat` 自动安装，或手动 `pip install -r requirements.txt`
- **API Key 无效**：检查 `backend/.env` 中 Key 是否正确
- **ChromaDB 错误**：删除 `backend/data/chromadb/` 目录重新索引
