"""
@PURPOSE: 测试 Mock 模块
@OUTLINE:
  - MockPage: 模拟 Playwright Page 对象
  - MockLocator: 模拟 Playwright Locator 对象
  - MockBrowserManager: 模拟 BrowserManager
  - MockOpenAIClient: 模拟 OpenAI API 客户端
  - Controller Mocks: 各种控制器 Mock
  - Data Mocks: 数据处理模块 Mock
@DEPENDENCIES:
  - 外部: unittest.mock
"""

from .api_mock import MockOpenAIClient, MockOpenAIResponse
from .browser_mock import MockBrowserManager, MockLocator, MockPage
from .controller_mock import (
    MockBatchEditController,
    MockCollectionController,
    MockCookieManager,
    MockFirstEditController,
    MockLoginController,
    MockMiaoshouController,
    MockPublishController,
)
from .data_mock import (
    MockDataConverter,
    MockExcelReader,
    MockMetricsCollector,
    MockPriceCalculator,
    MockPriceResult,
    MockProductDataReader,
    MockProductSelectionRow,
    MockSelectionTableReader,
    MockTitleGenerator,
)
from .playwright_mock import MockBrowser, MockBrowserContext, MockPlaywright

__all__ = [
    "MockBatchEditController",
    "MockBrowser",
    "MockBrowserContext",
    "MockBrowserManager",
    "MockCollectionController",
    "MockCookieManager",
    "MockDataConverter",
    "MockExcelReader",
    "MockFirstEditController",
    "MockLocator",
    # Controller mocks
    "MockLoginController",
    "MockMetricsCollector",
    "MockMiaoshouController",
    # API mocks
    "MockOpenAIClient",
    "MockOpenAIResponse",
    # Browser mocks
    "MockPage",
    "MockPlaywright",
    "MockPriceCalculator",
    "MockPriceResult",
    "MockProductDataReader",
    # Data mocks
    "MockProductSelectionRow",
    "MockPublishController",
    "MockSelectionTableReader",
    "MockTitleGenerator",
]
