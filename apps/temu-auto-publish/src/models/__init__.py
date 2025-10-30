"""
@PURPOSE: 数据模型模块，使用Pydantic定义所有数据结构
@OUTLINE:
  - ProductInput, TaskProduct, TaskData: 任务相关模型
  - SearchResult, EditResult, PublishResult, BrowserResult: 结果相关模型
@DEPENDENCIES:
  - 内部: .task, .result
"""

from .result import BrowserResult, EditResult, PublishResult, SearchResult
from .task import ProductInput, TaskData, TaskProduct

__all__ = [
    "BrowserResult",
    "EditResult",
    "ProductInput",
    "PublishResult",
    "SearchResult",
    "TaskData",
    "TaskProduct",
]
