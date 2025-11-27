"""
@PURPOSE: 发布控制器，负责商品的发布流程（SOP步骤8-11）
@OUTLINE:
  - class PublishController: 发布控制器主类
  - async def select_all_20_products(): 全选20条产品
  - async def select_shop(): 选择店铺（SOP步骤8）
  - async def set_supply_price(): 设置供货价（SOP步骤9）
  - async def batch_publish(): 批量发布（SOP步骤10）
  - async def check_publish_result(): 查看发布记录（SOP步骤11）
@GOTCHAS:
  - 批量发布需要2次确认
  - 供货价公式：真实供货价×3 = 成本×7.5
  - 发布后需要检查成功率
@TECH_DEBT:
  - TODO: 需要使用Playwright Codegen获取实际选择器
  - TODO: 添加发布失败的错误处理和重试机制
@DEPENDENCIES:
  - 内部: data_processor.price_calculator
  - 外部: playwright, loguru
@RELATED: miaoshou_controller.py, batch_edit_controller.py
"""

import asyncio
import json
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger
from playwright.async_api import Page

from ..data_processor.price_calculator import PriceCalculator


class PublishController:
    """发布控制器（SOP步骤8-11）.

    负责商品发布的完整流程：
    - 步骤8：选择店铺
    - 步骤9：设置供货价
    - 步骤10：批量发布（2次确认）
    - 步骤11：查看发布记录

    Attributes:
        selectors: 选择器配置
        price_calculator: 价格计算器

    Examples:
        >>> ctrl = PublishController()
        >>> await ctrl.select_shop(page, "测试店铺")
        >>> await ctrl.set_supply_price(page, products_data)
        >>> await ctrl.batch_publish(page)
        >>> result = await ctrl.check_publish_result(page)
    """

    def __init__(self, selector_path: str = "config/miaoshou_selectors_v2.json"):
        """初始化发布控制器.

        Args:
            selector_path: 选择器配置文件路径
        """
        self.selector_path = Path(selector_path)
        self.selectors = self._load_selectors()
        self.price_calculator = PriceCalculator()
        
        logger.info("发布控制器初始化（SOP步骤8-11）")

    def _load_selectors(self) -> dict:
        """加载选择器配置.

        Returns:
            选择器配置字典
        """
        try:
            if not self.selector_path.is_absolute():
                current_file = Path(__file__)
                project_root = current_file.parent.parent.parent
                selector_file = project_root / self.selector_path
            else:
                selector_file = self.selector_path

            with open(selector_file, "r", encoding="utf-8") as f:
                config = json.load(f)
                logger.debug(f"选择器配置已加载: {selector_file}")
                return config
        except Exception as e:
            logger.warning(f"加载选择器配置失败: {e}，将使用默认选择器")
            return {}

    async def select_all_20_products(self, page: Page) -> bool:
        """全选20条产品（发布前准备）.

        Args:
            page: Playwright页面对象

        Returns:
            是否成功全选

        Examples:
            >>> await ctrl.select_all_20_products(page)
            True
        """
        logger.info("全选20条产品...")
        #等待页面加载完成
        await page.wait_for_load_state("domcontentloaded")
        try:
            # 使用全选按钮
            collection_box_config = self.selectors.get("collection_box", {})
            pagination_config = collection_box_config.get("pagination", {})
            select_all_selector = pagination_config.get("select_all", "text='全选'")
            
            await page.locator(select_all_selector).click()
            await page.wait_for_timeout(500)

            logger.success("✓ 已全选20条产品")
            return True

        except Exception as e:
            logger.error(f"全选产品失败: {e}")
            return False

    async def select_shop(self, page: Page, shop_name: Optional[str] = None) -> bool:
        """选择店铺（SOP步骤8）.

        Args:
            page: Playwright页面对象
            shop_name: 店铺名称（可选，None则选择第一个）

        Returns:
            是否选择成功

        Examples:
            >>> await ctrl.select_shop(page, "我的测试店铺")
            True
        """
        logger.info("=" * 60)
        logger.info("[SOP步骤8] 选择店铺")
        logger.info("=" * 60)

        try:
            # 注意：需要使用Codegen获取实际的选择器
            # 这里提供框架代码，实际选择器需要补充

            logger.info("先全选需要发布的商品")
            await self.select_all_20_products(page)
            await page.wait_for_timeout(500)
            
            collection_box_config = self.selectors.get("collection_box", {})
            action_buttons = collection_box_config.get("action_buttons", {})
            
            # 1. 点击"选择店铺"按钮（或类似按钮）
            # TODO: 需要通过Codegen确认实际按钮文本和选择器
            select_shop_selector = (
                "xpath=/html/body/div[1]/section/div/div[4]/div/div[1]/button[2]"
            )
            
            logger.info("点击「选择店铺」按钮...")
            await page.locator(select_shop_selector).click()
            await page.wait_for_timeout(1000)

            # 2. 选择店铺
            normalized_name = (shop_name or "").strip()
            skip_specific_shop = normalized_name == "" or normalized_name.lower() in {"未指定", "all", "*"}

            if not skip_specific_shop:
                logger.info(f"选择店铺: {normalized_name}")
                shop_selector = f"text='{normalized_name}'"
                try:
                    target = page.locator(shop_selector)
                    if await target.count() == 0:
                        raise RuntimeError(f"未在弹窗中找到店铺: {normalized_name}")
                    await target.first.click()
                except Exception as exc:
                    logger.warning("定位店铺 %s 失败，尝试改为全选店铺: %s", normalized_name, exc)
                    await self._select_all_shops(page)
            else:
                logger.info("未指定店铺，直接全选所有店铺")
                await self._select_all_shops(page)

            await page.wait_for_timeout(500)

            # 3. 确认选择
            await self._confirm_shop_selection(page)
            await page.wait_for_timeout(1000)

            logger.success("✓ 店铺选择完成")
            return True

        except Exception as e:
            logger.error(f"选择店铺失败: {e}")
            logger.warning("⚠️  需要使用Codegen获取正确的选择器")
            return False

    async def _select_all_shops(self, page: Page) -> None:
        """在店铺弹窗中勾选“全选”复选框."""

        selectors = [
            "label.jx-checkbox.jx-checkbox--small.pro-checkbox-group-all-select.pro-checkbox",
            "label:has-text('全选')",
            "button:has-text('全选')",
            "text='全选'",
        ]

        for selector in selectors:
            locator = page.locator(selector)
            try:
                if await locator.count() == 0:
                    continue
                await locator.first.click()
                logger.success("✓ 已全选所有店铺 (selector=%s)", selector)
                return
            except Exception as exc:
                logger.debug("尝试 selector=%s 失败: %s", selector, exc)

        raise RuntimeError("未找到可用的“全选”选项，无法继续选择店铺")

    async def _confirm_shop_selection(self, page: Page) -> None:
        """点击店铺选择弹窗中的“确定/确认”按钮."""

        confirm_selectors = [
            "button.jx-button.jx-button--primary:has-text('确定')",
            "button.pro-button:has-text('确定')",
            "button:has-text('确认')",
            "div[role='dialog'] button.jx-button--primary",
            "footer button.jx-button--primary",
            "button[type='button']:has-text('确定')",
        ]

        last_error: Exception | None = None
        for selector in confirm_selectors:
            locator = page.locator(selector)
            try:
                if await locator.count() == 0:
                    continue
                button = locator.first
                if not await button.is_enabled():
                    continue
                await button.scroll_into_view_if_needed()
                await button.click(timeout=3_000)
                logger.success("✓ 点击店铺选择确认按钮 (selector=%s)", selector)
                return
            except Exception as exc:
                last_error = exc
                logger.debug("点击确认按钮失败 selector=%s, err=%s", selector, exc)

        # fallback: 尝试按 Enter 或 Esc
        try:
            await page.keyboard.press("Enter")
            logger.info("已通过键盘 Enter 确认店铺选择")
            return
        except Exception:
            pass

        if last_error:
            raise last_error
        raise RuntimeError("未能找到“确定”按钮，无法确认店铺选择")

    async def set_supply_price(
        self,
        page: Page,
        products_data: List[Dict]
    ) -> bool:
        """设置供货价（SOP步骤9）.

        公式：
        - 真实供货价 = 成本 × 2.5（最低）
        - 妙手供货价 = 真实供货价 × 3 = 成本 × 7.5

        Args:
            page: Playwright页面对象
            products_data: 产品数据列表，每个包含cost字段

        Returns:
            是否设置成功

        Examples:
            >>> products = [{"cost": 10.0}, {"cost": 12.0}]
            >>> await ctrl.set_supply_price(page, products)
            True
        """
        logger.info("=" * 60)
        logger.info("[SOP步骤9] 设置供货价")
        logger.info("=" * 60)
        await page.wait_for_timeout(500)
