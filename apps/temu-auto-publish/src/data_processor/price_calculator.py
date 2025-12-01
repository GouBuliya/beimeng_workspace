"""
@PURPOSE: 价格计算器,根据成本价计算建议售价和供货价(基于SOP v2.0规则)
@OUTLINE:
  - class PriceResult: 价格计算结果模型
  - class PriceCalculator: 价格计算器主类
  - def calculate(): 计算单个价格
  - def calculate_batch(): 批量计算价格
@GOTCHAS:
  - 价格规则来自SOP手册,不要随意修改倍率
  - 建议售价 = 成本 x 10(用于步骤7.14)
  - 供货价 = 成本 x 7.5(用于步骤9,实际是:真实供货价x3)
@DEPENDENCIES:
  - 外部: pydantic
@RELATED: processor.py
"""

from loguru import logger
from pydantic import BaseModel, Field


class PriceResult(BaseModel):
    """价格计算结果(基于SOP v2.0规则).

    Attributes:
        cost_price: 成本价
        suggested_price: 建议售价(成本 x 10,用于SOP步骤7.14)
        supply_price: 妙手供货价(成本 x 7.5,用于SOP步骤9)
        real_supply_price: 真实供货价(成本 x 2.5,中间值)
        suggested_multiplier: 建议售价倍率(10.0)
        supply_multiplier: 供货价倍率(7.5)

    Examples:
        >>> result = PriceResult.calculate(150)
        >>> result.suggested_price
        1500.0
        >>> result.supply_price
        1125.0
        >>> result.real_supply_price
        375.0
    """

    cost_price: float = Field(..., description="成本价")
    suggested_price: float = Field(..., description="建议售价(SOP步骤7.14)")
    supply_price: float = Field(..., description="妙手供货价(SOP步骤9)")
    real_supply_price: float = Field(..., description="真实供货价(中间值)")
    suggested_multiplier: float = Field(default=10.0, description="建议售价倍率")
    supply_multiplier: float = Field(default=7.5, description="供货价倍率")

    @classmethod
    def calculate(
        cls,
        cost_price: float,
        suggested_multiplier: float = 10.0,
        supply_multiplier: float = 7.5,
    ) -> "PriceResult":
        """计算价格(基于SOP v2.0规则).

        SOP规则:
        - 建议售价 = 成本 x 10(步骤7.14)
        - 真实供货价 = 成本 x 2.5(最低倍率)
        - 妙手供货价 = 真实供货价 x 3 = 成本 x 7.5(步骤9)

        Args:
            cost_price: 成本价
            suggested_multiplier: 建议售价倍率,默认 10.0(SOP规则)
            supply_multiplier: 供货价倍率,默认 7.5(SOP规则)

        Returns:
            价格计算结果

        Examples:
            >>> result = PriceResult.calculate(150)
            >>> result.suggested_price
            1500.0
            >>> result.supply_price
            1125.0
        """
        # SOP步骤7.14:建议售价
        suggested_price = round(cost_price * suggested_multiplier, 2)

        # SOP步骤9:供货价
        # 真实供货价 = 成本 x 2.5
        real_supply_price = round(cost_price * 2.5, 2)
        # 妙手供货价 = 真实 x 3 = 成本 x 7.5
        supply_price = round(cost_price * supply_multiplier, 2)

        return cls(
            cost_price=cost_price,
            suggested_price=suggested_price,
            supply_price=supply_price,
            real_supply_price=real_supply_price,
            suggested_multiplier=suggested_multiplier,
            supply_multiplier=supply_multiplier,
        )


