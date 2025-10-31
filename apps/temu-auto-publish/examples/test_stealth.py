"""
@PURPOSE: 测试 playwright-stealth 反检测功能
@OUTLINE:
  - async def test_stealth(): 测试反爬虫检测能力
  - main: 运行测试
@GOTCHAS:
  - 需要人工查看页面确认 WebDriver 检测结果
  - WebDriver 应该显示为 false 表示通过反检测
@DEPENDENCIES:
  - 外部: playwright.async_api, playwright_stealth
"""

import asyncio

import pytest
from playwright.async_api import async_playwright
from playwright_stealth.stealth import Stealth


@pytest.mark.asyncio
@pytest.mark.integration
async def test_stealth():
    """测试反检测功能."""
    print("=" * 60)
    print("Playwright Stealth 反检测测试")
    print("=" * 60)

    # 创建 Stealth 实例
    stealth_config = Stealth()

    async with async_playwright() as p:
        # 启动浏览器
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        # 应用反检测补丁
        await stealth_config.apply_stealth_async(page)
        print("✓ 反检测补丁已应用")

        # 访问反爬虫检测网站
        print("\n正在访问反爬虫检测网站...")
        await page.goto("https://bot.sannysoft.com/")
        await page.wait_for_load_state("networkidle")

        print("✓ 访问反爬虫检测网站成功")
        print("\n" + "=" * 60)
        print("请手动查看浏览器页面：")
        print("  - WebDriver: 应该显示 false（通过反检测）")
        print("  - Chrome: 应该显示正常")
        print("  - Permissions: 应该显示正常")
        print("=" * 60)

        # 自动等待5秒（pytest环境无法交互）
        print("\n等待5秒以便查看...")
        await page.wait_for_timeout(5000)

        await browser.close()
        print("\n✓ 测试完成")


if __name__ == "__main__":
    asyncio.run(test_stealth())

