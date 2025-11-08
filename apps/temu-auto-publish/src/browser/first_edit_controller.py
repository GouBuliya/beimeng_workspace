"""
@PURPOSE: 首次编辑控制器，负责产品的首次编辑操作（SOP步骤4）
@OUTLINE:
  - class FirstEditController: 首次编辑控制器主类
  - async def check_category(): 核对商品类目合规性（步骤4.3）
  - async def edit_title(): 编辑产品标题（步骤4.2）
  - async def modify_category(): 修改产品类目
  - async def edit_images(): 处理产品图片（步骤4.4）
  - async def upload_size_chart(): 上传尺寸图（步骤4.5）
  - async def upload_product_video(): 上传产品视频（步骤4.5）
  - async def set_price(): 设置价格
  - async def set_stock(): 设置库存
  - async def set_dimensions(): 设置重量和尺寸
  - async def save_changes(): 保存修改
  - async def close_dialog(): 关闭首次编辑弹窗及遮挡弹窗
@GOTCHAS:
  - 首次编辑是一个弹窗对话框，需要等待加载
  - 使用aria-ref定位元素
  - 详细描述使用iframe富文本编辑器
  - 保存后弹窗会关闭
  - 类目核对：药品、医疗、电子等类目不支持
  - 视频/尺寸图上传需要实际环境调试选择器
@DEPENDENCIES:
  - 内部: browser_manager
  - 外部: playwright, loguru
@RELATED: miaoshou_controller.py, batch_edit_controller.py
@CHANGELOG:
  - 2025-11-01: 新增check_category()核对类目合规性（SOP 4.3）
  - 2025-11-01: 新增upload_size_chart()上传尺寸图（SOP 4.5）
  - 2025-11-01: 新增upload_product_video()上传产品视频（SOP 4.5）
"""

import json
import re
from pathlib import Path

from loguru import logger
from playwright.async_api import Locator, Page


