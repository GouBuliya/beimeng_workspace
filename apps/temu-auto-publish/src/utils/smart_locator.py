"""
@PURPOSE: 智能选择器工具,处理动态页面的元素定位
@OUTLINE:
  - class SmartLocator: 智能定位器主类
  - async def find_element(): 使用多重策略查找元素
  - async def find_with_fallback(): 使用后备选择器查找
  - async def find_by_text(): 根据文本内容查找
  - async def wait_and_find(): 等待并查找元素
  - class WaitStrategy: 等待策略配置
  - class PageWaiter: 页面等待工具(从page_waiter导入)
@GOTCHAS:
  - 避免使用动态的aria-ref属性
  - 优先使用文本定位器(稳定)
  - 支持多个后备选择器
  - 处理页面加载延迟
@DEPENDENCIES:
  - 外部: playwright, loguru
@RELATED: batch_edit_controller.py, first_edit_controller.py
"""

from loguru import logger
from playwright.async_api import Locator, Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from .page_waiter import PageWaiter, WaitStrategy


class SmartLocator:
    """智能选择器工具(处理动态页面).

    解决问题:
    1. aria-ref等动态属性值会变化
    2. 页面结构可能调整
    3. 元素加载时机不确定

    策略:
    1. 使用稳定的文本定位器
    2. 支持多个后备选择器
    3. 智能等待和重试

    Examples:
        >>> locator = SmartLocator(page)
        >>> element = await locator.find_element([
        ...     "button:has-text('保存')",
        ...     "button:has-text('确定')",
        ...     "[role='button']:has-text('保存')"
        ... ])
    """

    def __init__(
        self,
        page: Page,
        default_timeout: int = 5000,
        retry_count: int = 3,
        wait_after_action: int = 120,
        wait_strategy: WaitStrategy | None = None,
    ):
        """初始化智能定位器.

        Args:
            page: Playwright页面对象
            default_timeout: 默认超时时间(毫秒)
            retry_count: 重试次数
            wait_after_action: 操作后等待时间(毫秒,兼容旧配置)
            wait_strategy: 自定义等待策略
        """
        self.page = page
        self.default_timeout = default_timeout
        self.retry_count = retry_count
        if wait_strategy:
            self.wait_strategy = wait_strategy
        else:
            self.wait_strategy = WaitStrategy(
                wait_after_action_ms=wait_after_action,
                validation_timeout_ms=default_timeout,
            )
        self.waiter = PageWaiter(page, self.wait_strategy)
        logger.debug(
            "SmartLocator初始化"
            f" (timeout={default_timeout}ms, retry={retry_count}, "
            f"wait_after_action={self.wait_strategy.wait_after_action_ms}ms)"
        )

    async def find_element(
        self,
        selectors: str | list[str],
        timeout: int | None = None,
        must_be_visible: bool = True,
    ) -> Locator | None:
        """使用多重策略查找元素.

        Args:
            selectors: 选择器字符串或列表(按优先级排序)
            timeout: 超时时间(毫秒),None使用默认值
            must_be_visible: 是否必须可见

        Returns:
            找到的元素Locator,未找到返回None

        Examples:
            >>> element = await locator.find_element([
            ...     "button:has-text('保存')",
            ...     "button:has-text('确定')"
            ... ])
        """
        timeout = timeout or self.default_timeout

        # 转换为列表
        if isinstance(selectors, str):
            selectors = [selectors]

        # 依次尝试每个选择器
        for i, selector in enumerate(selectors):
            try:
                logger.debug(f"尝试选择器 [{i + 1}/{len(selectors)}]: {selector}")

                locator = self.page.locator(selector).first

                state = "visible" if must_be_visible else "attached"
                await locator.wait_for(state=state, timeout=timeout)
                logger.success(f"✓ 找到元素: {selector}")
                return locator

            except PlaywrightTimeoutError as exc:
                logger.debug(f"等待元素超时: {selector}, 错误: {exc}")
                continue
            except Exception as e:
                logger.debug(f"选择器失败: {selector}, 错误: {e}")
                continue

        logger.warning(f"未找到元素,尝试了 {len(selectors)} 个选择器")
        return None

    async def find_by_text(
        self,
        text: str,
        element_type: str | None = None,
        exact: bool = False,
        timeout: int | None = None,
    ) -> Locator | None:
        """根据文本内容查找元素.

        Args:
            text: 要查找的文本
            element_type: 元素类型(button, input等),None表示任意类型
            exact: 是否精确匹配
            timeout: 超时时间(毫秒)

        Returns:
            找到的元素Locator,未找到返回None

        Examples:
            >>> button = await locator.find_by_text("保存", element_type="button")
        """
        timeout = timeout or self.default_timeout

        # 构建选择器
        text_selector = f":text-is('{text}')" if exact else f":text('{text}')"

        selector = f"{element_type}:has-text('{text}')" if element_type else text_selector

        return await self.find_element(selector, timeout=timeout)

    async def find_input_by_label(
        self, label_text: str, timeout: int | None = None
    ) -> Locator | None:
        """根据标签文本查找输入框.

        Args:
            label_text: 标签文本(如"重量","长度")
            timeout: 超时时间(毫秒)

        Returns:
            找到的输入框Locator,未找到返回None

        Examples:
            >>> weight_input = await locator.find_input_by_label("重量")
        """
        selectors = [
            f"label:has-text('{label_text}') + input",
            f":text('{label_text}') >> .. >> input",
            f"input[placeholder*='{label_text}']",
            f"input[name*='{label_text}']",
        ]

        return await self.find_element(selectors, timeout=timeout)

    async def find_select_by_label(
        self, label_text: str, timeout: int | None = None
    ) -> Locator | None:
        """根据标签文本查找下拉框.

        Args:
            label_text: 标签文本
            timeout: 超时时间(毫秒)

        Returns:
            找到的下拉框Locator,未找到返回None

        Examples:
            >>> origin_select = await locator.find_select_by_label("产地")
        """
        selectors = [
            f"label:has-text('{label_text}') + select",
            f":text('{label_text}') >> .. >> select",
            f"select:near(:text('{label_text}'))",
        ]

        return await self.find_element(selectors, timeout=timeout)

    async def click_with_retry(
        self, selectors: str | list[str], max_retries: int | None = None
    ) -> bool:
        """点击元素(带重试).

        Args:
            selectors: 选择器字符串或列表
            max_retries: 最大重试次数,None使用默认值

        Returns:
            是否点击成功

        Examples:
            >>> success = await locator.click_with_retry("button:has-text('保存')")
        """
        max_retries = max_retries or self.retry_count

        for attempt in range(max_retries):
            try:
                element = await self.find_element(selectors)
                if not element:
                    raise ValueError("未找到可点击的元素")

                await element.click()
                await self.waiter.post_action_wait()
                logger.debug(f"✓ 点击成功 (尝试 {attempt + 1}/{max_retries})")
                return True
            except Exception as e:
                logger.warning(f"点击失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await self.waiter.apply_retry_backoff(attempt)
                    continue

        logger.error(f"点击失败,已重试 {max_retries} 次")
        return False

    async def _is_select_value(self, element: Locator, target: str) -> bool:
        """判断下拉框是否已选中目标值或标签."""

        try:
            selected = await element.evaluate(
                """
                (el) => Array.from(el.selectedOptions || []).map(opt => ({
                    value: opt.value,
                    label: opt.label
                }))
                """
            )
        except Exception as exc:
            logger.debug(f"读取下拉框选项失败: {exc}")
            return False

        for option in selected or []:
            if option.get("value") == target or option.get("label") == target:
                return True
        return False

    async def fill_with_retry(
        self,
        selectors: str | list[str],
        value: str,
        max_retries: int | None = None,
    ) -> bool:
        """填写输入框(带重试).

        Args:
            selectors: 选择器字符串或列表
            value: 要填写的值
            max_retries: 最大重试次数

        Returns:
            是否填写成功

        Examples:
            >>> success = await locator.fill_with_retry(
            ...     "input[placeholder*='重量']",
            ...     "7500"
            ... )
        """
        max_retries = max_retries or self.retry_count

        for attempt in range(max_retries):
            try:
                element = await self.find_element(selectors)
                if not element:
                    raise ValueError("未找到输入框")

                target_value = str(value)
                current_value = ""
                try:
                    current_value = await element.input_value()
                except PlaywrightTimeoutError:
                    current_value = ""

                if current_value == target_value:
                    logger.debug("输入框已包含目标值,跳过填写.")
                    return True

                await element.fill("")
                await element.fill(target_value)
                actual_value = await element.input_value()

                if actual_value != target_value:
                    raise ValueError(f"填写后值不匹配,期望 {target_value},实际 {actual_value}")

                await self.waiter.post_action_wait()
                logger.debug(f"✓ 填写成功: {value} (尝试 {attempt + 1}/{max_retries})")
                return True
            except Exception as e:
                logger.warning(f"填写失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await self.waiter.apply_retry_backoff(attempt)
                    continue

        logger.error(f"填写失败,已重试 {max_retries} 次")
        return False

    async def select_option_with_retry(
        self,
        selectors: str | list[str],
        value: str,
        max_retries: int | None = None,
    ) -> bool:
        """选择下拉选项(带重试).

        Args:
            selectors: 选择器字符串或列表
            value: 要选择的值
            max_retries: 最大重试次数

        Returns:
            是否选择成功

        Examples:
            >>> success = await locator.select_option_with_retry(
            ...     "select:near(:text('产地'))",
            ...     "浙江"
            ... )
        """
        max_retries = max_retries or self.retry_count

        for attempt in range(max_retries):
            try:
                element = await self.find_element(selectors)
                if not element:
                    raise ValueError("未找到下拉框")

                if await self._is_select_value(element, value):
                    logger.debug("下拉框已选择目标值,跳过选择.")
                    return True

                await element.select_option(label=value)

                if not await self._is_select_value(element, value):
                    await element.select_option(value=value)

                if not await self._is_select_value(element, value):
                    raise ValueError("选择后值未生效")

                await self.waiter.post_action_wait()
                logger.debug(f"✓ 选择成功: {value} (尝试 {attempt + 1}/{max_retries})")
                return True
            except Exception as e:
                logger.warning(f"选择失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await self.waiter.apply_retry_backoff(attempt)
                    continue

        logger.error(f"选择失败,已重试 {max_retries} 次")
        return False


# 测试代码
if __name__ == "__main__":
    print("=" * 60)
    print("SmartLocator - 智能选择器工具")
    print("=" * 60)
    print()
    print("功能:")
    print("1. 多重后备选择器")
    print("2. 智能等待和重试")
    print("3. 文本定位器优先")
    print("4. 处理动态aria-ref")
    print()
    print("使用示例:")
    print("""
    from smart_locator import SmartLocator

    locator = SmartLocator(page)

    # 使用多个后备选择器
    button = await locator.find_element([
        "button:has-text('保存')",
        "button:has-text('确定')",
        "[role='button']:has-text('保存')"
    ])

    # 根据标签查找输入框
    weight_input = await locator.find_input_by_label("重量")

    # 点击(带重试)
    await locator.click_with_retry("button:has-text('下一步')")

    # 填写(带重试)
    await locator.fill_with_retry("input[placeholder*='重量']", "7500")
    """)
    print("=" * 60)
