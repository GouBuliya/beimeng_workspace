"""
@PURPOSE: 随机数据生成器，生成符合SOP规则的随机重量和尺寸
@OUTLINE:
  - class RandomDataGenerator: 随机数据生成器主类
  - def generate_weight(): 生成重量 (5000-9999G)
  - def generate_dimensions(): 生成尺寸 (50-99cm, 长>宽>高)
  - def generate_weight_kg(): 生成重量 (KG单位)
  - def generate_packaging_dimensions(): 生成外包装尺寸
@GOTCHAS:
  - 尺寸必须满足: 长 > 宽 > 高 (SOP步骤7.10要求)
  - 重量范围: 5000-9999G (SOP步骤7.9)
  - 尺寸范围: 50-99cm (SOP步骤7.10)
@DEPENDENCIES:
  - 外部: random
@RELATED: batch_edit_controller.py, processor.py
"""

import random

from loguru import logger


class RandomDataGenerator:
    """随机数据生成器（基于SOP v2.0规则）.

    生成符合SOP手册要求的随机数据，用于批量编辑填充。

    SOP规则：
    - 重量: 5000-9999G（步骤7.9）
    - 尺寸: 50-99cm，且长>宽>高（步骤7.10）
    - 外包装: 长方体、硬包装（步骤7.5）

    Attributes:
        weight_min: 最小重量（克），默认5000
        weight_max: 最大重量（克），默认9999
        dimension_min: 最小尺寸（厘米），默认50
        dimension_max: 最大尺寸（厘米），默认99

    Examples:
        >>> generator = RandomDataGenerator()
        >>> weight = generator.generate_weight()
        >>> 5000 <= weight <= 9999
        True
        >>> length, width, height = generator.generate_dimensions()
        >>> length > width > height
        True
    """

    # SOP规则常量（不要随意修改）
    DEFAULT_WEIGHT_MIN = 5000  # 克，步骤7.9
    DEFAULT_WEIGHT_MAX = 9999  # 克，步骤7.9
    DEFAULT_DIMENSION_MIN = 50  # 厘米，步骤7.10
    DEFAULT_DIMENSION_MAX = 99  # 厘米，步骤7.10

    def __init__(
        self,
        weight_min: int = None,
        weight_max: int = None,
        dimension_min: int = None,
        dimension_max: int = None,
        seed: int = None,
    ):
        """初始化随机数据生成器.

        Args:
            weight_min: 最小重量（克），默认使用SOP规则5000
            weight_max: 最大重量（克），默认使用SOP规则9999
            dimension_min: 最小尺寸（厘米），默认使用SOP规则50
            dimension_max: 最大尺寸（厘米），默认使用SOP规则99
            seed: 随机种子，用于可重现的测试
        """
        self.weight_min = weight_min or self.DEFAULT_WEIGHT_MIN
        self.weight_max = weight_max or self.DEFAULT_WEIGHT_MAX
        self.dimension_min = dimension_min or self.DEFAULT_DIMENSION_MIN
        self.dimension_max = dimension_max or self.DEFAULT_DIMENSION_MAX
        self.seed = seed

        # 如果设置了种子，使用独立的Random实例以避免全局状态污染
        if seed is not None:
            self._random = random.Random(seed)
        else:
            self._random = random

        logger.info(
            f"随机数据生成器初始化（SOP v2.0），"
            f"重量: {self.weight_min}-{self.weight_max}G, "
            f"尺寸: {self.dimension_min}-{self.dimension_max}cm"
        )

    def generate_weight(self) -> int:
        """生成随机重量（克，SOP步骤7.9）.

        Returns:
            随机重量（克）

        Examples:
            >>> generator = RandomDataGenerator()
            >>> weight = generator.generate_weight()
            >>> 5000 <= weight <= 9999
            True
        """
        weight = self._random.randint(self.weight_min, self.weight_max)
        logger.debug(f"生成重量: {weight}G")
        return weight

    def generate_weight_kg(self) -> float:
        """生成随机重量（千克）.

        Returns:
            随机重量（千克，保留2位小数）

        Examples:
            >>> generator = RandomDataGenerator()
            >>> weight_kg = generator.generate_weight_kg()
            >>> 5.0 <= weight_kg <= 10.0
            True
        """
        weight_g = self.generate_weight()
        weight_kg = round(weight_g / 1000, 2)
        logger.debug(f"生成重量: {weight_kg}KG ({weight_g}G)")
        return weight_kg

    def generate_dimensions(self) -> tuple[int, int, int]:
        """生成随机尺寸（厘米，SOP步骤7.10）.

        SOP要求：长 > 宽 > 高

        Returns:
            尺寸元组 (长, 宽, 高)，单位厘米

        Examples:
            >>> generator = RandomDataGenerator()
            >>> length, width, height = generator.generate_dimensions()
            >>> length > width > height
            True
            >>> 50 <= length <= 99
            True
        """
        # 生成三个不同的随机数
        dimensions = self._random.sample(range(self.dimension_min, self.dimension_max + 1), 3)
        # 排序: 从大到小
        dimensions.sort(reverse=True)
        length, width, height = dimensions

        logger.debug(f"生成尺寸: {length}×{width}×{height}cm (长>宽>高)")
        return length, width, height

    def generate_packaging_dimensions(self) -> tuple[int, int, int]:
        """生成外包装尺寸（厘米）.

        用于SOP步骤7.5的外包装信息。
        与商品尺寸类似，但可能稍大。

        Returns:
            外包装尺寸元组 (长, 宽, 高)，单位厘米

        Examples:
            >>> generator = RandomDataGenerator()
            >>> length, width, height = generator.generate_packaging_dimensions()
            >>> length > width > height
            True
        """
        # 外包装通常比商品本身大一些
        padding = self._random.randint(5, 10)  # 额外5-10cm
        dimensions = self._random.sample(
            range(self.dimension_min + padding, self.dimension_max + padding + 1), 3
        )
        dimensions.sort(reverse=True)
        length, width, height = dimensions

        logger.debug(f"生成外包装尺寸: {length}×{width}×{height}cm")
        return length, width, height

    def generate_batch_data(self, count: int = 20) -> list[dict]:
        """批量生成随机数据.

        用于批量编辑20条商品时的数据填充。

        Args:
            count: 生成数量，默认20（SOP规定的批量数量）

        Returns:
            随机数据列表，每个元素包含weight和dimensions

        Examples:
            >>> generator = RandomDataGenerator()
            >>> data_list = generator.generate_batch_data(5)
            >>> len(data_list)
            5
            >>> all('weight' in d and 'dimensions' in d for d in data_list)
            True
        """
        data_list = []
        for i in range(count):
            weight = self.generate_weight()
            dimensions = self.generate_dimensions()
            data_list.append(
                {
                    "index": i + 1,
                    "weight": weight,
                    "weight_kg": round(weight / 1000, 2),
                    "dimensions": {
                        "length": dimensions[0],
                        "width": dimensions[1],
                        "height": dimensions[2],
                    },
                    "dimensions_tuple": dimensions,
                }
            )

        logger.info(f"批量生成完成，共 {count} 条随机数据")
        return data_list

    def validate_dimensions(self, length: int, width: int, height: int) -> bool:
        """验证尺寸是否符合SOP规则.

        Args:
            length: 长度（厘米）
            width: 宽度（厘米）
            height: 高度（厘米）

        Returns:
            是否符合规则（长>宽>高 且 在范围内）

        Examples:
            >>> generator = RandomDataGenerator()
            >>> generator.validate_dimensions(80, 60, 50)
            True
            >>> generator.validate_dimensions(50, 60, 80)
            False
        """
        # 检查范围
        if not all(self.dimension_min <= d <= self.dimension_max for d in [length, width, height]):
            return False

        # 检查顺序: 长>宽>高
        if not (length > width > height):
            return False

        return True


