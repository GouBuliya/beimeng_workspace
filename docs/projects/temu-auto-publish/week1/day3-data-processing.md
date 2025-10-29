# Day 3：Python 数据处理层

**目标**：完成 Excel 读取、AI 标题生成、价格计算等核心数据处理逻辑

---

## 上午任务（3-4小时）

### 3.1 选品表 Excel 读取模块

#### 准备测试数据
创建测试用的选品表 `data/input/products_sample.xlsx`，包含列：
- 商品名称
- 成本价
- 类目
- 关键词
- 备注

#### 创建 Excel 读取器 (`src/data_processor/excel_reader.py`)

```python
"""Excel 选品表读取器"""

from pathlib import Path
from typing import List
import pandas as pd
from loguru import logger
from pydantic import BaseModel, Field, validator


class ProductInput(BaseModel):
    """选品表单行数据模型"""
    
    name: str = Field(..., description="商品名称")
    cost_price: float = Field(..., gt=0, description="成本价")
    category: str = Field(..., description="类目")
    keyword: str = Field(..., description="搜索关键词")
    notes: str = Field(default="", description="备注")
    
    @validator("cost_price")
    def validate_price(cls, v):
        if v <= 0:
            raise ValueError("成本价必须大于0")
        return round(v, 2)


class ExcelReader:
    """Excel 读取器"""
    
    def __init__(self, file_path: str | Path):
        """初始化读取器
        
        Args:
            file_path: Excel 文件路径
        """
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"文件不存在: {self.file_path}")
    
    def read(self) -> List[ProductInput]:
        """读取并验证 Excel 数据
        
        Returns:
            产品列表
            
        Raises:
            ValueError: 数据验证失败
        """
        logger.info(f"开始读取 Excel: {self.file_path}")
        
        try:
            # 读取 Excel
            df = pd.read_excel(self.file_path)
            logger.debug(f"读取到 {len(df)} 行数据")
            
            # 列名标准化（处理不同的表头格式）
            df.columns = df.columns.str.strip()
            column_mapping = {
                "商品名称": "name",
                "成本价": "cost_price",
                "类目": "category",
                "关键词": "keyword",
                "备注": "notes"
            }
            df = df.rename(columns=column_mapping)
            
            # 删除空行
            df = df.dropna(subset=["name"])
            
            # 填充默认值
            df["notes"] = df["notes"].fillna("")
            
            # 转换为 Pydantic 模型
            products = []
            errors = []
            
            for idx, row in df.iterrows():
                try:
                    product = ProductInput(**row.to_dict())
                    products.append(product)
                except Exception as e:
                    errors.append(f"第 {idx+2} 行错误: {e}")
            
            # 报告结果
            if errors:
                logger.warning(f"数据验证发现 {len(errors)} 个错误:")
                for error in errors[:5]:  # 最多显示5个
                    logger.warning(f"  {error}")
            
            logger.success(f"成功读取 {len(products)} 个有效产品")
            return products
            
        except Exception as e:
            logger.error(f"读取 Excel 失败: {e}")
            raise


# 测试代码
if __name__ == "__main__":
    reader = ExcelReader("data/input/products_sample.xlsx")
    products = reader.read()
    
    for p in products[:3]:
        print(p.model_dump_json(indent=2, ensure_ascii=False))
```

#### 任务清单
- [ ] 创建 `src/data_processor/` 目录
- [ ] 实现 `excel_reader.py`
- [ ] 创建测试用 Excel 文件（至少3个产品）
- [ ] 运行测试，确保能正确读取
- [ ] **验证标准**：能读取 Excel 并转换为 Pydantic 模型，错误行能被识别

---

## 下午任务（3-4小时）

### 3.2 价格计算模块

创建 `src/data_processor/price_calculator.py`：

