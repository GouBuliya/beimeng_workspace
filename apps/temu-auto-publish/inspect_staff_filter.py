"""
@PURPOSE: 检查采集箱页面的人员筛选控件
@OUTLINE:
  - 连接到浏览器
  - 截图查看页面结构
  - 输出所有可能的筛选控件
"""
import asyncio
from playwright.async_api import async_playwright
from pathlib import Path
import os
from dotenv import load_dotenv

async def inspect_staff_filter():
    """检查人员筛选控件"""
    
    # 加载环境变量
    load_dotenv()
    username = os.getenv("MIAOSHOU_USERNAME") or os.getenv("TEMU_USERNAME")
    password = os.getenv("MIAOSHOU_PASSWORD") or os.getenv("TEMU_PASSWORD")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        # 登录
        print("正在登录...")
        await page.goto("https://erp.91miaoshou.com/sub_account/users")
        await page.fill("input[name='mobile']", username)
        await page.fill("input[name='password']", password)
        await page.click("button:has-text('登录')")
        await page.wait_for_timeout(3000)
        
        # 导航到采集箱
        print("导航到采集箱...")
        await page.goto("https://erp.91miaoshou.com/common_collect_box/items")
        await page.wait_for_timeout(3000)
        
        # 关闭弹窗
        try:
            await page.click("text='我知道了'", timeout=2000)
        except:
            pass
        
        # 截图
        screenshot_path = Path("debug/staff_filter_page.png")
        screenshot_path.parent.mkdir(exist_ok=True)
        await page.screenshot(path=str(screenshot_path), full_page=True)
        print(f"✓ 截图已保存: {screenshot_path}")
        
        # 查找所有可能的筛选控件
        print("\n========== 查找筛选控件 ==========")
        
        # 1. 查找所有 select 元素
        selects = await page.locator("select").all()
        print(f"\n找到 {len(selects)} 个 <select> 元素:")
        for i, select in enumerate(selects):
            try:
                text = await select.inner_text()
                print(f"  [{i}] {text[:100]}")
            except:
                pass
        
        # 2. 查找所有包含"人员"、"采集人"的元素
        keywords = ["人员", "采集人", "创建人", "收录人"]
        for keyword in keywords:
            elements = await page.locator(f"*:has-text('{keyword}')").all()
            print(f"\n找到 {len(elements)} 个包含'{keyword}'的元素:")
            for i, elem in enumerate(elements[:5]):  # 只显示前5个
                try:
                    tag = await elem.evaluate("el => el.tagName")
                    classes = await elem.evaluate("el => el.className")
                    print(f"  [{i}] <{tag}> class='{classes[:100]}'")
                except:
                    pass
        
        # 3. 查找所有下拉框类型的控件
        dropdowns = await page.locator(".jx-select, .el-select, [class*='select']").all()
        print(f"\n找到 {len(dropdowns)} 个下拉框控件:")
        for i, dropdown in enumerate(dropdowns[:10]):  # 只显示前10个
            try:
                classes = await dropdown.evaluate("el => el.className")
                text = await dropdown.inner_text()
                print(f"  [{i}] {classes[:80]} | text: {text[:50]}")
            except:
                pass
        
        # 4. 输出页面的 HTML 结构（搜索区域）
        print("\n========== 搜索区域 HTML ==========")
        try:
            search_area = await page.locator(".search-box, .filter-box, [class*='search'], [class*='filter']").first.inner_html()
            html_path = Path("debug/search_area.html")
            html_path.write_text(search_area, encoding="utf-8")
            print(f"✓ 搜索区域HTML已保存: {html_path}")
        except Exception as e:
            print(f"无法获取搜索区域: {e}")
        
        print("\n等待60秒，你可以手动检查页面...")
        await page.wait_for_timeout(60000)
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(inspect_staff_filter())

