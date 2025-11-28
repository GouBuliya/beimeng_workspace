```
@PURPOSE: 梳理数据处理模块的职责、输入输出格式与复用方式
@OUTLINE:
  - 模块概览与目录结构
  - 核心组件说明
  - 数据流与校验规则
  - 与工作流/控制器的联动
@DEPENDENCIES:
  - 内部: src.config.settings, src.models.*
  - 外部: pandas, pydantic, loguru
```

# Data Processor 模块说明

数据处理模块负责读取选品表、生成业务所需的中间数据，并提供 AI 标题、价格计算、随机规格生成等服务。模块设计目标：

- **可靠性**：统一的字段校验与错误日志，保障批量流程稳定
- **可复用性**：为工作流、控制器、测试提供一致的接口
- **可扩展性**：易于新增数据源、转换规则与缓存策略

---

## 目录结构

```
src/data_processor/
├── README.md                    # 当前文档
├── __init__.py
├── selection_table_reader.py    # 选品表读取与校验
├── product_data_reader.py       # 产品数据聚合与随机信息生成
├── price_calculator.py          # 建议售价/供货价计算
├── ai_title_generator.py        # AI 标题生成 + 回退机制
├── random_generator.py          # 物流信息随机化
├── data_converter.py            # 辅助转换函数（保留）
├── title_generator.py           # 历史标题生成器（待兼容）
└── processor.py                 # 旧版统一入口（计划淘汰）
```

---

## 核心组件

| 组件 | 主要职责 | 备注 |
| --- | --- | --- |
| `SelectionTableReader` | 支持 CSV/Excel 解析、列名标准化、Pydantic 验证 | 输出 `ProductSelectionRow` 列表 |
| `ProductDataReader` | 基于选品表生成工作流输入、随机尺寸/重量 | 与 `random_generator` 协同 |
| `PriceCalculator` | 根据 SOP 定义计算建议售价、供货价、真实供货价 | 支持倍率配置，返回 `PriceResult` |
| `AITitleGenerator` | 调用 OpenAI/Anthropic 或回退使用原标题 | 下一阶段将加入缓存与批量接口 |
| `RandomDataGenerator` | 生成物流尺寸/重量、包装参数 | 测试用例覆盖 |
| `SelectionTableQueue` | 把选品表当作队列，提供 pop/rollback/archive | 供 `run_until_empty.py` 等守护脚本使用 |

---

## 数据流概览

1. **选品表读取**  
   `SelectionTableReader.read_excel` → 校验必填列 → 生成 `ProductSelectionRow`  
   - 自动拼接尺寸图/视频 URL（基于 OSS 前缀）  
   - 支持 CSV (`utf-8-sig`) 与 Excel (`openpyxl`)

2. **任务数据准备**  
   `ProductDataReader.build_workflow_payload` → 结合价格、随机参数生成任务字典  
   - 标记缺失字段、记录警告日志  
   - 提供 `generate_random_weight/dimensions` 辅助

3. **价格与标题**  
   `PriceCalculator.calculate_batch` → 返回倍率计算结果  
   `AITitleGenerator.generate_titles` → 在 AI 不可用时自动回退原标题

---

## 与工作流/控制器的联动

- `CompletePublishWorkflow`：  
  - 使用 `SelectionTableReader` 解析 CSV/Excel  
  - 通过 `PriceCalculator`、`AITitleGenerator` 构建首编 payload  
  - 将 `EditedProduct` 转换为后续批量编辑/发布输入
- `FirstEditController`：消费数据处理模块生成的重量、尺寸、价格
- `BatchEditController`：复用 `PriceCalculator` 生成的供货价（待接入）

---

## 使用示例

```python
from pathlib import Path
from src.data_processor.selection_table_reader import SelectionTableReader
from src.data_processor.price_calculator import PriceCalculator
from src.data_processor.selection_table_queue import SelectionTableQueue

reader = SelectionTableReader()
rows = reader.read_excel(Path("data/input/10月新品可上架.csv"))

calculator = PriceCalculator(suggested_multiplier=10.0, supply_multiplier=7.5)
price = calculator.calculate_one(cost_price=12.5)
print(rows[0].product_name, price.suggested_price, price.supply_price)

queue = SelectionTableQueue("data/input/selection.xlsx")
batch = queue.pop_next_batch(batch_size=20)
# ...执行发布逻辑...
queue.archive_batch(batch.rows, suffix="success")
```

AI 标题生成回退示例：

```python
from src.data_processor.ai_title_generator import AITitleGenerator

generator = AITitleGenerator(provider="openai", max_retries=0)
titles = await generator.generate_titles(["原标题1", "原标题2"], "A0049型号")
# AI 不可用时返回原标题 + 型号后缀
```

---

## 后续优化路线

- **缓存**：阶段6将引入选择器/价格/标题缓存，减少重复计算
- **批量接口**：`AITitleGenerator.generate_titles_batch`、`PriceCalculator.calculate_bulk`
- **数据清洗**：在 `SelectionTableReader` 中补充尺寸图/型号格式纠错

---

## 相关文档

- `../browser/README.md`：查看控制器如何消费数据
- `../workflows/README.md`：了解数据在流程中的流转
- 项目根目录 `README.md`：安装、环境配置、命令行入口

