"""
@PURPOSE: 工作流包，包含各种自动化工作流
@OUTLINE:
  - five_to_twenty_workflow: 5→20工作流（首次编辑+认领）
  - complete_publish_workflow: 完整发布工作流（SOP步骤4-11）
@DEPENDENCIES:
  - 内部: browser, data_processor
  - 外部: playwright
"""

from .complete_publish_workflow import (
    CompletePublishWorkflow,
    execute_complete_workflow,
)
from .five_to_twenty_workflow import (
    FiveToTwentyWorkflow,
    execute_five_to_twenty_workflow,
)

__all__ = [
    "FiveToTwentyWorkflow",
    "execute_five_to_twenty_workflow",
    "CompletePublishWorkflow",
    "execute_complete_workflow",
]


