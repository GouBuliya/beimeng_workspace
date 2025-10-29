"""价格计算器.

根据成本价计算建议售价和供货价。
"""

from typing import List

from loguru import logger
from pydantic import BaseModel, Field


class PriceResult(BaseModel):
    """价格计算结果.
    
    Attributes:
        cost_price: 成本价
        multiplier: 倍率
        suggested_price: 建议售价
        supply_price: 供货价
        
    Examples:
        >>> result = PriceResult.calculate(100, 7.5)
        >>> result.suggested_price
        750.0
        >>> result.supply_price
        1000.0
    """

    cost_price: float = Field(..., description="成本价")
    multiplier: float = Field(default=7.5, description="倍率 (2.5×3)")
    suggested_price: float = Field(..., description="建议售价")
    supply_price: float = Field(..., description="供货价")

    @classmethod
    def calculate(
        cls, cost_price: float, multiplier: float = 7.5, supply_multiplier: float = 10.0
    ) -> "PriceResult":
        """计算价格.
        
        Args:
            cost_price: 成本价
            multiplier: 价格倍率，默认 7.5 (即 2.5×3)
            supply_multiplier: 供货价倍率，默认 10
            
        Returns:
            价格计算结果
            
        Examples:
            >>> result = PriceResult.calculate(100)
            >>> result.suggested_price
            750.0
        """
        suggested_price = round(cost_price * multiplier, 2)
        supply_price = round(cost_price * supply_multiplier, 2)

        return cls(
            cost_price=cost_price,
            multiplier=multiplier,
            suggested_price=suggested_price,
            supply_price=supply_price,
        )


class PriceCalculator:
    """价格计算器.
    
    批量计算产品价格。
    
    Attributes:
        multiplier: 默认价格倍率
        supply_multiplier: 默认供货价倍率
        
    Examples:
        >>> calculator = PriceCalculator()
        >>> results = calculator.calculate_batch([100, 200, 300])
        >>> len(results)
        3
    """

    def __init__(self, multiplier: float = 7.5, supply_multiplier: float = 10.0):
        """初始化计算器.
        
        Args:
            multiplier: 默认价格倍率
            supply_multiplier: 默认供货价倍率
        """
        self.multiplier = multiplier
        self.supply_multiplier = supply_multiplier
        logger.info(f"价格计算器初始化，倍率: {multiplier}, 供货价倍率: {supply_multiplier}")

    def calculate_batch(self, cost_prices: List[float]) -> List[PriceResult]:
        """批量计算价格.
        
        Args:
            cost_prices: 成本价列表
            
        Returns:
            价格结果列表
        """
        results = []
        for cost in cost_prices:
            result = PriceResult.calculate(cost, self.multiplier, self.supply_multiplier)
            results.append(result)

        logger.debug(f"批量计算完成，共 {len(results)} 个")
        return results


# 测试代码
if __name__ == "__main__":
    calculator = PriceCalculator()

    # 单个计算
    result = PriceResult.calculate(100)
    print(result.model_dump_json(indent=2))

    # 批量计算
    results = calculator.calculate_batch([100, 200, 300])
    for r in results:
        print(f"成本: ¥{r.cost_price} → 建议售价: ¥{r.suggested_price} → 供货价: ¥{r.supply_price}")


