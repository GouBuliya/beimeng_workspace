"""Common package - 通用组件和工具库

这个包提供项目中多个组件共享的通用功能。
"""

__version__ = "0.1.0"

from packages.common.config import BaseAppConfig
from packages.common.logger import setup_logger

__all__ = [
    "BaseAppConfig",
    "setup_logger",
]

