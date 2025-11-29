"""
@PURPOSE: 搜索采集控制器，使用Playwright实现站内搜索和商品采集
@OUTLINE:
  - class SearchController: 搜索采集控制器主类
  - async def search_and_collect(): 搜索并采集商品链接
  - async def _navigate_to_search(): 导航到搜索页
  - async def _input_and_search(): 输入关键词并搜索
  - async def _wait_for_results(): 等待搜索结果
  - async def _extract_products(): 提取商品信息
@GOTCHAS:
  - 搜索结果加载需要等待网络空闲
  - 商品链接提取需要处理动态加载
  - 建议添加随机延迟避免被检测
@DEPENDENCIES:
  - 内部: .browser_manager
  - 外部: playwright
@RELATED: browser_manager.py, edit_controller.py
"""

import asyncio
import random
from datetime import datetime

from loguru import logger

from ..models.result import SearchResult
from ..utils.page_load_decorator import wait_network_idle
from .browser_manager import BrowserManager


class SearchController:
    """搜索采集控制器.

    负责在 Temu 后台搜索商品并采集链接。

    Attributes:
        browser_manager: 浏览器管理器实例
        base_url: Temu 卖家后台基础 URL

    Examples:
        >>> controller = SearchController(browser_manager)
        >>> result = await controller.search_and_collect("智能手表", 5)
        >>> len(result.links)
        5
    """

    def __init__(self, browser_manager: BrowserManager):
        """初始化控制器.

        Args:
            browser_manager: 浏览器管理器实例
        """
        self.browser_manager = browser_manager
        self.base_url = "https://seller.temu.com"
        logger.info("搜索控制器已初始化")

    async def search_and_collect(
        self, product_id: str, keyword: str, collect_count: int = 5
    ) -> SearchResult:
        """搜索并采集商品链接.

        完整流程：导航 → 搜索 → 等待结果 → 提取商品信息

        Args:
            product_id: 对应的产品ID
            keyword: 搜索关键词
            collect_count: 采集数量，默认5

        Returns:
            SearchResult: 搜索采集结果

        Raises:
            RuntimeError: 如果浏览器未启动或搜索失败

        Examples:
            >>> result = await controller.search_and_collect("P001", "智能手表", 5)
            >>> result.status
            'success'
        """
        logger.info("=" * 60)
        logger.info(f"开始搜索采集: {keyword}")
        logger.info("=" * 60)

        page = self.browser_manager.page
        if not page:
            raise RuntimeError("浏览器未启动")

        result = SearchResult(product_id=product_id, keyword=keyword, status="pending")

        try:
            # 1. 导航到搜索页面
            await self._navigate_to_search()

            # 2. 输入关键词并搜索
            await self._input_and_search(keyword)

            # 3. 等待搜索结果加载
            await self._wait_for_results()

            # 4. 提取商品信息
            products = await self._extract_products(collect_count)

            result.links = products
            result.count = len(products)
            result.status = "success"

            logger.success(f"✓ 搜索采集成功: {result.count} 个商品")

            # 截图保存结果
            screenshot_path = f"data/temp/screenshots/search_{keyword}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            await self.browser_manager.screenshot(screenshot_path)

        except Exception as e:
            logger.error(f"✗ 搜索采集失败: {e}")
            result.status = "failed"

            # 错误截图
            try:
                screenshot_path = f"data/temp/screenshots/search_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                await self.browser_manager.screenshot(screenshot_path)
            except:
                pass

        return result

    async def _navigate_to_search(self) -> None:
        """导航到搜索页面.

        导航到 Temu 卖家后台的商品搜索页面。

        Raises:
            Exception: 如果导航失败
        """
        page = self.browser_manager.page

        # TODO: 根据实际的 Temu 后台结构调整 URL
        # 这里需要根据实际页面确定搜索页面的 URL
        search_url = f"{self.base_url}/goods/search"  # 示例URL，需要调整

        logger.info(f"导航到搜索页: {search_url}")
        await page.goto(search_url, wait_until="networkidle")

        # 等待页面稳定
        await asyncio.sleep(1 + random.random())  # 随机延迟 1-2 秒

    async def _input_and_search(self, keyword: str) -> None:
        """输入关键词并执行搜索.

        Args:
            keyword: 搜索关键词

        Raises:
            Exception: 如果输入或搜索失败
        """
        page = self.browser_manager.page

        logger.info(f"输入关键词: {keyword}")

        # TODO: 根据实际页面结构调整选择器
        # 定位搜索输入框（需要根据实际页面调整选择器）
        search_input = page.locator(
            'input[type="text"][placeholder*="搜索"], input[name*="search"], input[class*="search"]'
        ).first

        # 清空并输入关键词
        await search_input.clear()
        await search_input.fill(keyword)

        # 模拟真实用户输入，添加随机延迟
        await asyncio.sleep(0.5 + random.random() * 0.5)

        # 点击搜索按钮或按回车
        search_button = page.locator('button:has-text("搜索"), button[type="submit"]').first

        try:
            await search_button.click()
        except:
            # 如果没有搜索按钮，尝试按回车
            await search_input.press("Enter")

        logger.debug("已触发搜索")

    async def _wait_for_results(self, timeout: int = 30000) -> None:
        """等待搜索结果加载.

        Args:
            timeout: 超时时间（毫秒），默认30秒

        Raises:
            Exception: 如果等待超时
        """
        page = self.browser_manager.page

        logger.info("等待搜索结果加载...")

        # TODO: 根据实际页面结构调整选择器
        # 等待商品列表容器出现
        try:
            await page.wait_for_selector(
                '[class*="product-list"], [class*="goods-list"], .product-item', timeout=timeout
            )

            # 等待网络空闲
            await wait_network_idle(page, context=" [search results]")

            # 额外等待，确保动态内容加载完成
            await asyncio.sleep(2 + random.random())

            logger.debug("✓ 搜索结果已加载")

        except Exception as e:
            logger.warning(f"等待搜索结果超时: {e}")
            # 尝试继续，可能是选择器问题

    async def _extract_products(self, count: int) -> list[dict[str, str]]:
        """提取商品信息.

        从搜索结果页面提取指定数量的商品信息。

        Args:
            count: 需要采集的商品数量

        Returns:
            商品信息列表，每个元素包含 url, title, price 等字段

        Raises:
            Exception: 如果提取失败
        """
        page = self.browser_manager.page

        logger.info(f"提取商品信息 (目标: {count} 个)")

        products = []

        # TODO: 根据实际页面结构调整选择器
        # 这里需要根据实际的 Temu 后台商品列表结构来定位

        # 示例实现（需要根据实际页面调整）:
        try:
            # 定位商品项
            product_items = page.locator('.product-item, [class*="goods-item"]')

            # 获取商品数量
            total_count = await product_items.count()
            logger.debug(f"找到 {total_count} 个商品")

            # 提取指定数量
            actual_count = min(count, total_count)

            for i in range(actual_count):
                try:
                    item = product_items.nth(i)

                    # 提取商品信息
                    # 注意：以下选择器需要根据实际页面结构调整
                    title_elem = item.locator('[class*="title"], h3, h4').first
                    price_elem = item.locator('[class*="price"], .price').first
                    link_elem = item.locator("a").first

                    # 获取文本和链接
                    title = (
                        await title_elem.text_content()
                        if await title_elem.count() > 0
                        else "未知标题"
                    )
                    price = (
                        await price_elem.text_content()
                        if await price_elem.count() > 0
                        else "未知价格"
                    )
                    url = (
                        await link_elem.get_attribute("href") if await link_elem.count() > 0 else ""
                    )

                    # 处理相对链接
                    if url and not url.startswith("http"):
                        url = f"{self.base_url}{url}"

                    products.append(
                        {"url": url, "title": title.strip(), "price": price.strip(), "index": i + 1}
                    )

                    logger.debug(f"  [{i + 1}] {title[:30]}...")

                except Exception as e:
                    logger.warning(f"提取第 {i + 1} 个商品失败: {e}")
                    continue

            logger.success(f"✓ 成功提取 {len(products)} 个商品")

        except Exception as e:
            logger.error(f"提取商品信息失败: {e}")
            # 返回空列表，让调用者决定如何处理

        return products


# 测试代码
if __name__ == "__main__":
    import asyncio

    from .login_controller import LoginController

    async def test():
        """测试搜索采集功能."""
        # 初始化
        controller = LoginController()

        # 登录
        success = await controller.login("test_user", "test_pass", headless=False)
        if not success:
            logger.error("登录失败，无法测试搜索")
            return

        # 创建搜索控制器
        search_controller = SearchController(controller.browser_manager)

        # 执行搜索
        result = await search_controller.search_and_collect(
            product_id="P001", keyword="智能手表", collect_count=5
        )

        logger.info("\n搜索结果:")
        logger.info(f"  状态: {result.status}")
        logger.info(f"  采集数量: {result.count}")
        for link in result.links:
            logger.info(f"    - {link['title']}")

        # 关闭浏览器
        await controller.browser_manager.close()

    asyncio.run(test())
