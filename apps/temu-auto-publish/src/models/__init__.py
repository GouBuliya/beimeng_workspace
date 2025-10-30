"""
@PURPOSE: 数据模型模块，使用Pydantic定义所有数据结构
@OUTLINE:
  - ProductInput, TaskProduct, TaskData: 任务相关模型
  - SearchResult, EditResult, PublishResult, YingdaoResult: 结果相关模型
@DEPENDENCIES:
  - 内部: .task, .result
"""

from .task import ProductInput, TaskProduct, TaskData
from .result import SearchResult, EditResult, PublishResult, YingdaoResult

__all__ = [
    "ProductInput",
    "TaskProduct",
    "TaskData",
    "SearchResult",
    "EditResult",
    "PublishResult",
    "YingdaoResult",
]


