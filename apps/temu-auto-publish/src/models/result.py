"""
@PURPOSE: 定义Playwright浏览器自动化执行结果的数据结构
@OUTLINE:
  - class BrowserResult: 浏览器操作执行结果基类
  - class SearchResult: 搜索采集结果
  - class EditResult: 商品编辑结果
  - class PublishResult: 商品发布结果
@DEPENDENCIES:
  - 外部: pydantic
@RELATED: src/browser/search_controller.py, src/browser/edit_controller.py
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BrowserResult(BaseModel):
    """浏览器操作执行结果基类.

    使用 Playwright 执行浏览器自动化的通用结果结构。

    Attributes:
        task_id: 任务ID
        operation: 操作名称（search|edit|publish）
        status: 执行状态（success|failed|pending）
        result: 结果数据
        execution_time: 执行耗时（秒）
        completed_at: 完成时间
        error_message: 错误信息
        logs: 执行日志
        screenshot_path: 错误截图路径（如果有）
    """

    task_id: str = Field(..., description="任务ID")
    operation: str = Field(..., description="操作名称")
    status: str = Field(..., description="执行状态")
    result: dict[str, Any] = Field(default_factory=dict, description="结果数据")
    execution_time: float = Field(default=0.0, description="执行耗时")
    completed_at: str = Field(
        default_factory=lambda: datetime.now().isoformat(), description="完成时间"
    )
    error_message: str | None = Field(default=None, description="错误信息")
    logs: list[str] = Field(default_factory=list, description="执行日志")
    screenshot_path: str | None = Field(default=None, description="错误截图路径")


class SearchResult(BaseModel):
    """搜索采集结果.

    Attributes:
        product_id: 对应的产品ID
        keyword: 搜索关键词
        collected_at: 采集时间
        links: 采集的商品链接列表
        count: 实际采集数量
        status: 采集状态
    """

    product_id: str = Field(..., description="产品ID")
    keyword: str = Field(..., description="搜索关键词")
    collected_at: str = Field(
        default_factory=lambda: datetime.now().isoformat(), description="采集时间"
    )
    links: list[dict[str, str]] = Field(default_factory=list, description="商品链接列表")
    count: int = Field(default=0, description="采集数量")
    status: str = Field(default="pending", description="采集状态")


class EditResult(BaseModel):
    """编辑结果.

    Attributes:
        product_id: 产品ID
        claimed_ids: 认领成功的商品ID列表
        edited_at: 编辑时间
        changes: 修改内容记录
        images_confirmed: 图片是否已确认
        saved: 是否已保存
        status: 编辑状态
        error_message: 错误信息
    """

    product_id: str = Field(..., description="产品ID")
    claimed_ids: list[str] = Field(default_factory=list, description="认领的商品ID")
    edited_at: str = Field(
        default_factory=lambda: datetime.now().isoformat(), description="编辑时间"
    )
    changes: dict[str, dict[str, str]] = Field(default_factory=dict, description="修改内容")
    images_confirmed: bool = Field(default=False, description="图片已确认")
    saved: bool = Field(default=False, description="已保存")
    status: str = Field(default="pending", description="编辑状态")
    error_message: str | None = Field(default=None, description="错误信息")


class PublishResult(BaseModel):
    """发布结果.

    Attributes:
        product_id: 产品ID
        published_at: 发布时间
        items: 发布的商品列表
        total_published: 总发布数量
        success_count: 成功数量
        failed_count: 失败数量
        status: 发布状态
    """

    product_id: str = Field(..., description="产品ID")
    published_at: str = Field(
        default_factory=lambda: datetime.now().isoformat(), description="发布时间"
    )
    items: list[dict[str, Any]] = Field(default_factory=list, description="发布商品列表")
    total_published: int = Field(default=0, description="总发布数量")
    success_count: int = Field(default=0, description="成功数量")
    failed_count: int = Field(default=0, description="失败数量")
    status: str = Field(default="pending", description="发布状态")
