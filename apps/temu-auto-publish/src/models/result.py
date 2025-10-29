"""结果数据模型定义.

定义了影刀流程执行结果的数据结构。
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class YingdaoResult(BaseModel):
    """影刀流程执行结果基类.
    
    所有影刀返回结果的通用结构。
    
    Attributes:
        task_id: 任务ID
        flow: 流程名称
        status: 执行状态（success|failed）
        result: 结果数据
        execution_time: 执行耗时（秒）
        completed_at: 完成时间
        error_message: 错误信息
        logs: 执行日志
    """

    task_id: str = Field(..., description="任务ID")
    flow: str = Field(..., description="流程名称")
    status: str = Field(..., description="执行状态")
    result: Dict[str, Any] = Field(default_factory=dict, description="结果数据")
    execution_time: float = Field(default=0.0, description="执行耗时")
    completed_at: str = Field(default_factory=lambda: datetime.now().isoformat(), description="完成时间")
    error_message: Optional[str] = Field(default=None, description="错误信息")
    logs: List[str] = Field(default_factory=list, description="执行日志")


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
    collected_at: str = Field(default_factory=lambda: datetime.now().isoformat(), description="采集时间")
    links: List[Dict[str, str]] = Field(default_factory=list, description="商品链接列表")
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
    claimed_ids: List[str] = Field(default_factory=list, description="认领的商品ID")
    edited_at: str = Field(default_factory=lambda: datetime.now().isoformat(), description="编辑时间")
    changes: Dict[str, Dict[str, str]] = Field(default_factory=dict, description="修改内容")
    images_confirmed: bool = Field(default=False, description="图片已确认")
    saved: bool = Field(default=False, description="已保存")
    status: str = Field(default="pending", description="编辑状态")
    error_message: Optional[str] = Field(default=None, description="错误信息")


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
    published_at: str = Field(default_factory=lambda: datetime.now().isoformat(), description="发布时间")
    items: List[Dict[str, Any]] = Field(default_factory=list, description="发布商品列表")
    total_published: int = Field(default=0, description="总发布数量")
    success_count: int = Field(default=0, description="成功数量")
    failed_count: int = Field(default=0, description="失败数量")
    status: str = Field(default="pending", description="发布状态")


