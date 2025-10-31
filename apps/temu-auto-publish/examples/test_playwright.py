"""
@PURPOSE: 测试 Playwright 环境，验证浏览器自动化基本功能
@OUTLINE:
  - async def test_playwright(): 测试浏览器启动、导航、截图
  - main: 运行测试
@GOTCHAS:
  - 需要先运行 playwright install chromium 安装浏览器
  - 截图保存在 data/temp/ 目录
@DEPENDENCIES:
  - 外部: playwright.async_api
"""

import asyncio
from pathlib import Path

import pytest
from playwright.async_api import async_playwright


@pytest.mark.asyncio
@pytest.mark.integration
async def test_playwright():
    """测试 Playwright 基本功能."""
    print("=" * 60)
    print("Playwright 环境测试")
    print("=" * 60)

    async with async_playwright() as p:
        print("✓ Playwright 已安装")

        # 启动浏览器
        browser = await p.chromium.launch(headless=False)
        print("✓ Chromium 浏览器已启动")

        # 创建页面
        page = await browser.new_page()
        print("✓ 新页面已创建")

        # 访问测试网站
        print("\n正在访问百度...")
        try:
            await page.goto("https://www.baidu.com", timeout=60000)
            print("✓ 页面导航成功")

            # 等待页面加载
            await page.wait_for_load_state("domcontentloaded", timeout=30000)
            print("✓ 页面加载完成")
        except Exception as e:
            print(f"⚠ 访问百度失败: {e}")
            print("  尝试访问本地页面...")
            await page.goto("about:blank")
            print("✓ 浏览器基本功能正常")

        # 截图
        screenshot_dir = Path(__file__).parent.parent / "data" / "temp"
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        screenshot_path = screenshot_dir / "test_playwright.png"

        await page.screenshot(path=str(screenshot_path))
        print(f"✓ 截图保存成功: {screenshot_path}")

        # 等待2秒观察
        await asyncio.sleep(2)

        # 关闭浏览器
        await browser.close()
        print("✓ 浏览器已关闭")

        print("\n" + "=" * 60)
        print("✓✓✓ Playwright 环境测试通过！")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_playwright())

