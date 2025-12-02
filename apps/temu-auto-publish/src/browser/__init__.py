"""
@PURPOSE: 浏览器自动化模块,封装Playwright操作和页面控制器(基于SOP v2.0)
@OUTLINE:
  - BrowserManager: 浏览器管理器
  - CookieManager: Cookie管理器
  - LoginController: 登录控制器
  - CollectionController: 商品采集控制器(SOP步骤1-3)
  - MiaoshouController: 妙手采集箱控制器(SOP步骤4-6)
  - FirstEditController: 首次编辑控制器(SOP步骤4)
  - BatchEditController: 批量编辑控制器(SOP步骤7)
  - PublishController: 发布控制器(SOP步骤8-11)
@DEPENDENCIES:
  - 外部: playwright
@RELATED: ../data_processor/, ../../config/
"""

from .batch_edit_controller import BatchEditController
from .browser_manager import BrowserManager
from .collection_controller import CollectionController
from .cookie_manager import CookieManager
from .first_edit_controller import FirstEditController
from .image_manager import ImageManager
from .login_controller import LoginController
from .miaoshou_controller import MiaoshouController
from .publish_controller import PublishController

__all__ = [
    "BatchEditController",
    "BrowserManager",
    "CollectionController",
    "CookieManager",
    "FirstEditController",
    "ImageManager",
    "LoginController",
    "MiaoshouController",
    "PublishController",
]
