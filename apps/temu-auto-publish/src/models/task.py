"""
@PURPOSE: 定义任务数据模型，从Excel读取到任务生成的所有数据结构
@OUTLINE:
  - class ProductInput: 选品表单行数据模型
  - class TaskProduct: 任务商品数据模型（包含价格计算结果）
  - class TaskData: 完整任务数据模型
@DEPENDENCIES:
  - 外部: pydantic
@RELATED: src/data_processor/excel_reader.py, src/data_processor/processor.py
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class ProductInput(BaseModel):
    """选品表单行数据模型.
    
    从 Excel 读取的原始数据。
    
    Attributes:
        name: 商品名称
        cost_price: 成本价（元）
        category: 商品类目路径
        keyword: 站内搜索关键词
        notes: 备注信息
        
    Examples:
        >>> product = ProductInput(
        ...     name="智能手表运动防水",
        ...     cost_price=150.00,
        ...     category="电子产品/智能穿戴",
        ...     keyword="智能手表"
        ... )
        >>> product.cost_price
        150.0
    """

    name: str = Field(..., min_length=1, description="商品名称")
    cost_price: float = Field(..., gt=0, description="成本价")
    category: str = Field(..., description="类目")
    keyword: str = Field(..., description="搜索关键词")
    notes: str = Field(default="", description="备注")

    @field_validator("cost_price")
    @classmethod
    def round_price(cls, v: float) -> float:
        """价格保留2位小数."""
        return round(v, 2)


class TaskProduct(BaseModel):
    """任务产品数据.
    
    处理后的产品数据，用于影刀流程执行。
    
    Attributes:
        id: 产品ID（格式：P001, P002, ...）
        keyword: 搜索关键词
        original_name: 原始商品名称
        ai_title: AI 生成的标题
        cost_price: 成本价
        suggested_price: 建议售价（成本价 × 7.5）
        supply_price: 供货价（成本价 × 10）
        category: 类目路径
        search_count: 需要采集的同款数量
        status: 产品状态
        collected_links: 采集的链接列表
        claimed_ids: 认领后的商品ID列表
        edit_result: 编辑结果
        publish_result: 发布结果
    """

    id: str = Field(..., pattern=r"^P\d{3}$", description="产品ID")
    keyword: str = Field(..., description="搜索关键词")
    original_name: str = Field(..., description="原始名称")
    ai_title: str = Field(..., description="AI 标题")
    cost_price: float = Field(..., gt=0, description="成本价")
    suggested_price: float = Field(..., gt=0, description="建议售价")
    supply_price: float = Field(..., gt=0, description="供货价")
    category: str = Field(..., description="类目")
    search_count: int = Field(default=5, ge=1, le=10, description="采集数量")
    status: str = Field(default="pending", description="状态")
    collected_links: List[str] = Field(default_factory=list, description="采集的链接")
    claimed_ids: List[str] = Field(default_factory=list, description="认领的商品ID")
    edit_result: Optional[dict] = Field(default=None, description="编辑结果")
    publish_result: Optional[dict] = Field(default=None, description="发布结果")

    @field_validator("suggested_price", "supply_price")
    @classmethod
    def round_price(cls, v: float) -> float:
        """价格保留2位小数."""
        return round(v, 2)


class TaskData(BaseModel):
    """任务数据.
    
    完整的任务信息，包含所有待处理的产品。
    
    Attributes:
        task_id: 任务ID（格式：YYYYMMDD_HHMMSS）
        created_at: 创建时间（ISO 8601）
        status: 任务状态（pending|processing|completed|failed）
        products: 产品列表
        statistics: 统计信息
        
    Examples:
        >>> from datetime import datetime
        >>> task = TaskData(
        ...     task_id="20251029_143000",
        ...     created_at=datetime.now().isoformat(),
        ...     products=[product]
        ... )
    """

    task_id: str = Field(..., description="任务ID")
    created_at: str = Field(..., description="创建时间")
    status: str = Field(default="pending", description="任务状态")
    products: List[TaskProduct] = Field(default_factory=list, description="产品列表")
    statistics: dict = Field(
        default_factory=lambda: {
            "total": 0,
            "pending": 0,
            "processing": 0,
            "success": 0,
            "failed": 0,
        },
        description="统计信息",
    )

    def update_statistics(self) -> None:
        """更新统计信息."""
        self.statistics["total"] = len(self.products)
        self.statistics["pending"] = sum(1 for p in self.products if p.status == "pending")
        self.statistics["processing"] = sum(1 for p in self.products if p.status == "processing")
        self.statistics["success"] = sum(1 for p in self.products if p.status == "success")
        self.statistics["failed"] = sum(1 for p in self.products if p.status == "failed")


