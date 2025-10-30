# Day 3：Python 数据处理层（v2.0 - 基于 SOP）

**目标**：完成 Excel 读取、AI 标题生成、价格计算等核心数据处理逻辑

**更新说明**：基于 SOP 手册调整价格计算规则和标题生成逻辑

---

## 上午任务（3-4小时）

### 3.1 选品表 Excel 读取模块 ✅

#### 准备测试数据
创建测试用的选品表 `data/input/products_sample.xlsx`，包含列：
- **商品名称** - 产品的中文名称
- **成本价** - 单位：元（如 150.00）
- **类目** - 类目路径（如 "家居/收纳用品"）
- **关键词** - 站内搜索关键词
- **型号** - 产品型号（新增，如 "A0001"）
- **备注** - 其他说明

#### Excel 读取器已实现 ✅

文件：`src/data_processor/excel_reader.py`

**关键功能**：
- 读取 Excel 并验证数据
- 列名标准化处理
- Pydantic 数据验证
- 错误行记录和跳过

**测试命令**：
```bash
cd /Users/candy/beimeng_workspace
PYTHONPATH=/Users/candy/beimeng_workspace/apps/temu-auto-publish:$PYTHONPATH \
uv run python -c "
from src.data_processor.excel_reader import ExcelReader
reader = ExcelReader('apps/temu-auto-publish/data/input/products_sample.xlsx')
products = reader.read()
print(f'读取到 {len(products)} 个产品')
for p in products:
    print(f'  - {p.name}: {p.cost_price}元')
"
```

---

## 下午任务（3-4小时）

### 3.2 价格计算器 ⚠️ 需要更新

根据 **SOP 手册**，价格计算规则需要调整：

#### 原规则 ❌
```python
建议售价 = 成本价 × 7.5
供货价 = 成本价 × 10
```

#### 新规则（基于 SOP）✅
```python
# SOP 步骤 7.14
建议售价 = 成本价 × 10

# SOP 步骤 9
真实供货价 = 成本价 × 2.5（最低倍率）
妙手供货价 = 真实供货价 × 3 = 成本价 × 7.5
```

#### 更新代码

**修改文件**：`src/data_processor/price_calculator.py`

