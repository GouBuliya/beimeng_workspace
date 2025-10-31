"""
@PURPOSE: 完整发布工作流，集成从5→20到批量编辑到发布的全流程（SOP步骤4-11）
@OUTLINE:
  - class CompletePublishWorkflow: 完整工作流控制类
  - async def execute(): 执行完整流程
  - async def execute_with_retry(): 带重试的执行
@GOTCHAS:
  - 工作流分为三个阶段：5→20、批量编辑、发布
  - 需要等待每个阶段完成后再进入下一阶段
  - 批量编辑步骤较多，需要足够的等待时间
@TECH_DEBT:
  - TODO: 添加断点续传功能
  - TODO: 添加详细的进度追踪
  - TODO: 支持部分失败的恢复
@DEPENDENCIES:
  - 内部: workflows.five_to_twenty_workflow, browser.batch_edit_controller, browser.publish_controller
  - 外部: playwright, loguru
@RELATED: five_to_twenty_workflow.py, batch_edit_controller.py, publish_controller.py
"""

import asyncio
from typing import Dict, List, Optional

from loguru import logger
from playwright.async_api import Page

from ..browser.batch_edit_controller import BatchEditController
from ..browser.miaoshou_controller import MiaoshouController
from ..browser.publish_controller import PublishController
from .five_to_twenty_workflow import FiveToTwentyWorkflow


