"""
@PURPOSE: Pytest配置文件，配置测试环境和fixtures
@OUTLINE:
  - pytest_configure(): 配置pytest
  - pytest_asyncio_mode: 设置asyncio模式为auto
@DEPENDENCIES:
  - 外部: pytest, pytest-asyncio
"""

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

