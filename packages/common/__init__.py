"""
@PURPOSE: 通用组件和工具库，提供项目中多个组件共享的通用功能
@OUTLINE:
  - BaseAppConfig: 应用配置基类
  - setup_logger: 日志配置函数
@DEPENDENCIES:
  - 内部: .config, .logger
"""

__version__ = "0.1.0"

from packages.common.config import BaseAppConfig
from packages.common.logger import setup_logger

__all__ = [
    "BaseAppConfig",
    "setup_logger",
]
