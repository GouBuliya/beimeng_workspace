"""
@PURPOSE: 配置模块，导出settings实例供其他模块使用
@OUTLINE:
  - settings: 全局配置实例
@DEPENDENCIES:
  - 内部: .settings
"""

from .settings import settings

__all__ = ["settings"]