```python
"""
@PURPOSE: 价格计算器，根据成本价计算建议售价和供货价
@OUTLINE:
  - class PriceCalculator: 价格计算器
  - def calculate_suggested_price(): 建议售价 = 成本 × 10
  - def calculate_supply_price(): 供货价 = 成本 × 7.5
  - def calculate_all(): 计算所有价格
@GOTCHAS:
  - 价格规则来自 SOP 手册，不要随意修改倍率
  - 建议售价用于步骤 7.14（批量编辑）
  - 供货价用于步骤 9（设置供货价）
@DEPENDENCIES:
  - 标准库: dataclasses, typing
"""

from dataclasses import dataclass
from typing import Dict


@dataclass
class PriceResult:
    """价格计算结果"""
    cost_price: float              # 成本价
    suggested_price: float         # 建议售价（步骤7.14）
    supply_price: float           # 妙手供货价（步骤9）
    real_supply_price: float      # 真实供货价（中间值）


class PriceCalculator:
    """价格计算器（基于 SOP 规则）"""
    
    # SOP 规则倍率
    SUGGESTED_PRICE_MULTIPLIER = 10.0   # 步骤 7.14
    REAL_SUPPLY_MULTIPLIER = 2.5        # 最低倍率
    MIAOSHOU_MULTIPLIER = 3.0           # 妙手倍率
    
    def calculate_suggested_price(self, cost_price: float) -> float:
        """计算建议售价（SOP 步骤 7.14）
        
        Args:
            cost_price: 成本价
        
        Returns:
            建议售价 = 成本价 × 10
            
        Examples:
            >>> calc = PriceCalculator()
            >>> calc.calculate_suggested_price(150.0)
            1500.0
        """
        return round(cost_price * self.SUGGESTED_PRICE_MULTIPLIER, 2)
    
    def calculate_supply_price(self, cost_price: float) -> float:
        """计算妙手供货价（SOP 步骤 9）
        
        计算逻辑：
        1. 真实供货价 = 成本价 × 2.5（最低倍率）
        2. 妙手供货价 = 真实供货价 × 3
        3. 最终 = 成本价 × 7.5
        
        Args:
            cost_price: 成本价
            
        Returns:
            供货价 = 成本价 × 7.5
            
        Examples:
            >>> calc = PriceCalculator()
            >>> calc.calculate_supply_price(150.0)
            1125.0
        """
        real_supply = cost_price * self.REAL_SUPPLY_MULTIPLIER
        miaoshou_supply = real_supply * self.MIAOSHOU_MULTIPLIER
        return round(miaoshou_supply, 2)
    
    def calculate_all(self, cost_price: float) -> PriceResult:
        """计算所有价格
        
        Args:
            cost_price: 成本价
        
        Returns:
            PriceResult: 包含所有价格的结果对象
            
        Examples:
            >>> calc = PriceCalculator()
            >>> result = calc.calculate_all(150.0)
            >>> result.suggested_price
            1500.0
            >>> result.supply_price
            1125.0
        """
        real_supply = cost_price * self.REAL_SUPPLY_MULTIPLIER
        
        return PriceResult(
            cost_price=round(cost_price, 2),
            suggested_price=self.calculate_suggested_price(cost_price),
            supply_price=self.calculate_supply_price(cost_price),
            real_supply_price=round(real_supply, 2)
        )
    
    def get_price_breakdown(self, cost_price: float) -> Dict[str, float]:
        """获取价格明细（用于调试和展示）
        
        Args:
            cost_price: 成本价
        
        Returns:
            包含价格明细的字典
        """
        result = self.calculate_all(cost_price)
        return {
            "成本价": result.cost_price,
            "建议售价（×10）": result.suggested_price,
            "真实供货价（×2.5）": result.real_supply_price,
            "妙手供货价（×7.5）": result.supply_price,
            "建议售价倍率": self.SUGGESTED_PRICE_MULTIPLIER,
            "供货价倍率": self.REAL_SUPPLY_MULTIPLIER * self.MIAOSHOU_MULTIPLIER,
        }
```

#### 测试更新后的价格计算

```bash
cd /Users/candy/beimeng_workspace
PYTHONPATH=/Users/candy/beimeng_workspace/apps/temu-auto-publish:$PYTHONPATH \
uv run python -c "
from src.data_processor.price_calculator import PriceCalculator

calc = PriceCalculator()
    
# 测试案例：成本价 150 元
result = calc.calculate_all(150.0)
print('价格计算结果（成本价 150 元）：')
print(f'  建议售价：{result.suggested_price} 元（×10）')
print(f'  真实供货价：{result.real_supply_price} 元（×2.5）')
print(f'  妙手供货价：{result.supply_price} 元（×7.5）')
print()

# 价格明细
breakdown = calc.get_price_breakdown(150.0)
for key, value in breakdown.items():
    print(f'{key}: {value}')
"
```

**预期输出**：
```
价格计算结果（成本价 150 元）：
  建议售价：1500.0 元（×10）
  真实供货价：375.0 元（×2.5）
  妙手供货价：1125.0 元（×7.5）

成本价: 150.0
建议售价（×10）: 1500.0
真实供货价（×2.5）: 375.0
妙手供货价（×7.5）: 1125.0
建议售价倍率: 10.0
供货价倍率: 7.5
```

---

### 3.3 AI 标题生成器 ⚠️ 需要增强

根据 **SOP 步骤 4.1**，标题生成有严格要求：

#### SOP 要求
1. 提取 5 个原标题中的高频热搜词
2. 生成 5 个新的中文标题
3. **必须添加型号后缀**（如 "A0001型号"）
4. 可选添加修饰词（如 "2025新款"）
5. 不要出现医疗相关词汇
6. 符合欧美阅读习惯
7. 符合 TEMU/亚马逊平台规则

#### AI 提示词模板（来自 SOP）

```python
TITLE_GENERATION_PROMPT = """
提取上面5个商品标题中的高频热搜词，写5个新的中文标题，不要出现药品、急救等医疗相关的词汇
符合欧美人的阅读习惯，符合TEMU/亚马逊平台规则，提高搜索流量
"""
```

#### 更新代码

