"""
@PURPOSE: 使用调试工具在同步模式下运行 Playwright, 便于快速验证脚本
@OUTLINE:
  - async def open_example(): 打开示例站点并打印标题
  - def main(): 通过 run_with_optional_syncify 同步执行调试脚本
@DEPENDENCIES:
  - 内部: src.browser.browser_manager, src.browser.debug_tools
  - 外部: loguru
"""

from __future__ import annotations

from loguru import logger
from src.browser.browser_manager import BrowserManager
from src.browser.debug_tools import run_with_optional_syncer


async def open_example() -> None:
    """打开 example.com 并输出页面标题, 用于验证浏览器环境."""

    async with BrowserManager() as manager:
        page = manager.page
        assert page is not None, "BrowserManager 未能创建 Playwright 页面"

        await page.goto("https://example.com", wait_until="domcontentloaded")
        title = await page.title()
        logger.info("示例页面标题: {}", title)


def main() -> None:
    """入口函数, 支持同步/异步调试模式."""

    run_with_optional_syncer(open_example)


if __name__ == "__main__":
    main()
