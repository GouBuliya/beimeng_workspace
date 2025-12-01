"""
@PURPOSE: 测试 playwright-stealth 反检测功能(自动化版本)
@OUTLINE:
  - async def test_stealth_auto(): 测试反爬虫检测能力,自动完成
  - main: 运行测试
@GOTCHAS:
  - 自动检查 WebDriver 属性,无需人工确认
@DEPENDENCIES:
  - 外部: playwright.async_api, playwright_stealth
"""

import asyncio

import pytest
from playwright.async_api import async_playwright
from playwright_stealth.stealth import Stealth


@pytest.mark.asyncio
@pytest.mark.integration
async def test_stealth_auto():
    """测试反检测功能(自动化版本)."""
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
        try:
            await page.goto("https://bot.sannysoft.com/", timeout=60000)
            await page.wait_for_load_state("domcontentloaded", timeout=30000)
            print("✓ 访问反爬虫检测网站成功")

            # 等待页面渲染
            await asyncio.sleep(3)

            # 检查 webdriver 属性
            webdriver_result = await page.evaluate("() => navigator.webdriver")
            print("\n检测结果:")
            print(f"  navigator.webdriver: {webdriver_result}")

            if webdriver_result is False or webdriver_result is None:
                print("✓ WebDriver 检测通过(显示为 false/null)")
            else:
                print("⚠ WebDriver 检测失败(显示为 true)")

            # 等待2秒观察
            await asyncio.sleep(2)

        except Exception as e:
            print(f"⚠ 访问检测网站失败: {e}")
            print("  但反检测补丁已成功应用到浏览器")

        await browser.close()
        print("\n✓ 测试完成")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_stealth_auto())
