"""
@PURPOSE: 认证服务客户端，用于与远程认证服务器通信
@OUTLINE:
  - class AuthClient: 认证服务客户端类
    - login(): 用户登录
    - logout(): 用户登出
    - verify_token(): 验证令牌
    - refresh_token(): 刷新令牌
    - get_user_info(): 获取用户信息
@GOTCHAS:
  - 需要配置 AUTH_SERVER_URL 环境变量指向认证服务器
  - 令牌存储在内存中，重启后需要重新登录
@DEPENDENCIES:
  - 外部: httpx, pydantic
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from loguru import logger
from pydantic import BaseModel


class TokenData(BaseModel):
    """令牌数据."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserInfo(BaseModel):
    """用户信息."""

    user_id: str
    username: str
    is_superuser: bool


class VerifyResult(BaseModel):
    """验证结果."""

    valid: bool
    user_id: str | None = None
    username: str | None = None
    is_superuser: bool = False
    message: str | None = None


class AuthClient:
    """认证服务客户端."""

    def __init__(self, base_url: str | None = None, timeout: float = 10.0) -> None:
        """初始化认证客户端.

        Args:
            base_url: 认证服务器地址，默认从环境变量读取
            timeout: 请求超时时间（秒）
        """
        self.base_url = base_url or os.environ.get(
            "AUTH_SERVER_URL", "http://localhost:8001"
        )
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
            )
        return self._client

    async def close(self) -> None:
        """关闭客户端连接."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def login(self, username: str, password: str) -> TokenData | None:
        """用户登录.

        Args:
            username: 用户名
            password: 密码

        Returns:
            TokenData | None: 令牌数据，登录失败返回 None
        """
        try:
            client = await self._get_client()
            response = await client.post(
                "/auth/login",
                data={"username": username, "password": password},
            )

            if response.status_code == 200:
                data = response.json()
                logger.info(f"用户登录成功: username={username}")
                return TokenData(**data)

            logger.warning(f"用户登录失败: username={username}, status={response.status_code}")
            return None

        except Exception as e:
            logger.error(f"登录请求失败: {e}")
            return None

    async def logout(self, access_token: str) -> bool:
        """用户登出.

        Args:
            access_token: 访问令牌

        Returns:
            bool: 是否成功
        """
        try:
            client = await self._get_client()
            response = await client.post(
                "/auth/logout",
                headers={"Authorization": f"Bearer {access_token}"},
            )

            if response.status_code == 200:
                logger.info("用户登出成功")
                return True

            logger.warning(f"用户登出失败: status={response.status_code}")
            return False

        except Exception as e:
            logger.error(f"登出请求失败: {e}")
            return False

    async def verify_token(self, access_token: str) -> VerifyResult:
        """验证令牌.

        Args:
            access_token: 访问令牌

        Returns:
            VerifyResult: 验证结果
        """
        try:
            client = await self._get_client()
            response = await client.post(
                "/auth/verify",
                json={"token": access_token},
            )

            if response.status_code == 200:
                data = response.json()
                return VerifyResult(**data)

            return VerifyResult(valid=False, message="验证请求失败")

        except Exception as e:
            logger.error(f"验证请求失败: {e}")
            return VerifyResult(valid=False, message=str(e))

    async def refresh_token(self, refresh_token: str) -> TokenData | None:
        """刷新令牌.

        Args:
            refresh_token: 刷新令牌

        Returns:
            TokenData | None: 新的令牌数据
        """
        try:
            client = await self._get_client()
            response = await client.post(
                "/auth/refresh",
                json={"refresh_token": refresh_token},
            )

            if response.status_code == 200:
                data = response.json()
                logger.info("令牌刷新成功")
                return TokenData(**data)

            logger.warning(f"令牌刷新失败: status={response.status_code}")
            return None

        except Exception as e:
            logger.error(f"刷新请求失败: {e}")
            return None

    async def get_user_info(self, access_token: str) -> UserInfo | None:
        """获取用户信息.

        Args:
            access_token: 访问令牌

        Returns:
            UserInfo | None: 用户信息
        """
        try:
            client = await self._get_client()
            response = await client.get(
                "/auth/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )

            if response.status_code == 200:
                data = response.json()
                return UserInfo(
                    user_id=str(data["id"]),
                    username=data["username"],
                    is_superuser=data["is_superuser"],
                )

            return None

        except Exception as e:
            logger.error(f"获取用户信息失败: {e}")
            return None

    async def health_check(self) -> bool:
        """健康检查.

        Returns:
            bool: 认证服务器是否可用
        """
        try:
            client = await self._get_client()
            response = await client.get("/health")
            return response.status_code == 200
        except Exception:
            return False


# 全局客户端实例
_auth_client: AuthClient | None = None


def get_auth_client() -> AuthClient:
    """获取认证客户端实例.

    Returns:
        AuthClient: 认证客户端
    """
    global _auth_client
    if _auth_client is None:
        _auth_client = AuthClient()
    return _auth_client


async def close_auth_client() -> None:
    """关闭认证客户端."""
    global _auth_client
    if _auth_client:
        await _auth_client.close()
        _auth_client = None

