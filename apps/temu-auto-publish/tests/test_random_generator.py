"""
@PURPOSE: 测试随机数据生成器功能
@OUTLINE:
  - test_generate_weight: 测试重量生成
  - test_generate_weight_kg: 测试重量生成（千克）
  - test_generate_dimensions: 测试尺寸生成
  - test_dimensions_order: 测试尺寸顺序（长>宽>高）
  - test_validate_dimensions: 测试尺寸验证
  - test_generate_batch_data: 测试批量生成
  - test_custom_ranges: 测试自定义范围
@DEPENDENCIES:
  - 外部: pytest
  - 内部: src.data_processor.random_generator
"""

import pytest

from src.data_processor.random_generator import RandomDataGenerator


def test_generate_weight():
    """测试重量生成（克）."""
    generator = RandomDataGenerator()

    for _ in range(10):
        weight = generator.generate_weight()
        assert 5000 <= weight <= 9999
        assert isinstance(weight, int)


def test_generate_weight_kg():
    """测试重量生成（千克）."""
    generator = RandomDataGenerator()

    for _ in range(10):
        weight_kg = generator.generate_weight_kg()
        assert 5.0 <= weight_kg <= 10.0
        assert isinstance(weight_kg, float)


def test_generate_dimensions():
    """测试尺寸生成."""
    generator = RandomDataGenerator()

    for _ in range(10):
        length, width, height = generator.generate_dimensions()
        assert 50 <= length <= 99
        assert 50 <= width <= 99
        assert 50 <= height <= 99


def test_dimensions_order():
    """测试尺寸顺序（长>宽>高）."""
    generator = RandomDataGenerator()

    for _ in range(20):
        length, width, height = generator.generate_dimensions()
        assert length > width > height, f"尺寸顺序错误: {length}×{width}×{height}"


def test_validate_dimensions():
    """测试尺寸验证功能."""
    generator = RandomDataGenerator()

    # 正确的尺寸
    assert generator.validate_dimensions(80, 60, 50) is True
    assert generator.validate_dimensions(90, 70, 60) is True

    # 顺序错误
    assert generator.validate_dimensions(50, 60, 80) is False
    assert generator.validate_dimensions(80, 80, 80) is False

    # 超出范围
    assert generator.validate_dimensions(100, 80, 60) is False
    assert generator.validate_dimensions(40, 30, 20) is False


def test_generate_batch_data():
    """测试批量生成."""
    generator = RandomDataGenerator()
    data_list = generator.generate_batch_data(20)

    assert len(data_list) == 20

    for data in data_list:
        assert "weight" in data
        assert "weight_kg" in data
        assert "dimensions" in data
        assert "dimensions_tuple" in data

        # 验证重量
        assert 5000 <= data["weight"] <= 9999

        # 验证尺寸
        dims = data["dimensions"]
        assert dims["length"] > dims["width"] > dims["height"]


def test_custom_ranges():
    """测试自定义范围."""
    generator = RandomDataGenerator(
        weight_min=1000, weight_max=2000, dimension_min=10, dimension_max=30
    )

    # 测试重量
    weight = generator.generate_weight()
    assert 1000 <= weight <= 2000

    # 测试尺寸
    length, width, height = generator.generate_dimensions()
    assert 10 <= length <= 30
    assert 10 <= width <= 30
    assert 10 <= height <= 30
    assert length > width > height


def test_packaging_dimensions():
    """测试外包装尺寸生成."""
    generator = RandomDataGenerator()

    for _ in range(10):
        length, width, height = generator.generate_packaging_dimensions()
        # 外包装尺寸会比普通尺寸稍大
        assert 55 <= length <= 109  # 50+5 to 99+10
        assert length > width > height


def test_seed_reproducibility():
    """测试随机种子可重现性."""
    gen1 = RandomDataGenerator(seed=42)
    gen2 = RandomDataGenerator(seed=42)

    # 使用相同种子应生成相同结果
    weight1 = gen1.generate_weight()
    weight2 = gen2.generate_weight()
    assert weight1 == weight2

    dims1 = gen1.generate_dimensions()
    dims2 = gen2.generate_dimensions()
    assert dims1 == dims2

