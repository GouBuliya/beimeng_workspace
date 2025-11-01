"""
@PURPOSE: 读取和处理Excel选品表，提取商品信息用于采集
@OUTLINE:
  - class SelectionTableReader: 选品表读取器
  - def read_excel(): 读取Excel文件
  - def validate_row(): 验证行数据完整性
  - def extract_products(): 提取产品列表
@GOTCHAS:
  - Excel格式必须符合SOP规范
  - 型号编号格式为A0001, A0002等
  - 必填字段：产品名称、型号编号
@DEPENDENCIES:
  - 外部: pandas, openpyxl
  - 内部: loguru
@RELATED: collection_controller.py, collection_workflow.py
@CHANGELOG:
  - 2025-11-01: 初始创建，实现Excel选品表读取功能
"""

from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from loguru import logger
from pydantic import BaseModel, Field, field_validator


class ProductSelectionRow(BaseModel):
    """选品表中的单行产品数据.
    
    根据SOP文档定义的Excel结构：
    - 主品负责人
    - 产品名称 (用作搜索关键词)
    - 标题后缀 (型号编号如A0001)
    - 产品颜色/规格
    - 产品图
    - 尺寸图
    
    Attributes:
        owner: 主品负责人
        product_name: 产品名称/关键词
        model_number: 型号编号 (如A0001, A026, A045/A046等)
        color_spec: 产品颜色/规格
        collect_count: 需要采集的数量（默认5）
        cost_price: 进货价/成本价
    
    Examples:
        >>> row = ProductSelectionRow(
        ...     owner="张三",
        ...     product_name="药箱收纳盒",
        ...     model_number="A0049",
        ...     color_spec="白色/大号",
        ...     collect_count=5
        ... )
    """
    
    owner: str = Field(..., description="主品负责人")
    product_name: str = Field(..., description="产品名称（用作搜索关键词）")
    model_number: str = Field(..., description="型号编号")
    color_spec: Optional[str] = Field(None, description="产品颜色/规格")
    collect_count: int = Field(default=5, ge=1, le=100, description="采集数量")
    
    # 新增字段：价格
    cost_price: Optional[float] = Field(None, description="进货价/成本价", ge=0)
    
    @field_validator("model_number")
    @classmethod
    def validate_model_number(cls, v: str) -> str:
        """验证型号编号格式（放宽验证，支持 A026, A045/A046 等格式）."""
        if not v or not v.startswith("A"):
            raise ValueError("型号编号必须以A开头")
        return v