class PriceCalculator:
    """价格计算器(基于SOP v2.0规则).

    批量计算产品价格,使用SOP手册定义的倍率.

    Attributes:
        suggested_multiplier: 建议售价倍率(默认10.0)
        supply_multiplier: 供货价倍率(默认7.5)

    Examples:
        >>> calculator = PriceCalculator()
        >>> results = calculator.calculate_batch([150, 200, 300])
        >>> len(results)
        3
        >>> results[0].suggested_price
        1500.0
    """

    # SOP规则倍率(不要随意修改)
    DEFAULT_SUGGESTED_MULTIPLIER = 10.0  # 步骤7.14
    DEFAULT_SUPPLY_MULTIPLIER = 7.5  # 步骤9

    def __init__(
        self,
        suggested_multiplier: float | None = None,
        supply_multiplier: float | None = None,
    ):
        """初始化计算器.

        Args:
            suggested_multiplier: 建议售价倍率(默认使用SOP规则10.0)
            supply_multiplier: 供货价倍率(默认使用SOP规则7.5)
        """
        self.suggested_multiplier = suggested_multiplier or self.DEFAULT_SUGGESTED_MULTIPLIER
        self.supply_multiplier = supply_multiplier or self.DEFAULT_SUPPLY_MULTIPLIER

        logger.info(
            f"价格计算器初始化(SOP v2.0),"
            f"建议售价倍率: {self.suggested_multiplier}, "
            f"供货价倍率: {self.supply_multiplier}"
        )

    def calculate_batch(self, cost_prices: list[float]) -> list[PriceResult]:
        """批量计算价格.

        Args:
            cost_prices: 成本价列表

        Returns:
            价格结果列表
        """
        results = []
        for cost in cost_prices:
            result = PriceResult.calculate(cost, self.suggested_multiplier, self.supply_multiplier)
            results.append(result)

        logger.debug(f"批量计算完成,共 {len(results)} 个")
        return results

    def get_price_breakdown(self, cost_price: float) -> dict:
        """获取价格明细(用于调试和展示).

        Args:
            cost_price: 成本价

        Returns:
            包含价格明细的字典

        Examples:
            >>> calc = PriceCalculator()
            >>> breakdown = calc.get_price_breakdown(150.0)
            >>> breakdown["成本价"]
            150.0
        """
        result = PriceResult.calculate(
            cost_price, self.suggested_multiplier, self.supply_multiplier
        )

        return {
            "成本价": result.cost_price,
            "建议售价(SOP步骤7.14)": result.suggested_price,
            "建议售价倍率": result.suggested_multiplier,
            "真实供货价(x2.5)": result.real_supply_price,
            "妙手供货价(SOP步骤9)": result.supply_price,
            "供货价倍率": result.supply_multiplier,
        }

    def calculate_suggested_price(self, cost: float) -> float:
        """计算建议售价(SOP步骤7.14).

        Args:
            cost: 成本价

        Returns:
            建议售价(成本 x 10)

        Examples:
            >>> calc = PriceCalculator()
            >>> calc.calculate_suggested_price(150)
            1500.0
        """
        return round(cost * self.suggested_multiplier, 2)

    def calculate_supply_price(self, cost: float) -> float:
        """计算妙手供货价(SOP步骤9).

        公式:
        - 真实供货价 = 成本 x 2.5(最低倍率)
        - 妙手供货价 = 真实供货价 x 3 = 成本 x 7.5

        Args:
            cost: 成本价

        Returns:
            妙手供货价(成本 x 7.5)

        Examples:
            >>> calc = PriceCalculator()
            >>> calc.calculate_supply_price(150)
            1125.0
        """
        return round(cost * self.supply_multiplier, 2)

    def calculate_supply_price_for_publish(self, cost: float) -> float:
        """计算发布时的供货价(SOP步骤9).

        这是步骤9"设置供货价"使用的价格.
        公式:真实供货价 x 3 = 成本 x 7.5

        Args:
            cost: 成本价

        Returns:
            供货价(成本 x 7.5)

        Examples:
            >>> calc = PriceCalculator()
            >>> calc.calculate_supply_price_for_publish(150)
            1125.0
        """
        return self.calculate_supply_price(cost)

    def calculate_real_supply_price(self, cost: float) -> float:
        """计算真实供货价(中间价格).

        公式:成本 x 2.5(最低倍率)

        Args:
            cost: 成本价

        Returns:
            真实供货价(成本 x 2.5)

        Examples:
            >>> calc = PriceCalculator()
            >>> calc.calculate_real_supply_price(150)
            375.0
        """
        return round(cost * 2.5, 2)


# 测试代码
if __name__ == "__main__":
    print("=" * 60)
    print("价格计算器测试(SOP v2.0规则)")
    print("=" * 60)

    calculator = PriceCalculator()

    # 单个计算(使用SOP示例:成本150元)
    print("\n单个计算示例(成本150元):")
    result = PriceResult.calculate(150)
    print(result.model_dump_json(indent=2))

    # 价格明细
    print("\n价格明细:")
    breakdown = calculator.get_price_breakdown(150.0)
    for key, value in breakdown.items():
        print(f"  {key}: {value}")

    # 批量计算
    print("\n批量计算示例:")
    results = calculator.calculate_batch([100, 150, 200, 300])
    for r in results:
        print(
            f"成本: ¥{r.cost_price:>6.2f} → "
            f"建议售价: ¥{r.suggested_price:>7.2f} (x{r.suggested_multiplier}) → "
            f"供货价: ¥{r.supply_price:>7.2f} (x{r.supply_multiplier})"
        )

    print("\n" + "=" * 60)
