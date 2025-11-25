"""
@PURPOSE: 提供首次编辑控制器通用的选择器加载与配置工具.
@OUTLINE:
  - class FirstEditBase: 基础初始化与选择器读取
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from loguru import logger
from playwright.async_api import Page

from ..selector_resolver import SelectorResolver


class FirstEditBase:
    """首次编辑控制器的基础能力混入,负责读取选择器配置."""

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
            解析后的选择器配置字典;读取失败时返回空字典.
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