class SelectionTableReader:
    """Excel选品表读取器.
    
    负责读取和解析Excel选品表，提取商品信息用于采集流程。
    
    Examples:
        >>> reader = SelectionTableReader()
        >>> products = reader.read_excel("data/input/selection_table.xlsx")
        >>> print(len(products))
        10
        >>> print(products[0].product_name)
        '药箱收纳盒'
    """
    
    def __init__(self):
        """初始化选品表读取器."""
        logger.info("选品表读取器初始化")
        
        # Excel列名映射（支持中英文）
        self.column_mapping = {
            "主品负责人": "owner",
            "owner": "owner",
            "负责人": "owner",
            
            "产品名称": "product_name",
            "product_name": "product_name",
            "商品名称": "product_name",
            "名称": "product_name",
            
            "标题后缀": "model_number",
            "model_number": "model_number",
            "型号": "model_number",
            "型号编号": "model_number",
            
            "产品颜色/规格": "color_spec",
            "color_spec": "color_spec",
            "颜色规格": "color_spec",
            "规格": "color_spec",
            
            "采集数量": "collect_count",
            "collect_count": "collect_count",
            
            # 新增映射：进货价
            "进货价": "cost_price",
            "    进货价": "cost_price",  # 处理带空格的列名
            "成本价": "cost_price",
            "cost_price": "cost_price",
            "价格": "cost_price",
        }
    
    def read_excel(
        self,
        file_path: str,
        sheet_name: str = 0,
        skip_rows: int = 0
    ) -> List[ProductSelectionRow]:
        """读取Excel选品表.
        
        Args:
            file_path: Excel文件路径
            sheet_name: 工作表名称或索引（默认第一个）
            skip_rows: 跳过的行数（如果有标题行）
            
        Returns:
            产品列表
            
        Raises:
            FileNotFoundError: 文件不存在
            ValueError: Excel格式错误
            
        Examples:
            >>> reader = SelectionTableReader()
            >>> products = reader.read_excel("selection.xlsx")
            >>> len(products) > 0
            True
        """
        logger.info(f"读取选品表: {file_path}")
        
        # 检查文件是否存在
        if not Path(file_path).exists():
            raise FileNotFoundError(f"选品表文件不存在: {file_path}")
        
        try:
            # 读取Excel
            df = pd.read_excel(
                file_path,
                sheet_name=sheet_name,
                skiprows=skip_rows,
                dtype=str  # 先全部读成字符串，后续转换
            )
            
            logger.info(f"✓ Excel读取成功，共 {len(df)} 行数据")
            logger.debug(f"  列名: {df.columns.tolist()}")
            
            # 标准化列名
            df = self._normalize_columns(df)
            
            # 转换为ProductSelectionRow列表
            products = self.extract_products(df)
            
            logger.success(f"✓ 成功解析 {len(products)} 个产品")
            
            return products
            
        except Exception as e:
            logger.error(f"读取Excel失败: {e}")
            raise
    
    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """标准化列名.
        
        将中文列名映射为英文字段名。
        
        Args:
            df: 原始DataFrame
            
        Returns:
            标准化后的DataFrame
        """
        # 创建列名映射
        rename_dict = {}
        for col in df.columns:
            col_str = str(col).strip()
            if col_str in self.column_mapping:
                rename_dict[col] = self.column_mapping[col_str]
        
        # 重命名列
        if rename_dict:
            df = df.rename(columns=rename_dict)
            logger.debug(f"列名标准化: {rename_dict}")
        
        return df
    
    def extract_products(self, df: pd.DataFrame) -> List[ProductSelectionRow]:
        """从DataFrame提取产品列表.
        
        Args:
            df: pandas DataFrame
            
        Returns:
            产品列表
            
        Raises:
            ValueError: 数据验证失败
        """
        products = []
        errors = []
        
        for idx, row in df.iterrows():
            try:
                # 跳过空行
                if pd.isna(row.get("product_name")) or str(row.get("product_name")).strip() == "":
                    logger.debug(f"跳过第 {idx+1} 行（空行）")
                    continue
                
                # 构建产品数据
                product_data = {
                    "owner": str(row.get("owner", "未指定")).strip(),
                    "product_name": str(row.get("product_name")).strip(),
                    "model_number": str(row.get("model_number")).strip(),
                    "color_spec": str(row.get("color_spec", "")).strip() or None,
                    "product_image": str(row.get("product_image", "")).strip() or None,
                    "size_chart": str(row.get("size_chart", "")).strip() or None,
                    "collect_count": int(row.get("collect_count", 5)) if pd.notna(row.get("collect_count")) else 5,
                }
                
                # 验证并创建ProductSelectionRow
                product = ProductSelectionRow(**product_data)
                products.append(product)
                
                logger.debug(f"✓ 第 {idx+1} 行: {product.product_name} ({product.model_number})")
                
            except Exception as e:
                error_msg = f"第 {idx+1} 行数据错误: {e}"
                errors.append(error_msg)
                logger.warning(f"⚠️ {error_msg}")
                continue
        
        # 如果有错误，汇总报告
        if errors:
            logger.warning(f"⚠️ 共 {len(errors)} 行数据存在问题")
            for err in errors[:5]:  # 只显示前5个错误
                logger.warning(f"  - {err}")
            if len(errors) > 5:
                logger.warning(f"  ... 还有 {len(errors) - 5} 个错误")
        
        return products
    
    def validate_row(self, row: Dict) -> tuple[bool, Optional[str]]:
        """验证单行数据.
        
        Args:
            row: 行数据字典
            
        Returns:
            (是否有效, 错误信息)
            
        Examples:
            >>> reader = SelectionTableReader()
            >>> valid, error = reader.validate_row({
            ...     "product_name": "药箱",
            ...     "model_number": "A0001"
            ... })
            >>> valid
            True
        """
        # 检查必填字段
        if not row.get("product_name"):
            return False, "缺少产品名称"
        
        if not row.get("model_number"):
            return False, "缺少型号编号"
        
        # 验证型号格式
        model = str(row.get("model_number")).strip()
        if not (model.startswith("A") and len(model) == 5 and model[1:].isdigit()):
            return False, f"型号编号格式错误: {model}，应为A0001-A9999"
        
        return True, None
    
    def create_sample_excel(
        self,
        output_path: str,
        num_samples: int = 3
    ) -> None:
        """创建示例Excel选品表.
        
        用于测试和演示。
        
        Args:
            output_path: 输出文件路径
            num_samples: 示例数量
            
        Examples:
            >>> reader = SelectionTableReader()
            >>> reader.create_sample_excel("data/sample.xlsx", num_samples=3)
        """
        logger.info(f"创建示例选品表: {output_path}")
        
        # 示例数据
        sample_data = [
            {
                "主品负责人": "张三",
                "产品名称": "药箱收纳盒",
                "标题后缀": "A0049",
                "产品颜色/规格": "白色/大号",
                "采集数量": 5
            },
            {
                "主品负责人": "李四",
                "产品名称": "智能手表运动防水",
                "标题后缀": "A0050",
                "产品颜色/规格": "黑色/标准版",
                "采集数量": 5
            },
            {
                "主品负责人": "王五",
                "产品名称": "便携洗衣机迷你",
                "标题后缀": "A0051",
                "产品颜色/规格": "蓝色/家用款",
                "采集数量": 5
            }
        ]
        
        # 取前N个
        data = sample_data[:num_samples]
        
        # 创建DataFrame
        df = pd.DataFrame(data)
        
        # 确保目录存在
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        # 保存Excel
        df.to_excel(output_path, index=False, engine="openpyxl")
        
        logger.success(f"✓ 示例选品表已创建: {output_path}")
        logger.info(f"  包含 {len(data)} 个示例产品")