#重试3次
        for _ in range(3):
            if await self.select_all_20_products(page):
                break
            await asyncio.sleep(1)
        else:
            logger.error("全选商品失败")
            return False
            
        try:
            # 1. 点击"设置供货价"按钮
            # TODO: 需要通过Codegen确认实际按钮文本和选择器
            set_price_btn_selector = "button:has-text('设置供货价'), button:has-text('供货价')"
            
            logger.info("点击「设置供货价」按钮...")
            await page.locator(set_price_btn_selector).click()
            await page.wait_for_timeout(1000)
            
            # 2. 选择“使用公式”
            logger.info("选择「使用公式」模式...")
            formula_locators = [
                "label:has(span.jx-radio__label:has-text('使用公式'))"
            ]

            clicked_selector = None
            for selector in formula_locators:
                locator = page.locator(selector).first
                try:
                    await locator.click()
                    clicked_selector = selector
                    break
                except Exception as exc:
                    logger.debug("使用选择器 %s 点击失败: %s", selector, exc)
            if not clicked_selector:
                raise RuntimeError("未能点击『使用公式』选项，请检查DOM结构")
            logger.info("使用公式选择器命中：%s", clicked_selector)

            await page.wait_for_timeout(500)

            # 3. 点击“倍数”文本框并填写 3
            multiplier_locators = [
                "input[placeholder='倍数']",
                "xpath=//label[contains(.,'倍数')]/following::input[1]",
            ]
            multiplier_clicked = None
            for selector in multiplier_locators:
                try:
                    multiplier_input = page.locator(selector).first
                    await multiplier_input.click()
                    multiplier_clicked = selector
                    break
                except Exception as exc:
                    logger.debug("倍数输入框选择器 %s 点击失败: %s", selector, exc)
            if not multiplier_clicked:
                raise RuntimeError("未能定位到『倍数』输入框，请检查DOM结构")

            await multiplier_input.fill("3")
            logger.info("倍数输入框选择器命中：%s", multiplier_clicked)
            await page.wait_for_timeout(300)

            # 4. 点击“应用”按钮
            await page.locator("button:has-text('应用')").first.click()
            await page.wait_for_timeout(1000)

            # 5. 等待提示弹窗并关闭
            close_selectors = [
                "body > div:nth-child(25) > div > div > footer > button",
                "button:has-text('关闭')",
            ]
            close_clicked = None
            for selector in close_selectors:
                try:
                    await page.locator(selector).first.click()
                    close_clicked = selector
                    break
                except Exception as exc:
                    logger.debug("关闭提示弹窗选择器 %s 失败: %s", selector, exc)
            if close_clicked:
                logger.info("已关闭提示弹窗：%s", close_clicked)
            else:
                logger.warning("未能自动关闭提示弹窗，请确认页面状态")

            logger.success("✓ 供货价设置完成（使用公式倍数 3）")
            return True

        except Exception as e:
            logger.error(f"设置供货价失败: {e}")
            logger.warning("⚠️  需要使用Codegen获取正确的选择器")
            return False

    async def batch_publish(self, page: Page) -> bool:
        """批量发布（SOP步骤10）.

        需要2次确认：
        1. 第1次点击"批量发布"
        2. 第2次确认发布

        结果：20条 × 2次 = 40条产品

        Args:
            page: Playwright页面对象

        Returns:
            是否发布成功

        Examples:
            >>> await ctrl.batch_publish(page)
            True
        """
        logger.info("=" * 60)
        logger.info("[SOP步骤10] 批量发布（2次确认）")
        logger.info("=" * 60)
        await page.wait_for_timeout(500)

        for _ in range(3):
            if await self.select_all_20_products(page):
                break
            await asyncio.sleep(1)
        else:
            logger.error("全选商品失败")
            return False
        try:
            # 1. 第1次：点击"批量发布"按钮
            publish_btn_selectors = [
                "#appScrollContainer > div.sticky-operate-box.space-between > div > div:nth-child(1) > button:nth-child(1)",
                "button:has-text('批量发布')",
                "button:has-text('发布')",
            ]

            logger.info("[1/2] 点击「批量发布」按钮...")
            publish_clicked = None
            for selector in publish_btn_selectors:
                try:
                    await page.locator(selector).first.click()
                    publish_clicked = selector
                    break
                except Exception as exc:
                    logger.debug("批量发布按钮选择器 %s 点击失败: %s", selector, exc)
            if not publish_clicked:
                raise RuntimeError("未能点击「批量发布」按钮，请检查DOM结构")
            logger.info("批量发布按钮选择器命中：%s", publish_clicked)
            await page.wait_for_timeout(1500)

            # 1.2 等待弹窗出现并点击确认
            await page.wait_for_timeout(5000)
            confirm_first_selectors = [
                "body > div:nth-child(26) > div > div > footer > div > div > button",
                "button:has-text('我已完成整改')",
                "button:has-text('知道了')",
            ]
            confirm_first_clicked = None
            for selector in confirm_first_selectors:
                try:
                    await page.locator(selector).first.click()
                    confirm_first_clicked = selector
                    break
                except Exception as exc:
                    logger.debug("批量发布前置弹窗选择器 %s 点击失败: %s", selector, exc)
            if confirm_first_clicked:
                logger.info("批量发布前置弹窗已关闭：%s", confirm_first_clicked)
            else:
                logger.warning("未能自动关闭批量发布前置弹窗，可能页面未出现该弹窗")

            # 1.5 点击“图片顺序随机打乱”
            shuffle_selectors = [
                "button:has-text('图片顺序随机打乱')",
                "label:has-text('图片顺序随机打乱')",
                "text=图片顺序随机打乱",
            ]
            shuffle_clicked = None
            for selector in shuffle_selectors:
                try:
                    await page.locator(selector).first.click()
                    shuffle_clicked = selector
                    await page.wait_for_timeout(500)
                    logger.info("已点击「图片顺序随机打乱」：%s", selector)
                    break
                except Exception as exc:
                    logger.debug("图片顺序随机打乱选择器 %s 点击失败: %s", selector, exc)
            if not shuffle_clicked:
                logger.warning("未能点击「图片顺序随机打乱」，请确认页面状态")

            # 2. 第2次确认：确认发布
            confirm_publish_selectors = [
                "body > div:nth-child(25) > div > div > footer > div > div.release-footer-wrapper__right > button.jx-button.jx-button--primary.jx-button--default.pro-button",
                "button:has-text('确认发布')",
                "button:has-text('确定')",
            ]

            logger.info("[2/2] 确认发布...")
            confirm_publish_clicked = None
            for selector in confirm_publish_selectors:
                try:
                    await page.locator(selector).first.click()
                    confirm_publish_clicked = selector
                    break
                except Exception as exc:
                    logger.debug("确认发布按钮选择器 %s 点击失败: %s", selector, exc)
            if not confirm_publish_clicked:
                raise RuntimeError("未能点击「确认发布」按钮，请检查DOM结构")
            logger.info("确认发布按钮选择器命中：%s", confirm_publish_clicked)
            await page.wait_for_timeout(2000)

            logger.success("✓ 批量发布完成（20条×2次=40条产品）")
            return True

        except Exception as e:
            logger.error(f"批量发布失败: {e}")
            logger.warning("⚠️  需要使用Codegen获取正确的选择器")
            return False

    async def check_publish_result(self, page: Page) -> Dict:
        """查看发布记录（SOP步骤11）.

        Args:
            page: Playwright页面对象

        Returns:
            发布结果字典：{
                "success_count": int,  # 成功数量
                "fail_count": int,     # 失败数量
                "total_count": int,    # 总数量
                "fail_reasons": List[str]  # 失败原因列表
            }

        Examples:
            >>> result = await ctrl.check_publish_result(page)
            >>> result["success_count"]
            35
        """
        logger.info("=" * 60)
        logger.info("[SOP步骤11] 查看发布记录")
        logger.info("=" * 60)

        result = {
            "success_count": 0,
            "fail_count": 0,
            "total_count": 0,
            "fail_reasons": []
        }

        try:
            # 1. 点击"发布记录"入口
            # TODO: 需要通过Codegen确认实际入口位置
            publish_record_selector = "text='发布记录', a:has-text('发布记录')"
            
            logger.info("打开「发布记录」...")
            await page.locator(publish_record_selector).click()
            await page.wait_for_timeout(2000)

            # 2. 选择自己的店铺（如果需要）
            # TODO: 实际操作可能需要选择店铺筛选

            # 3. 获取发布统计
            # TODO: 需要确认实际的统计显示方式
            logger.info("获取发布统计...")
            
            # 示例：解析页面上的成功/失败数量
            # 实际实现需要根据页面结构调整
            success_text = await page.locator("text=/成功.*\\d+/").first.text_content(timeout=3000)
            if success_text:
                import re
                match = re.search(r"(\d+)", success_text)
                if match:
                    result["success_count"] = int(match.group(1))

            fail_text = await page.locator("text=/失败.*\\d+/").first.text_content(timeout=3000)
            if fail_text:
                import re
                match = re.search(r"(\d+)", fail_text)
                if match:
                    result["fail_count"] = int(match.group(1))

            result["total_count"] = result["success_count"] + result["fail_count"]

            logger.info("=" * 60)
            logger.info("发布结果统计：")
            logger.info(f"  总计: {result['total_count']}")
            logger.info(f"  成功: {result['success_count']}")
            logger.info(f"  失败: {result['fail_count']}")
            logger.info("=" * 60)

            # SOP规定：正常可以发布成功50-100条
            if result["success_count"] >= 50:
                logger.success("✓ 发布成功率正常（≥50条）")
            elif result["success_count"] > 0:
                logger.warning(f"⚠️  发布成功率偏低（{result['success_count']}条）")
            else:
                logger.error("✗ 发布全部失败")

            return result

        except Exception as e:
            logger.error(f"查看发布记录失败: {e}")
            logger.warning("⚠️  需要使用Codegen获取正确的选择器")
            return result

    async def execute_publish_workflow(
        self,
        page: Page,
        products_data: List[Dict],
        shop_name: Optional[str] = None
    ) -> Dict:
        """执行完整的发布工作流（SOP步骤8-11）.

        Args:
            page: Playwright页面对象
            products_data: 产品数据列表
            shop_name: 店铺名称（可选）

        Returns:
            执行结果字典：{
                "success": bool,
                "shop_selected": bool,
                "price_set": bool,
                "published": bool,
                "publish_result": Dict
            }

        Examples:
            >>> result = await ctrl.execute_publish_workflow(page, products_data, "测试店铺")
            >>> result["success"]
            True
        """
        logger.info("=" * 80)
        logger.info("开始执行发布工作流（SOP步骤8-11）")
        logger.info("=" * 80)

        result = {
            "success": False,
            "shop_selected": False,
            "price_set": False,
            "published": False,
            "publish_result": {}
        }

        try:
            # 1. 全选20条产品
            logger.info("\n[准备] 全选20条产品...")
            await self.select_all_20_products(page)

            # 2. 选择店铺（步骤8）
            logger.info("\n[步骤8/11] 选择店铺...")
            if await self.select_shop(page, shop_name):
                result["shop_selected"] = True

            # 3. 设置供货价（步骤9）
            logger.info("\n[步骤9/11] 设置供货价...")
            if await self.set_supply_price(page, products_data):
                result["price_set"] = True

            # 4. 批量发布（步骤10）
            logger.info("\n[步骤10/11] 批量发布...")
            if await self.batch_publish(page):
                result["published"] = True

            # 5. 查看发布记录（步骤11）
            logger.info("\n[步骤11/11] 查看发布记录...")
            publish_result = await self.check_publish_result(page)
            result["publish_result"] = publish_result

            # 判断整体是否成功
            result["success"] = (
                result["shop_selected"] and
                result["price_set"] and
                result["published"] and
                publish_result.get("success_count", 0) > 0
            )

            logger.info("\n" + "=" * 80)
            logger.info("发布工作流执行完成")
            logger.info(f"执行结果: {'✓ 成功' if result['success'] else '✗ 失败'}")
            logger.info("=" * 80)

            return result

        except Exception as e:
            logger.error(f"发布工作流执行失败: {e}")
            return result


# 测试代码
if __name__ == "__main__":
    # 这个控制器需要配合Page对象使用
    # 测试请在集成测试中进行
    pass

