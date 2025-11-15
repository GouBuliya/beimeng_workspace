"""
@PURPOSE: Temu Web Panel 入口包, 汇总 API 创建函数与表单常量
@OUTLINE:
  - create_app: FastAPI 应用工厂
  - FORM_FIELDS: Web 表单字段定义
"""
# ruff: noqa: N999

from .api import create_app
from .fields import FORM_FIELDS

__all__ = ["FORM_FIELDS", "create_app"]
