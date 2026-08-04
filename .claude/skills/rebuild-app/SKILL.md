---
name: rebuild-app
description: 清理并重建项目依赖与数据库（重置环境）
---

## 重建项目环境

清理项目运行环境并从头重建，用于解决依赖冲突或数据库异常。

### 操作步骤

1. **清理数据库和向量数据**
   ```bash
   rm -rf backend/data/app.db
   rm -rf backend/data/chromadb/
   ```

2. **重建 Python 虚拟环境**
   ```bash
   cd backend
   rm -rf venv/
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
   ```

3. **重建前端依赖**
   ```bash
   cd frontend
   rm -rf node_modules/
   npm install
   ```

4. **验证重建结果**
   - 运行 `start.bat` 启动系统
   - 确认数据库自动创建，admin 账户可登录
   - 重新上传知识库文档

### 重要说明

- 此操作会**删除所有数据库记录**（用户、会话、消息）和**向量索引**
- 仅用于开发环境，不适用于生产环境
- 操作后需要重新上传知识库文档并重新注册用户

### 常见使用场景

- ChromaDB 版本升级导致旧数据不兼容
- Python 依赖版本冲突
- 磁盘空间不足需要清理
- 重置到"干净状态"重新开始
