"""测试 security 模块 — JWT 令牌管理 + bcrypt 密码哈希"""

import pytest
from app.core.security import hash_password, verify_password, create_access_token, decode_access_token


class TestPasswordHashing:
    """密码哈希 — bcrypt 加密和验证"""

    def test_正常密码_哈希后验证通过(self):
        """场景：正常密码 → 哈希后验证成功"""
        password = "123456"
        hashed = hash_password(password)

        assert hashed != password
        assert hashed.startswith("$2b$")
        assert verify_password(password, hashed) is True

    def test_错误密码_验证失败(self):
        """场景：错误密码 → 验证返回 False"""
        hashed = hash_password("correct_password")
        assert verify_password("wrong_password", hashed) is False

    def test_空密码_哈希后验证通过(self):
        """场景：空密码 → 仍能正常哈希和验证"""
        password = ""
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_相同密码两次哈希_结果不同(self):
        """场景：相同密码两次哈希 → 生成不同的哈希值（盐不同）"""
        password = "mypassword"
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        assert hash1 != hash2  # 不同的盐
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True

    def test_长密码_正常验证(self):
        """场景：50位长密码 → 正常哈希和验证"""
        password = "a" * 50
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_特殊字符密码_正常验证(self):
        """场景：包含特殊字符的密码 → 正常处理"""
        password = "P@ssw0rd!@#$%^&*()中文密码"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True


class TestJWTToken:
    """JWT 令牌 — 创建和验证"""

    def test_正常创建和解码_token(self):
        """场景：正常用户数据 → 创建 token 后能正确解码"""
        token = create_access_token({"sub": "1", "role": "admin"})
        assert token is not None
        assert len(token) > 20

        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "1"
        assert payload["role"] == "admin"

    def test_包含过期时间的_token(self):
        """场景：token 包含 exp 字段"""
        from datetime import timedelta
        token = create_access_token({"sub": "2"}, expires_delta=timedelta(hours=1))
        payload = decode_access_token(token)

        assert payload is not None
        assert "exp" in payload

    def test_无效_token_返回None(self):
        """场景：无效/伪造的 token → decode 返回 None"""
        payload = decode_access_token("invalid.token.here")
        assert payload is None

    def test_空字符串_token_返回None(self):
        """场景：空字符串 → decode 返回 None"""
        payload = decode_access_token("")
        assert payload is None

    def test_NOne_token_返回None(self):
        """场景：None → decode 返回 None"""
        payload = decode_access_token(None)
        assert payload is None

    def test_不同角色_token_携带正确角色(self):
        """场景：普通用户角色 → token 携带 user 角色"""
        token = create_access_token({"sub": "3", "role": "user"})
        payload = decode_access_token(token)

        assert payload is not None
        assert payload["role"] == "user"
