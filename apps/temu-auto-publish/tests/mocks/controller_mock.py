"""
@PURPOSE: Controller 类 Mock 模块
@OUTLINE:
  - MockLoginController: 模拟登录控制器
  - MockMiaoshouController: 模拟妙手控制器
  - MockBatchEditController: 模拟批量编辑控制器
  - MockPublishController: 模拟发布控制器
  - MockCollectionController: 模拟采集控制器
@DEPENDENCIES:
  - 外部: unittest.mock
  - 内部: browser_mock
"""

from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock

from .browser_mock import MockBrowserManager, MockPage


class MockLoginController:
    """模拟 LoginController"""
    
    def __init__(self, login_success: bool = True):
        self.browser_manager = MockBrowserManager()
        self.cookie_manager = MagicMock()
        self.selectors = {}
        self._login_success = login_success
        self._is_logged_in = False
        self.call_count = {"login": 0, "logout": 0}
        
    async def login(
        self,
        username: str,
        password: str,
        force: bool = False
    ) -> bool:
        """模拟登录"""
        self.call_count["login"] += 1
        self._is_logged_in = self._login_success
        return self._login_success
    
    async def login_if_needed(self) -> bool:
        """模拟按需登录"""
        if self._is_logged_in:
            return True
        return await self.login("", "")
    
    async def logout(self) -> bool:
        """模拟登出"""
        self.call_count["logout"] += 1
        self._is_logged_in = False
        return True
    
    async def check_login_status(self) -> bool:
        """检查登录状态"""
        return self._is_logged_in
    
    def _load_selectors(self) -> Dict:
        """加载选择器"""
        return {}


class MockMiaoshouController:
    """模拟 MiaoshouController"""
    
    def __init__(self, success: bool = True):
        self._success = success
        self.selectors = {}
        self.call_history: List[Dict] = []
        
    async def navigate_to_collection_box(self, page: MockPage) -> bool:
        """模拟导航到采集箱"""
        self.call_history.append({"method": "navigate_to_collection_box"})
        return self._success
    
    async def switch_tab(self, page: MockPage, tab_name: str) -> bool:
        """模拟切换标签"""
        self.call_history.append({"method": "switch_tab", "tab_name": tab_name})
        return self._success
    
    async def claim_product(self, page: MockPage, product_index: int) -> bool:
        """模拟认领产品"""
        self.call_history.append({
            "method": "claim_product",
            "product_index": product_index
        })
        return self._success
    
    async def select_products(
        self,
        page: MockPage,
        count: int = 5
    ) -> List[Dict]:
        """模拟选择产品"""
        self.call_history.append({
            "method": "select_products",
            "count": count
        })
        return [{"id": i, "name": f"Product {i}"} for i in range(count)]


class MockBatchEditController:
    """模拟 BatchEditController"""
    
    def __init__(self, success: bool = True):
        self._success = success
        self.selectors = {}
        self.executed_steps: List[str] = []
        
    async def execute_batch_edit_steps(
        self,
        page: MockPage,
        products_data: List[Dict]
    ) -> Dict[str, Any]:
        """模拟执行批量编辑步骤"""
        self.executed_steps = [f"step_{i:02d}" for i in range(1, 19)]
        return {
            "success": self._success,
            "steps_completed": len(self.executed_steps),
            "errors": [] if self._success else ["Step failed"]
        }
    
    async def step_01_modify_title(self, page: MockPage) -> bool:
        self.executed_steps.append("step_01")
        return self._success
    
    async def step_02_english_title(self, page: MockPage) -> bool:
        self.executed_steps.append("step_02")
        return self._success
    
    async def step_04_main_sku(self, page: MockPage) -> bool:
        self.executed_steps.append("step_04")
        return self._success
    
    async def step_07_customization(self, page: MockPage) -> bool:
        self.executed_steps.append("step_07")
        return self._success
    
    async def step_08_sensitive_attrs(self, page: MockPage) -> bool:
        self.executed_steps.append("step_08")
        return self._success
    
    async def step_15_package_list(self, page: MockPage) -> bool:
        self.executed_steps.append("step_15")
        return self._success


class MockPublishController:
    """模拟 PublishController"""
    
    def __init__(self, success: bool = True):
        self._success = success
        self.published_products: List[Dict] = []
        
    async def select_shop(self, page: MockPage, shop_name: str) -> bool:
        """模拟选择店铺"""
        return self._success
    
    async def set_supply_price(self, page: MockPage, price: float) -> bool:
        """模拟设置供货价"""
        return self._success
    
    async def publish_products(
        self,
        page: MockPage,
        products: List[Dict]
    ) -> Dict[str, Any]:
        """模拟发布产品"""
        self.published_products.extend(products)
        return {
            "success": self._success,
            "total": len(products),
            "success_count": len(products) if self._success else 0,
            "fail_count": 0 if self._success else len(products)
        }


class MockCollectionController:
    """模拟 CollectionController"""
    
    def __init__(self, success: bool = True):
        self._success = success
        self.collected_products: List[Dict] = []
        
    async def search_products(
        self,
        page: MockPage,
        keyword: str,
        count: int = 5
    ) -> List[Dict]:
        """模拟搜索产品"""
        products = [
            {"id": i, "name": f"{keyword} Product {i}", "price": 100 + i * 10}
            for i in range(count)
        ]
        self.collected_products.extend(products)
        return products
    
    async def collect_product(
        self,
        page: MockPage,
        product_data: Dict
    ) -> bool:
        """模拟采集产品"""
        if self._success:
            self.collected_products.append(product_data)
        return self._success


class MockFirstEditController:
    """模拟 FirstEditController"""
    
    def __init__(self, success: bool = True):
        self._success = success
        self.edited_products: List[Dict] = []
        
    async def open_edit_dialog(self, page: MockPage, product_index: int) -> bool:
        """模拟打开编辑弹窗"""
        return self._success
    
    async def fill_title(self, page: MockPage, title: str) -> bool:
        """模拟填写标题"""
        return self._success
    
    async def select_category(self, page: MockPage, category: str) -> bool:
        """模拟选择类目"""
        return self._success
    
    async def fill_logistics(
        self,
        page: MockPage,
        weight: int,
        dimensions: tuple
    ) -> bool:
        """模拟填写物流信息"""
        return self._success
    
    async def complete_first_edit(
        self,
        page: MockPage,
        product_data: Dict
    ) -> Dict[str, Any]:
        """模拟完成首次编辑"""
        self.edited_products.append(product_data)
        return {
            "success": self._success,
            "product": product_data
        }


class MockCookieManager:
    """模拟 CookieManager"""
    
    def __init__(self, valid: bool = True):
        self._valid = valid
        self._cookies: List[Dict] = []
        
    def is_valid(self) -> bool:
        """检查Cookie是否有效"""
        return self._valid
    
    def update(self, cookies: List[Dict]) -> None:
        """更新Cookies"""
        self._cookies = cookies
    
    def get(self) -> List[Dict]:
        """获取Cookies"""
        return self._cookies
    
    def clear(self) -> None:
        """清除Cookies"""
        self._cookies = []
        self._valid = False
    
    def save(self, path: str) -> bool:
        """保存Cookies到文件"""
        return True
    
    def load(self, path: str) -> bool:
        """从文件加载Cookies"""
        return self._valid





