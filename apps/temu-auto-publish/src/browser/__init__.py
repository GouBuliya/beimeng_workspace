"""
@PURPOSE: 浏览器自动化模块，使用Playwright进行浏览器自动化操作，支持反检测
@OUTLINE:
  - BrowserManager: 浏览器管理器
  - CookieManager: Cookie管理
  - LoginController: 登录控制
@DEPENDENCIES:
  - 内部: .browser_manager, .cookie_manager, .login_controller
"""

from .browser_manager import BrowserManager
from .cookie_manager import CookieManager
from .login_controller import LoginController

__all__ = [
    "BrowserManager",
    "CookieManager",
    "LoginController",
]

