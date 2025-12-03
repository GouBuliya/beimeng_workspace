"""调试 DOM 结构，查找产品 ID 提取方式."""
import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from playwright.async_api import async_playwright
from src.browser.cookie_manager import CookieManager


async def debug_dom():
    """调试 DOM 结构."""
    cookie_file = project_root.parent.parent / "data/temp/miaoshou_cookies.json"
    manager = CookieManager(str(cookie_file))
    cookies = manager.load_playwright_cookies()
    
    if not cookies:
        print("无法加载 Cookie")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        await context.add_cookies(cookies)
        
        page = await context.new_page()
        await page.goto("https://erp.91miaoshou.com/common_collect_box/items?tabPaneName=all")
        await page.wait_for_timeout(3000)
        
        # 调试 DOM 结构
        result = await page.evaluate("""() => {
            const debug = {
                scrollerExists: false,
                rowCount: 0,
                sampleRowText: '',
                sampleRowHTML: '',
                vueData: null,
                allMatches: []
            };
            
            // 检查 scroller
            const scroller = document.querySelector('.vue-recycle-scroller');
            debug.scrollerExists = !!scroller;
            
            // 检查行
            const rows = document.querySelectorAll('.vue-recycle-scroller__item-view');
            debug.rowCount = rows.length;
            
            if (rows.length > 0) {
                debug.sampleRowText = rows[0].textContent?.substring(0, 500);
                debug.sampleRowHTML = rows[0].innerHTML?.substring(0, 1000);
            }
            
            // 检查 Vue 数据
            if (scroller && scroller.__vue__) {
                const vue = scroller.__vue__;
                debug.vueData = {
                    hasItems: !!vue.items,
                    hasPool: !!vue.pool,
                    itemsLength: vue.items?.length || 0,
                    poolLength: vue.pool?.length || 0,
                    keys: Object.keys(vue).slice(0, 20)
                };
            }
            
            // 从页面文本中匹配
            const allText = document.body.innerText;
            const matches = [...allText.matchAll(/采集箱产品ID[:：]\s*(\d+)/g)];
            debug.allMatches = matches.slice(0, 5).map(m => m[1]);
            
            return debug;
        }""")
        
        print("=== DOM 调试信息 ===")
        print(f"Scroller 存在: {result['scrollerExists']}")
        print(f"行数: {result['rowCount']}")
        print(f"样本行文本: {result['sampleRowText'][:200] if result['sampleRowText'] else 'N/A'}...")
        print(f"Vue 数据: {result['vueData']}")
        print(f"页面文本匹配: {result['allMatches']}")
        
        await browser.close()


if __name__ == "__main__":
    asyncio.run(debug_dom())
