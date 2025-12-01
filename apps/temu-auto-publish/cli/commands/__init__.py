"""
@PURPOSE: CLI 命令模块包初始化
@OUTLINE:
  - 导出所有命令模块
@DEPENDENCIES:
  - 内部: cli.commands.*
"""

from cli.commands.config import config_app
from cli.commands.debug import debug_app
from cli.commands.monitor import monitor_app
from cli.commands.workflow import workflow_app

__all__ = [
    "config_app",
    "debug_app",
    "monitor_app",
    "workflow_app",
]