```python
"""价格计算器"""

from pydantic import BaseModel, Field
from loguru import logger


class PriceResult(BaseModel):
    """价格计算结果"""
    
    cost_price: float = Field(..., description="成本价")
    multiplier: float = Field(default=7.5, description="倍率 (2.5×3)")
    suggested_price: float = Field(..., description="建议售价")
    supply_price: float = Field(..., description="供货价")
    
    @classmethod
    def calculate(cls, cost_price: float, multiplier: float = 7.5) -> "PriceResult":
        """计算价格
        
        Args:
            cost_price: 成本价
            multiplier: 价格倍率，默认 7.5 (即 2.5×3)
        
        Returns:
            价格计算结果
            
        Examples:
            >>> result = PriceResult.calculate(100)
            >>> result.suggested_price
            750.0
        """
        suggested_price = round(cost_price * multiplier, 2)
        supply_price = round(cost_price * 10, 2)  # 供货价 = 成本×10
        
        return cls(
            cost_price=cost_price,
            multiplier=multiplier,
            suggested_price=suggested_price,
            supply_price=supply_price
        )


class PriceCalculator:
    """价格计算器"""
    
    def __init__(self, multiplier: float = 7.5):
        """初始化计算器
        
        Args:
            multiplier: 默认价格倍率
        """
        self.multiplier = multiplier
        logger.info(f"价格计算器初始化，倍率: {multiplier}")
    
    def calculate_batch(self, cost_prices: list[float]) -> list[PriceResult]:
        """批量计算价格
        
        Args:
            cost_prices: 成本价列表
        
        Returns:
            价格结果列表
        """
        results = []
        for cost in cost_prices:
            result = PriceResult.calculate(cost, self.multiplier)
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
        print(f"成本: ¥{r.cost_price} → 建议售价: ¥{r.suggested_price}")
```

#### 任务清单
- [ ] 实现 `price_calculator.py`
- [ ] 编写单元测试（至少3个测试用例）
- [ ] 测试边界情况（如：成本价=0.01，成本价=999999）
- [ ] **验证标准**：价格计算正确，精度保留2位小数

### 3.3 AI 标题生成模块

创建 `src/data_processor/title_generator.py`：

```python
"""AI 标题生成器"""

import re
from typing import Optional
from loguru import logger


class TitleGenerator:
    """AI 标题生成器
    
    优先级：
    1. 使用 Temu 自带 AI 功能（通过影刀触发）
    2. 调用外部 API（如 OpenAI, 通义千问等）
    3. 基于规则生成（保底方案）
    """
    
    def __init__(self, mode: str = "temu"):
        """初始化生成器
        
        Args:
            mode: 生成模式 (temu|api|rule)
        """
        self.mode = mode
        logger.info(f"标题生成器初始化，模式: {mode}")
    
    def generate_by_rule(self, product_name: str, keyword: str) -> str:
        """基于规则生成标题（保底方案）
        
        规则：
        - 提取核心词汇
        - 添加修饰词（新款、热卖、优质等）
        - 控制长度 50-80 字符
        
        Args:
            product_name: 商品名称
            keyword: 关键词
        
        Returns:
            生成的标题
        """
        # 简单规则：关键词 + 产品名 + 修饰语
        modifiers = ["新款", "热卖", "优质", "精选"]
        
        # 清理产品名
        clean_name = re.sub(r'[^\w\s-]', '', product_name).strip()
        
        # 组合标题
        title = f"{keyword} {clean_name} 【{modifiers[0]}】"
        
        # 截断到合理长度
        if len(title) > 80:
            title = title[:77] + "..."
        
        logger.debug(f"规则生成标题: {title}")
        return title
    
    def generate_by_api(self, product_name: str, keyword: str) -> str:
        """调用 API 生成标题
        
        Args:
            product_name: 商品名称
            keyword: 关键词
        
        Returns:
            生成的标题
            
        Note:
            MVP 阶段可以先返回 None，后续再实现
        """
        logger.warning("API 模式暂未实现，使用规则生成")
        return self.generate_by_rule(product_name, keyword)
    
    def generate(
        self, 
        product_name: str, 
        keyword: str,
        fallback: bool = True
    ) -> str:
        """生成标题（主入口）
        
        Args:
            product_name: 商品名称
            keyword: 关键词
            fallback: 失败时是否降级到规则生成
        
        Returns:
            生成的标题
        """
        try:
            if self.mode == "temu":
                # Temu 模式：在影刀中触发，这里只是标记
                logger.info("将使用 Temu 自带 AI 生成标题（影刀执行）")
                return f"[TEMU_AI:{keyword}]"  # 占位符
            
            elif self.mode == "api":
                return self.generate_by_api(product_name, keyword)
            
            else:  # rule
                return self.generate_by_rule(product_name, keyword)
        
        except Exception as e:
            logger.error(f"标题生成失败: {e}")
            if fallback:
                logger.info("降级到规则生成")
                return self.generate_by_rule(product_name, keyword)
            raise


# 测试代码
if __name__ == "__main__":
    generator = TitleGenerator(mode="rule")
    
    test_cases = [
        ("智能手表 运动防水", "智能手表"),
        ("无线蓝牙耳机 降噪 TWS", "蓝牙耳机"),
        ("咖啡机 全自动 家用", "咖啡机"),
    ]
    
    for name, keyword in test_cases:
        title = generator.generate(name, keyword)
        print(f"原名: {name}")
        print(f"标题: {title}\n")
```

