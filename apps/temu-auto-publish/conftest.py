"""
@PURPOSE: Pytest配置文件，配置测试环境和fixtures
@OUTLINE:
  - pytest_configure(): 配置pytest
  - pytest_asyncio_mode: 设置asyncio模式为auto
  - Mock fixtures: mock_page, mock_browser_manager, mock_openai_client
  - Data fixtures: sample_product_data, sample_excel_file
  - Integration fixtures: login_controller, miaoshou_controller
@DEPENDENCIES:
  - 外部: pytest, pytest-asyncio, openpyxl
  - 内部: tests.mocks
"""

import os
import tempfile

import pytest
import sys
from pathlib import Path
from typing import List, Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch

# 添加项目根目录到Python路径
app_root = Path(__file__).parent
if str(app_root) not in sys.path:
    sys.path.insert(0, str(app_root))

# 导入 Mock 类
from tests.mocks import (
    MockPage,
    MockLocator,
    MockBrowserManager,
    MockPlaywright,
    MockOpenAIClient,
)


def pytest_configure(config):
    """配置pytest."""
    # 标记注册
    config.addinivalue_line("markers", "asyncio: 标记异步测试")
    config.addinivalue_line("markers", "integration: 标记集成测试（需要浏览器环境）")
    config.addinivalue_line("markers", "slow: 标记慢速测试")


# 设置pytest-asyncio模式为auto，自动检测async测试函数
pytest_plugins = ("pytest_asyncio",)


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


# ============================================================
# Mock Fixtures - 用于单元测试，无需真实浏览器环境
# ============================================================


@pytest.fixture
def mock_page() -> MockPage:
    """提供模拟的 Playwright Page 对象.

    Returns:
        MockPage: 模拟页面对象
    """
    return MockPage()


@pytest.fixture
def mock_locator() -> MockLocator:
    """提供模拟的 Playwright Locator 对象.

    Returns:
        MockLocator: 模拟定位器对象
    """
    return MockLocator()


@pytest.fixture
def mock_browser_manager() -> MockBrowserManager:
    """提供模拟的 BrowserManager 对象.

    Returns:
        MockBrowserManager: 模拟浏览器管理器
    """
    return MockBrowserManager()


@pytest.fixture
def mock_playwright() -> MockPlaywright:
    """提供模拟的 Playwright 主对象.

    Returns:
        MockPlaywright: 模拟 Playwright 对象
    """
    return MockPlaywright()


@pytest.fixture
def mock_openai_client() -> MockOpenAIClient:
    """提供模拟的 OpenAI 客户端.

    Returns:
        MockOpenAIClient: 模拟 OpenAI 客户端
    """
    return MockOpenAIClient()


# ============================================================
# Data Fixtures - 提供测试数据
# ============================================================


@pytest.fixture
def sample_product_data() -> List[Dict[str, Any]]:
    """提供样例产品数据.

    Returns:
        List[Dict]: 5个产品的测试数据
    """
    return [
        {"keyword": "测试产品1", "model_number": "T001", "cost": 100.0, "stock": 50},
        {"keyword": "测试产品2", "model_number": "T002", "cost": 150.0, "stock": 100},
        {"keyword": "测试产品3", "model_number": "T003", "cost": 200.0, "stock": 75},
        {"keyword": "测试产品4", "model_number": "T004", "cost": 80.0, "stock": 200},
        {"keyword": "测试产品5", "model_number": "T005", "cost": 120.0, "stock": 150},
    ]


@pytest.fixture
def sample_single_product() -> Dict[str, Any]:
    """提供单个产品测试数据.

    Returns:
        Dict: 单个产品数据
    """
    return {
        "keyword": "药箱收纳盒",
        "model_number": "YX001",
        "cost": 15.0,
        "stock": 100,
        "title": "Large Medicine Box Organizer",
        "category": "Home & Garden",
    }


@pytest.fixture
def sample_excel_file(tmp_path) -> Path:
    """创建临时测试 Excel 文件.

    Args:
        tmp_path: pytest 提供的临时目录

    Returns:
        Path: Excel 文件路径
    """
    from openpyxl import Workbook

    file_path = tmp_path / "test_products.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "产品数据"

    # 添加表头
    headers = ["关键词", "型号", "成本", "库存", "标题"]
    ws.append(headers)

    # 添加测试数据
    test_data = [
        ["药箱收纳盒", "YX001", 15.0, 100, "Medicine Box Organizer"],
        ["厨房收纳架", "CF002", 25.0, 50, "Kitchen Storage Rack"],
        ["桌面整理盒", "ZM003", 12.0, 200, "Desktop Organizer Box"],
    ]
    for row in test_data:
        ws.append(row)

    wb.save(file_path)
    return file_path


@pytest.fixture
def sample_empty_excel_file(tmp_path) -> Path:
    """创建空的测试 Excel 文件（仅有表头）.

    Args:
        tmp_path: pytest 提供的临时目录

    Returns:
        Path: Excel 文件路径
    """
    from openpyxl import Workbook

    file_path = tmp_path / "empty_products.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.append(["关键词", "型号", "成本", "库存"])
    wb.save(file_path)
    return file_path


@pytest.fixture
def sample_selection_table_data() -> List[Dict[str, Any]]:
    """提供选品表测试数据.

    Returns:
        List[Dict]: 选品表数据
    """
    return [
        {
            "序号": 1,
            "关键词": "药箱收纳盒",
            "1688链接": "https://detail.1688.com/xxx",
            "成本": 15.0,
            "建议售价": 150.0,
            "供货价": 112.5,
        },
        {
            "序号": 2,
            "关键词": "厨房收纳架",
            "1688链接": "https://detail.1688.com/yyy",
            "成本": 25.0,
            "建议售价": 250.0,
            "供货价": 187.5,
        },
    ]


# ============================================================
# Helper Fixtures - 辅助工具
# ============================================================


@pytest.fixture
def temp_data_dir(tmp_path) -> Path:
    """创建临时数据目录结构.

    Args:
        tmp_path: pytest 提供的临时目录

    Returns:
        Path: 数据目录路径
    """
    data_dir = tmp_path / "data"
    (data_dir / "input").mkdir(parents=True)
    (data_dir / "output").mkdir(parents=True)
    (data_dir / "logs").mkdir(parents=True)
    (data_dir / "temp").mkdir(parents=True)
    return data_dir


@pytest.fixture
def mock_env_vars(monkeypatch):
    """设置测试环境变量.

    Args:
        monkeypatch: pytest 提供的环境修改工具
    """
    monkeypatch.setenv("MIAOSHOU_USERNAME", "test_user")
    monkeypatch.setenv("MIAOSHOU_PASSWORD", "test_password")
    monkeypatch.setenv("OPENAI_API_KEY", "test-api-key")
    monkeypatch.setenv("DEBUG_MODE", "true")
