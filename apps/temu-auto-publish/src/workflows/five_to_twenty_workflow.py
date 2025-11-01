"""
@PURPOSE: 实现5→20工作流（SOP步骤4-6）：逐个编辑5条链接，每条认领4次，生成20条产品
@OUTLINE:
  - async def execute_five_to_twenty_workflow(): 执行完整的5→20流程（逐个AI生成模式）
  - async def edit_single_product(): 编辑单个产品（首次编辑+逐个AI生成）
  - class FiveToTwentyWorkflow: 工作流控制类
@GOTCHAS:
  - 必须先完成首次编辑，再进行认领
  - 认领操作需要等待UI更新
  - 最终需要验证是否达到20条产品
  - 每个产品独立调用AI生成标题，失败时自动降级
@TECH_DEBT:
  - TODO: 添加更详细的错误恢复机制
  - TODO: 支持自定义认领次数
@DEPENDENCIES:
  - 内部: browser.miaoshou_controller, browser.first_edit_controller, data_processor.ai_title_generator
  - 外部: playwright, loguru
@RELATED: miaoshou_controller.py, first_edit_controller.py, ai_title_generator.py
"""

import asyncio
import random
from typing import Dict, List, Optional, Tuple

from loguru import logger
from playwright.async_api import Page

from ..browser.first_edit_controller import FirstEditController
from ..browser.miaoshou_controller import MiaoshouController
from ..data_processor.title_generator import TitleGenerator
from ..data_processor.price_calculator import PriceCalculator
from ..data_processor.random_generator import RandomDataGenerator
from ..data_processor.ai_title_generator import AITitleGenerator
from ..utils.debug_helper import DebugHelper


