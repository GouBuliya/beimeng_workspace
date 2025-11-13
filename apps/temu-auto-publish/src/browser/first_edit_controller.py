"""
@PURPOSE: 首次编辑控制器旧路径兼容层.
@OUTLINE:
  - from .first_edit import FirstEditController
@GOTCHAS:
  - 新代码请直接使用 `src.browser.first_edit` 模块.
"""

from __future__ import annotations

from .first_edit import FirstEditController

__all__ = ["FirstEditController"]

