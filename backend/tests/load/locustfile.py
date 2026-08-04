"""
电商RAG知识库问答系统 — 压力测试脚本
使用 Locust 模拟100人并发使用场景

启动方式:
  locust -f backend/tests/load/locustfile.py --host=http://localhost:8000

然后打开 http://localhost:8089 配置并发参数
"""

import json
import os
import random
from locust import HttpUser, task, between, events
from locust.runners import Runner

# 加载测试数据
_DATA_DIR = os.path.dirname(__file__)

with open(os.path.join(_DATA_DIR, "test_questions.json"), encoding="utf-8") as f:
    QUESTIONS = json.load(f)["questions"]

# 尝试加载预注册用户，没有则用动态注册
_USERS_FILE = os.path.join(_DATA_DIR, "test_users.json")
_PRELOADED_USERS = []
if os.path.exists(_USERS_FILE):
    with open(_USERS_FILE, encoding="utf-8") as f:
        _PRELOADED_USERS = json.load(f)


# ============================================================
# 场景 A: 轻量 CRUD — 用户日常操作（100并发）
# ============================================================
class LightCRUDUser(HttpUser):
    """模拟用户日常浏览操作：登录、看会话、改资料"""
    weight = 5
    wait_time = between(2, 5)

    def on_start(self):
        """每个虚拟用户启动时注册/登录"""
        username = f"perf_user_{random.randint(1000, 9999)}"
        password = "test123456"

        # 注册（忽略已存在错误）
        self.client.post("/api/auth/register", json={
            "username": username,
            "password": password,
            "confirm_password": password,
        })

        # 登录
        resp = self.client.post("/api/auth/login", data={
            "username": username,
            "password": password,
        })
        if resp.status_code == 200:
            self.token = resp.json()["access_token"]
            self.user_id = resp.json()["user"]["id"]
            self.conv_id = None
        else:
            self.token = None

    @task(8)
    def list_conversations(self):
        """获取会话列表 — 高频操作"""
        if not self.token:
            return
        with self.client.get(
            "/api/conversations",
            headers={"Authorization": f"Bearer {self.token}"},
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"list_conversations failed: {resp.status_code}")

    @task(3)
    def create_conversation(self):
        """创建新会话 — 中频操作"""
        if not self.token:
            return
        with self.client.post(
            "/api/conversations",
            json={"title": f"会话-{random.randint(1, 999)}"},
            headers={"Authorization": f"Bearer {self.token}"},
            catch_response=True,
        ) as resp:
            if resp.status_code == 201:
                data = resp.json()
                self.conv_id = data["id"]
            else:
                resp.failure(f"create_conversation failed: {resp.status_code}")

    @task(5)
    def get_profile(self):
        """获取个人信息 — 中频操作"""
        if not self.token:
            return
        with self.client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {self.token}"},
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"get_profile failed: {resp.status_code}")

    @task(1)
    def health_check(self):
        """健康检查 — 低频"""
        self.client.get("/api/health")


# ============================================================
# 场景 B: 聊天 RAG — 真实链路（5-10并发，免费API限制）
# ============================================================
class ChatRAGUser(HttpUser):
    """模拟用户提问，触发完整RAG管道（嵌入+检索+LLM生成）"""
    weight = 1
    wait_time = between(5, 10)  # 较长间隔，避免触发API限流

    def on_start(self):
        """登录并创建会话"""
        username = f"chat_user_{random.randint(1000, 9999)}"
        password = "test123456"

        self.client.post("/api/auth/register", json={
            "username": username, "password": password,
            "confirm_password": password,
        })

        resp = self.client.post("/api/auth/login", data={
            "username": username, "password": password,
        })
        if resp.status_code == 200:
            self.token = resp.json()["access_token"]
        else:
            self.token = None
            return

        # 创建一个会话
        resp = self.client.post(
            "/api/conversations",
            json={"title": "压测会话"},
            headers={"Authorization": f"Bearer {self.token}"},
        )
        if resp.status_code == 201:
            self.conv_id = resp.json()["id"]
        else:
            self.conv_id = None

    @task
    def ask_question(self):
        """发送问题，通过SSE接收流式回答"""
        if not self.token or not self.conv_id:
            return

        question = random.choice(QUESTIONS)

        with self.client.post(
            f"/api/conversations/{self.conv_id}/messages",
            json={"content": question},
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "text/event-stream",
            },
            stream=True,
            catch_response=True,
            timeout=30,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"chat failed: {resp.status_code}")
                return

            # 读取SSE流直到done事件
            first_token_time = None
            try:
                for line in resp.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data = json.loads(line[6:])
                        if "token" in data:
                            if first_token_time is None:
                                first_token_time = True
                        elif "error" in data:
                            resp.failure(f"chat error: {data['error']}")
                            return
                        elif "message_id" in data:
                            # done event
                            resp.success()
                            return
            except Exception as e:
                resp.failure(f"stream read error: {e}")


# ============================================================
# 场景 C: 知识库管理 — 管理员操作（10-20并发）
# ============================================================
class KBAdminUser(HttpUser):
    """模拟管理员搜索知识库"""
    weight = 1
    wait_time = between(3, 6)

    def on_start(self):
        """管理员登录"""
        resp = self.client.post("/api/auth/login", data={
            "username": "admin", "password": "123456",
        })
        if resp.status_code == 200:
            self.token = resp.json()["access_token"]
        else:
            self.token = None

    @task(5)
    def search_kb(self):
        """语义搜索知识库"""
        if not self.token:
            return
        q = random.choice(QUESTIONS)
        with self.client.get(
            "/api/kb/search",
            params={"q": q, "top_k": 3},
            headers={"Authorization": f"Bearer {self.token}"},
            catch_response=True,
            timeout=30,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"kb_search failed: {resp.status_code}")

    @task(3)
    def list_documents(self):
        """获取文档列表"""
        if not self.token:
            return
        with self.client.get(
            "/api/kb/documents",
            headers={"Authorization": f"Bearer {self.token}"},
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"list_documents failed: {resp.status_code}")

    @task(2)
    def kb_stats(self):
        """获取KB统计"""
        if not self.token:
            return
        with self.client.get(
            "/api/kb/stats",
            headers={"Authorization": f"Bearer {self.token}"},
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"kb_stats failed: {resp.status_code}")


# ============================================================
# 事件钩子 — 压测开始/结束时打印汇总
# ============================================================
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    print("\n" + "=" * 50)
    print("  RAG System Load Test — Starting")
    print(f"  Questions loaded: {len(QUESTIONS)}")
    print(f"  Preloaded users: {len(_PRELOADED_USERS)}")
    print("=" * 50 + "\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    print("\n" + "=" * 50)
    print("  RAG System Load Test — Finished")
    stats = environment.stats
    print(f"  Total requests: {stats.total.num_requests}")
    print(f"  Failures: {stats.total.num_failures}")
    if stats.total.num_requests > 0:
        print(f"  Avg response: {stats.total.avg_response_time:.0f}ms")
        print(f"  P95 response: {stats.total.get_response_time_percentile(0.95):.0f}ms")
        print(f"  RPS: {stats.total.total_rps:.1f}")
    print("=" * 50 + "\n")
