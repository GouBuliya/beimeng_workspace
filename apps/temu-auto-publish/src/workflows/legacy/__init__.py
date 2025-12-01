
"""
@PURPOSE: 归档历史版本的工作流实现, 供兼容性参考
@OUTLINE:
  - 模块化导出 legacy_complete_workflow_v1
  - 模块化导出 legacy_complete_workflow_v2
@GOTCHAS:
  - 仅用于历史兼容, 新的生产代码请使用最新工作流
@RELATED: complete_publish_workflow_v1.py, complete_publish_workflow_v2.py
"""

from .complete_publish_workflow_v1 import CompletePublishWorkflow as CompletePublishWorkflowV1
from .complete_publish_workflow_v2 import CompletePublishWorkflow as CompletePublishWorkflowV2

__all__ = [
    "CompletePublishWorkflowV1",
    "CompletePublishWorkflowV2",
]
