"""
@PURPOSE: Pytest配置文件，配置测试环境和fixtures
@OUTLINE:
  - pytest_configure(): 配置pytest
  - pytest_asyncio_mode: 设置asyncio模式为auto
  - login_controller: 登录控制器fixture
  - miaoshou_controller: 妙手控制器fixture
@DEPENDENCIES:
  - 外部: pytest, pytest-asyncio
"""

import os

import pytest
import sys
from pathlib import Path

# 添加项目根目录到Python路径
app_root = Path(__file__).parent
if str(app_root) not in sys.path:
    sys.path.insert(0, str(app_root))


def pytest_configure(config):
    """配置pytest."""
    # 标记注册
    config.addinivalue_line(
        "markers", "asyncio: 标记异步测试"
    )
    config.addinivalue_line(
        "markers", "integration: 标记集成测试（需要浏览器环境）"
    )
    config.addinivalue_line(
        "markers", "slow: 标记慢速测试"
    )


# 设置pytest-asyncio模式为auto，自动检测async测试函数
pytest_plugins = ('pytest_asyncio',)


@pytest.fixture(scope="session")
def event_loop_policy():
    """设置事件循环策略."""
    import asyncio
    return asyncio.get_event_loop_policy()


@pytest.fixture
async def login_controller():
    """登录控制器 fixture.
    
    提供已登录的 LoginController 实例，用于集成测试。
    测试结束后自动清理资源。
    
    Yields:
        LoginController: 已登录的控制器实例
    """
    from src.browser.login_controller import LoginController
    
    controller = LoginController()
    await controller.browser_manager.start()
    
    # 执行登录
    username = os.getenv("MIAOSHOU_USERNAME")
    password = os.getenv("MIAOSHOU_PASSWORD")
    
    if not username or not password:
        pytest.skip("未设置 MIAOSHOU_USERNAME 或 MIAOSHOU_PASSWORD 环境变量")
    
    success = await controller.login(username, password)
    if not success:
        await controller.browser_manager.close()
        pytest.fail("登录失败")
    
    yield controller
    
    # 清理
    await controller.browser_manager.close()


@pytest.fixture
async def miaoshou_controller(login_controller):
    """妙手控制器 fixture（依赖登录控制器）.
    
    提供 MiaoshouController 实例，使用已登录的 login_controller。
    
    Args:
        login_controller: 登录控制器 fixture
    
    Yields:
        MiaoshouController: 妙手控制器实例
    """
    from src.browser.miaoshou_controller import MiaoshouController
    
    controller = MiaoshouController()
    yield controller


