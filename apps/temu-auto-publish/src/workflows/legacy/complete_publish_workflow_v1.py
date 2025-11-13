# ruff: noqa

"""
@PURPOSE: 完整发布工作流 v1 (遗留版本), 集成 5→20、批量编辑、发布流程
@OUTLINE:
  - class CompletePublishWorkflow: v1 工作流控制类
  - async def execute(): 执行完整流程
  - async def execute_with_retry(): 带重试执行
  - async def execute_complete_workflow(): 便捷函数
@GOTCHAS:
  - 依赖旧版本 controllers, 保留以兼容历史脚本
@TECH_DEBT:
  - 不再维护, 仅用于参考
@RELATED: ..complete_publish_workflow.py (最新工作流)
"""

from __future__ import annotations

import asyncio
from typing import Dict, List, Optional

from loguru import logger
from playwright.async_api import Page

from ..five_to_twenty_workflow import FiveToTwentyWorkflow
from ...browser.legacy.batch_edit_controller_v1 import (
    BatchEditController as BatchEditControllerV1,
)
from ...browser.miaoshou_controller import MiaoshouController
from ...browser.publish_controller import PublishController


class CompletePublishWorkflow:
    """完整发布工作流（遗留版本，SOP步骤4-11）."""

    def __init__(self, use_ai_titles: bool = True) -> None:
        self.five_to_twenty = FiveToTwentyWorkflow(use_ai_titles=use_ai_titles)
        self.batch_edit_ctrl = BatchEditControllerV1()
        self.publish_ctrl = PublishController()
        self.miaoshou_ctrl = MiaoshouController()
        self.use_ai_titles = use_ai_titles

        logger.info(
            "完整发布工作流 v1 已初始化（AI标题: %s）",
            "启用" if use_ai_titles else "禁用",
        )

    async def execute(
        self,
        page: Page,
        products_data: List[Dict],
        shop_name: Optional[str] = None,
        enable_batch_edit: bool = True,
        enable_publish: bool = True,
    ) -> Dict:
        """执行完整的发布工作流."""

        logger.info("开始执行完整发布工作流 v1（SOP步骤4-11）")

        result: Dict[str, object] = {
            "success": False,
            "stage1_result": {},
            "stage2_result": {},
            "stage3_result": {},
            "errors": [],
        }

        try:
            logger.info("进入阶段1：5→20工作流（首次编辑 & 认领）")
            stage1_result = await self.five_to_twenty.execute(page, products_data)
            result["stage1_result"] = stage1_result

            if not stage1_result.get("success"):
                error_msg = "阶段1失败：5→20工作流未成功完成"
                result["errors"].append(error_msg)
                logger.error(error_msg)
                return result

            if enable_batch_edit:
                logger.info("进入阶段2：批量编辑18步")
                try:
                    await self.miaoshou_ctrl.switch_tab(page, "claimed")
                    await page.wait_for_timeout(1000)

                    if not await self.miaoshou_ctrl.select_all_products(page):
                        raise RuntimeError("全选产品失败")

                    if not await self.batch_edit_ctrl.enter_batch_edit_mode(page):
                        raise RuntimeError("进入批量编辑模式失败")

                    finished = await self.batch_edit_ctrl.execute_batch_edit_steps(
                        page, products_data
                    )
                    if finished:
                        result["stage2_result"] = {
                            "success": True,
                            "steps_completed": 18,
                        }
                        logger.success("批量编辑流程完成")
                    else:
                        raise RuntimeError("批量编辑步骤执行失败")

                except Exception as exc:  # noqa: BLE001
                    error_msg = f"阶段2失败：{exc}"
                    result["errors"].append(error_msg)
                    result["stage2_result"] = {"success": False, "error": str(exc)}
                    logger.exception("批量编辑出现异常")
            else:
                result["stage2_result"] = {"success": True, "skipped": True}

            if enable_publish:
                logger.info("进入阶段3：发布流程（选择店铺/供货价/批量发布）")
                try:
                    stage3_result = await self.publish_ctrl.execute_publish_workflow(
                        page, products_data, shop_name
                    )
                    result["stage3_result"] = stage3_result
                    if not stage3_result.get("success"):
                        raise RuntimeError("发布流程未成功完成")
                except Exception as exc:  # noqa: BLE001
                    error_msg = f"阶段3失败：{exc}"
                    result["errors"].append(error_msg)
                    result["stage3_result"] = {"success": False, "error": str(exc)}
                    logger.exception("发布流程出现异常")
            else:
                result["stage3_result"] = {"success": True, "skipped": True}

            result["success"] = (
                result["stage1_result"].get("success", False)
                and result["stage2_result"].get("success", False)
                and result["stage3_result"].get("success", False)
            )

            logger.info("完整发布工作流 v1 执行结束，结果: %s", result["success"])
            return result

        except Exception as exc:  # noqa: BLE001
            error_msg = f"工作流执行异常: {exc}"
            result["errors"].append(error_msg)
            logger.exception(error_msg)
            return result

    async def execute_with_retry(
        self,
        page: Page,
        products_data: List[Dict],
        shop_name: Optional[str] = None,
        max_retries: int = 3,
        enable_batch_edit: bool = True,
        enable_publish: bool = True,
    ) -> Dict:
        """带重试机制的执行完整工作流."""

        logger.info("完整发布工作流 v1 将重试执行，最大次数 %s", max_retries)

        last_result: Dict = {}
        for attempt in range(max_retries):
            logger.info("尝试第 %s/%s 次", attempt + 1, max_retries)
            last_result = await self.execute(
                page,
                products_data,
                shop_name,
                enable_batch_edit,
                enable_publish,
            )

            if last_result.get("success"):
                logger.success("第 %s 次尝试成功", attempt + 1)
                return last_result

            wait_ms = (attempt + 1) * 5000
            logger.warning("第 %s 次尝试失败，等待 %sms 后重试", attempt + 1, wait_ms)
            await page.wait_for_timeout(wait_ms)

        logger.error("工作流执行失败，已重试 %s 次", max_retries)
        return last_result


async def execute_complete_workflow(
    page: Page,
    products_data: List[Dict],
    shop_name: Optional[str] = None,
    enable_batch_edit: bool = True,
    enable_publish: bool = True,
) -> Dict:
    """便捷函数，调用遗留版本工作流."""

    workflow = CompletePublishWorkflow()
    return await workflow.execute(
        page,
        products_data,
        shop_name,
        enable_batch_edit,
        enable_publish,
    )


__all__ = ["CompletePublishWorkflow", "execute_complete_workflow"]