#### 任务清单
- [ ] 实现 `title_generator.py`
- [ ] 测试规则生成模式
- [ ] 研究 Temu AI 标题功能的触发方式（为影刀做准备）
- [ ] （可选）注册一个 AI API 账号（如通义千问）
- [ ] **验证标准**：规则模式能生成合理标题，长度合适

### 3.4 数据处理流程整合

创建主处理流程 `src/data_processor/processor.py`：

```python
"""数据处理流程整合"""

from pathlib import Path
from datetime import datetime
from typing import List
import json
from loguru import logger
from pydantic import BaseModel, Field

from .excel_reader import ExcelReader, ProductInput
from .price_calculator import PriceCalculator, PriceResult
from .title_generator import TitleGenerator


class TaskProduct(BaseModel):
    """任务产品数据"""
    
    id: str = Field(..., description="产品 ID")
    keyword: str = Field(..., description="搜索关键词")
    original_name: str = Field(..., description="原始名称")
    ai_title: str = Field(..., description="AI 标题")
    cost_price: float = Field(..., description="成本价")
    suggested_price: float = Field(..., description="建议售价")
    supply_price: float = Field(..., description="供货价")
    category: str = Field(..., description="类目")
    search_count: int = Field(default=5, description="采集数量")
    status: str = Field(default="pending", description="状态")


class TaskData(BaseModel):
    """任务数据"""
    
    task_id: str = Field(..., description="任务 ID")
    created_at: str = Field(..., description="创建时间")
    products: List[TaskProduct] = Field(default_factory=list)


class DataProcessor:
    """数据处理器"""
    
    def __init__(self):
        self.price_calculator = PriceCalculator()
        self.title_generator = TitleGenerator(mode="temu")
    
    def process_excel(self, excel_path: str | Path, output_path: str | Path) -> TaskData:
        """处理 Excel 生成任务数据
        
        Args:
            excel_path: Excel 文件路径
            output_path: 输出 JSON 路径
        
        Returns:
            任务数据
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
            price_result = PriceResult.calculate(product.cost_price)
            logger.debug(f"  价格: ¥{price_result.cost_price} → ¥{price_result.suggested_price}")
            
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
            products=task_products
        )
        
        # 4. 保存到 JSON
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(
                task_data.model_dump(),
                f,
                ensure_ascii=False,
                indent=2
            )
        
        logger.success(f"\n✓ 任务数据已生成: {output_path}")
        logger.info(f"  任务 ID: {task_data.task_id}")
        logger.info(f"  产品数: {len(task_data.products)}")
        
        return task_data


# 测试代码
if __name__ == "__main__":
    processor = DataProcessor()
    
    task_data = processor.process_excel(
        excel_path="data/input/products_sample.xlsx",
        output_path="data/output/task.json"
    )
    
    print("\n任务预览:")
    print(task_data.model_dump_json(indent=2, ensure_ascii=False))
```

#### 任务清单
- [ ] 实现 `processor.py` 整合所有模块
- [ ] 创建完整的测试流程
- [ ] 运行端到端测试：Excel → JSON
- [ ] 检查生成的 JSON 格式是否符合设计
- [ ] **验证标准**：能从 Excel 完整生成符合格式的任务 JSON

---

## Day 3 交付物

### 必须完成 ✅
1. Excel 读取模块 - 能读取并验证数据
2. 价格计算模块 - 正确计算建议售价和供货价
3. 标题生成模块 - 至少实现规则生成
4. 数据处理流程 - 能从 Excel 生成任务 JSON
5. 单元测试通过

### 测试数据准备 📋
```
data/input/products_sample.xlsx
  - 至少 3 个测试产品
  - 包含各种边界情况（如极低价格、超长名称等）

data/output/task.json
  - 格式正确
  - 所有字段完整
  - 价格计算准确
```

---

## 可能遇到的问题

### Excel 表格格式不统一
- **现象**：列名不一样、顺序不同
- **解决**：在 `ExcelReader` 中增加列名映射和容错

### 价格计算精度问题
- **现象**：出现 149.999999
- **解决**：使用 `round(price, 2)` 保留2位小数

### 中文编码问题
- **现象**：JSON 中中文变成 \uXXXX
- **解决**：`json.dump` 时设置 `ensure_ascii=False`

---

## 下一步
完成 Day 3 后，继续 [Day 4：影刀登录流程](day4-yingdao-login.md)

