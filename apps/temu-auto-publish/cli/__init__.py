"""
@PURPOSE: CLI 入口层包初始化
@OUTLINE:
  - 导出主要 CLI 组件
@DEPENDENCIES:
  - 内部: cli.main
"""

from cli.main import app

__all__ = ["app"]
