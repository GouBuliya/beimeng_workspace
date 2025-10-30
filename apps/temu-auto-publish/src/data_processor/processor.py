"""
@PURPOSE: 数据处理流程整合，提供统一的数据处理接口
@OUTLINE:
  - class DataProcessor: 数据处理器主类
  - def process_excel(): 处理Excel文件并生成任务数据
  - def _process_products(): 处理单个商品数据
@DEPENDENCIES:
  - 内部: .excel_reader, .price_calculator, .title_generator, ..models.task
@RELATED: excel_reader.py, price_calculator.py, title_generator.py
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List

from loguru import logger

from ..models.task import ProductInput, TaskData, TaskProduct
from .excel_reader import ExcelReader
from .price_calculator import PriceCalculator, PriceResult
from .title_generator import TitleGenerator


class DataProcessor:
    """数据处理器.
    
    整合 Excel 读取、价格计算、标题生成等功能。
    
    Attributes:
        price_calculator: 价格计算器
        title_generator: 标题生成器
        
    Examples:
        >>> processor = DataProcessor()
        >>> task_data = processor.process_excel(
        ...     "data/input/products.xlsx",
        ...     "data/output/task.json"
        ... )
        >>> len(task_data.products) > 0
        True
    """

    def __init__(
        self,
        price_multiplier: float = 7.5,
        supply_multiplier: float = 10.0,
        title_mode: str = "temu",
    ):
        """初始化处理器.
        
        Args:
            price_multiplier: 价格倍率
            supply_multiplier: 供货价倍率
            title_mode: 标题生成模式
        """
        self.price_calculator = PriceCalculator(price_multiplier, supply_multiplier)
        self.title_generator = TitleGenerator(mode=title_mode)

    def process_excel(self, excel_path: str | Path, output_path: str | Path) -> TaskData:
        """处理 Excel 生成任务数据.
        
        Args:
            excel_path: Excel 文件路径
            output_path: 输出 JSON 路径
            
        Returns:
            任务数据
            
        Raises:
            FileNotFoundError: Excel 文件不存在
            ValueError: 数据验证失败
            
        Examples:
            >>> processor = DataProcessor()
            >>> task = processor.process_excel(
            ...     "products.xlsx",
            ...     "task.json"
            ... )
        """
        logger.info("=" * 60)
        logger.info("开始处理选品表")
        logger.info("=" * 60)

        # 1. 读取 Excel
        reader = ExcelReader(excel_path)
        products_input = reader.read()
        logger.info(f"✓ 读取完成: {len(products_input)} 个产品")

        # 2. 处理每个产品
        task_products = []
        for idx, product in enumerate(products_input, 1):
            logger.info(f"\n处理第 {idx}/{len(products_input)} 个产品: {product.name}")

            # 价格计算
            price_result = PriceResult.calculate(
                product.cost_price,
                self.price_calculator.multiplier,
                self.price_calculator.supply_multiplier,
            )
            logger.debug(
                f"  价格: ¥{price_result.cost_price} → 建议售价: ¥{price_result.suggested_price} → 供货价: ¥{price_result.supply_price}"
            )

            # 标题生成
            ai_title = self.title_generator.generate(product.name, product.keyword)
            logger.debug(f"  标题: {ai_title}")

            # 构建任务产品
            task_product = TaskProduct(
                id=f"P{idx:03d}",
                keyword=product.keyword,
                original_name=product.name,
                ai_title=ai_title,
                cost_price=price_result.cost_price,
                suggested_price=price_result.suggested_price,
                supply_price=price_result.supply_price,
                category=product.category,
            )
            task_products.append(task_product)

        # 3. 生成任务数据
        task_data = TaskData(
            task_id=datetime.now().strftime("%Y%m%d_%H%M%S"),
            created_at=datetime.now().isoformat(),
            products=task_products,
        )
        task_data.update_statistics()

        # 4. 保存到 JSON
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(task_data.model_dump(), f, ensure_ascii=False, indent=2)

        logger.success(f"\n✓ 任务数据已生成: {output_path}")
        logger.info(f"  任务 ID: {task_data.task_id}")
        logger.info(f"  产品数: {len(task_data.products)}")

        return task_data


# 测试代码
if __name__ == "__main__":
    processor = DataProcessor()

    task_data = processor.process_excel(
        excel_path="data/input/products_sample.xlsx", output_path="data/output/task.json"
    )

    print("\n任务预览:")
    print(task_data.model_dump_json(indent=2, ensure_ascii=False))


