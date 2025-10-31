"""
@PURPOSE: 实现5→20工作流（SOP步骤4-6）：首次编辑5条链接，每条认领4次，生成20条产品
@OUTLINE:
  - async def execute_five_to_twenty_workflow(): 执行完整的5→20流程
  - async def edit_single_product(): 编辑单个产品（首次编辑）
  - class FiveToTwentyWorkflow: 工作流控制类
@GOTCHAS:
  - 必须先完成首次编辑，再进行认领
  - 认领操作需要等待UI更新
  - 最终需要验证是否达到20条产品
@TECH_DEBT:
  - TODO: 添加更详细的错误恢复机制
  - TODO: 支持自定义认领次数
@DEPENDENCIES:
  - 内部: browser.miaoshou_controller, browser.first_edit_controller
  - 外部: playwright, loguru
@RELATED: miaoshou_controller.py, first_edit_controller.py
"""

import asyncio
from typing import Dict, List, Optional, Tuple

from loguru import logger
from playwright.async_api import Page

from ..browser.first_edit_controller import FirstEditController
from ..browser.miaoshou_controller import MiaoshouController
from ..data_processor.title_generator import TitleGenerator
from ..data_processor.price_calculator import PriceCalculator
from ..data_processor.random_generator import RandomDataGenerator


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

    def __init__(self):
        """初始化工作流控制器."""
        self.miaoshou_ctrl = MiaoshouController()
        self.first_edit_ctrl = FirstEditController()
        self.title_generator = TitleGenerator()
        self.price_calculator = PriceCalculator()
        self.random_generator = RandomDataGenerator()
        
        logger.info("5→20工作流控制器已初始化")

    async def edit_single_product(
        self,
        page: Page,
        product_index: int,
        product_data: Dict
    ) -> bool:
        """编辑单个产品（首次编辑）.

        执行SOP步骤4的首次编辑：
        - 修改标题（AI生成+型号）
        - 设置价格
        - 设置库存

        Args:
            page: Playwright页面对象
            product_index: 产品索引（0-4）
            product_data: 产品数据字典，包含：
                - keyword: 关键词
                - model_number: 型号（如A0001）
                - cost: 成本价
                - stock: 库存

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
        logger.info(f"开始首次编辑第{product_index+1}个产品")
        logger.info(f"=" * 60)

        try:
            # 1. 点击编辑按钮，打开编辑弹窗
            if not await self.miaoshou_ctrl.click_edit_product_by_index(page, product_index):
                logger.error(f"✗ 无法打开第{product_index+1}个产品的编辑弹窗")
                return False

            # 2. 生成标题（含型号）
            keyword = product_data.get("keyword", "商品")
            model_number = product_data.get("model_number", f"A{str(product_index+1).zfill(4)}")
            
            # 使用简单标题生成（后续可集成AI）
            title = f"{keyword} {model_number}型号"
            logger.info(f"生成标题: {title}")

            # 3. 计算价格
            cost = product_data.get("cost", 10.0)
            price = self.price_calculator.calculate_supply_price(cost)
            logger.info(f"计算价格: ¥{price} (成本: ¥{cost})")

            # 4. 获取库存
            stock = product_data.get("stock", 100)
            logger.info(f"设置库存: {stock}")

            # 5. 生成随机重量和尺寸（暂时不使用，在批量编辑中处理）
            weight = self.random_generator.generate_weight()
            dimensions = self.random_generator.generate_dimensions()

            # 6. 执行首次编辑
            success = await self.first_edit_ctrl.complete_first_edit(
                page=page,
                title=title,
                price=price,
                stock=stock,
                weight=weight,
                dimensions=dimensions
            )

            if success:
                logger.success(f"✓ 第{product_index+1}个产品首次编辑完成")
                # 等待保存完成
                await page.wait_for_timeout(1000)
                return True
            else:
                logger.error(f"✗ 第{product_index+1}个产品首次编辑失败")
                return False

        except Exception as e:
            logger.error(f"编辑第{product_index+1}个产品失败: {e}")
            return False

    async def execute(
        self,
        page: Page,
        products_data: List[Dict],
        claim_times: int = 4
    ) -> Dict:
        """执行完整的5→20工作流.

        SOP步骤4-6的完整实现：
        1. 循环编辑5个产品（首次编辑）
        2. 每个产品认领4次
        3. 验证最终是否有20条产品

        Args:
            page: Playwright页面对象
            products_data: 5个产品的数据列表
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
            ValueError: 如果产品数量不是5个

        Examples:
            >>> result = await workflow.execute(page, [
            ...     {"keyword": "药箱", "model_number": "A0001", "cost": 10, "stock": 100},
            ...     {"keyword": "药箱", "model_number": "A0002", "cost": 12, "stock": 100},
            ...     # ... 共5个
            ... ])
            >>> result["final_count"]
            20
        """
        logger.info("=" * 80)
        logger.info("开始执行5→20工作流（SOP步骤4-6）")
        logger.info("=" * 80)

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
            # 阶段1：首次编辑5个产品
            logger.info("\n" + "=" * 60)
            logger.info("[阶段1/3] 首次编辑5个产品")
            logger.info("=" * 60)

            # 注意：假设已经在"全部"tab（在调用此函数前应该已经切换过）

            edited_count = 0
            for i in range(5):
                logger.info(f"\n>>> 编辑第{i+1}/5个产品...")
                
                if await self.edit_single_product(page, i, products_data[i]):
                    edited_count += 1
                    logger.success(f"✓ 第{i+1}个产品编辑成功（总计: {edited_count}/5）")
                else:
                    error_msg = f"第{i+1}个产品编辑失败"
                    result["errors"].append(error_msg)
                    logger.error(f"✗ {error_msg}")
                
                # 每个产品编辑完后等待一下
                await page.wait_for_timeout(500)

            result["edited_count"] = edited_count
            logger.info(f"\n✓ 阶段1完成：成功编辑{edited_count}/5个产品")

            if edited_count == 0:
                logger.error("✗ 没有成功编辑任何产品，终止工作流")
                return result

            # 阶段2：每个产品认领4次
            logger.info("\n" + "=" * 60)
            logger.info(f"[阶段2/3] 认领产品（每个认领{claim_times}次）")
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

