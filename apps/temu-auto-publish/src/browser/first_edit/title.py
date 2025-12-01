"""
@PURPOSE: 处理首次编辑弹窗中的标题定位、读取与覆盖更新。
@OUTLINE:
  - class FirstEditTitleMixin: 标题定位、读取、覆盖与拼接
@DEPENDENCIES:
  - 内部: ...utils.page_load_decorator.wait_dom_loaded, .base.find_visible_element
  - 外部: playwright.async_api
"""

from __future__ import annotations

from loguru import logger
from playwright.async_api import Locator, Page

from ...utils.page_load_decorator import wait_dom_loaded
from .base import TIMEOUTS, FirstEditBase
from .retry import first_edit_step_retry

TITLE_INPUT_SELECTORS: list[str] = [
    ".jx-overlay-dialog input.jx-input__inner[type='text']:visible",
    (
        "xpath=//label[contains(text(), '产品标题')]"
        "/following-sibling::*/descendant::input[@type='text'][1]"
    ),
    "xpath=//label[contains(text(), '产品标题')]/following::input[@type='text'][1]",
    (
        "xpath=//div[contains(@class, 'jx-form-item')]//label[contains(text(), '产品标题:')]//"
        "following-sibling::*/descendant::input[@type='text']"
    ),
    (
        "xpath=//label[contains(text(), '产品标题')]/ancestor::div[contains(@class, 'jx-form-"
        "item')]//input[contains(@class, 'jx-input__inner') and @type='text']"
    ),
]


class FirstEditTitleMixin(FirstEditBase):
    """提供首次编辑场景下的标题读取与覆盖能力。"""

    @first_edit_step_retry(max_attempts=3, retry_on_false=False)
    async def _locate_title_input(self, page: Page) -> Locator | None:
        """定位标题输入框。

        Args:
            page: Playwright 页面对象.

        Returns:
            匹配到的标题输入框，未找到时返回 None。
        """
        logger.debug("定位标题输入框")
        # 优化：移除冗余的 wait_for_load_state，由调用方保证页面已加载

        title_input = await self.find_visible_element(
            page,
            TITLE_INPUT_SELECTORS,
            timeout_ms=TIMEOUTS.NORMAL,
            context_name="标题输入框定位",
        )

        if not title_input:
            logger.error("未定位到标题输入框")
        return title_input

    @first_edit_step_retry(max_attempts=3, initial_delay_ms=400, retry_on_false=False)
    async def get_original_title(self, page: Page, max_retries: int = 3) -> str:
        """获取产品的原始标题（SOP 步骤 4.2 准备）。

        Args:
            page: Playwright 页面对象.
            max_retries: 最大重试次数，默认 3 次.

        Returns:
            原始标题文本; 若获取失败返回空字符串。
        """
        # 优化：移除冗余的 wait_for_load_state
        for attempt in range(1, max_retries + 1):
            title_input = await self._locate_title_input(page)
            if title_input:
                title = (await title_input.input_value()).strip()
                logger.success("获取到原始标题 {}", title[:50])
                return title

            if attempt < max_retries:
                logger.warning("第 {}/{} 次未找到标题输入框，等待后重试", attempt, max_retries)
                await wait_dom_loaded(page, TIMEOUTS.NORMAL, context=" [retry title]")

        logger.error("重试 {} 次后仍未获取到原标题", max_retries)
        return ""

    @first_edit_step_retry(max_attempts=3)
    async def edit_title(self, page: Page, new_title: str) -> bool:
        """覆盖产品标题（SOP 步骤 4.1）。

        Args:
            page: Playwright 页面对象.
            new_title: 需要覆盖的标题内容.

        Returns:
            标题是否成功更新。
        """
        logger.info("SOP 4.1: 覆盖标题 -> {}", new_title)
        # 优化：移除冗余的 wait_for_load_state
        title_input = await self._locate_title_input(page)
        if not title_input:
            return False

        await title_input.fill(new_title)
        updated_title = (await title_input.input_value()).strip()

        if updated_title != new_title.strip():
            logger.warning("标题覆盖后与期望不一致，期望: {}，实际: {}", new_title, updated_title)
            return False

        logger.success("标题已更新为 {}", updated_title)
        return True

    @first_edit_step_retry(max_attempts=3)
    async def append_model_to_title(self, page: Page, model_number: str) -> bool:
        """按"原标题 + 型号"的伪代码逻辑覆盖标题。

        伪代码步骤：
        1) 定位标题输入框;
        2) 获取原有标题;
        3) 拼接新标题（原标题 + 型号）;
        4) 覆盖原有标题;
        5) 返回执行结果。

        Args:
            page: Playwright 页面对象.
            model_number: 型号后缀，例如 "A0001".

        Returns:
            标题是否成功更新。
        """
        logger.info("按照原标题 + 型号覆盖标题，型号 {}", model_number)
        # 优化：移除冗余的 wait_for_load_state
        title_input = await self._locate_title_input(page)
        if not title_input:
            return False

        original_title = (await title_input.input_value()).strip()
        logger.debug("原标题 {}", original_title[:50])

        combined_title = f"{original_title} {model_number}".strip()
        await title_input.fill(combined_title)

        updated_title = (await title_input.input_value()).strip()
        if updated_title != combined_title:
            logger.warning("标题覆盖可能未成功，期望: {}，实际: {}", combined_title, updated_title)
            return False

        logger.success("标题已覆盖为: {}", updated_title)
        return True

    @first_edit_step_retry(max_attempts=3)
    async def edit_title_with_ai(
        self,
        page: Page,
        product_index: int,
        all_original_titles: list[str],
        model_number: str,
        use_ai: bool = True,
    ) -> bool:
        """兼容旧接口: 直接采用“原标题 + 型号”覆盖标题。

        Args:
            page: Playwright 页面对象.
            product_index: 兼容参数，当前逻辑未使用.
            all_original_titles: 兼容参数，当前逻辑未使用.
            model_number: 型号后缀.
            use_ai: 兼容参数，当前逻辑未使用.

        Returns:
            标题是否成功更新。
        """
        _ = (product_index, all_original_titles, use_ai)
        logger.info("已切换为简化逻辑: 原标题 + 型号覆盖标题")
        return await self.append_model_to_title(page, model_number)
