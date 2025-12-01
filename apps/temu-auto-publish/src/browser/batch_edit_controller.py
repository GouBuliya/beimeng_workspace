"""
@PURPOSE: 兼容旧导入路径的批量编辑控制器入口
@OUTLINE:
  - from .batch_edit import BatchEditController
@DEPENDENCIES:
  - 内部: src.browser.batch_edit
"""

from .batch_edit import BatchEditController

__all__ = ["BatchEditController"]
