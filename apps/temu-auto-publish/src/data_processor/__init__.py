"""
@PURPOSE: 数据处理模块，负责Excel读取、价格计算、标题生成等数据处理逻辑
@OUTLINE:
  - ExcelReader: Excel读取器
  - PriceCalculator, PriceResult: 价格计算
  - TitleGenerator: 标题生成
  - DataProcessor: 数据处理整合
@DEPENDENCIES:
  - 内部: .excel_reader, .price_calculator, .title_generator, .processor
"""

from .excel_reader import ExcelReader, ProductInput
from .price_calculator import PriceCalculator, PriceResult
from .processor import DataProcessor, TaskData, TaskProduct
from .title_generator import TitleGenerator

__all__ = [
    "DataProcessor",
    "ExcelReader",
    "PriceCalculator",
    "PriceResult",
    "ProductInput",
    "TaskData",
    "TaskProduct",
    "TitleGenerator",
]
