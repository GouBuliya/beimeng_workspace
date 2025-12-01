"""
@PURPOSE: 安全工具模块,提供密码哈希和 JWT 令牌生成/验证功能
@OUTLINE:
  - verify_password(): 验证密码
  - get_password_hash(): 生成密码哈希
  - create_access_token(): 创建访问令牌
  - create_refresh_token(): 创建刷新令牌
  - decode_token(): 解码并验证令牌
@DEPENDENCIES:
  - 内部: app.core.config
  - 外部: passlib, jose, datetime
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from .config import get_settings

settings = get_settings()

# 密码哈希上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TokenPayload(BaseModel):
    """JWT 令牌载荷."""

    sub: str  # 用户 ID
    jti: str  # 令牌唯一 ID
    exp: datetime  # 过期时间
    iat: datetime  # 签发时间
    token_type: str  # 令牌类型: access / refresh


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码是否正确.

    Args:
        plain_password: 明文密码
        hashed_password: 哈希后的密码

    Returns:
        bool: 密码是否匹配
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """生成密码哈希.

    Args:
        password: 明文密码

    Returns:
        str: 哈希后的密码
    """
    return pwd_context.hash(password)


def create_access_token(user_id: str | uuid.UUID) -> tuple[str, str, datetime]:
    """创建访问令牌.

    Args:
        user_id: 用户 ID

    Returns:
        tuple[str, str, datetime]: (令牌, JTI, 过期时间)
    """
    jti = str(uuid.uuid4())
    now = datetime.now(UTC)
    expire = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)

    payload = {
        "sub": str(user_id),
        "jti": jti,
        "exp": expire,
        "iat": now,
        "token_type": "access",
    }

    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, jti, expire


def create_refresh_token(user_id: str | uuid.UUID) -> tuple[str, str, datetime]:
    """创建刷新令牌.

    Args:
        user_id: 用户 ID

    Returns:
        tuple[str, str, datetime]: (令牌, JTI, 过期时间)
    """
    jti = str(uuid.uuid4())
    now = datetime.now(UTC)
    expire = now + timedelta(days=settings.jwt_refresh_token_expire_days)

    payload = {
        "sub": str(user_id),
        "jti": jti,
        "exp": expire,
        "iat": now,
        "token_type": "refresh",
    }

    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, jti, expire


def decode_token(token: str) -> TokenPayload | None:
    """解码并验证令牌.

    Args:
        token: JWT 令牌字符串

    Returns:
        TokenPayload | None: 解码后的载荷,验证失败返回 None
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return TokenPayload(
            sub=payload["sub"],
            jti=payload["jti"],
            exp=datetime.fromtimestamp(payload["exp"], tz=UTC),
            iat=datetime.fromtimestamp(payload["iat"], tz=UTC),
            token_type=payload["token_type"],
        )
    except JWTError:
        return None
