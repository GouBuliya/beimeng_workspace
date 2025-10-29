"""数据模型定义.

使用 Pydantic 定义所有数据结构，确保类型安全和数据验证。
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


