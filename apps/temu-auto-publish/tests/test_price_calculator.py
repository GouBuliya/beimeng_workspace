"""
@PURPOSE: 测试价格计算器功能（基于SOP v2.0规则）
@OUTLINE:
  - test_price_result_calculate_sop_rules: 测试SOP规则价格计算
  - test_price_result_rounding: 测试价格四舍五入
  - test_price_calculator_batch: 测试批量计算
  - test_price_calculator_custom_multipliers: 测试自定义倍率
  - test_price_calculator_default_sop_rules: 测试默认SOP规则
  - test_real_supply_price: 测试真实供货价计算
@DEPENDENCIES:
  - 外部: pytest
  - 内部: src.data_processor.price_calculator
@GOTCHAS:
  - SOP v2.0规则：建议售价×10，供货价×7.5
"""

import pytest

from src.data_processor.price_calculator import PriceCalculator, PriceResult


def test_price_result_calculate_sop_rules():
    """测试SOP v2.0规则价格计算.
    
    SOP规则：
    - 建议售价 = 成本 × 10（步骤7.14）
    - 真实供货价 = 成本 × 2.5
    - 妙手供货价 = 成本 × 7.5（步骤9）
    """
    result = PriceResult.calculate(150.0)

    assert result.cost_price == 150.0
    assert result.suggested_multiplier == 10.0
    assert result.supply_multiplier == 7.5
    assert result.suggested_price == 1500.0  # 150 × 10
    assert result.supply_price == 1125.0  # 150 × 7.5
    assert result.real_supply_price == 375.0  # 150 × 2.5


def test_price_result_rounding():
    """测试价格四舍五入."""
    result = PriceResult.calculate(99.99)

    assert result.suggested_price == 999.90  # 99.99 × 10 = 999.90
    assert result.supply_price == 749.92  # 99.99 × 7.5 = 749.925 → 749.92
    assert result.real_supply_price == 249.97  # 99.99 × 2.5 = 249.975 → 249.97


def test_price_calculator_batch():
    """测试批量计算（使用默认SOP规则）."""
    calculator = PriceCalculator()
    results = calculator.calculate_batch([100, 150, 200, 300])

    assert len(results) == 4
    # 成本100: 建议售价1000, 供货价750
    assert results[0].suggested_price == 1000.0
    assert results[0].supply_price == 750.0
    # 成本150: 建议售价1500, 供货价1125
    assert results[1].suggested_price == 1500.0
    assert results[1].supply_price == 1125.0
    # 成本200: 建议售价2000, 供货价1500
    assert results[2].suggested_price == 2000.0
    assert results[2].supply_price == 1500.0
    # 成本300: 建议售价3000, 供货价2250
    assert results[3].suggested_price == 3000.0
    assert results[3].supply_price == 2250.0


def test_price_calculator_custom_multipliers():
    """测试自定义倍率."""
    calculator = PriceCalculator(suggested_multiplier=5.0, supply_multiplier=8.0)
    results = calculator.calculate_batch([100])

    assert results[0].suggested_price == 500.0
    assert results[0].supply_price == 800.0
    assert results[0].suggested_multiplier == 5.0
    assert results[0].supply_multiplier == 8.0


def test_price_calculator_default_sop_rules():
    """测试默认使用SOP规则."""
    calculator = PriceCalculator()

    assert calculator.suggested_multiplier == 10.0
    assert calculator.supply_multiplier == 7.5


def test_real_supply_price():
    """测试真实供货价计算.
    
    SOP规则：真实供货价 = 成本 × 2.5（最低倍率）
    妙手供货价 = 真实供货价 × 3 = 成本 × 7.5
    """
    result = PriceResult.calculate(200.0)

    assert result.real_supply_price == 500.0  # 200 × 2.5
    assert result.supply_price == 1500.0  # 200 × 7.5
    # 验证关系：供货价 = 真实供货价 × 3
    assert result.supply_price == result.real_supply_price * 3


def test_price_breakdown():
    """测试价格明细功能."""
    calculator = PriceCalculator()
    breakdown = calculator.get_price_breakdown(150.0)

    assert breakdown["成本价"] == 150.0
    assert breakdown["建议售价（SOP步骤7.14）"] == 1500.0
    assert breakdown["建议售价倍率"] == 10.0
    assert breakdown["真实供货价（×2.5）"] == 375.0
    assert breakdown["妙手供货价（SOP步骤9）"] == 1125.0
    assert breakdown["供货价倍率"] == 7.5


