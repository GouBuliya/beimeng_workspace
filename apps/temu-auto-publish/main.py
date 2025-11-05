"""
@PURPOSE: Temu 发布工作流可执行入口
@OUTLINE:
  - 导入 CompletePublishWorkflow
  - 实例化并执行完整流程
@GOTCHAS:
  - 运行前需在 .env 配置妙手账号和AI密钥
"""

from src.workflows.complete_publish_workflow import CompletePublishWorkflow

workflow = CompletePublishWorkflow()
workflow.execute()
