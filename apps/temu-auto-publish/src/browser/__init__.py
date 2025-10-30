"""
@PURPOSE: 浏览器自动化模块，封装Playwright操作和页面控制器（基于SOP v2.0）
@OUTLINE:
  - BrowserManager: 浏览器管理器
  - CookieManager: Cookie管理器
  - LoginController: 登录控制器
  - MiaoshouController: 妙手采集箱控制器（新）
  - FirstEditController: 首次编辑控制器（新）
  - BatchEditController: 批量编辑控制器（新）
  - SearchController: 搜索控制器（旧版，保留）
  - EditController: 编辑控制器（旧版，保留）
@GOTCHAS:
  - 新版流程使用 Miaoshou + FirstEdit + BatchEdit 控制器
  - 旧版 Search + Edit 控制器保留用于参考
@DEPENDENCIES:
  - 外部: playwright
@RELATED: ../data_processor/, ../../config/
"""

from .batch_edit_controller import BatchEditController
from .browser_manager import BrowserManager
from .cookie_manager import CookieManager
from .edit_controller import EditController
from .first_edit_controller import FirstEditController
from .login_controller import LoginController
from .miaoshou_controller import MiaoshouController
from .search_controller import SearchController

__all__ = [
    "BrowserManager",
    "CookieManager",
    "LoginController",
    "MiaoshouController",
    "FirstEditController",
    "BatchEditController",
    "SearchController",  # 旧版，保留
    "EditController",  # 旧版，保留
]
