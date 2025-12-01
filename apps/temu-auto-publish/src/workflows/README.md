```
@PURPOSE: 介绍工作流模块的职责、阶段划分与扩展方式
@OUTLINE:
  - 模块概览与目录结构
  - 核心工作流说明
  - 阶段输出数据结构
  - 集成与调试建议
@DEPENDENCIES:
  - 内部: src.browser.*, src.data_processor.*, src.config.settings
  - 外部: playwright, loguru
```

# Workflows 模块说明

工作流模块负责 orchestrate Temu 自动化的端到端业务流程，统一调度浏览器控制器、数据处理组件与重试策略。模块目标：

1. 以阶段化结构管理复杂 SOP（首次编辑 → 认领 → 批量编辑 → 发布）
2. 提供可重用的数据结构与结果汇总，便于测试、监控与上层系统复用
3. 保留遗留版本用于兼容旧脚本，同时鼓励使用最新实现

---

## 目录结构

```
src/workflows/
├── README.md                     # 当前文档
├── __init__.py                   # 模块导出
├── complete_publish_workflow.py  # 最新完整工作流（首推）
├── five_to_twenty_workflow.py    # 5→20 首次编辑与认领工作流
├── collection_workflow.py        # 采集流程（历史兼容）
├── collection_to_edit_workflow.py# 采集到编辑的快捷流程
├── full_publish_workflow.py      # 旧版整合入口（待淘汰）
└── legacy/                       # v1/v2 遗留实现
```

---

## 核心工作流

| 工作流 | 结构 | 适用场景 | 说明 |
| --- | --- | --- | --- |
| `CompletePublishWorkflow` | dataclass + 阶段方法 | 完整 SOP，生产环境主入口 | 支持 Codegen/原生批量编辑切换、AI 标题生成等配置 |
| `FiveToTwentyWorkflow` | 协程函数 + 辅助类 | 只需首次编辑 + 认领 | 常用于快速验证采集表或训练新账号 |
| `collection_*_workflow` | 旧流程 | 历史脚本保留 | 推荐迁移到新工作流 |
| `legacy/complete_publish_workflow_v1/v2` | 类 + 函数 | 老接口兼容 | `execute_complete_workflow` 仍可调用到 v1 |

> 导出接口：`__all__` 仅包含最新 `CompletePublishWorkflow` 与 `FiveToTwentyWorkflow`，其余入口需显式从 `legacy` 导入。

---

## 阶段数据结构

`complete_publish_workflow.py` 定义了三个关键 dataclass：

- `StageOutcome`：描述阶段名称、成功状态、消息与详情
- `EditedProduct`：首次编辑产物（标题、尺寸、价格等）
- `WorkflowExecutionResult`：聚合工作流 ID、整体成功与各阶段结果

各阶段方法（`_stage_first_edit`, `_stage_claim_products`, `_stage_batch_edit`, `_stage_publish`）均返回 `StageOutcome`，便于外部监控与重试。

---

## 与其他模块的关系

- **browser**：借助控制器完成页面操作（登录、批量编辑等）
- **data_processor**：读取/校验选品表、计算价格、生成标题
- **config.settings**：统一读取业务参数、账号、调试选项

完整流程默认按照以下顺序执行：

1. 登录并准备工作环境 (`LoginController`, `BrowserManager`)
2. 解析选品表并构建工作队列 (`SelectionTableReader`, `ProductDataReader`)
3. 首次编辑弹窗录入 (`FirstEditController` + Codegen)
4. 认领 + 批量编辑 + 发布 (`MiaoshouController`, `BatchEditController`, `PublishController`)

---

## 使用示例

```python
from pathlib import Path
from src.workflows import CompletePublishWorkflow

workflow = CompletePublishWorkflow(
    headless=False,
    selection_table=Path("data/input/10月新品可上架.csv"),
    use_ai_titles=True,
    use_codegen_batch_edit=True,
)
result = workflow.execute()
print(result.total_success, result.errors)
```

如需与遗留脚本兼容，可继续调用：

```python
from src.workflows.complete_publish_workflow import execute_complete_workflow
# Page 对象由上层登录流程提供
await execute_complete_workflow(page, products_data, enable_publish=False)
```

---

## 调试与验证

- 调试单个阶段：直接调用 `_stage_*` 私有方法（需要模拟阶段输入）
- 运行样例脚本：`python scripts/demo_quick_workflow.py`（计划在阶段2补充）
- 记录调试数据：开启 `settings.debug` 中的 HTML/截图选项
- 监控指标：已集成 `core.performance_tracker` 性能追踪系统

---

## 相关文档

- `../browser/README.md`：了解控制器与 Codegen 的使用方式
- `../data_processor/README.md`：输入数据结构、价格与标题生成逻辑
- 根目录 `README.md`：环境搭建、命令行入口

