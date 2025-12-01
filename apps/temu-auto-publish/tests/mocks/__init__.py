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

from .browser_mock import MockPage, MockLocator, MockBrowserManager
from .playwright_mock import MockPlaywright, MockBrowser, MockBrowserContext
from .api_mock import MockOpenAIClient, MockOpenAIResponse
from .controller_mock import (
    MockLoginController,
    MockMiaoshouController,
    MockBatchEditController,
    MockPublishController,
    MockCollectionController,
    MockFirstEditController,
    MockCookieManager,
)
from .data_mock import (
    MockProductSelectionRow,
    MockSelectionTableReader,
    MockProductDataReader,
    MockPriceCalculator,
    MockPriceResult,
    MockDataConverter,
    MockTitleGenerator,
    MockExcelReader,
    MockMetricsCollector,
)

__all__ = [
    # Browser mocks
    "MockPage",
    "MockLocator",
    "MockBrowserManager",
    "MockPlaywright",
    "MockBrowser",
    "MockBrowserContext",
    # API mocks
    "MockOpenAIClient",
    "MockOpenAIResponse",
    # Controller mocks
    "MockLoginController",
    "MockMiaoshouController",
    "MockBatchEditController",
    "MockPublishController",
    "MockCollectionController",
    "MockFirstEditController",
    "MockCookieManager",
    # Data mocks
    "MockProductSelectionRow",
    "MockSelectionTableReader",
    "MockProductDataReader",
    "MockPriceCalculator",
    "MockPriceResult",
    "MockDataConverter",
    "MockTitleGenerator",
    "MockExcelReader",
    "MockMetricsCollector",
]
