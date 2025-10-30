"""
@PURPOSE: 测试价格计算器功能
@OUTLINE:
  - test_price_result_calculate: 测试价格计算
  - test_price_result_rounding: 测试价格四舍五入
  - test_price_calculator_batch: 测试批量计算
  - test_price_calculator_custom_multipliers: 测试自定义倍率
@DEPENDENCIES:
  - 外部: pytest
  - 内部: src.data_processor.price_calculator
"""

import pytest

from src.data_processor.price_calculator import PriceCalculator, PriceResult


def test_price_result_calculate():
    """测试价格计算."""
    result = PriceResult.calculate(100, multiplier=7.5, supply_multiplier=10.0)

    assert result.cost_price == 100
    assert result.multiplier == 7.5
    assert result.suggested_price == 750.0
    assert result.supply_price == 1000.0


def test_price_result_rounding():
    """测试价格四舍五入."""
    result = PriceResult.calculate(99.99, multiplier=7.5, supply_multiplier=10.0)

    assert result.suggested_price == 749.92  # 99.99 * 7.5 = 749.925 → round = 749.92
    assert result.supply_price == 999.90


def test_price_calculator_batch():
    """测试批量计算."""
    calculator = PriceCalculator(multiplier=7.5, supply_multiplier=10.0)
    results = calculator.calculate_batch([100, 200, 300])

    assert len(results) == 3
    assert results[0].suggested_price == 750.0
    assert results[1].suggested_price == 1500.0
    assert results[2].suggested_price == 2250.0


def test_price_calculator_custom_multiplier():
    """测试自定义倍率."""
    calculator = PriceCalculator(multiplier=5.0, supply_multiplier=8.0)
    results = calculator.calculate_batch([100])

    assert results[0].suggested_price == 500.0
    assert results[0].supply_price == 800.0