**修改文件**：`src/data_processor/title_generator.py`

```python
"""
@PURPOSE: AI标题生成器，根据原始标题生成优化后的新标题
@OUTLINE:
  - class TitleGenerator: 标题生成器
  - def generate_with_model_suffix(): 生成标题并添加型号（SOP要求）
  - def add_optional_modifiers(): 添加可选修饰词
@GOTCHAS:
  - 必须添加型号后缀（SOP步骤4.1要求）
  - 避免医疗相关词汇
@DEPENDENCIES:
  - 标准库: typing, random
"""

from typing import List, Optional
import random


class TitleGenerator:
    """AI 标题生成器（基于 SOP 规则）"""
    
    # SOP 提示词模板
    PROMPT_TEMPLATE = """
提取上面{count}个商品标题中的高频热搜词，写{count}个新的中文标题，不要出现药品、急救等医疗相关的词汇
符合欧美人的阅读习惯，符合TEMU/亚马逊平台规则，提高搜索流量

原标题：
{titles}
"""
    
    # 可选修饰词库
    OPTIONAL_MODIFIERS = [
        "2025新款",
        "适用于多种场景",
        "节日必备",
        "热销款",
        "限时特惠",
        "高品质",
    ]
    
    def __init__(self, mode: str = "placeholder"):
        """初始化生成器
        
        Args:
            mode: 生成模式
                - "placeholder": 占位符模式（MVP）
                - "ai": AI 模式（需要接入实际 AI 服务）
        """
        self.mode = mode
    
    def generate_with_model_suffix(
        self,
        original_titles: List[str],
        model_prefix: str = "A",
        start_number: int = 1,
        add_modifiers: bool = False
    ) -> List[str]:
        """生成标题并添加型号后缀（SOP 步骤 4.1）
        
        Args:
            original_titles: 原始标题列表
            model_prefix: 型号前缀（默认 "A"）
            start_number: 起始编号（默认 1）
            add_modifiers: 是否添加可选修饰词
        
        Returns:
            带型号后缀的新标题列表
            
        Examples:
            >>> gen = TitleGenerator()
            >>> titles = ["智能手表", "运动手表", "防水手表"]
            >>> new_titles = gen.generate_with_model_suffix(titles)
            >>> new_titles[0]
            'TEMU_AI:智能手表 A0001型号'
        """
        # 生成基础标题
        base_titles = self._generate_base_titles(original_titles)
        
        # 添加型号后缀（必须）
        result = []
        for i, title in enumerate(base_titles):
            model_number = f"{model_prefix}{start_number + i:04d}"
        
            # 构建完整标题
            if add_modifiers:
                modifier = random.choice(self.OPTIONAL_MODIFIERS)
                full_title = f"{title} {modifier} {model_number}型号"
            else:
                full_title = f"{title} {model_number}型号"
            
            result.append(full_title)
        
        return result
    
    def _generate_base_titles(self, original_titles: List[str]) -> List[str]:
        """生成基础标题（不含型号）
        
        Args:
            original_titles: 原始标题列表
            
        Returns:
            新标题列表
        """
        if self.mode == "placeholder":
            # MVP 模式：占位符
            return [f"[TEMU_AI:{title}]" for title in original_titles]
        
        elif self.mode == "ai":
            # AI 模式：调用实际 AI 服务
            return self._call_ai_service(original_titles)
        
        else:
            raise ValueError(f"不支持的模式: {self.mode}")
    
    def _call_ai_service(self, titles: List[str]) -> List[str]:
        """调用 AI 服务生成标题
        
        Args:
            titles: 原始标题
        
        Returns:
            AI 生成的新标题
            
        Note:
            Phase 2 实现：接入 GPT/Claude/Qwen 等服务
        """
        # TODO: 接入实际 AI API
        prompt = self.PROMPT_TEMPLATE.format(
            count=len(titles),
            titles="\n".join([f"{i+1}. {t}" for i, t in enumerate(titles)])
        )
        # ai_response = call_ai_api(prompt)
        # return parse_ai_response(ai_response)
        
        raise NotImplementedError("AI 模式尚未实现，请使用 placeholder 模式")
    
    def get_prompt_preview(self, titles: List[str]) -> str:
        """预览 AI 提示词（用于调试）
        
        Args:
            titles: 原始标题
        
        Returns:
            完整的提示词
        """
        return self.PROMPT_TEMPLATE.format(
            count=len(titles),
            titles="\n".join([f"{i+1}. {t}" for i, t in enumerate(titles)])
        )
```

