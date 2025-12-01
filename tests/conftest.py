"""
@PURPOSE: Pytest 配置和通用 fixtures
@OUTLINE:
  - mock_auth_client: Mock 认证客户端,用于测试环境
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# 添加 apps/temu-auto-publish 到路径
APP_ROOT = Path(__file__).resolve().parents[1] / "apps" / "temu-auto-publish"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))


@pytest.fixture(autouse=True)
def mock_auth_client(monkeypatch):
    """自动 mock 认证客户端,让所有测试通过认证.

    这个 fixture 会自动应用到所有测试中,避免每个测试都需要单独 mock.
    """
    # 导入需要 mock 的模块
    from web_panel import auth_client
    from web_panel.auth_client import TokenData

    # 创建 mock 认证客户端
    mock_client = MagicMock()

    # Mock health_check - 始终返回健康
    mock_client.health_check = AsyncMock(return_value=True)

    # Mock login - 只接受正确的测试密码
    async def mock_login(username: str, password: str) -> TokenData | None:
        # 检查密码是否正确（与 TEST_ADMIN_PASSWORD 匹配）
        if password == "bm123456789":  # TEST_ADMIN_PASSWORD
            return TokenData(
                access_token="mock_token",
                refresh_token="mock_refresh_token",
                token_type="bearer",
                expires_in=3600,
            )
        return None  # 密码错误返回 None

    mock_client.login = mock_login

    # Mock logout
    mock_client.logout = AsyncMock(return_value=True)

    # Mock verify_token
    async def mock_verify(token: str):
        from web_panel.auth_client import VerifyResult

        return VerifyResult(
            valid=True,
            user_id="test_user",
            username="test",
            is_superuser=True,
        )

    mock_client.verify_token = mock_verify

    # Mock get_user_info
    async def mock_get_user_info(token: str):
        from web_panel.auth_client import UserInfo

        return UserInfo(
            user_id="test_user",
            username="test",
            is_superuser=True,
        )

    mock_client.get_user_info = mock_get_user_info

    # 替换 get_auth_client 函数
    # 需要在 auth_client 模块和 api 模块中都替换
    monkeypatch.setattr(auth_client, "get_auth_client", lambda: mock_client)

    # 同时替换 api 模块中的引用
    try:
        from web_panel import api

        monkeypatch.setattr(api, "get_auth_client", lambda: mock_client)
    except ImportError:
        pass  # 如果 api 模块还没加载,跳过

    return mock_client
