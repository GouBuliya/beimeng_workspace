"""
@PURPOSE: 首次编辑控制器组合入口.
@OUTLINE:
  - class FirstEditController: 聚合各类首次编辑操作能力
"""

from __future__ import annotations

from .base import FirstEditBase
from .category import FirstEditCategoryMixin
from .dialog import FirstEditDialogMixin
from .logistics import FirstEditLogisticsMixin
from .media import FirstEditMediaMixin
from .sku import FirstEditSkuMixin
from .sku_spec_replace import FirstEditSkuSpecReplaceMixin
from .title import FirstEditTitleMixin
from .workflow import FirstEditWorkflowMixin


class FirstEditController(
    FirstEditWorkflowMixin,
    FirstEditMediaMixin,
    FirstEditSkuMixin,
    FirstEditSkuSpecReplaceMixin,
    FirstEditLogisticsMixin,
    FirstEditTitleMixin,
    FirstEditCategoryMixin,
    FirstEditDialogMixin,
    FirstEditBase,
):
    """面向业务的首次编辑控制器,实现 SOP 步骤 4 所需操作."""

    __slots__ = ()

    def __init__(self, selector_path: str = "config/miaoshou_selectors_v2.json") -> None:
        """初始化控制器."""
        super().__init__(selector_path=selector_path)