# 测试代码
if __name__ == "__main__":
    print("=" * 60)
    print("随机数据生成器测试（SOP v2.0规则）")
    print("=" * 60)

    generator = RandomDataGenerator()

    # 测试生成重量
    print("\n生成重量（克）:")
    for i in range(5):
        weight = generator.generate_weight()
        print(f"  {i + 1}. {weight}G")

    # 测试生成重量（千克）
    print("\n生成重量（千克）:")
    for i in range(5):
        weight_kg = generator.generate_weight_kg()
        print(f"  {i + 1}. {weight_kg}KG")

    # 测试生成尺寸
    print("\n生成尺寸（厘米）:")
    for i in range(5):
        length, width, height = generator.generate_dimensions()
        is_valid = generator.validate_dimensions(length, width, height)
        print(f"  {i + 1}. {length}×{width}×{height}cm (长>宽>高: {is_valid})")

    # 测试生成外包装尺寸
    print("\n生成外包装尺寸（厘米）:")
    for i in range(3):
        length, width, height = generator.generate_packaging_dimensions()
        print(f"  {i + 1}. {length}×{width}×{height}cm")

    # 测试批量生成
    print("\n批量生成（20条）:")
    data_list = generator.generate_batch_data(20)
    for data in data_list[:3]:  # 只显示前3条
        print(
            f"  {data['index']}. 重量: {data['weight']}G ({data['weight_kg']}KG), "
            f"尺寸: {data['dimensions']['length']}×"
            f"{data['dimensions']['width']}×"
            f"{data['dimensions']['height']}cm"
        )
    print(f"  ... (共{len(data_list)}条)")

    # 测试验证功能
    print("\n验证尺寸:")
    test_cases = [
        (80, 60, 50, True),
        (50, 60, 80, False),
        (90, 90, 90, False),
        (100, 80, 60, False),
    ]
    for length, width, height, expected in test_cases:
        is_valid = generator.validate_dimensions(length, width, height)
        status = "✓" if is_valid == expected else "✗"
        print(f"  {status} {length}×{width}×{height}cm -> {is_valid} (预期: {expected})")

    print("\n" + "=" * 60)
