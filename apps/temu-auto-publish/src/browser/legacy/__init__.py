"""
@PURPOSE: 浏览器模块的遗留实现集合，保留兼容旧流程的控制器
@OUTLINE:
  - BatchEditControllerV1: 旧版批量编辑控制器
@RELATED: ../batch_edit_controller.py, ../../workflows/legacy/
"""

from .batch_edit_controller_v1 import BatchEditController as BatchEditControllerV1

__all__ = ["BatchEditControllerV1"]

