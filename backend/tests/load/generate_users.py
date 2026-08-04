"""
批量生成测试用户 — 为压力测试预注册100个用户
运行: python backend/tests/load/generate_users.py
"""

import requests
import json
import os
import sys

API_BASE = os.environ.get("API_BASE", "http://localhost:8000/api")
USER_COUNT = 100
USER_PREFIX = "testuser"
USER_PASSWORD = "test123456"

output_file = os.path.join(os.path.dirname(__file__), "test_users.json")


def register_user(username: str, password: str) -> dict:
    """注册单个用户"""
    resp = requests.post(
        f"{API_BASE}/auth/register",
        json={
            "username": username,
            "password": password,
            "confirm_password": password,
        },
        timeout=10,
    )
    if resp.status_code == 201:
        return resp.json()
    elif resp.status_code == 409:
        # 用户已存在，尝试登录获取信息
        login_resp = requests.post(
            f"{API_BASE}/auth/login",
            data={"username": username, "password": password},
            timeout=10,
        )
        if login_resp.status_code == 200:
            data = login_resp.json()
            return {"id": data["user"]["id"], "username": username, "token": data["access_token"]}
        else:
            return {"username": username, "error": f"login failed: {login_resp.status_code}"}
    else:
        return {"username": username, "error": resp.text}


def main():
    print(f"Generating {USER_COUNT} test users...")
    print(f"API: {API_BASE}")
    print()

    users = []
    success = 0
    failed = 0

    for i in range(1, USER_COUNT + 1):
        username = f"{USER_PREFIX}{i:03d}"
        result = register_user(username, USER_PASSWORD)

        if "error" not in result:
            success += 1
            users.append({
                "username": username,
                "password": USER_PASSWORD,
                "user_id": result.get("id", i),
                "token": result.get("token", ""),
            })
            if i % 20 == 0:
                print(f"  {i}/{USER_COUNT} done ({success} ok, {failed} fail)")
        else:
            failed += 1
            print(f"  [{username}] FAILED: {result['error'][:80]}")

    print()
    print(f"Done: {success} success, {failed} failed")

    # 保存到文件
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)
    print(f"Users saved to: {output_file}")


if __name__ == "__main__":
    main()