class CompletePublishWorkflow:
    """完整发布工作流（SOP步骤4-11）.

    集成三个主要阶段：
    1. 阶段1（步骤4-6）：5→20工作流
       - 首次编辑5条链接
       - 每条认领4次
       - 生成20条产品
    
    2. 阶段2（步骤7）：批量编辑18步
       - 全选20条产品
       - 执行18步批量编辑流程
    
    3. 阶段3（步骤8-11）：发布流程
       - 选择店铺
       - 设置供货价
       - 批量发布
       - 查看结果

    Attributes:
        five_to_twenty: 5→20工作流控制器
        batch_edit_ctrl: 批量编辑控制器
        publish_ctrl: 发布控制器
        miaoshou_ctrl: 妙手采集箱控制器

    Examples:
        >>> workflow = CompletePublishWorkflow()
        >>> result = await workflow.execute(page, products_data, shop_name="测试店铺")
        >>> result["success"]
        True
    """

    def __init__(self):
        """初始化完整工作流控制器."""
        self.five_to_twenty = FiveToTwentyWorkflow()
        self.batch_edit_ctrl = BatchEditController()
        self.publish_ctrl = PublishController()
        self.miaoshou_ctrl = MiaoshouController()
        
        logger.info("完整发布工作流控制器已初始化（SOP步骤4-11）")

    async def execute(
        self,
        page: Page,
        products_data: List[Dict],
        shop_name: Optional[str] = None,
        enable_batch_edit: bool = True,
        enable_publish: bool = True
    ) -> Dict:
        """执行完整的发布工作流.

        Args:
            page: Playwright页面对象
            products_data: 5个产品的数据列表
            shop_name: 店铺名称（可选）
            enable_batch_edit: 是否启用批量编辑（默认True）
            enable_publish: 是否启用发布流程（默认True）

        Returns:
            执行结果字典：{
                "success": bool,
                "stage1_result": Dict,  # 5→20结果
                "stage2_result": Dict,  # 批量编辑结果
                "stage3_result": Dict,  # 发布结果
                "errors": List[str]
            }

        Examples:
            >>> result = await workflow.execute(page, products_data)
            >>> result["success"]
            True
        """
        logger.info("=" * 100)
        logger.info("开始执行完整发布工作流（SOP步骤4-11）")
        logger.info("=" * 100)

        result = {
            "success": False,
            "stage1_result": {},
            "stage2_result": {},
            "stage3_result": {},
            "errors": []
        }

        try:
            # ========== 阶段1：5→20工作流（SOP步骤4-6）==========
            logger.info("\n" + "▶" * 50)
            logger.info("【阶段1/3】5→20工作流（SOP步骤4-6）")
            logger.info("▶" * 50)

            # 1. 导航到采集箱
            logger.info("导航到采集箱页面...")
            if not await self.miaoshou_ctrl.navigate_to_collection_box(page):
                raise Exception("导航到采集箱失败")
            await page.wait_for_timeout(2000)
            
            # 2. 切换到"全部"tab
            logger.info("切换到'全部'tab...")
            if not await self.miaoshou_ctrl.switch_tab(page, "all"):
                raise Exception("切换到'全部'tab失败")
            await page.wait_for_timeout(1000)
            
            # 3. 筛选人员并搜索（如果配置了人员名称）
            staff_name = products_data[0].get("staff_name") if products_data else None
            if staff_name:
                logger.info(f"筛选人员: {staff_name}")
                if not await self.miaoshou_ctrl.filter_and_search(page, staff_name):
                    logger.warning(f"⚠️ 人员筛选失败，但继续执行（人员: {staff_name}）")
                    # 不失败，继续执行（可能人员筛选不是必须的）
                await page.wait_for_timeout(1000)

            # 4. 执行5→20工作流
            stage1_result = await self.five_to_twenty.execute(page, products_data)
            result["stage1_result"] = stage1_result

            if not stage1_result.get("success"):
                error_msg = "阶段1失败：5→20工作流未成功完成"
                result["errors"].append(error_msg)
                logger.error(f"✗ {error_msg}")
                logger.warning("⚠️  后续阶段将被跳过")
                return result

            logger.success(f"✓ 阶段1完成：成功生成{stage1_result.get('final_count', 0)}条产品")
            await page.wait_for_timeout(2000)  # 等待UI更新

            # ========== 阶段2：批量编辑18步（SOP步骤7）==========
            if enable_batch_edit:
                logger.info("\n" + "▶" * 50)
                logger.info("【阶段2/3】批量编辑18步（SOP步骤7）")
                logger.info("▶" * 50)

                try:
                    # 1. 切换到"已认领"tab
                    await self.miaoshou_ctrl.switch_tab(page, "claimed")
                    await page.wait_for_timeout(1000)

                    # 2. 全选20条产品
                    logger.info("全选20条产品...")
                    if not await self.miaoshou_ctrl.select_all_products(page):
                        raise Exception("全选产品失败")

                    # 3. 进入批量编辑模式
                    logger.info("进入批量编辑模式...")
                    if not await self.batch_edit_ctrl.enter_batch_edit_mode(page):
                        raise Exception("进入批量编辑模式失败")

                    # 4. 执行18步批量编辑
                    logger.info("执行18步批量编辑流程...")
                    if await self.batch_edit_ctrl.execute_batch_edit_steps(page, products_data):
                        result["stage2_result"] = {"success": True, "steps_completed": 18}
                        logger.success("✓ 阶段2完成：批量编辑18步执行成功")
                    else:
                        raise Exception("批量编辑步骤执行失败")

                    await page.wait_for_timeout(2000)

                except Exception as e:
                    error_msg = f"阶段2失败：{e}"
                    result["errors"].append(error_msg)
                    result["stage2_result"] = {"success": False, "error": str(e)}
                    logger.error(f"✗ {error_msg}")
                    logger.warning("⚠️  批量编辑失败，但可以继续发布流程")
            else:
                logger.info("\n⏭️  阶段2已跳过（批量编辑已禁用）")
                result["stage2_result"] = {"success": True, "skipped": True}

            # ========== 阶段3：发布流程（SOP步骤8-11）==========
            if enable_publish:
                logger.info("\n" + "▶" * 50)
                logger.info("【阶段3/3】发布流程（SOP步骤8-11）")
                logger.info("▶" * 50)

                try:
                    stage3_result = await self.publish_ctrl.execute_publish_workflow(
                        page, products_data, shop_name
                    )
                    result["stage3_result"] = stage3_result

                    if not stage3_result.get("success"):
                        raise Exception("发布流程未成功完成")

                    logger.success("✓ 阶段3完成：发布流程执行成功")

                except Exception as e:
                    error_msg = f"阶段3失败：{e}"
                    result["errors"].append(error_msg)
                    result["stage3_result"] = {"success": False, "error": str(e)}
                    logger.error(f"✗ {error_msg}")
            else:
                logger.info("\n⏭️  阶段3已跳过（发布流程已禁用）")
                result["stage3_result"] = {"success": True, "skipped": True}

            # ========== 最终结果 ==========
            result["success"] = (
                result["stage1_result"].get("success", False) and
                result["stage2_result"].get("success", False) and
                result["stage3_result"].get("success", False)
            )

            logger.info("\n" + "=" * 100)
            logger.info("完整发布工作流执行完成")
            logger.info("=" * 100)
            logger.info(f"阶段1（5→20）：{'✓ 成功' if result['stage1_result'].get('success') else '✗ 失败'}")
            logger.info(f"阶段2（批量编辑）：{'✓ 成功' if result['stage2_result'].get('success') else '✗ 失败'}")
            logger.info(f"阶段3（发布）：{'✓ 成功' if result['stage3_result'].get('success') else '✗ 失败'}")
            logger.info(f"总体结果：{'✓ 成功' if result['success'] else '✗ 失败'}")
            logger.info("=" * 100)

            return result

        except Exception as e:
            error_msg = f"工作流执行异常: {e}"
            result["errors"].append(error_msg)
            logger.error(error_msg)
            return result

    async def execute_with_retry(
        self,
        page: Page,
        products_data: List[Dict],
        shop_name: Optional[str] = None,
        max_retries: int = 3,
        enable_batch_edit: bool = True,
        enable_publish: bool = True
    ) -> Dict:
        """带重试机制的执行完整工作流.

        Args:
            page: Playwright页面对象
            products_data: 5个产品的数据列表
            shop_name: 店铺名称（可选）
            max_retries: 最大重试次数（默认3次）
            enable_batch_edit: 是否启用批量编辑
            enable_publish: 是否启用发布流程

        Returns:
            执行结果字典

        Examples:
            >>> result = await workflow.execute_with_retry(page, products_data, max_retries=3)
            >>> result["success"]
            True
        """
        logger.info(f"开始执行完整工作流（最多重试{max_retries}次）...")

        for attempt in range(max_retries):
            logger.info(f"\n尝试第{attempt + 1}/{max_retries}次...")

            result = await self.execute(
                page,
                products_data,
                shop_name,
                enable_batch_edit,
                enable_publish
            )

            if result.get("success"):
                logger.success(f"✓ 第{attempt + 1}次尝试成功！")
                return result
            else:
                logger.warning(f"⚠️  第{attempt + 1}次尝试失败")
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 5  # 递增等待时间
                    logger.info(f"等待{wait_time}秒后重试...")
                    await page.wait_for_timeout(wait_time * 1000)

        logger.error(f"✗ 工作流执行失败，已重试{max_retries}次")
        return result


# 便捷函数
async def execute_complete_workflow(
    page: Page,
    products_data: List[Dict],
    shop_name: Optional[str] = None,
    enable_batch_edit: bool = True,
    enable_publish: bool = True
) -> Dict:
    """执行完整发布工作流的便捷函数.

    Args:
        page: Playwright页面对象
        products_data: 5个产品的数据列表
        shop_name: 店铺名称（可选）
        enable_batch_edit: 是否启用批量编辑
        enable_publish: 是否启用发布流程

    Returns:
        执行结果字典

    Examples:
        >>> result = await execute_complete_workflow(page, products_data, "测试店铺")
        >>> result["success"]
        True
    """
    workflow = CompletePublishWorkflow()
    return await workflow.execute(page, products_data, shop_name, enable_batch_edit, enable_publish)


# 测试代码
if __name__ == "__main__":
    # 这个工作流需要配合Page对象和真实数据使用
    # 测试请在集成测试中进行
    pass

