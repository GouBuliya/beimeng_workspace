"""
@PURPOSE: Temu 发布工作流可执行入口
@OUTLINE:
  - 导入 CompletePublishWorkflow
  - 实例化并执行完整流程
@GOTCHAS:
  - 运行前需在 .env 配置妙手账号和AI密钥
"""

from src.workflows.complete_publish_workflow import CompletePublishWorkflow

# 启用 Codegen 录制的首次编辑弹窗填写模块
workflow = CompletePublishWorkflow(use_codegen_first_edit=True)
workflow.execute()
