"""
@PURPOSE: 解析 JSON 选择器配置并转换为 Playwright Locator 对象
@OUTLINE:
  - class SelectorResolver: 根据配置动态创建定位器
  - resolve_locator(): 单个选择器转 Locator
  - resolve_field(): 字段配置(多个候选)转 Locator 列表
@GOTCHAS:
  - 支持 get_by_label, get_by_role, get_by_placeholder, get_by_text, css 等类型
  - 按配置顺序尝试,找到第一个可用的返回
  - 自动记录成功的选择器命中信息
@DEPENDENCIES:
  - 内部: utils.selector_hit_recorder
  - 外部: playwright.async_api
@RELATED: first_edit/base.py, miaoshou_selectors_v2.json
"""

from __future__ import annotations

from typing import Any

from loguru import logger
from playwright.async_api import Locator, Page

from ..utils.selector_hit_recorder import record_selector_hit
from ..utils.selector_race import TIMEOUTS


class SelectorResolver:
    """将 JSON 选择器配置转换为 Playwright Locator."""

    def __init__(self, page: Page):
        """初始化解析器.

        Args:
            page: Playwright 页面对象.
        """
        self.page = page

    def resolve_locator(self, config: dict[str, Any] | str) -> Locator:
        """根据配置创建单个 Locator.

        Args:
            config: 选择器配置字典或 CSS 选择器字符串.
                字典格式: {"type": "get_by_label", "value": "产品标题", "exact": False}

        Returns:
            Playwright Locator 对象.

        Examples:
            >>> resolver.resolve_locator({"type": "get_by_label", "value": "产品标题"})
            >>> resolver.resolve_locator("input[placeholder*='标题']")
        """
        # 兼容简单字符串配置
        if isinstance(config, str):
            return self.page.locator(config)

        locator_type = config.get("type", "css")
        value = config.get("value", "")
        exact = config.get("exact", False)

        if locator_type == "get_by_label":
            return self.page.get_by_label(value, exact=exact)
        elif locator_type == "get_by_role":
            role = value
            name = config.get("name")
            return self.page.get_by_role(role, name=name, exact=exact)
        elif locator_type == "get_by_placeholder":
            return self.page.get_by_placeholder(value, exact=exact)
        elif locator_type == "get_by_text":
            return self.page.get_by_text(value, exact=exact)
        elif locator_type == "get_by_title":
            return self.page.get_by_title(value, exact=exact)
        elif locator_type == "css":
            return self.page.locator(value)
        elif locator_type == "xpath":
            return self.page.locator(f"xpath={value}")
        else:
            logger.warning(f"未知的定位器类型: {locator_type}, 降级为 CSS")
            return self.page.locator(value)

    async def resolve_field(
        self,
        field_config: dict[str, Any],
        timeout_ms: int = TIMEOUTS.NORMAL,
        context_name: str = "",
    ) -> Locator | None:
        """解析字段配置,返回第一个可用的 Locator.

        Args:
            field_config: 字段配置,包含 locators 列表.
            timeout_ms: 等待超时时间(毫秒).
            context_name: 业务上下文名称,用于记录选择器命中(如"产品标题输入框").

        Returns:
            第一个可见的 Locator,如果都不可用则返回 None.

        Examples:
            >>> config = {
            ...     "locators": [
            ...         {"type": "get_by_label", "value": "产品标题"},
            ...         {"type": "css", "value": "input[placeholder*='标题']"}
            ...     ]
            ... }
            >>> locator = await resolver.resolve_field(config, context_name="产品标题")
        """
        locators_config = field_config.get("locators", [])

        # 兼容简单的字符串列表
        if isinstance(locators_config, str):
            locators_config = [locators_config]

        for index, loc_config in enumerate(locators_config):
            try:
                locator = self.resolve_locator(loc_config)
                # 检查元素是否存在且可见
                if await locator.count() > 0:
                    first = locator.first
                    try:
                        await first.wait_for(state="visible", timeout=timeout_ms)
                        # 记录选择器命中
                        record_selector_hit(
                            selector=loc_config,
                            selector_list=locators_config,
                            index=index,
                            context=context_name or field_config.get("name", "resolve_field"),
                        )
                        return first
                    except Exception:
                        # 元素存在但不可见,继续尝试下一个
                        continue
            except Exception as e:
                logger.debug(f"定位器 {loc_config} 解析失败: {e}")
                continue

        logger.warning(f"字段配置中的所有定位器都不可用: {field_config}")
        return None

    async def resolve_field_list(self, field_config: dict[str, Any]) -> list[Locator]:
        """解析字段配置,返回所有匹配的 Locator 列表.

        Args:
            field_config: 字段配置,包含 locators 列表.

        Returns:
            所有匹配的 Locator 列表.

        Examples:
            >>> config = {"locators": ["button:has-text('保存')", "button:has-text('确定')"]}
            >>> locators = await resolver.resolve_field_list(config)
        """
        locators_config = field_config.get("locators", [])
        if isinstance(locators_config, str):
            locators_config = [locators_config]

        result = []
        for loc_config in locators_config:
            try:
                locator = self.resolve_locator(loc_config)
                if await locator.count() > 0:
                    result.append(locator)
            except Exception as e:
                logger.debug(f"定位器 {loc_config} 解析失败: {e}")
                continue

        return result
