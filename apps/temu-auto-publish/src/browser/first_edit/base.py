"""
@PURPOSE: 提供首次编辑控制器通用的选择器加载与配置工具.
@OUTLINE:
  - class FirstEditBase: 基础初始化、选择器读取与通用元素定位
  - def find_visible_element(): 顺序定位可见元素的通用工具
  - TIMEOUTS: 统一超时配置常量（从 selector_race 导出）
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from loguru import logger
from playwright.async_api import Locator, Page

from ...utils.selector_race import TIMEOUTS
from ..selector_resolver import SelectorResolver

# 导出 TIMEOUTS 便于 mixin 模块直接使用
__all__ = ["FirstEditBase", "TIMEOUTS"]


class FirstEditBase:
    """首次编辑控制器的基础能力混入，负责读取选择器配置并提供通用定位工具。"""

    def __init__(self, selector_path: str = "config/miaoshou_selectors_v2.json") -> None:
        """初始化基础配置.

        Args:
            selector_path: 选择器配置文件路径.
        """
        self.selector_path = Path(selector_path)
        self.selectors = self._load_selectors()
        self._resolver: SelectorResolver | None = None
        logger.info("首次编辑基础配置加载完成(选择器解析器版本)")

    def _get_resolver(self, page: Page) -> SelectorResolver:
        """获取或创建选择器解析器实例.

        Args:
            page: Playwright 页面对象.

        Returns:
            SelectorResolver 实例.
        """
        if self._resolver is None or self._resolver.page != page:
            self._resolver = SelectorResolver(page)
        return self._resolver

    def _load_selectors(self) -> dict[str, Any]:
        """加载首次编辑相关的选择器配置.

        Returns:
            解析后的选择器配置字典; 读取失败时返回空字典.
        """
        try:
            if self.selector_path.is_absolute():
                selector_file = self.selector_path
            else:
                relative_path = self.selector_path
                current_file = Path(__file__).resolve()
                selector_file: Path | None = None

                for parent in current_file.parents:
                    candidate = parent / relative_path
                    if candidate.exists():
                        selector_file = candidate
                        break

                if selector_file is None:
                    selector_file = current_file.parent.parent.parent / relative_path

            with open(selector_file, encoding="utf-8") as file:
                return json.load(file)
        except Exception as exc:  # pragma: no cover - 配置读取与IO环境相关
            logger.warning(f"加载首次编辑选择器失败: {exc}")
            return {}

    async def find_visible_element(
        self,
        page: Page,
        selectors: list[str],
        timeout_ms: int = TIMEOUTS.FAST,
        context_name: str = "",
        nth: int = 0,
    ) -> Locator | None:
        """顺序尝试定位可见元素，命中即返回.

        Args:
            page: Playwright 页面对象.
            selectors: 选择器列表（按优先级排序）.
            timeout_ms: 单个选择器的超时时间（毫秒）.
            context_name: 日志上下文，便于排查.
            nth: 针对存在多个匹配元素时，取第几个（0-based）.

        Returns:
            首个匹配的 Locator，未找到则返回 None.
        """
        for index, selector in enumerate(selectors):
            try:
                locator = page.locator(selector)
                count = await locator.count()
                if count <= nth:
                    continue
                candidate = locator.nth(nth)
                if await candidate.is_visible(timeout=timeout_ms):
                    logger.debug(
                        "顺序选择器命中: {} -> 索引 {} (nth={})",
                        context_name or selector,
                        index,
                        nth,
                    )
                    return candidate
            except Exception as exc:  # pragma: no cover - Playwright 环境相关
                logger.trace(
                    "定位元素失败，继续尝试后续选择器: {} (selector={}, nth={})",
                    exc,
                    selector,
                    nth,
                )
                continue

        logger.warning(
            "顺序选择器未命中任何元素: {} (共 {} 个选择器)",
            context_name or "未命名上下文",
            len(selectors),
        )
        return None
