
"""
@PURPOSE: 工作流包, 包含各种自动化工作流
@OUTLINE:
  - five_to_twenty_workflow: 5→20 工作流 (首次编辑+认领)
  - complete_publish_workflow: 最新完整发布工作流 (SOP 全流程)
  - legacy: 历史版本兼容入口
@DEPENDENCIES:
  - 内部: browser, data_processor
  - 外部: playwright
"""

from .complete_publish_workflow import (
    CompletePublishWorkflow,
    EditedProduct,
    StageOutcome,
    WorkflowExecutionResult,
)
from .five_to_twenty_workflow import (
    FiveToTwentyWorkflow,
    execute_five_to_twenty_workflow,
)

__all__ = [
    "CompletePublishWorkflow",
    "EditedProduct",
    "FiveToTwentyWorkflow",
    "StageOutcome",
    "WorkflowExecutionResult",
    "execute_five_to_twenty_workflow",
]
