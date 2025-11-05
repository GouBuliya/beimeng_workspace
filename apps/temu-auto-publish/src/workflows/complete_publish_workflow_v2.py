"""
@PURPOSE: v2 工作流兼容入口，代理到 legacy 版本实现
@OUTLINE:
  - class CompletePublishWorkflow: 引用 legacy v2 实现
@GOTCHAS:
  - 仅为兼容旧引用，新代码请使用 `src.workflows.complete_publish_workflow`
@RELATED: legacy.complete_publish_workflow_v2
"""

from __future__ import annotations

from .legacy.complete_publish_workflow_v2 import CompletePublishWorkflow  # noqa: F401

__all__ = ["CompletePublishWorkflow"]