class FiveToTwentyWorkflow:
    """5→20工作流控制器（SOP步骤4-6）.

    实现妙手ERP的核心流程：
    1. 首次编辑5条链接（标题、价格、库存）
    2. 每条链接认领4次
    3. 验证是否生成20条产品

    SOP规定：5条 × 4次认领 = 20条产品

    Attributes:
        miaoshou_ctrl: 妙手采集箱控制器
        first_edit_ctrl: 首次编辑控制器
        title_generator: 标题生成器
        price_calculator: 价格计算器
        random_generator: 随机数据生成器

    Examples:
        >>> workflow = FiveToTwentyWorkflow()
        >>> result = await workflow.execute(page, products_data)
        >>> result["success"]
        True
    """

    def __init__(self, use_ai_titles: bool = True, debug_mode: bool = False):
        """初始化工作流控制器.
        
        Args:
            use_ai_titles: 是否使用AI生成标题（默认True）
            debug_mode: 是否启用调试模式（默认False）
        """
        self.miaoshou_ctrl = MiaoshouController()
        self.first_edit_ctrl = FirstEditController()
        self.title_generator = TitleGenerator()
        self.price_calculator = PriceCalculator()
        self.random_generator = RandomDataGenerator()
        self.ai_title_generator = AITitleGenerator()
        self.use_ai_titles = use_ai_titles
        self.debug = DebugHelper(enabled=debug_mode)
        
        logger.info(f"5→20工作流控制器已初始化（AI标题: {'启用' if use_ai_titles else '禁用'}，调试模式: {'启用' if debug_mode else '禁用'}）")

    async def edit_single_product(
        self,
        page: Page,
        product_index: int,
        product_data: Dict,
        new_titles: Optional[List[str]] = None
    ) -> bool:
        """编辑单个产品（首次编辑+逐个AI生成）.

        执行SOP步骤4的首次编辑（逐个AI生成模式）：
        1. 点击编辑按钮
        2. 读取原始标题
        3. 调用AI生成新标题（独立对话）
        4. 填写新标题
        5. 设置价格、库存
        6. 保存并关闭

        Args:
            page: Playwright页面对象
            product_index: 产品索引（0-4）
            product_data: 产品数据字典，包含：
                - keyword: 关键词
                - model_number: 型号（如A0001）
                - cost: 成本价
                - stock: 库存
            new_titles: 已弃用参数（为保持兼容性保留，逐个模式下不使用）

        Returns:
            是否编辑成功

        Examples:
            >>> await workflow.edit_single_product(page, 0, {
            ...     "keyword": "药箱收纳盒",
            ...     "model_number": "A0001",
            ...     "cost": 10.0,
            ...     "stock": 100
            ... })
            True
        """
        logger.info(f"=" * 60)
        logger.info(f"开始首次编辑第{product_index+1}个产品（逐个AI生成模式）")
        logger.info(f"=" * 60)

        # 🔴 调试断点: 开始编辑产品
        await self.debug.breakpoint(
            f"准备编辑第{product_index+1}个产品",
            data={
                "产品索引": product_index,
                "关键词": product_data.get("keyword"),
                "型号": product_data.get("model_number"),
                "成本": product_data.get("cost"),
            }
        )

        try:
            # 1. 点击编辑按钮，打开编辑弹窗
            if not await self.miaoshou_ctrl.click_edit_product_by_index(page, product_index):
                logger.error(f"✗ 无法打开第{product_index+1}个产品的编辑弹窗")
                return False

            # 🔴 调试断点: 编辑弹窗已打开
            await self.debug.breakpoint(f"编辑弹窗已打开（第{product_index+1}个产品）")

            # 2. 读取原始标题
            logger.info(f">>> 步骤1: 读取原始标题...")
            original_title = await self.first_edit_ctrl.get_original_title(page)
            if original_title:
                logger.success(f"✓ 原始标题: {original_title[:60]}...")
            else:
                logger.warning(f"⚠️ 未能读取原始标题，使用关键词作为原标题")
                original_title = product_data.get("keyword", "商品")

            # 2.5. 核对商品类目（SOP 4.3）
            logger.info(f"\n>>> 步骤1.5: 核对商品类目（SOP 4.3）...")
            is_valid_category, category_name = await self.first_edit_ctrl.check_category(page)
            
            if not is_valid_category:
                logger.error(f"❌ 类目不合规: {category_name}")
                logger.warning(f"⚠️  建议：跳过此产品或人工确认后继续")
                # 注意：这里不强制返回False，而是记录警告，由用户决定是否继续
                # 如果需要强制跳过，取消下面的注释
                # await self.first_edit_ctrl.close_dialog(page)
                # return False
            else:
                logger.success(f"✓ 类目合规: {category_name}")

            # 3. 使用AI生成新标题（独立对话）
            model_number = product_data.get("model_number", f"A{str(product_index+1).zfill(4)}")
            
            # 🔴 调试断点: 准备AI生成
            await self.debug.breakpoint(
                f"准备调用AI生成标题",
                data={
                    "原始标题": original_title[:80],
                    "型号": model_number,
                    "AI启用": self.use_ai_titles,
                }
            )
            
            if self.use_ai_titles:
                logger.info(f"\n>>> 步骤2: 调用AI生成新标题（独立对话）...")
                logger.debug(f"    AI提供商: {self.ai_title_generator.provider}")
                logger.debug(f"    模型: {self.ai_title_generator.model}")
                if self.ai_title_generator.base_url:
                    logger.debug(f"    API地址: {self.ai_title_generator.base_url}")
                
                try:
                    import time
                    start_time = time.time()
                    
                    # 调用AI生成单个标题
                    title = await self.ai_title_generator.generate_single_title(
                        original_title,
                        model_number=f"{model_number}型号",
                        use_ai=True
                    )
                    
                    elapsed_time = time.time() - start_time
                    logger.success(f"✓ AI生成完成，耗时: {elapsed_time:.2f}秒")
                    logger.info(f"✓ 新标题: {title}")
                    
                    # 🔴 调试断点: AI生成完成
                    await self.debug.breakpoint(
                        f"AI标题生成完成",
                        data={
                            "原始标题": original_title[:60],
                            "新标题": title,
                            "耗时": f"{elapsed_time:.2f}秒",
                        }
                    )
                    
                except Exception as e:
                    logger.error(f"❌ AI生成失败: {e}")
                    logger.warning(f"⚠️ 使用降级方案：原标题+型号")
                    title = f"{original_title} {model_number}型号"
            else:
                # AI未启用，使用原标题+型号
                title = f"{original_title} {model_number}型号"
                logger.info(f">>> AI未启用，使用原标题+型号: {title}")

            # 4. 编辑标题
            logger.info(f"\n>>> 步骤3: 填写新标题...")
            logger.debug(f"    标题内容: {title}")
            logger.debug(f"    标题长度: {len(title)} 字符")
            
            edit_result = await self.first_edit_ctrl.edit_title(page, title)
            
            if not edit_result:
                logger.error(f"✗ 标题编辑失败")
                logger.error(f"    失败的标题: {title}")
            else:
                logger.success(f"✓ 标题编辑成功")
            
            # 等待标题更新生效
            await page.wait_for_timeout(1000)
            logger.debug(f"    已等待1秒确保标题更新")

            # 5. 计算价格
            cost = product_data.get("cost", 10.0)
            price = self.price_calculator.calculate_supply_price(cost)
            logger.info(f"\n>>> 步骤4: 设置价格...")
            logger.debug(f"    价格: ¥{price} (成本: ¥{cost})")

            # 6. 获取库存
            stock = product_data.get("stock", 100)
            logger.info(f">>> 步骤5: 设置库存...")
            logger.debug(f"    库存: {stock}")

            # 7. 设置价格
            if not await self.first_edit_ctrl.set_sku_price(page, price):
                logger.error(f"✗ 价格设置失败")
                return False
            
            # 8. 设置库存
            if not await self.first_edit_ctrl.set_sku_stock(page, stock):
                logger.error(f"✗ 库存设置失败")
                return False
            
            # 9. 设置重量（SOP 7.9要求：5000-9999G）
            logger.info(f"\n>>> 步骤6: 设置重量...")
            weight = random.randint(5000, 9999)
            logger.debug(f"    重量: {weight}G")
            try:
                if await self.first_edit_ctrl.set_sku_weight(page, weight):
                    logger.success(f"✓ 重量已设置: {weight}G")
                else:
                    logger.warning(f"⚠️  重量设置失败（可能需要在实际环境调试选择器）")
            except Exception as e:
                logger.warning(f"⚠️  重量设置异常: {e}")
            
            # 10. 设置尺寸（SOP 7.10要求：长>宽>高，50-99cm）
            logger.info(f"\n>>> 步骤7: 设置尺寸...")
            # 生成符合要求的尺寸（长>宽>高）
            length = random.randint(80, 99)
            width = random.randint(60, length - 10)
            height = random.randint(50, width - 10)
            logger.debug(f"    尺寸: 长{length}cm × 宽{width}cm × 高{height}cm")
            try:
                if await self.first_edit_ctrl.set_sku_dimensions(page, length, width, height):
                    logger.success(f"✓ 尺寸已设置: {length}×{width}×{height}cm")
                else:
                    logger.warning(f"⚠️  尺寸设置失败（可能需要在实际环境调试选择器）")
            except Exception as e:
                logger.warning(f"⚠️  尺寸设置异常: {e}")
            
            # 11. 上传尺寸图（如果提供了URL）- SOP 4.5
            size_chart_url = product_data.get("size_chart_url")
            if size_chart_url:
                logger.info(f"\n>>> 步骤8: 上传尺寸图（SOP 4.5）...")
                try:
                    if await self.first_edit_ctrl.upload_size_chart(page, size_chart_url):
                        logger.success("✓ 尺寸图上传成功")
                    else:
                        logger.warning("⚠️  尺寸图上传失败（可能需要在实际环境调试选择器）")
                except Exception as e:
                    logger.warning(f"⚠️  尺寸图上传异常: {e}")
            else:
                logger.debug("跳过尺寸图上传（未提供URL）")

            # 12. 上传产品视频（如果提供了URL）- SOP 4.5
            video_url = product_data.get("video_url")
            if video_url:
                logger.info(f"\n>>> 步骤9: 上传产品视频（SOP 4.5）...")
                try:
                    if await self.first_edit_ctrl.upload_product_video(page, video_url):
                        logger.success("✓ 产品视频上传成功")
                    else:
                        logger.warning("⚠️  产品视频上传失败（可能需要在实际环境调试选择器）")
                except Exception as e:
                    logger.warning(f"⚠️  产品视频上传异常: {e}")
            else:
                logger.debug("跳过产品视频上传（未提供URL）")
            
            # 🔴 调试断点: 准备保存
            await self.debug.breakpoint(
                f"所有编辑完成，准备保存（第{product_index+1}个产品）",
                data={
                    "标题": title[:60],
                    "价格": price,
                    "库存": stock,
                }
            )
            
            # 13. 保存修改
            logger.info(f"\n>>> 步骤10: 保存修改...")
            if not await self.first_edit_ctrl.save_changes(page, wait_for_close=False):
                logger.error(f"✗ 保存失败")
                return False
            
            # 14. 关闭弹窗
            await self.first_edit_ctrl.close_dialog(page)
            await page.wait_for_timeout(500)

            logger.success(f"✓ 第{product_index+1}个产品首次编辑完成")
            return True

        except Exception as e:
            logger.error(f"编辑第{product_index+1}个产品失败: {e}")
            logger.exception("详细错误信息:")
            return False

    async def execute(
        self,
        page: Page,
        products_data: Optional[List[Dict]] = None,
        claim_times: int = 4
    ) -> Dict:
        """执行完整的5→20工作流.

        SOP步骤4-6的完整实现：
        1. 循环编辑5个产品（首次编辑）
        2. 每个产品认领4次
        3. 验证最终是否有20条产品

        Args:
            page: Playwright页面对象
            products_data: 5个产品的数据列表（可选，简化模式下为None）
            claim_times: 每个产品认领次数（默认4，符合SOP）

        Returns:
            执行结果字典：{
                "success": bool,
                "edited_count": int,
                "claimed_count": int,
                "final_count": int,
                "errors": List[str]
            }

        Raises:
            ValueError: 如果产品数量不正确（完整模式下）

        Examples:
            >>> # 使用Excel真实数据
            >>> result = await workflow.execute(page, [
            ...     {"keyword": "药箱", "model_number": "A0001", "cost": 10, "stock": 100, "size_chart_url": "..."},
            ...     {"keyword": "药箱", "model_number": "A0002", "cost": 12, "stock": 100, "size_chart_url": "..."},
            ...     # ... 共5个
            ... ])
            >>> result["final_count"]
            20
        """
        logger.info("=" * 80)
        logger.info("开始执行5→20工作流（SOP步骤4-6）")
        logger.info("=" * 80)

        # 验证输入数据
        if products_data is None:
            raise ValueError("必须提供产品数据（products_data），不再支持空数据模式")
        
        if len(products_data) != 5:
            raise ValueError(f"必须提供5个产品数据，当前提供了{len(products_data)}个")

        result = {
            "success": False,
            "edited_count": 0,
            "claimed_count": 0,
            "final_count": 0,
            "errors": []
        }

        try:
            # 阶段0：首次编辑5个产品（逐个AI生成模式）
            logger.info("\n" + "=" * 60)
            logger.info("[阶段0/2] 首次编辑5个产品（逐个AI生成）")
            logger.info("=" * 60)

            # 注意：假设已经在"全部"tab（在调用此函数前应该已经切换过）

            edited_count = 0
            for i in range(5):
                logger.info(f"\n>>> 编辑第{i+1}/5个产品...")
                
                # 逐个模式：不再传入new_titles，每个产品内部独立生成
                if await self.edit_single_product(page, i, products_data[i], None):
                    edited_count += 1
                    logger.success(f"✓ 第{i+1}个产品编辑成功（总计: {edited_count}/5）")
                else:
                    error_msg = f"第{i+1}个产品编辑失败"
                    result["errors"].append(error_msg)
                    logger.error(f"✗ {error_msg}")
                
                # 每个产品编辑完后等待一下
                await page.wait_for_timeout(500)

            result["edited_count"] = edited_count
            logger.info(f"\n✓ 阶段0完成：成功编辑{edited_count}/5个产品")

            if edited_count == 0:
                logger.error("✗ 没有成功编辑任何产品，终止工作流")
                return result

            # 阶段1：每个产品认领4次
            logger.info("\n" + "=" * 60)
            logger.info(f"[阶段1/2] 认领产品（每个认领{claim_times}次）")
            logger.info("=" * 60)

            # 切换到"未认领"tab
            await self.miaoshou_ctrl.switch_tab(page, "unclaimed")
            await page.wait_for_timeout(1000)

            claimed_count = 0
            for i in range(edited_count):
                logger.info(f"\n>>> 认领第{i+1}/{edited_count}个产品...")
                
                # 注意：认领后产品会移动，所以始终认领索引0的产品
                if await self.miaoshou_ctrl.claim_product_multiple_times(page, 0, claim_times):
                    claimed_count += 1
                    logger.success(f"✓ 第{i+1}个产品认领成功（总计: {claimed_count}/{edited_count}）")
                else:
                    error_msg = f"第{i+1}个产品认领失败"
                    result["errors"].append(error_msg)
                    logger.error(f"✗ {error_msg}")
                
                # 每个产品认领完后等待一下
                await page.wait_for_timeout(500)

            result["claimed_count"] = claimed_count
            logger.info(f"\n✓ 阶段2完成：成功认领{claimed_count}/{edited_count}个产品")

            # 阶段3：验证最终产品数量
            logger.info("\n" + "=" * 60)
            logger.info("[阶段3/3] 验证最终产品数量")
            logger.info("=" * 60)

            expected_count = claimed_count * claim_times
            logger.info(f"期望产品数量: {claimed_count} × {claim_times} = {expected_count}")

            if await self.miaoshou_ctrl.verify_claim_success(page, expected_count):
                result["success"] = True
                logger.success(f"✓ 工作流执行成功！最终产品数量: {expected_count}")
            else:
                error_msg = "产品数量验证失败"
                result["errors"].append(error_msg)
                logger.error(f"✗ {error_msg}")

            # 获取最终数量
            counts = await self.miaoshou_ctrl.get_product_count(page)
            result["final_count"] = counts.get("claimed", 0)

            logger.info("\n" + "=" * 80)
            logger.info("5→20工作流执行完成")
            logger.info(f"编辑成功: {result['edited_count']}/5")
            logger.info(f"认领成功: {result['claimed_count']}/{result['edited_count']}")
            logger.info(f"最终产品数: {result['final_count']} (期望: {expected_count})")
            logger.info(f"执行结果: {'✓ 成功' if result['success'] else '✗ 失败'}")
            logger.info("=" * 80)

            return result

        except Exception as e:
            error_msg = f"工作流执行异常: {e}"
            result["errors"].append(error_msg)
            logger.error(error_msg)
            return result


# 便捷函数
async def execute_five_to_twenty_workflow(
    page: Page,
    products_data: List[Dict],
    claim_times: int = 4
) -> Dict:
    """执行5→20工作流的便捷函数.

    Args:
        page: Playwright页面对象
        products_data: 5个产品的数据列表
        claim_times: 每个产品认领次数（默认4）

    Returns:
        执行结果字典

    Examples:
        >>> result = await execute_five_to_twenty_workflow(page, products_data)
    """
    workflow = FiveToTwentyWorkflow()
    return await workflow.execute(page, products_data, claim_times)


# 测试代码
if __name__ == "__main__":
    # 这个工作流需要配合Page对象和真实数据使用
    # 测试请在集成测试中进行
    pass

