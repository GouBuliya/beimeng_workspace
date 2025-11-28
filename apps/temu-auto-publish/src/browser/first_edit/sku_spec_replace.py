"""
@PURPOSE: 首次编辑中替换 SKU 规格选项的逻辑.
@OUTLINE:
  - class FirstEditSkuSpecReplaceMixin: 替换销售属性列表中的规格选项（Mixin类版本）
  - async replace_sku_spec_options(): 独立公共函数，供 first_edit_dialog_codegen 调用
  - async _cleanup_excess_options_standalone(): 清理多余选项（保留前2个）
  - async _fill_spec_values_standalone(): 填充规格值
@DEPENDENCIES:
  - 内部: .base.FirstEditBase
  - 外部: playwright.async_api.Page, loguru.logger
@RELATED: first_edit_dialog_codegen.py
"""

from __future__ import annotations

import asyncio

from loguru import logger
from playwright.async_api import Locator, Page

from ...utils.selector_race import TIMEOUTS
from .base import FirstEditBase


async def _wait_for_count_change(
    locator: Locator,
    expected_count: int,
    *,
    timeout_ms: int = TIMEOUTS.SLOW,
    poll_interval: float = 0.05,
    max_interval: float = 0.15,
) -> bool:
    """智能等待元素数量变化（指数退避轮询）."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + (timeout_ms / 1_000)
    interval = poll_interval

    while loop.time() < deadline:
        try:
            current = await locator.count()
            if current == expected_count:
                return True
        except Exception:
            pass
        await asyncio.sleep(interval)
        interval = min(interval * 1.5, max_interval)  # 指数退避

    return False


class FirstEditSkuSpecReplaceMixin(FirstEditBase):
    """封装首次编辑流程中的 SKU 规格选项替换操作."""

    async def replace_sku_spec_options(
        self,
        page: Page,
        spec_array: list[str],
        timeout: int = 3000,
    ) -> bool:
        """替换销售属性列表中的规格选项.

        根据传入的规格数组，替换 sale-attribute-list 中的选项值。
        
        流程：
        1. 清理阶段：如果列表项 > 2，删除第3个及之后的所有选项
        2. 填充阶段：从第2个输入框开始，依次填入规格数组的值

        Args:
            page: Playwright 页面对象
            spec_array: 规格值数组，如 ["3", "4", "5"]
            timeout: 元素等待超时时间（毫秒）

        Returns:
            是否替换成功

        Examples:
            >>> await mixin.replace_sku_spec_options(page, ["3", "4", "5"])
            True
        """
        logger.info("开始替换 SKU 规格选项，目标规格: {}", spec_array)

        if not spec_array:
            logger.warning("规格数组为空，跳过替换")
            return True

        try:
            # 阶段 1: 清理多余选项（保留前2个）
            await self._cleanup_excess_options(page, timeout)

            # 阶段 2: 填充规格值
            success = await self._fill_spec_values(page, spec_array, timeout)

            if success:
                logger.success("✓ SKU 规格选项替换完成，共填充 {} 个规格", len(spec_array))
            else:
                logger.error("SKU 规格选项替换失败")

            return success

        except Exception as exc:
            logger.error("替换 SKU 规格选项异常: {}", exc)
            return False

    async def _cleanup_excess_options(self, page: Page, timeout: int = TIMEOUTS.SLOW) -> None:
        """清理多余选项，保留前2个（智能等待版本）.

        如果 sale-attribute-list 中的选项数量 > 2，
        从后往前删除第3个及之后的所有选项。

        Args:
            page: Playwright 页面对象
            timeout: 元素等待超时时间（毫秒）
        """
        logger.info("阶段1: 检查并清理多余的规格选项...")

        # 定位 sale-attribute-list 容器
        list_container_selector = ".sale-attribute-list"

        # 定位所有的 input-group 项（每个规格选项）
        item_selector = f"{list_container_selector} .jx-input-group"

        # 删除按钮选择器（垃圾桶图标在 append 区域）
        delete_btn_selector = ".jx-input-group__append .jx-icon"

        try:
            # 获取当前列表项数量
            items = page.locator(item_selector)
            count = await items.count()
            logger.debug("当前规格选项数量: {}", count)

            # 如果数量 <= 2，不需要清理
            if count <= 2:
                logger.info("规格选项数量 <= 2，无需清理")
                return

            # 从后往前删除第3个及之后的选项（避免索引变化问题）
            delete_count = count - 2
            logger.info("需要删除 {} 个多余选项", delete_count)

            for i in range(count - 1, 1, -1):  # 从最后一个到第3个（索引2）
                logger.debug("删除第 {} 个规格选项（索引 {}）", i + 1, i)

                # 获取该项的删除按钮
                item = items.nth(i)
                delete_btn = item.locator(delete_btn_selector)

                # 点击删除按钮
                if await delete_btn.count() > 0:
                    current_count = await items.count()
                    await delete_btn.click()
                    # 智能等待: 等待元素数量减少
                    await _wait_for_count_change(items, current_count - 1, timeout_ms=timeout)
                else:
                    logger.warning("第 {} 个选项的删除按钮未找到", i + 1)

            # 验证删除结果
            remaining = await items.count()
            logger.info("清理完成，剩余选项数量: {}", remaining)

        except Exception as exc:
            logger.error("清理多余选项失败: {}", exc)
            raise

    async def _fill_spec_values(
        self,
        page: Page,
        spec_array: list[str],
        timeout: int = TIMEOUTS.SLOW,
    ) -> bool:
        """填充规格值到输入框（智能等待版本）.

        从第2个输入框开始（因为清理后最后一个必然是第2个），
        依次填入规格数组的值。每填入一个值后（除最后一个），
        点击"添加选项"按钮创建新输入框。

        Args:
            page: Playwright 页面对象
            spec_array: 规格值数组
            timeout: 元素等待超时时间（毫秒）

        Returns:
            是否填充成功
        """
        logger.info("阶段2: 开始填充规格值...")

        # 选择器定义
        list_container_selector = ".sale-attribute-list"
        input_selector = f"{list_container_selector} input.jx-input__inner"
        add_btn_selector = f"{list_container_selector} button.jx-button"

        try:
            for i, spec_value in enumerate(spec_array):
                logger.debug("填充第 {} 个规格: {}", i + 1, spec_value)

                # 找到当前所有输入框
                inputs = page.locator(input_selector)
                input_count = await inputs.count()

                if input_count < 2:
                    logger.error("输入框数量不足，至少需要2个，当前: {}", input_count)
                    return False

                # 获取最后一个输入框（第2个位置，因为清理后只剩2个）
                # 随着添加操作，最后一个会变化，所以每次都取最后一个
                last_input = inputs.nth(input_count - 1)

                # 清空并填入规格值
                await last_input.fill("")
                await last_input.fill(spec_value)

                logger.debug("已填入规格值: {}", spec_value)

                # 如果还有下一个规格要添加，则点击"添加选项"按钮
                if i < len(spec_array) - 1:
                    add_btn = page.locator(add_btn_selector).first
                    if await add_btn.count() > 0:
                        current_count = input_count
                        await add_btn.click()
                        # 智能等待: 等待新输入框出现
                        await _wait_for_count_change(inputs, current_count + 1, timeout_ms=timeout)
                        logger.debug("已点击添加选项按钮")
                    else:
                        logger.error("添加选项按钮未找到")
                        return False

            logger.success("规格值填充完成")
            return True

        except Exception as exc:
            logger.error("填充规格值失败: {}", exc)
            return False


# ============ 独立公共函数（供 first_edit_dialog_codegen 调用） ============


async def replace_sku_spec_options(
    page: Page,
    spec_array: list[str],
    timeout: int = 3000,
) -> bool:
    """替换销售属性列表中的规格选项（独立函数版本）.

    根据传入的规格数组，替换 sale-attribute-list 中的选项值。
    
    流程：
    1. 清理阶段：如果列表项 > 2，删除第3个及之后的所有选项
    2. 填充阶段：从第2个输入框开始，依次填入规格数组的值

    Args:
        page: Playwright 页面对象
        spec_array: 规格值数组，如 ["3", "4", "5"]
        timeout: 元素等待超时时间（毫秒）

    Returns:
        是否替换成功

    Examples:
        >>> await replace_sku_spec_options(page, ["3", "4", "5"])
        True
    """
    logger.info(f"开始替换 SKU 规格选项，目标规格: {spec_array}")

    if not spec_array:
        logger.warning("规格数组为空，跳过替换")
        return True

    try:
        # 阶段 1: 清理多余选项（保留前2个）
        await _cleanup_excess_options_standalone(page, timeout)

        # 阶段 2: 填充规格值
        success = await _fill_spec_values_standalone(page, spec_array, timeout)

        if success:
            logger.success(f"✓ SKU 规格选项替换完成，共填充 {len(spec_array)} 个规格")
        else:
            logger.error("SKU 规格选项替换失败")

        return success

    except Exception as exc:
        logger.error(f"替换 SKU 规格选项异常: {exc}")
        return False


async def _cleanup_excess_options_standalone(page: Page, timeout: int = TIMEOUTS.SLOW) -> None:
    """清理多余选项，保留前2个（独立函数版本，智能等待）."""
    logger.info("阶段1: 检查并清理多余的规格选项...")

    # 精确定位：只选择包含"请输入选项名称"的输入框所在的 input-group
    # 使用 placeholder 属性精确定位选项输入框
    option_input_selector = "input[placeholder='请输入选项名称']"

    try:
        # 获取当前选项输入框数量
        option_inputs = page.locator(option_input_selector)
        count = await option_inputs.count()
        logger.debug(f"当前规格选项数量: {count}")

        # 如果数量 <= 2，不需要清理
        if count <= 2:
            logger.info(f"规格选项数量 ({count}) <= 2，无需清理")
            return

        # 从后往前删除第3个及之后的选项（避免索引变化问题）
        delete_count = count - 2
        logger.info(f"需要删除 {delete_count} 个多余选项")

        for i in range(count - 1, 1, -1):  # 从最后一个到第3个（索引2）
            logger.debug(f"删除第 {i + 1} 个规格选项（索引 {i}）")

            # 获取该输入框的父级 input-group，然后找删除按钮
            input_el = option_inputs.nth(i)
            # 向上查找最近的 jx-input-group 父元素，然后找删除按钮
            delete_btn = input_el.locator("xpath=ancestor::div[contains(@class, 'jx-input-group')]//div[contains(@class, 'jx-input-group__append')]//i[contains(@class, 'jx-icon')]")

            # 点击删除按钮
            if await delete_btn.count() > 0:
                current_count = await option_inputs.count()
                await delete_btn.first.click()
                # 智能等待: 等待元素数量减少
                await _wait_for_count_change(option_inputs, current_count - 1, timeout_ms=timeout)
            else:
                logger.warning(f"第 {i + 1} 个选项的删除按钮未找到")

        # 验证删除结果
        remaining = await option_inputs.count()
        logger.info(f"清理完成，剩余选项数量: {remaining}")

    except Exception as exc:
        logger.error(f"清理多余选项失败: {exc}")
        raise


async def _fill_spec_values_standalone(
    page: Page,
    spec_array: list[str],
    timeout: int = TIMEOUTS.SLOW,
) -> bool:
    """填充规格值到输入框（独立函数版本，智能等待）.

    清理后保留2个输入框，然后按以下逻辑填充：
    - 第1个规格 → 填入第1个输入框（索引0）
    - 第2个规格 → 填入第2个输入框（索引1）
    - 第3个及之后 → 先点击"添加选项"创建新输入框，再填入

    示例：原有 [1, 2, 3, 4, 5]，输入 [3, 4, 5]
    1. 清理后剩余 [1, 2]
    2. 填入3到索引0 → [3, 2]
    3. 填入4到索引1 → [3, 4]
    4. 添加+填入5 → [3, 4, 5]
    """
    logger.info("阶段2: 开始填充规格值...")

    # 精确选择器：只选择"请输入选项名称"的输入框
    option_input_selector = "input[placeholder='请输入选项名称']"
    # 添加选项按钮：包含"添加选项"文本的按钮
    add_btn_selector = "button:has-text('添加选项')"

    try:
        for i, spec_value in enumerate(spec_array):
            logger.debug(f"填充第 {i + 1} 个规格: {spec_value}")

            # 找到当前所有选项输入框
            inputs = page.locator(option_input_selector)
            input_count = await inputs.count()
            logger.debug(f"当前选项输入框数量: {input_count}")

            if input_count < 1:
                logger.error(f"选项输入框数量不足，至少需要1个，当前: {input_count}")
                return False

            if i < input_count:
                # 前面的规格：直接覆盖现有输入框
                target_input = inputs.nth(i)
                logger.debug(f"覆盖第 {i + 1} 个输入框（索引 {i}）")
            else:
                # 后续规格：先点击添加按钮创建新输入框
                add_btn = page.locator(add_btn_selector)
                if await add_btn.count() > 0:
                    current_count = input_count
                    await add_btn.first.click()
                    # 智能等待: 等待新输入框出现
                    await _wait_for_count_change(inputs, current_count + 1, timeout_ms=timeout)
                    logger.debug("已点击添加选项按钮")
                else:
                    logger.error("添加选项按钮未找到")
                    return False

                # 重新获取输入框列表，取最后一个（新创建的）
                inputs = page.locator(option_input_selector)
                input_count = await inputs.count()
                target_input = inputs.nth(input_count - 1)
                logger.debug(f"填入新创建的输入框（索引 {input_count - 1}）")

            # 清空并填入规格值
            await target_input.click()
            await target_input.fill("")
            await target_input.fill(spec_value)

            logger.debug(f"已填入规格值: {spec_value}")

        logger.success(f"规格值填充完成，共填充 {len(spec_array)} 个")
        return True

    except Exception as exc:
        logger.error(f"填充规格值失败: {exc}")
        return False

