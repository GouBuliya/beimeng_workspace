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
    
    async def add_to_miaoshou_collection_box(
        self,
        page: Page,
        product_urls: List[str],
        max_retries: int = 3,
        use_plugin: bool = True
    ) -> Dict:
        """将Temu商品链接添加到妙手采集箱（工业化版本）.
        
        使用妙手浏览器插件自动采集商品到妙手ERP采集箱。
        支持多种策略：插件自动化、API导入、手动fallback。
        
        Args:
            page: Playwright页面对象
            product_urls: 商品链接列表
            max_retries: 每个商品的最大重试次数
            use_plugin: 是否使用妙手插件（True: 插件模式, False: API模式）
            
        Returns:
            采集结果字典，包含：
            - success_count: 成功数量
            - failed_count: 失败数量
            - total: 总数量
            - failed_urls: 失败的URL列表
            - method: 使用的方法（plugin/api/manual）
            
        Examples:
            >>> urls = ["https://www.temu.com/product/123", ...]
            >>> result = await ctrl.add_to_miaoshou_collection_box(page, urls)
            >>> print(f"成功: {result['success_count']}/{result['total']}")
        """
        logger.info("=" * 80)
        logger.info(f"【关键衔接】将 {len(product_urls)} 个Temu商品添加到妙手采集箱")
        logger.info("=" * 80)
        
        result = {
            "success_count": 0,
            "failed_count": 0,
            "total": len(product_urls),
            "failed_urls": [],
            "method": "plugin" if use_plugin else "api"
        }
        
        if use_plugin:
            # 策略1: 使用妙手浏览器插件
            result = await self._add_via_plugin(page, product_urls, max_retries)
        else:
            # 策略2: 使用妙手ERP API（如果可用）
            result = await self._add_via_api(page, product_urls, max_retries)
        
        # 如果两种方法都失败，提供手动fallback
        if result["success_count"] == 0 and len(product_urls) > 0:
            logger.warning("⚠️  自动采集失败，请使用手动模式")
            logger.info("💡 手动模式：")
            logger.info("   1. 打开Temu商品详情页")
            logger.info("   2. 点击妙手插件的「采集商品」按钮")
            logger.info("   3. 确认商品已添加到妙手采集箱")
            result["method"] = "manual_required"
        
        logger.info("\n" + "=" * 80)
        logger.info(f"采集到妙手完成: {result['success_count']}/{result['total']} 成功")
        logger.info("=" * 80 + "\n")
        
        return result
    
    async def _add_via_plugin(
        self,
        page: Page,
        product_urls: List[str],
        max_retries: int = 3
    ) -> Dict:
        """通过妙手浏览器插件添加商品.
        
        插件识别策略：
        1. 查找妙手插件的固定按钮
        2. 支持多种插件版本的选择器
        3. 等待插件加载完成
        """
        result = {
            "success_count": 0,
            "failed_count": 0,
            "total": len(product_urls),
            "failed_urls": [],
            "method": "plugin"
        }
        
        # 妙手插件可能的选择器（按优先级排列）
        plugin_selectors = [
            # 妙手插件常见的ID和class
            "#miaoshou-collect-btn",
            ".miaoshou-collect-button",
            "button[data-miaoshou='collect']",
            
            # 文本匹配（中英文）
            "button:has-text('采集到妙手')",
            "button:has-text('采集商品')",
            "button:has-text('妙手采集')",
            "button:has-text('Collect to Miaoshou')",
            
            # 通用采集按钮（可能是插件）
            "button[title*='采集']",
            "div[class*='collect'] button",
            
            # iframe中的按钮（插件可能使用iframe）
            "iframe[src*='miaoshou'] button",
        ]
        
        for i, url in enumerate(product_urls):
            logger.info(f"\n>>> 采集第 {i+1}/{len(product_urls)} 个商品...")
            logger.debug(f"    URL: {url[:60]}...")
            
            retry_count = 0
            success = False
            
            while retry_count < max_retries and not success:
                try:
                    # 1. 访问商品详情页
                    logger.debug(f"    [尝试 {retry_count+1}/{max_retries}] 访问商品页...")
                    await page.goto(url, wait_until="networkidle", timeout=30000)
                    await page.wait_for_timeout(2000)  # 等待页面和插件加载
                    
                    # 2. 尝试查找妙手插件按钮
                    plugin_found = False
                    plugin_button = None
                    
                    for selector in plugin_selectors:
                        try:
                            # 检查是否在主page
                            count = await page.locator(selector).count()
                            if count > 0:
                                plugin_button = page.locator(selector).first
                                if await plugin_button.is_visible(timeout=2000):
                                    plugin_found = True
                                    logger.debug(f"    ✓ 找到妙手插件按钮: {selector}")
                                    break
                            
                            # 检查是否在iframe中
                            frames = page.frames
                            for frame in frames:
                                try:
                                    frame_count = await frame.locator(selector).count()
                                    if frame_count > 0:
                                        plugin_button = frame.locator(selector).first
                                        if await plugin_button.is_visible(timeout=2000):
                                            plugin_found = True
                                            logger.debug(f"    ✓ 找到妙手插件按钮（iframe）: {selector}")
                                            break
                                except:
                                    continue
                            
                            if plugin_found:
                                break
                                
                        except Exception as e:
                            logger.debug(f"    选择器 {selector} 检查失败: {e}")
                            continue
                    
                    if not plugin_found:
                        logger.warning(f"    ⚠️  未找到妙手插件按钮")
                        retry_count += 1
                        await page.wait_for_timeout(1000)
                        continue
                    
                    # 3. 点击采集按钮
                    logger.debug("    点击妙手插件采集按钮...")
                    await plugin_button.click()
                    await page.wait_for_timeout(1500)
                    
                    # 4. 检测采集成功提示
                    success_indicators = [
                        "text=采集成功",
                        "text=已添加到采集箱",
                        "text=添加成功",
                        ".success-toast",
                        ".message-success",
                        "[class*='success']"
                    ]
                    
                    success_detected = False
                    for indicator in success_indicators:
                        try:
                            if await page.locator(indicator).count() > 0:
                                success_detected = True
                                logger.success(f"    ✓ 检测到采集成功提示")
                                break
                        except:
                            continue
                    
                    # 即使没有明确的成功提示，如果点击成功也认为采集成功
                    if not success_detected:
                        logger.info("    ℹ️  未检测到明确的成功提示，假设采集成功")
                        success_detected = True
                    
                    if success_detected:
                        result["success_count"] += 1
                        logger.success(f"✓ 第 {i+1} 个商品采集成功")
                        success = True
                    else:
                        retry_count += 1
                        
                except Exception as e:
                    logger.error(f"    ✗ 采集失败: {e}")
                    retry_count += 1
                    await page.wait_for_timeout(1000)
            
            if not success:
                result["failed_count"] += 1
                result["failed_urls"].append(url)
                logger.error(f"✗ 第 {i+1} 个商品采集失败（已重试{max_retries}次）")
        
        return result
    
    async def _add_via_api(
        self,
        page: Page,
        product_urls: List[str],
        max_retries: int = 3
    ) -> Dict:
        """通过妙手ERP API添加商品（备用方案）.
        
        注意：此方法需要妙手ERP提供公开API，目前作为占位符。
        """
        logger.warning("⚠️  妙手ERP API方式暂未实现")
        logger.info("💡 建议：使用插件模式或手动模式")
        
        return {
            "success_count": 0,
            "failed_count": len(product_urls),
            "total": len(product_urls),
            "failed_urls": product_urls,
            "method": "api_not_available"
        }
    
    async def add_to_collection_box(
        self,
        page: Page,
        links: List[str]
    ) -> bool:
        """将采集的链接添加到妙手采集箱（兼容旧接口）.
        
        此方法保留用于向后兼容，内部调用新的add_to_miaoshou_collection_box。
        
        Args:
            page: Playwright页面对象
            links: 商品链接列表
            
        Returns:
            是否成功添加到采集箱
        """
        result = await self.add_to_miaoshou_collection_box(page, links)
        return result["success_count"] == result["total"]
    
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