#### 测试标题生成

```bash
cd /Users/candy/beimeng_workspace
PYTHONPATH=/Users/candy/beimeng_workspace/apps/temu-auto-publish:$PYTHONPATH \
uv run python -c "
from src.data_processor.title_generator import TitleGenerator

gen = TitleGenerator(mode='placeholder')

# 测试：5个原始标题
original_titles = [
    '药箱收纳盒',
    '家用医药箱',
    '急救箱收纳',
    '医疗收纳盒',
    '药品整理箱'
]

# 生成带型号的标题
new_titles = gen.generate_with_model_suffix(
    original_titles,
    model_prefix='A',
    start_number=1,
    add_modifiers=True
)

print('原始标题 → 新标题（带型号）：')
for orig, new in zip(original_titles, new_titles):
    print(f'  {orig:15s} → {new}')

print()
print('AI 提示词预览：')
print(gen.get_prompt_preview(original_titles))
"
```

---

### 3.4 数据处理流程整合

#### 创建统一的处理器

**文件**：`src/data_processor/processor.py` （已存在，需要更新）

**关键更新**：
- 使用新的价格计算规则
- 集成带型号的标题生成
- 添加随机数据生成（重量、尺寸）

```python
from src.data_processor.excel_reader import ExcelReader
from src.data_processor.price_calculator import PriceCalculator
from src.data_processor.title_generator import TitleGenerator

class DataProcessor:
    """数据处理器（整合各个模块）"""
    
    def __init__(self):
        self.excel_reader = ExcelReader
        self.price_calc = PriceCalculator()
        self.title_gen = TitleGenerator(mode="placeholder")
    
    def process_excel(self, file_path: str) -> TaskData:
        """处理 Excel 文件，生成任务数据"""
        # 1. 读取 Excel
        reader = self.excel_reader(file_path)
        products = reader.read()
        
        # 2. 处理每个产品
        task_products = []
        for product in products:
            # 价格计算（新规则）
            prices = self.price_calc.calculate_all(product.cost_price)
            
            # 标题生成（带型号）
            titles = self.title_gen.generate_with_model_suffix([product.name])
            
            # 创建任务产品
            task_product = TaskProduct(
                keyword=product.keyword,
                original_name=product.name,
                ai_title=titles[0],
                cost_price=prices.cost_price,
                suggested_price=prices.suggested_price,
                supply_price=prices.supply_price,
                category=product.category,
            )
            task_products.append(task_product)
        
        # 3. 生成任务数据
        return TaskData(products=task_products)
```

---

## 验收标准 ✅

### 必须完成
- [x] Excel 读取器正常工作
- [ ] 价格计算器更新为新规则（×10 和 ×7.5）
- [ ] 标题生成器支持型号后缀
- [ ] 数据处理流程整合完成
- [ ] 单元测试通过

### 测试 Checklist
```bash
# 1. Excel 读取测试
uv run python -m pytest apps/temu-auto-publish/tests/test_excel_reader.py -v

# 2. 价格计算测试（需要更新断言）
uv run python -m pytest apps/temu-auto-publish/tests/test_price_calculator.py -v

# 3. 标题生成测试
# TODO: 添加新的测试用例

# 4. 集成测试
uv run python -m pytest apps/temu-auto-publish/tests/test_integration.py -v
```

---

## 价格规则对比

| 项目 | 原规则 | 新规则（SOP） | 示例（成本150元） |
|------|--------|--------------|-----------------|
| **建议售价** | 成本 × 7.5 | 成本 × 10 | 1500元 |
| **供货价** | 成本 × 10 | 成本 × 7.5 | 1125元 |
| **真实供货价** | - | 成本 × 2.5 | 375元 |
| **使用场景** | - | 步骤7.14 / 步骤9 | - |

---

## 下一步

完成 Day 3 后，继续 [Day 4：Playwright 登录和妙手访问](day4-playwright-login.md)
