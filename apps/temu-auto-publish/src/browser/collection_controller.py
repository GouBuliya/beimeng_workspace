"""
@PURPOSE: 实现商品采集功能（SOP步骤1-3）
@OUTLINE:
  - class CollectionController: 商品采集控制器
  - async def visit_store(): 访问前端店铺
  - async def search_products(): 站内搜索同款商品
  - async def collect_links(): 一次性采集5个同款商品链接
  - async def add_to_collection_box(): 添加到采集箱
@DEPENDENCIES:
  - 内部: browser.browser_manager, utils.logger_setup
  - 外部: playwright
@RELATED: miaoshou_controller.py, first_edit_controller.py
"""

import json
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger
from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from src.browser.browser_manager import BrowserManager


class CollectionController:
    """商品采集控制器（SOP步骤1-3）.
    
    负责：
    - 访问Temu前端店铺
    - 站内搜索同款商品
    - 采集符合要求的商品链接
    - 添加到妙手采集箱
    
    Examples:
        >>> ctrl = CollectionController()
        >>> await ctrl.visit_store(page)
        >>> links = await ctrl.search_and_collect(page, "药箱收纳盒", count=5)
    """
    
    def __init__(
        self,
        config_path: Optional[str] = None,
    ):
        """初始化采集控制器.
        
        Args:
            config_path: 选择器配置文件路径
            
        Examples:
            >>> ctrl = CollectionController()
            >>> ctrl = CollectionController("config/collection_selectors.json")
        """
        self.config_path = config_path or str(
            Path(__file__).parent.parent.parent / "config" / "collection_selectors.json"
        )
        self.selectors = self._load_selectors()
        logger.info("采集控制器初始化（SOP步骤1-3）")
    
    def _load_selectors(self) -> Dict:
        """加载选择器配置.
        
        Returns:
            选择器字典
            
        Examples:
            >>> selectors = ctrl._load_selectors()
            >>> print(selectors.keys())
        """
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                selectors = json.load(f)
            logger.debug(f"选择器配置已加载: {self.config_path}")
            return selectors
        except FileNotFoundError:
            logger.warning(f"选择器配置文件不存在: {self.config_path}，使用默认选择器")
            return self._get_default_selectors()
    
    def _get_default_selectors(self) -> Dict:
        """获取默认选择器.
        
        Returns:
            默认选择器字典
        """
        return {
            "store": {
                "visit_button": "button:has-text('一键访问店铺'), a:has-text('访问店铺')",
                "search_input": "input[type='search'], input[placeholder*='搜索']",
                "search_button": "button:has-text('搜索'), button[type='submit']"
            },
            "product": {
                "item_card": ".product-card, .item-card, [data-product-id]",
                "product_link": "a[href*='/product/'], a[href*='/goods/']",
                "product_title": ".title, .product-title, h3",
                "product_price": ".price, .product-price",
                "add_to_collection_btn": "button:has-text('采集'), button:has-text('加入采集箱')"
            },
            "collection_box": {
                "miaoshou_extension": ".miaoshou-extension, #miaoshou-plugin",
                "add_button": "button:has-text('添加到采集箱'), .add-to-collection"
            }
        }
    
    async def visit_store(self, page: Page) -> bool:
        """访问前端店铺（SOP步骤1）.
        
        在Temu商家后台首页点击"一键访问店铺"。
        
        Args:
            page: Playwright页面对象
            
        Returns:
            是否成功访问店铺
            
        Examples:
            >>> await ctrl.visit_store(page)
            True
        """
        logger.info("============================================================")
        logger.info("【SOP步骤1】访问前端店铺")
        logger.info("============================================================")
        
        try:
            store_config = self.selectors.get("store", {})
            visit_btn_selector = store_config.get(
                "visit_button",
                "button:has-text('一键访问店铺'), a:has-text('访问店铺')"
            )
            
            # 查找访问店铺按钮
            logger.debug("查找'一键访问店铺'按钮...")
            visit_btn_count = await page.locator(visit_btn_selector).count()
            
            if visit_btn_count == 0:
                logger.warning("⚠️ 未找到'一键访问店铺'按钮")
                # 可能已经在店铺页面，检查URL
                current_url = page.url
                if "temu.com" in current_url and "/product" not in current_url:
                    logger.info("✓ 已在店铺页面")
                    return True
                return False
            
            # 点击访问店铺按钮
            logger.debug("点击'一键访问店铺'按钮...")
            await page.locator(visit_btn_selector).first.click()
            
            # 等待页面跳转
            await page.wait_for_timeout(2000)
            
            # 验证是否成功跳转到店铺
            current_url = page.url
            logger.debug(f"当前URL: {current_url}")
            
            if "temu.com" in current_url:
                logger.success("✓ 成功访问前端店铺")
                return True
            else:
                logger.error("✗ 未成功跳转到店铺页面")
                return False
                
        except Exception as e:
            logger.error(f"访问店铺失败: {e}")
            return False
    
    async def search_products(
        self,
        page: Page,
        keyword: str,
        filters: Optional[Dict] = None
    ) -> bool:
        """站内搜索同款商品（SOP步骤2）.
        
        根据选品表的关键词，在Temu前端搜索同款商品。
        
        Args:
            page: Playwright页面对象
            keyword: 搜索关键词（如"药箱收纳盒"）
            filters: 筛选条件（如颜色、尺寸等）
            
        Returns:
            是否成功搜索到商品
            
        Examples:
            >>> await ctrl.search_products(page, "药箱收纳盒")
            True
            >>> await ctrl.search_products(page, "智能手表", {"color": "黑色"})
            True
        """
        logger.info("============================================================")
        logger.info(f"【SOP步骤2】站内搜索同款商品: {keyword}")
        logger.info("============================================================")
        
        try:
            store_config = self.selectors.get("store", {})
            search_input_selector = store_config.get(
                "search_input",
                "input[type='search'], input[placeholder*='搜索']"
            )
            search_btn_selector = store_config.get(
                "search_button",
                "button:has-text('搜索'), button[type='submit']"
            )
            
            # 查找搜索框
            logger.debug("查找搜索框...")
            search_input_count = await page.locator(search_input_selector).count()
            
            if search_input_count == 0:
                logger.error("✗ 未找到搜索框")
                return False
            
            # 输入关键词
            logger.debug(f"输入关键词: {keyword}")
            await page.locator(search_input_selector).first.fill(keyword)
            await page.wait_for_timeout(500)
            
            # 点击搜索按钮或按回车
            logger.debug("执行搜索...")
            search_btn_count = await page.locator(search_btn_selector).count()
            
            if search_btn_count > 0:
                await page.locator(search_btn_selector).first.click()
            else:
                # 如果没有搜索按钮，按回车
                await page.locator(search_input_selector).first.press("Enter")
            
            # 等待搜索结果加载
            await page.wait_for_timeout(3000)
            
            # 验证是否有搜索结果
            product_config = self.selectors.get("product", {})
            item_card_selector = product_config.get(
                "item_card",
                ".product-card, .item-card, [data-product-id]"
            )
            
            product_count = await page.locator(item_card_selector).count()
            
            if product_count > 0:
                logger.success(f"✓ 搜索成功，找到 {product_count} 个商品")
                return True
            else:
                logger.warning("⚠️ 未找到商品，请检查关键词")
                return False
                
        except Exception as e:
            logger.error(f"搜索商品失败: {e}")
            return False
    
    async def collect_links(
        self,
        page: Page,
        count: int = 5,
        validate: bool = True
    ) -> List[Dict]:
        """一次性采集N个同款商品链接（SOP步骤3）.
        
        从搜索结果中采集指定数量的商品链接。
        
        Args:
            page: Playwright页面对象
            count: 采集数量（默认5个）
            validate: 是否验证商品规格一致性
            
        Returns:
            采集的商品信息列表
            
        Examples:
            >>> links = await ctrl.collect_links(page, count=5)
            >>> print(len(links))  # 5
            >>> print(links[0].keys())  # ['url', 'title', 'price', 'image']
        """
        logger.info("============================================================")
        logger.info(f"【SOP步骤3】一次性采集 {count} 个同款商品链接")
        logger.info("============================================================")
        
        collected_links = []
        
        try:
            product_config = self.selectors.get("product", {})
            item_card_selector = product_config.get(
                "item_card",
                ".product-card, .item-card, [data-product-id]"
            )
            product_link_selector = product_config.get(
                "product_link",
                "a[href*='/product/'], a[href*='/goods/']"
            )
            product_title_selector = product_config.get(
                "product_title",
                ".title, .product-title, h3"
            )
            product_price_selector = product_config.get(
                "product_price",
                ".price, .product-price"
            )
            
            # 获取所有商品卡片
            logger.debug("获取商品列表...")
            product_cards = await page.locator(item_card_selector).all()
            
            if len(product_cards) < count:
                logger.warning(f"⚠️ 商品数量不足，需要 {count} 个，实际 {len(product_cards)} 个")
            
            # 采集前N个商品
            for i in range(min(count, len(product_cards))):
                card = product_cards[i]
                
                try:
                    # 提取商品信息
                    logger.debug(f"采集第 {i+1} 个商品...")
                    
                    # 获取商品链接
                    link_elem = card.locator(product_link_selector).first
                    url = await link_elem.get_attribute("href") or ""
                    
                    # 补全URL
                    if url.startswith("/"):
                        url = f"https://www.temu.com{url}"
                    
                    # 获取标题
                    try:
                        title = await card.locator(product_title_selector).first.inner_text()
                    except:
                        title = "未获取到标题"
                    
                    # 获取价格
                    try:
                        price = await card.locator(product_price_selector).first.inner_text()
                    except:
                        price = "未获取到价格"
                    
                    # 获取图片
                    try:
                        image = await card.locator("img").first.get_attribute("src") or ""
                    except:
                        image = ""
                    
                    product_info = {
                        "url": url,
                        "title": title.strip(),
                        "price": price.strip(),
                        "image": image,
                        "index": i + 1
                    }
                    
                    collected_links.append(product_info)
                    logger.success(f"✓ 第 {i+1} 个商品: {title[:30]}...")
                    
                except Exception as e:
                    logger.error(f"✗ 采集第 {i+1} 个商品失败: {e}")
                    continue
            
            logger.info(f"\n{'='*60}")
            logger.info(f"采集完成：成功采集 {len(collected_links)} 个商品链接")
            logger.info(f"{'='*60}\n")
            
            return collected_links
            
        except Exception as e:
            logger.error(f"采集链接失败: {e}")
            return collected_links
    
    async def add_to_collection_box(
        self,
        page: Page,
        links: List[str]
    ) -> bool:
        """将采集的链接添加到妙手采集箱.
        
        使用妙手插件将商品链接添加到采集箱。
        
        Args:
            page: Playwright页面对象
            links: 商品链接列表
            
        Returns:
            是否成功添加到采集箱
            
        Examples:
            >>> links = ["https://temu.com/product/123", ...]
            >>> await ctrl.add_to_collection_box(page, links)
            True
        """
        logger.info(f"添加 {len(links)} 个商品到妙手采集箱...")
        
        try:
            collection_config = self.selectors.get("collection_box", {})
            add_btn_selector = collection_config.get(
                "add_button",
                "button:has-text('添加到采集箱'), .add-to-collection"
            )
            
            success_count = 0
            
            for i, link in enumerate(links):
                try:
                    logger.debug(f"添加第 {i+1} 个商品: {link}")
                    
                    # 导航到商品详情页
                    await page.goto(link)
                    await page.wait_for_timeout(2000)
                    
                    # 查找并点击添加按钮
                    add_btn_count = await page.locator(add_btn_selector).count()
                    
                    if add_btn_count > 0:
                        await page.locator(add_btn_selector).first.click()
                        await page.wait_for_timeout(1000)
                        success_count += 1
                        logger.success(f"✓ 第 {i+1} 个商品已添加")
                    else:
                        logger.warning(f"⚠️ 第 {i+1} 个商品未找到添加按钮")
                    
                except Exception as e:
                    logger.error(f"✗ 添加第 {i+1} 个商品失败: {e}")
                    continue
            
            logger.info(f"成功添加 {success_count}/{len(links)} 个商品到采集箱")
            return success_count == len(links)
            
        except Exception as e:
            logger.error(f"添加到采集箱失败: {e}")
            return False
    
    async def search_and_collect(
        self,
        page: Page,
        keyword: str,
        count: int = 5,
        filters: Optional[Dict] = None
    ) -> List[Dict]:
        """搜索并采集商品（步骤2+3的组合）.
        
        Args:
            page: Playwright页面对象
            keyword: 搜索关键词
            count: 采集数量
            filters: 筛选条件
            
        Returns:
            采集的商品信息列表
            
        Examples:
            >>> links = await ctrl.search_and_collect(page, "药箱收纳盒", count=5)
            >>> print(len(links))  # 5
        """
        # 步骤2：搜索
        if not await self.search_products(page, keyword, filters):
            logger.error("搜索失败，无法进行采集")
            return []
        
        # 步骤3：采集
        links = await self.collect_links(page, count=count)
        
        return links