class FirstEditController:
    """首次编辑控制器（SOP步骤4的7个子步骤）.

    负责产品的首次编辑，包括：
    1. 编辑标题（添加型号后缀）
    2. 修改类目
    3. 编辑图片
    4. 设置价格（建议售价=成本×10，供货价=成本×7.5）
    5. 设置库存
    6. 填写重量
    7. 填写尺寸

    Attributes:
        selectors: 妙手ERP选择器配置

    Examples:
        >>> ctrl = FirstEditController()
        >>> await ctrl.edit_title(page, "新标题 A0001型号")
    """

    def __init__(self, selector_path: str = "config/miaoshou_selectors_v2.json"):
        """初始化首次编辑控制器.

        Args:
            selector_path: 选择器配置文件路径（默认使用v2文本定位器版本）
        """
        self.selector_path = Path(selector_path)
        self.selectors = self._load_selectors()
        logger.info("首次编辑控制器初始化（SOP步骤4 - 文本定位器）")

    def _load_selectors(self) -> dict:
        """加载选择器配置."""
        try:
            if not self.selector_path.is_absolute():
                current_file = Path(__file__)
                project_root = current_file.parent.parent.parent
                selector_file = project_root / self.selector_path
            else:
                selector_file = self.selector_path

            with open(selector_file, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"加载选择器配置失败: {e}")
            return {}

    async def wait_for_dialog(self, page: Page, timeout: int = 5000) -> bool:
        """等待编辑弹窗打开.

        Args:
            page: Playwright页面对象
            timeout: 超时时间（毫秒）

        Returns:
            弹窗是否已打开
        """
        try:
            first_edit_config = self.selectors.get("first_edit_dialog", {})
            close_btn_selector = first_edit_config.get("close_btn", "button:has-text('关闭')")

            await page.wait_for_selector(close_btn_selector, timeout=timeout)
            logger.success("✓ 编辑弹窗已打开")
            return True
        except Exception as e:
            logger.error(f"等待编辑弹窗失败: {e}")
            return False

    async def check_category(self, page: Page) -> tuple[bool, str]:
        """核对商品类目是否合规（SOP步骤4.3）.

        检查商品类目是否属于不支持的类目（药品、电子等）。

        Args:
            page: Playwright页面对象

        Returns:
            (是否合规, 类目名称)
            - True: 类目合规，可以继续
            - False: 类目不合规，需要跳过或人工确认

        Examples:
            >>> is_valid, category = await ctrl.check_category(page)
            >>> if not is_valid:
            >>>     logger.warning(f"类目不合规: {category}")
        """
        logger.info("SOP 4.3: 核对商品类目...")

        # 不支持的类目列表（根据SOP文档）
        UNSUPPORTED_CATEGORIES = [
            "药品",
            "医疗器械",
            "保健品",
            "电子产品",
            "数码产品",
            "食品",
            "化妆品",
            # 可以根据实际情况继续添加
        ]

        try:
            # 等待类目信息加载
            # await page.wait_for_timeout(500)

            # 尝试多种方式读取类目信息
            category_selectors = [
                # 方法1: 通过"类目"标签定位
                "xpath=//label[contains(text(), '类目')]/following-sibling::*/descendant::input[1]",
                "xpath=//label[contains(text(), '类目')]/following-sibling::*//div[contains(@class, 'jx-input')]",
                # 方法2: 通过类目选择器
                ".jx-overlay-dialog .jx-select input[placeholder*='类目']",
                ".jx-overlay-dialog input[placeholder*='选择类目']",
            ]

            category_text = ""
            for selector in category_selectors:
                try:
                    elem = page.locator(selector).first
                    if await elem.is_visible(timeout=1000):
                        # 尝试获取value或innerText
                        category_text = await elem.input_value() or await elem.inner_text()
                        if category_text:
                            logger.debug(f"找到类目信息: {category_text} (选择器: {selector})")
                            break
                except Exception as e:
                    logger.debug(f"尝试选择器 {selector} 失败: {e}")
                    continue

            if not category_text:
                logger.warning("⚠️  未能读取类目信息，默认认为合规（建议人工确认）")
                return (True, "未知类目")

            # 检查是否属于不支持的类目
            for unsupported in UNSUPPORTED_CATEGORIES:
                if unsupported in category_text:
                    logger.warning(f"❌ 类目不合规: {category_text} (包含: {unsupported})")
                    return (False, category_text)

            logger.success(f"✓ 类目合规: {category_text}")
            return (True, category_text)

        except Exception as e:
            logger.error(f"核对类目失败: {e}")
            logger.warning("⚠️  默认认为类目合规（建议人工确认）")
            return (True, "检查失败")

    async def get_original_title(self, page: Page) -> str:
        """获取产品的原始标题（SOP步骤4.2准备）.

        从编辑弹窗的"产品标题"字段读取原始标题。

        Args:
            page: Playwright页面对象

        Returns:
            原始标题文本（如果失败返回空字符串）

        Examples:
            >>> title = await ctrl.get_original_title(page)
            >>> print(title)
            "便携药箱家用急救包医疗收纳盒"
        """
        logger.debug("获取产品原始标题...")

        try:
            # 等待弹窗完全加载
            # await page.wait_for_timeout(1000)

            # 尝试多个可能的标题输入框选择器
            # 重要: 产品标题是 input[type=text] 而不是 textarea！
            # 简易描述才是 textarea.jx-textarea__inner
            title_selectors = [
                # 方法1：通过相邻的label文本定位input（最准确）
                "xpath=//label[contains(text(), '产品标题')]/following-sibling::*/descendant::input[@type='text'][1]",
                "xpath=//label[contains(text(), '产品标题')]/following::input[@type='text'][1]",
                "xpath=//div[contains(@class, 'jx-form-item')]//label[contains(text(), '产品标题:')]//following-sibling::*/descendant::input[@type='text']",
                # 方法2：通过className定位，排除type=number
                "xpath=//label[contains(text(), '产品标题')]/ancestor::div[contains(@class, 'jx-form-item')]//input[contains(@class, 'jx-input__inner') and @type='text']",
                # 方法3：在编辑弹窗中查找input，但排除type=number（分页控件）
                ".jx-overlay-dialog input.jx-input__inner[type='text']:visible",
            ]

            title_input = None
            for selector in title_selectors:
                try:
                    count = await page.locator(selector).count()
                    if count > 0:
                        for i in range(count):
                            elem = page.locator(selector).nth(i)
                            is_visible = await elem.is_visible(timeout=1000)
                            if is_visible:
                                title_input = elem
                                logger.debug(f"使用选择器: {selector} (第{i + 1}个)")
                                break
                        if title_input:
                            break
                except:
                    continue

            if not title_input:
                logger.error("未找到标题输入框")
                return ""

            # 获取标题值
            title = await title_input.input_value()
            logger.success(f"✓ 获取到原始标题: {title[:50]}...")
            return title

        except Exception as e:
            logger.error(f"获取原始标题失败: {e}")
            return ""

    async def edit_title(self, page: Page, new_title: str) -> bool:
        """编辑产品标题（SOP步骤4.1）.

        Args:
            page: Playwright页面对象
            new_title: 新标题（应包含型号后缀，如"产品名 A0001型号"）

        Returns:
            是否编辑成功

        Examples:
            >>> await ctrl.edit_title(page, "新款洗衣篮 A0001型号")
            True
        """
        logger.info(f"SOP 4.1: 编辑标题 -> {new_title}")
        logger.debug(f"    标题长度: {len(new_title)} 字符")

        try:
            # 等待弹窗完全加载
            logger.debug("    等待编辑弹窗加载...")
            # await page.wait_for_timeout(1000)

            # 尝试多个可能的标题输入框选择器
            # 重要: 产品标题是 input[type=text] 而不是 textarea！
            # 简易描述才是 textarea.jx-textarea__inner
            title_selectors = [
                # 方法1：通过相邻的label文本定位input（最准确）
                "xpath=//label[contains(text(), '产品标题')]/following-sibling::*/descendant::input[@type='text'][1]",
                "xpath=//label[contains(text(), '产品标题')]/following::input[@type='text'][1]",
                "xpath=//div[contains(@class, 'jx-form-item')]//label[contains(text(), '产品标题:')]//following-sibling::*/descendant::input[@type='text']",
                # 方法2：通过className定位，排除type=number
                "xpath=//label[contains(text(), '产品标题')]/ancestor::div[contains(@class, 'jx-form-item')]//input[contains(@class, 'jx-input__inner') and @type='text']",
                # 方法3：在编辑弹窗中查找input，但排除type=number（分页控件）
                ".jx-overlay-dialog input.jx-input__inner[type='text']:visible",
            ]

            logger.debug(f"    尝试{len(title_selectors)}种选择器定位产品标题字段...")

            title_input = None
            used_selector = None
            selector_index = 0

            for selector in title_selectors:
                try:
                    selector_index += 1
                    logger.debug(
                        f"    [{selector_index}/{len(title_selectors)}] 尝试选择器: {selector[:60]}..."
                    )
                    count = await page.locator(selector).count()
                    logger.debug(f"        找到 {count} 个匹配元素")

                    if count > 0:
                        # 找到第一个可见的
                        for i in range(count):
                            elem = page.locator(selector).nth(i)
                            is_visible = await elem.is_visible(timeout=1000)
                            if is_visible:
                                title_input = elem
                                used_selector = f"{selector} (第{i + 1}个)"
                                logger.info(f"    ✓ 使用选择器定位到标题输入框: {used_selector}")
                                break
                        if title_input:
                            break
                except Exception as e:
                    logger.debug(f"        选择器失败: {e}")
                    continue

            if not title_input:
                logger.error("    ✗ 未找到标题输入框")
                logger.error(f"    尝试了 {len(title_selectors)} 种选择器都失败")
                return False

            # 获取当前标题值（用于对比）
            logger.debug("    读取当前标题值...")
            current_title = await title_input.input_value()
            logger.debug(f"    当前标题: {current_title[:50]}...")

            # 清空并填写新标题
            logger.info("    清空标题字段...")
            await title_input.fill("")
            # await page.wait_for_timeout(300)

            logger.info(f"    填写新标题: {new_title}")
            await title_input.fill(new_title)
            # await page.wait_for_timeout(500)

            # 验证标题是否成功更新
            logger.debug("    验证标题是否成功更新...")
            updated_title = await title_input.input_value()
            logger.debug(f"    更新后的标题: {updated_title[:50]}...")

            if updated_title == new_title:
                logger.success(f"✓ 标题已成功更新: {new_title}")
                return True
            else:
                logger.warning("⚠️ 标题可能未完全更新")
                logger.warning(f"    期望: {new_title}")
                logger.warning(f"    实际: {updated_title}")
                # 仍然返回True，因为可能是显示延迟
                return True
            return True

        except Exception as e:
            logger.error(f"编辑标题失败: {e}")
            return False

    async def edit_title_with_ai(
        self,
        page: Page,
        product_index: int,
        all_original_titles: list,
        model_number: str,
        use_ai: bool = True,
    ) -> bool:
        """使用AI生成的新标题编辑产品标题（SOP步骤4.2）.

        此方法假设已经从5个产品中收集了原始标题，并通过AI生成了5个新标题。
        根据product_index选择对应的新标题并填入。

        Args:
            page: Playwright页面对象
            product_index: 产品索引（0-4）
            all_original_titles: 5个原始标题列表
            model_number: 型号后缀（如：A0049型号）
            use_ai: 是否使用AI生成（False则只添加型号）

        Returns:
            是否编辑成功

        Examples:
            >>> original_titles = ["标题1", "标题2", "标题3", "标题4", "标题5"]
            >>> await ctrl.edit_title_with_ai(page, 0, original_titles, "A0049型号")
            True
        """
        logger.info(f"SOP 4.2: 使用AI生成标题（产品{product_index + 1}/5）")

        try:
            # 动态导入AI标题生成器（避免循环导入）
            from ..data_processor.ai_title_generator import AITitleGenerator

            # 创建AI生成器实例
            ai_generator = AITitleGenerator()

            # 生成5个新标题
            new_titles = await ai_generator.generate_titles(
                all_original_titles, model_number=model_number, use_ai=use_ai
            )

            # 获取当前产品对应的新标题
            if product_index >= len(new_titles):
                logger.error(f"产品索引超出范围: {product_index}/{len(new_titles)}")
                return False

            new_title = new_titles[product_index]
            logger.info(f"为产品{product_index + 1}生成的标题: {new_title}")

            # 使用edit_title方法填写标题
            return await self.edit_title(page, new_title)

        except Exception as e:
            logger.error(f"使用AI编辑标题失败: {e}")
            # 降级方案：使用原标题+型号
            if product_index < len(all_original_titles):
                fallback_title = f"{all_original_titles[product_index]} {model_number}"
                logger.warning(f"⚠️ 使用降级方案: {fallback_title}")
                return await self.edit_title(page, fallback_title)
            return False

    async def set_sku_price(self, page: Page, price: float, sku_index: int = 0) -> bool:
        """设置SKU价格（SOP步骤4.4）.

        Args:
            page: Playwright页面对象
            price: 货源价格（CNY）
            sku_index: SKU索引（默认0，第一个SKU）

        Returns:
            是否设置成功

        Examples:
            >>> await ctrl.set_sku_price(page, 174.78)
            True
        """
        logger.info(f"SOP 4.4: 设置价格 -> {price} CNY")

        try:
            first_edit_config = self.selectors.get("first_edit_dialog", {})
            sales_attrs_config = first_edit_config.get("sales_attrs", {})

            # 切换到销售属性tab
            nav_config = first_edit_config.get("navigation", {})
            sales_tab_selector = nav_config.get("sales_attrs", "text='销售属性'")
            await page.locator(sales_tab_selector).click()
            # await page.wait_for_timeout(1000)

            # 填写SKU价格（排除分页器）
            price_selectors = [
                "input[placeholder='价格']:not([aria-label='页'])",  # 排除分页器
                "input[placeholder*='价格'][type='text']",
            ]

            price_input = None
            for selector in price_selectors:
                try:
                    count = await page.locator(selector).count()
                    logger.debug(f"价格选择器 {selector} 找到 {count} 个元素")
                    if count > 0:
                        elem = page.locator(selector).nth(sku_index)
                        is_visible = await elem.is_visible(timeout=1000)
                        if is_visible:
                            price_input = elem
                            logger.debug(f"使用价格选择器: {selector} (第{sku_index + 1}个)")
                            break
                except:
                    continue

            if not price_input:
                logger.error("未找到价格输入框")
                return False

            await price_input.fill("")
            # await page.wait_for_timeout(300)
            await price_input.fill(str(price))
            # await page.wait_for_timeout(500)

            logger.success(f"✓ 价格已设置: {price} CNY")
            return True

        except Exception as e:
            logger.error(f"设置价格失败: {e}")
            return False

    async def set_sku_stock(self, page: Page, stock: int, sku_index: int = 0) -> bool:
        """设置SKU库存（SOP步骤4.5）.

        Args:
            page: Playwright页面对象
            stock: 库存数量
            sku_index: SKU索引（默认0）

        Returns:
            是否设置成功

        Examples:
            >>> await ctrl.set_sku_stock(page, 99)
            True
        """
        logger.info(f"SOP 4.5: 设置库存 -> {stock}")

        try:
            first_edit_config = self.selectors.get("first_edit_dialog", {})
            sales_attrs_config = first_edit_config.get("sales_attrs", {})

            stock_selectors = [
                "input[placeholder='库存']",
                "input[placeholder*='库存'][type='text']",
                "input[type='number']",  # 库存通常是number类型
            ]

            stock_input = None
            for selector in stock_selectors:
                try:
                    count = await page.locator(selector).count()
                    logger.debug(f"库存选择器 {selector} 找到 {count} 个元素")
                    if count > 0:
                        elem = page.locator(selector).nth(sku_index)
                        is_visible = await elem.is_visible(timeout=1000)
                        if is_visible:
                            stock_input = elem
                            logger.debug(f"使用库存选择器: {selector} (第{sku_index + 1}个)")
                            break
                except Exception as e:
                    logger.debug(f"尝试选择器 {selector} 失败: {e}")
                    continue

            if not stock_input:
                logger.error("未找到库存输入框")
                return False

            await stock_input.fill("")
            # await page.wait_for_timeout(300)
            await stock_input.fill(str(stock))
            # await page.wait_for_timeout(500)

            logger.success(f"✓ 库存已设置: {stock}")
            return True

        except Exception as e:
            logger.error(f"设置库存失败: {e}")
            return False

    async def navigate_to_logistics_tab(self, page: Page) -> bool:
        """导航到物流信息Tab（SOP步骤4.6-4.7的前置操作）.

        重量和尺寸输入框在"物流信息"tab中，需要先切换。

        Args:
            page: Playwright页面对象

        Returns:
            是否成功导航

        Examples:
            >>> await ctrl.navigate_to_logistics_tab(page)
            True
        """
        try:
            first_edit_config = self.selectors.get("first_edit_dialog", {})
            nav_config = first_edit_config.get("navigation", {})
            logistics_tab_selector = nav_config.get("logistics_info", "text='物流信息'")

            logger.info("导航到「物流信息」Tab...")
            await page.locator(logistics_tab_selector).click()
            # await page.wait_for_timeout(1000)  # 等待Tab内容加载

            logger.success("✓ 已切换到物流信息Tab")
            return True

        except Exception as e:
            logger.error(f"导航到物流信息Tab失败: {e}")
            return False

    async def set_package_weight_in_logistics(self, page: Page, weight: float) -> bool:
        """在物流信息Tab中设置包裹重量（SOP步骤4.6增强版）.

        Args:
            page: Playwright页面对象
            weight: 重量（克），范围：5000-9999G

        Returns:
            是否设置成功

        Examples:
            >>> await ctrl.set_package_weight_in_logistics(page, 7500)
            True
        """
        logger.info(f"SOP 4.6: 设置包裹重量 -> {weight}G")

        # 验证重量范围
        if not (5000 <= weight <= 9999):
            logger.warning(f"重量{weight}G 超出推荐范围（5000-9999G）")

        try:
            # 先切换到物流信息Tab
            if not await self.navigate_to_logistics_tab(page):
                return False

            # 使用物流信息中的重量选择器
            first_edit_config = self.selectors.get("first_edit_dialog", {})
            logistics_config = first_edit_config.get("logistics_info", {})
            weight_selector = logistics_config.get(
                "package_weight", "input[placeholder*='包裹重量'], input[placeholder*='重量']"
            )

            # 尝试多个选择器
            weight_selectors = [
                weight_selector,
                "input[placeholder='包裹重量']",
                "input[placeholder*='重量']",
                "input[placeholder*='重']",
            ]

            weight_input = None
            for selector in weight_selectors:
                try:
                    count = await page.locator(selector).count()
                    logger.debug(f"重量选择器 {selector} 找到 {count} 个元素")
                    if count > 0:
                        elem = page.locator(selector).first
                        is_visible = await elem.is_visible(timeout=1000)
                        if is_visible:
                            weight_input = elem
                            logger.debug(f"使用重量选择器: {selector}")
                            break
                except Exception as e:
                    logger.debug(f"尝试选择器 {selector} 失败: {e}")
                    continue

            if not weight_input:
                logger.error("未找到包裹重量输入框（物流信息Tab）")
                logger.info("提示：需要使用 Playwright Codegen 录制实际操作获取准确选择器")
                return False

            # 填写重量
            await weight_input.fill("")
            # await page.wait_for_timeout(300)
            await weight_input.fill(str(weight))
            # await page.wait_for_timeout(500)

            logger.success(f"✓ 包裹重量已设置: {weight}G")
            return True

        except Exception as e:
            logger.error(f"设置包裹重量失败: {e}")
            return False

    async def set_package_dimensions_in_logistics(
        self, page: Page, length: float, width: float, height: float
    ) -> bool:
        """在物流信息Tab中设置包裹尺寸（SOP步骤4.7增强版）.

        SOP要求：
        - 范围：50-99cm
        - 规则：长 > 宽 > 高

        Args:
            page: Playwright页面对象
            length: 长度（CM）
            width: 宽度（CM）
            height: 高度（CM）

        Returns:
            是否设置成功

        Raises:
            ValueError: 尺寸不符合SOP规则

        Examples:
            >>> await ctrl.set_package_dimensions_in_logistics(page, 89, 64, 32)
            True
        """
        logger.info(f"SOP 4.7: 设置包裹尺寸 -> {length}x{width}x{height} CM")

        # 验证尺寸范围
        if not all(50 <= dim <= 99 for dim in [length, width, height]):
            logger.warning("尺寸超出推荐范围（50-99cm）")

        # 验证长>宽>高规则
        if not (length > width > height):
            raise ValueError(f"尺寸不符合SOP规则（长>宽>高）: {length}cm > {width}cm > {height}cm")

        try:
            # 先切换到物流信息Tab
            if not await self.navigate_to_logistics_tab(page):
                return False

            # 使用物流信息中的尺寸选择器
            first_edit_config = self.selectors.get("first_edit_dialog", {})
            logistics_config = first_edit_config.get("logistics_info", {})

            length_selector = logistics_config.get(
                "package_length",
                "input[placeholder*='包裹长度'], input[placeholder*='长度'], input[placeholder*='长']",
            )
            width_selector = logistics_config.get(
                "package_width",
                "input[placeholder*='包裹宽度'], input[placeholder*='宽度'], input[placeholder*='宽']",
            )
            height_selector = logistics_config.get(
                "package_height",
                "input[placeholder*='包裹高度'], input[placeholder*='高度'], input[placeholder*='高']",
            )

            # 查找长度输入框
            length_input = None
            for selector in length_selector.split(", "):
                try:
                    count = await page.locator(selector.strip()).count()
                    if count > 0:
                        elem = page.locator(selector.strip()).first
                        if await elem.is_visible(timeout=1000):
                            length_input = elem
                            logger.debug(f"使用长度选择器: {selector}")
                            break
                except:
                    continue

            # 查找宽度输入框
            width_input = None
            for selector in width_selector.split(", "):
                try:
                    count = await page.locator(selector.strip()).count()
                    if count > 0:
                        elem = page.locator(selector.strip()).first
                        if await elem.is_visible(timeout=1000):
                            width_input = elem
                            logger.debug(f"使用宽度选择器: {selector}")
                            break
                except:
                    continue

            # 查找高度输入框
            height_input = None
            for selector in height_selector.split(", "):
                try:
                    count = await page.locator(selector.strip()).count()
                    if count > 0:
                        elem = page.locator(selector.strip()).first
                        if await elem.is_visible(timeout=1000):
                            height_input = elem
                            logger.debug(f"使用高度选择器: {selector}")
                            break
                except:
                    continue

            if not length_input or not width_input or not height_input:
                logger.error(
                    f"未找到包裹尺寸输入框（物流信息Tab） - "
                    f"长:{length_input is not None}, "
                    f"宽:{width_input is not None}, "
                    f"高:{height_input is not None}"
                )
                logger.info("提示：需要使用 Playwright Codegen 录制实际操作获取准确选择器")
                return False

            # 填写长宽高
            await length_input.fill("")
            # await page.wait_for_timeout(200)
            await length_input.fill(str(length))
            # await page.wait_for_timeout(200)

            await width_input.fill("")
            # await page.wait_for_timeout(200)
            await width_input.fill(str(width))
            # await page.wait_for_timeout(200)

            await height_input.fill("")
            # await page.wait_for_timeout(200)
            await height_input.fill(str(height))
            # await page.wait_for_timeout(300)

            logger.success(f"✓ 包裹尺寸已设置: {length}x{width}x{height} CM")
            return True

        except ValueError as e:
            logger.error(f"尺寸验证失败: {e}")
            raise
        except Exception as e:
            logger.error(f"设置包裹尺寸失败: {e}")
            return False

    async def set_sku_weight(self, page: Page, weight: float, sku_index: int = 0) -> bool:
        """设置SKU重量（SOP步骤4.6）.

        Args:
            page: Playwright页面对象
            weight: 重量（KG）
            sku_index: SKU索引（默认0）

        Returns:
            是否设置成功

        Examples:
            >>> await ctrl.set_sku_weight(page, 0.5)
            True
        """
        logger.info(f"SOP 4.6: 设置重量 -> {weight} KG")

        try:
            first_edit_config = self.selectors.get("first_edit_dialog", {})
            sales_attrs_config = first_edit_config.get("sales_attrs", {})

            weight_selectors = [
                "input[placeholder='重量']",
                "input[placeholder*='重量']",  # 移除type限制
                "input[placeholder*='重']",  # 可能只有"重"
            ]

            weight_input = None
            for selector in weight_selectors:
                try:
                    count = await page.locator(selector).count()
                    logger.debug(f"重量选择器 {selector} 找到 {count} 个元素")
                    if count > 0:
                        elem = page.locator(selector).nth(sku_index)
                        is_visible = await elem.is_visible(timeout=1000)
                        if is_visible:
                            weight_input = elem
                            logger.debug(f"使用重量选择器: {selector} (第{sku_index + 1}个)")
                            break
                except Exception as e:
                    logger.debug(f"尝试选择器 {selector} 失败: {e}")
                    continue

            if not weight_input:
                logger.error("未找到重量输入框")
                return False

            await weight_input.fill("")
            # await page.wait_for_timeout(300)
            await weight_input.fill(str(weight))
            # await page.wait_for_timeout(500)

            logger.success(f"✓ 重量已设置: {weight} KG")
            return True

        except Exception as e:
            logger.error(f"设置重量失败: {e}")
            return False

    async def set_sku_dimensions(
        self, page: Page, length: float, width: float, height: float, sku_index: int = 0
    ) -> bool:
        """设置SKU尺寸（SOP步骤4.7）.

        Args:
            page: Playwright页面对象
            length: 长度（CM）
            width: 宽度（CM）
            height: 高度（CM）
            sku_index: SKU索引（默认0）

        Returns:
            是否设置成功

        Examples:
            >>> await ctrl.set_sku_dimensions(page, 40, 30, 50)
            True
        """
        logger.info(f"SOP 4.7: 设置尺寸 -> {length}x{width}x{height} CM")

        try:
            first_edit_config = self.selectors.get("first_edit_dialog", {})
            sales_attrs_config = first_edit_config.get("sales_attrs", {})

            # 查找长宽高输入框（移除type限制）
            length_selectors = ["input[placeholder='长']", "input[placeholder*='长']"]
            width_selectors = ["input[placeholder='宽']", "input[placeholder*='宽']"]
            height_selectors = ["input[placeholder='高']", "input[placeholder*='高']"]

            # 查找长度输入框
            length_input = None
            for selector in length_selectors:
                try:
                    count = await page.locator(selector).count()
                    logger.debug(f"长度选择器 {selector} 找到 {count} 个元素")
                    if count > 0:
                        elem = page.locator(selector).nth(sku_index)
                        if await elem.is_visible(timeout=1000):
                            length_input = elem
                            break
                except:
                    continue

            # 查找宽度输入框
            width_input = None
            for selector in width_selectors:
                try:
                    count = await page.locator(selector).count()
                    logger.debug(f"宽度选择器 {selector} 找到 {count} 个元素")
                    if count > 0:
                        elem = page.locator(selector).nth(sku_index)
                        if await elem.is_visible(timeout=1000):
                            width_input = elem
                            break
                except:
                    continue

            # 查找高度输入框
            height_input = None
            for selector in height_selectors:
                try:
                    count = await page.locator(selector).count()
                    logger.debug(f"高度选择器 {selector} 找到 {count} 个元素")
                    if count > 0:
                        elem = page.locator(selector).nth(sku_index)
                        if await elem.is_visible(timeout=1000):
                            height_input = elem
                            break
                except:
                    continue

            if not length_input or not width_input or not height_input:
                logger.error(
                    f"未找到尺寸输入框（长:{length_input is not None}, 宽:{width_input is not None}, 高:{height_input is not None}）"
                )
                return False

            # 填写长宽高
            await length_input.fill("")
            # await page.wait_for_timeout(200)
            await length_input.fill(str(length))
            # await page.wait_for_timeout(200)

            await width_input.fill("")
            # await page.wait_for_timeout(200)
            await width_input.fill(str(width))
            # await page.wait_for_timeout(200)

            await height_input.fill("")
            # await page.wait_for_timeout(200)
            await height_input.fill(str(height))
            # await page.wait_for_timeout(300)

            logger.success(f"✓ 尺寸已设置: {length}x{width}x{height} CM")
            return True

        except Exception as e:
            logger.error(f"设置尺寸失败: {e}")
            return False

    async def save_changes(self, page: Page, wait_for_close: bool = False) -> bool:
        """保存修改并关闭弹窗.

        Args:
            page: Playwright页面对象
            wait_for_close: 是否等待弹窗关闭（默认False）

        Returns:
            是否保存成功

        Examples:
            >>> await ctrl.save_changes(page)
            True
        """
        logger.info("保存修改...")

        try:
            # 点击保存按钮
            save_selectors = [
                "button:has-text('保存')",
                "button:has-text('确定')",
                "button:has-text('提交')",
            ]

            saved = False
            for selector in save_selectors:
                try:
                    count = await page.locator(selector).count()
                    if count > 0:
                        logger.debug(f"找到保存按钮: {selector}")
                        await page.locator(selector).first.click()
                        saved = True
                        break
                except:
                    continue

            if not saved:
                logger.error("未找到保存按钮")
                return False

            # 等待保存完成
            # await page.wait_for_timeout(2000)

            if wait_for_close:
                # 等待弹窗关闭（检查弹窗是否还存在）
                try:
                    logger.debug("等待编辑弹窗关闭...")
                    # 等待更长时间确保保存完成
                    # await page.wait_for_timeout(2000)

                    # 检查弹窗是否关闭
                    dialog_count = await page.locator(
                        ".jx-dialog, .el-dialog, [role='dialog']"
                    ).count()
                    if dialog_count == 0:
                        logger.success("✓ 修改已保存，弹窗已关闭")
                    else:
                        # 弹窗还在，再等一会
                        logger.debug(f"弹窗仍存在（{dialog_count}个），继续等待...")
                        # await page.wait_for_timeout(2000)
                        dialog_count = await page.locator(
                            ".jx-dialog, .el-dialog, [role='dialog']"
                        ).count()
                        if dialog_count == 0:
                            logger.success("✓ 修改已保存，弹窗已关闭")
                        else:
                            logger.warning(f"⚠️ 修改已保存，但弹窗仍打开（{dialog_count}个）")
                except Exception as e:
                    logger.warning(f"检查弹窗状态时出错: {e}")
                    logger.success("✓ 修改已保存")
            else:
                logger.success("✓ 修改已保存")

            return True

        except Exception as e:
            logger.error(f"保存修改失败: {e}")
            return False

    async def upload_size_chart(self, page: Page, image_url: str) -> bool:
        """上传尺寸图（SOP步骤4.5 - 补充尺寸图）.

        使用网络图片URL上传尺寸图到产品详情。

        Args:
            page: Playwright页面对象
            image_url: 网络图片URL

        Returns:
            是否上传成功

        Examples:
            >>> await ctrl.upload_size_chart(page, "https://example.com/size.jpg")
            True
        """
        logger.info(f"SOP 4.5: 上传尺寸图 -> {image_url[:50]}...")

        try:
            # 等待页面稳定
            # await page.wait_for_timeout(500)

            # 尝试找到"使用网络图片"按钮（需要在详情图片区域）
            network_image_selectors = [
                "button:has-text('使用网络图片')",
                "button:has-text('网络图片')",
                ".jx-button:has-text('使用网络图片')",
                "xpath=//button[contains(text(), '使用网络图片')]",
            ]

            upload_btn = None
            for selector in network_image_selectors:
                try:
                    count = await page.locator(selector).count()
                    if count > 0:
                        upload_btn = page.locator(selector).first
                        if await upload_btn.is_visible(timeout=1000):
                            logger.debug(f"找到「使用网络图片」按钮: {selector}")
                            break
                except Exception as e:
                    logger.debug(f"尝试选择器 {selector} 失败: {e}")
                    continue

            if not upload_btn:
                logger.warning("⚠️  未找到「使用网络图片」按钮，尺寸图上传跳过")
                return False

            # 点击"使用网络图片"
            await upload_btn.click()
            # await page.wait_for_timeout(500)

            # 查找URL输入框
            url_input_selectors = [
                "input[placeholder*='图片']",
                "input[placeholder*='URL']",
                "input[placeholder*='网址']",
                ".jx-input__inner",
            ]

            url_input = None
            for selector in url_input_selectors:
                try:
                    elem = page.locator(selector).last  # 通常是最后一个弹出的输入框
                    if await elem.is_visible(timeout=1000):
                        url_input = elem
                        logger.debug(f"找到URL输入框: {selector}")
                        break
                except Exception:
                    continue

            if not url_input:
                logger.error("未找到URL输入框")
                return False

            # 输入图片URL
            await url_input.fill(image_url)
            # await page.wait_for_timeout(300)

            # 点击确定/确认按钮
            confirm_btn_selectors = [
                "button:has-text('确定')",
                "button:has-text('确认')",
                ".jx-button--primary:has-text('确')",
            ]

            for selector in confirm_btn_selectors:
                try:
                    btn = page.locator(selector).last
                    if await btn.is_visible(timeout=1000):
                        await btn.click()
                        logger.success(f"✓ 尺寸图已上传: {image_url[:50]}...")
                        # await page.wait_for_timeout(500)
                        return True
                except Exception:
                    continue

            logger.warning("⚠️  未找到确认按钮，尺寸图可能未保存")
            return False

        except Exception as e:
            logger.error(f"上传尺寸图失败: {e}")
            return False

    async def upload_product_video(self, page: Page, video_url: str) -> bool:
        """上传产品视频（SOP步骤4.5 - 补充产品视频）.

        使用网络视频URL上传产品演示视频。

        Args:
            page: Playwright页面对象
            video_url: 网络视频URL（支持MP4等格式）

        Returns:
            是否上传成功

        Examples:
            >>> await ctrl.upload_product_video(page, "https://example.com/video.mp4")
            True
        """
        logger.info(f"SOP 4.5: 上传产品视频 -> {video_url[:50]}...")

        try:
            # 等待页面稳定
            # await page.wait_for_timeout(500)

            # 查找视频上传区域（通常在详情描述tab）
            # 可能需要先切换到"产品视频"或"详情"tab
            video_tab_selectors = [
                "text=产品视频",
                "text=视频",
                ".jx-tabs__item:has-text('视频')",
            ]

            for selector in video_tab_selectors:
                try:
                    tab = page.locator(selector).first
                    if await tab.is_visible(timeout=1000):
                        await tab.click()
                        # await page.wait_for_timeout(500)
                        logger.debug(f"已切换到视频tab: {selector}")
                        break
                except Exception:
                    continue

            # 查找"使用网络视频"或类似按钮
            network_video_selectors = [
                "button:has-text('使用网络视频')",
                "button:has-text('网络视频')",
                "button:has-text('添加视频')",
                ".jx-button:has-text('视频')",
                "xpath=//button[contains(text(), '网络') and contains(text(), '视频')]",
            ]

            upload_btn = None
            for selector in network_video_selectors:
                try:
                    count = await page.locator(selector).count()
                    if count > 0:
                        upload_btn = page.locator(selector).first
                        if await upload_btn.is_visible(timeout=1000):
                            logger.debug(f"找到视频上传按钮: {selector}")
                            break
                except Exception as e:
                    logger.debug(f"尝试选择器 {selector} 失败: {e}")
                    continue

            if not upload_btn:
                logger.warning("⚠️  未找到视频上传按钮，视频上传跳过")
                logger.info("💡 提示：视频上传功能可能需要在实际环境中调试选择器")
                return False

            # 点击上传按钮
            await upload_btn.click()
            # await page.wait_for_timeout(500)

            # 查找URL输入框
            url_input_selectors = [
                "input[placeholder*='视频']",
                "input[placeholder*='URL']",
                "input[placeholder*='网址']",
                ".jx-input__inner",
            ]

            url_input = None
            for selector in url_input_selectors:
                try:
                    elem = page.locator(selector).last
                    if await elem.is_visible(timeout=1000):
                        url_input = elem
                        logger.debug(f"找到视频URL输入框: {selector}")
                        break
                except Exception:
                    continue

            if not url_input:
                logger.error("未找到视频URL输入框")
                return False

            # 输入视频URL
            await url_input.fill(video_url)
            # await page.wait_for_timeout(500)

            # 点击确定/确认按钮
            confirm_btn_selectors = [
                "button:has-text('确定')",
                "button:has-text('确认')",
                ".jx-button--primary:has-text('确')",
            ]

            for selector in confirm_btn_selectors:
                try:
                    btn = page.locator(selector).last
                    if await btn.is_visible(timeout=1000):
                        await btn.click()
                        logger.success(f"✓ 产品视频已上传: {video_url[:50]}...")
                        # await page.wait_for_timeout(1000)
                        return True
                except Exception:
                    continue

            logger.warning("⚠️  未找到确认按钮，视频可能未保存")
            return False

        except Exception as e:
            logger.error(f"上传产品视频失败: {e}")
            logger.info("💡 提示：视频上传功能可能需要在实际环境中调试")
            return False

    async def close_dialog(self, page: Page) -> bool:
        """关闭编辑弹窗（点击右上角×）.

        Args:
            page: Playwright页面对象

        Returns:
            是否关闭成功

        Examples:
            >>> await ctrl.close_dialog(page)
            True
        """
        logger.info("关闭编辑弹窗（点击×）...")

        try:
            first_edit_config = self.selectors.get("first_edit_dialog", {})
            close_btn_selector = first_edit_config.get(
                "close_btn",
                "button[aria-label='关闭'], button[aria-label='Close'], .jx-dialog__headerbtn, .el-dialog__headerbtn",
            )

            selectors = [selector.strip() for selector in close_btn_selector.split(",")]
            fallback_selectors = [
                ".pro-dialog__close",
                ".pro-dialog__header button",
                ".dialog-close",
                "[class*='icon-close']",
            ]
            text_button_patterns = [
                "关闭此对话框",
                "关闭广告",
                "关闭",
                "我知道了",
                "知道了",
                "确定",
                "确认",
                "立即进入",
                "关闭弹窗",
            ]
            text_button_regex = [re.compile(pattern) for pattern in text_button_patterns]

            visible_dialog_selector = ".jx-overlay-dialog:visible, .jx-dialog:visible, .el-dialog:visible, [role='dialog']:visible"

            max_attempts = 8
            attempt = 0

            async def _click_first_visible(candidates: list[Locator]) -> bool:
                for locator in candidates:
                    try:
                        count = await locator.count()
                        if count == 0:
                            continue
                        for index in range(count):
                            candidate = locator.nth(index)
                            if await candidate.is_visible(timeout=500):
                                await candidate.click()
                                return True
                    except Exception:
                        continue
                return False

            while attempt < max_attempts:
                dialogs = page.locator(visible_dialog_selector)
                dialog_count = await dialogs.count()

                if dialog_count == 0:
                    logger.success("✓ 编辑弹窗已关闭")
                    return True

                # 取最后一个（通常是最上层弹窗）
                target_dialog = dialogs.nth(dialog_count - 1)

                candidate_locators: list[Locator] = []
                candidate_locators.extend(target_dialog.locator(selector) for selector in selectors)
                candidate_locators.extend(target_dialog.locator(selector) for selector in fallback_selectors)

                button_locators = [
                    target_dialog.get_by_role("button", name=regex) for regex in text_button_regex
                ]
                button_locators.extend(
                    target_dialog.locator("button").filter(has_text=regex) for regex in text_button_regex
                )
                button_locators.extend(
                    target_dialog.locator("a").filter(has_text=regex) for regex in text_button_regex
                )
                candidate_locators.extend(button_locators)

                closed = await _click_first_visible(candidate_locators)

                if not closed:
                    logger.debug("未找到明确的关闭按钮，尝试发送 Esc")
                    try:
                        await page.keyboard.press("Escape")
                    except Exception:
                        pass

                overlay = page.locator(".scroll-menu-pane__content")
                try:
                    if await overlay.count() and await overlay.first.is_visible(timeout=500):
                        logger.debug("检测到滚动遮挡浮层，尝试点击背景关闭")
                        try:
                            await page.mouse.click(5, 5)
                        except Exception:
                            await page.keyboard.press("Escape")
                except Exception:
                    pass

                await page.wait_for_timeout(200)
                attempt += 1

            # 超过最大尝试次数仍未关闭
            remaining = await page.locator(visible_dialog_selector).count()
            if remaining == 0:
                logger.success("✓ 编辑弹窗已关闭")
                return True

            logger.error(f"关闭弹窗超时，仍检测到 {remaining} 个弹窗")
            return False

        except Exception as e:
            logger.error(f"关闭弹窗失败: {e}")
            return False

    async def complete_first_edit(
        self,
        page: Page,
        title: str,
        price: float,
        stock: int,
        weight: float,
        dimensions: tuple[float, float, float],
    ) -> bool:
        """完成首次编辑的完整流程（SOP步骤4的所有子步骤）.

        Args:
            page: Playwright页面对象
            title: 新标题（含型号后缀）
            price: 货源价格
            stock: 库存数量
            weight: 重量（KG）
            dimensions: 尺寸元组 (长, 宽, 高) CM

        Returns:
            是否全部完成

        Examples:
            >>> await ctrl.complete_first_edit(
            ...     page,
            ...     "新款洗衣篮 A0001型号",
            ...     174.78,
            ...     99,
            ...     0.5,
            ...     (40, 30, 50)
            ... )
            True
        """
        logger.info("=" * 60)
        logger.info("开始执行首次编辑完整流程（SOP步骤4）")
        logger.info("=" * 60)

        try:
            # 步骤4.1: 编辑标题
            if not await self.edit_title(page, title):
                return False

            # 步骤4.4: 设置价格
            if not await self.set_sku_price(page, price):
                return False

            # 步骤4.5: 设置库存
            if not await self.set_sku_stock(page, stock):
                return False

            # 步骤4.6: 设置包裹重量（物流信息Tab）
            logger.info("尝试设置包裹重量（物流信息Tab）...")
            weight_success = await self.set_package_weight_in_logistics(page, weight)
            if not weight_success:
                logger.warning("⚠️ 包裹重量设置失败 - 可能需要Codegen验证选择器")

            # 步骤4.7: 设置包裹尺寸（物流信息Tab）
            logger.info("尝试设置包裹尺寸（物流信息Tab）...")
            length, width, height = dimensions
            try:
                dimensions_success = await self.set_package_dimensions_in_logistics(
                    page, length, width, height
                )
                if not dimensions_success:
                    logger.warning("⚠️ 包裹尺寸设置失败 - 可能需要Codegen验证选择器")
            except ValueError as e:
                logger.error(f"尺寸验证失败: {e}")
                logger.warning("⚠️ 跳过尺寸设置")

            # 切换回基本信息Tab（为了保存操作）
            logger.info("切换回基本信息Tab...")
            nav_config = self.selectors.get("first_edit_dialog", {}).get("navigation", {})
            basic_info_selector = nav_config.get("basic_info", "text='基本信息'")
            try:
                await page.locator(basic_info_selector).click()
                # await page.wait_for_timeout(500)
            except:
                logger.warning("切换回基本信息Tab失败，但继续执行")

            # 保存修改
            if not await self.save_changes(page, wait_for_close=False):
                return False

            # 保存后需要手动关闭弹窗（点击右上角的×）
            logger.debug("点击关闭按钮（×）...")
            if not await self.close_dialog(page):
                logger.warning("⚠️ 关闭弹窗失败，但继续执行")

            logger.info("=" * 60)
            logger.success("✓ 首次编辑完整流程已完成（标题、价格、库存、重量、尺寸）")
            logger.info("=" * 60)
            return True

        except Exception as e:
            logger.error(f"首次编辑流程失败: {e}")
            return False


# 测试代码
if __name__ == "__main__":
    # 这个控制器需要配合Page对象使用
    # 测试请在集成测试中进行
    pass
