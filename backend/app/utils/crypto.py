"""数据源密码加解密 — 基于 cryptography.fernet，key 从 JWT_SECRET 派生

- 不额外引入密钥管理，复用应用已有的 JWT_SECRET（不可变时加密结果稳定）
- 加密字段形如 "fernet:gAAAAA..."，可自解释，方便将来迁移/换 key
"""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings

_PREFIX = "fernet:"


def _get_fernet() -> Fernet:
    """从 JWT_SECRET 派生 Fernet key（SHA-256 → urlsafe_b64encode，32 字节）"""
    digest = hashlib.sha256(settings.JWT_SECRET.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_password(plain: str) -> str:
    """加密明文密码；空串/None 原样返回"""
    if not plain:
        return plain or ""
    token = _get_fernet().encrypt(plain.encode("utf-8"))
    return _PREFIX + token.decode("utf-8")


def decrypt_password(stored: str) -> str:
    """解密存储密码；非 fernet 前缀（历史明文）或解密失败时按原样返回并告警"""
    if not stored:
        return stored or ""
    if not stored.startswith(_PREFIX):
        print(f"[crypto] 警告: 密码非加密存储（缺少 {_PREFIX} 前缀），按明文返回")
        return stored
    try:
        token = stored[len(_PREFIX):].encode("utf-8")
        return _get_fernet().decrypt(token).decode("utf-8")
    except InvalidToken:
        print("[crypto] 警告: 密码解密失败（JWT_SECRET 可能已变更），按密文原样返回")
        return stored
