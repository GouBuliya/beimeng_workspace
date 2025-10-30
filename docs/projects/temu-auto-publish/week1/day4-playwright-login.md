# Day 4：Playwright 登录和妙手访问（v2.0）

**目标**：完成 Temu 后台登录并访问妙手采集箱

**技术**：Playwright + Cookie 持久化 + 异步编程

**重要更新**：根据 SOP 手册，实际使用「妙手」采集箱工具，而不是直接操作 Temu 原生后台

---

## 前置准备（30分钟）

### 4.0 了解业务流程

#### 登录流程（基于 SOP）
```
1. 登录 Temu 商家后台 (seller.temu.com)
   ↓
2. 点击「一键访问店铺」（进入前端店铺）
   ↓
3. 访问「妙手」采集箱页面
   ↓
4. 开始自动化操作
```

#### 研究任务
- [ ] 手动登录 Temu 商家后台
  - 记录登录 URL：`https://seller.temu.com/login`
  - 观察登录表单元素
  - 用户名输入框选择器
  - 密码输入框选择器
  - 登录按钮选择器
  - 验证码类型（如有）

- [ ] 手动访问妙手采集箱
  - 记录妙手采集箱的 URL
  - 观察采集箱页面结构
  - 记录关键功能入口选择器

- [ ] Cookie 研究
  - 使用浏览器开发者工具查看 Cookies
  - 确认哪些 Cookie 是认证必需的
  - 测试 Cookie 有效期（SOP 提到 24 小时）

**使用 Playwright Codegen**：
```bash
# 启动录制工具
uv run playwright codegen https://seller.temu.com/login

# 手动操作并记录：
# 1. 完成登录
# 2. 点击访问店铺
# 3. 访问妙手采集箱
# 4. 保存生成的选择器
```

---

## 上午任务（3-4小时）

### 4.1 实现 Temu 后台登录 ✅

参考已有的 `src/browser/login_controller.py`，它已经实现了基础登录框架。

#### 核心代码结构

```python
"""
@PURPOSE: 实现Temu后台登录自动化，支持Cookie复用和多种登录场景
@OUTLINE:
  - class LoginController: 登录流程控制器
    - async def login(): 主登录入口（优先使用Cookie）
    - async def _try_cookie_login(): Cookie登录尝试
    - async def _full_login(): 完整登录流程
    - async def _input_credentials(): 输入账号密码
    - async def _handle_captcha(): 处理验证码（人工介入）
    - async def _verify_login_success(): 验证登录成功
@GOTCHAS:
  - Cookie 有效期约 24 小时（SOP）
  - 验证码需要人工介入
  - 登录成功后需验证是否真正进入后台
@DEPENDENCIES:
  - 内部: browser_manager, cookie_manager
  - 外部: playwright, loguru
"""

import asyncio
from pathlib import Path
import json
from playwright.async_api import Page, BrowserContext
from loguru import logger


class LoginController:
    """登录控制器（支持 Cookie 复用）"""
    
    def __init__(self, username: str, password: str, cookie_file: Path):
        """初始化登录控制器
        
        Args:
            username: Temu 卖家账号
            password: Temu 密码
            cookie_file: Cookie 保存路径
        """
        self.username = username
        self.password = password
        self.cookie_file = cookie_file
        self.login_url = "https://seller.temu.com/login"
    
    async def login(self, page: Page, context: BrowserContext) -> bool:
        """主登录入口
        
        优先使用 Cookie 登录，失败则执行完整登录流程
        
        Args:
            page: Playwright 页面对象
            context: 浏览器上下文
            
        Returns:
            登录是否成功
        """
        logger.info("开始登录 Temu 商家后台...")
        
        # 1. 尝试 Cookie 登录
        if await self._try_cookie_login(page, context):
            logger.success("Cookie 登录成功")
            return True
        
        # 2. 执行完整登录
        logger.info("Cookie 无效，执行完整登录")
        return await self._full_login(page, context)
    
    async def _try_cookie_login(
        self,
        page: Page,
        context: BrowserContext
    ) -> bool:
        """尝试使用 Cookie 登录
        
        Args:
            page: 页面对象
            context: 浏览器上下文
            
        Returns:
            Cookie 登录是否成功
        """
        if not self.cookie_file.exists():
            logger.debug("Cookie 文件不存在，跳过 Cookie 登录")
            return False
        
        try:
        # 加载 Cookie
            cookies = json.loads(self.cookie_file.read_text())
        await context.add_cookies(cookies)
            logger.debug(f"加载了 {len(cookies)} 个 Cookie")
        
            # 访问后台首页验证
            await page.goto("https://seller.temu.com", timeout=30000)
            await page.wait_for_load_state("domcontentloaded")
        
        # 检查是否登录成功
        return await self._verify_login_success(page)
            
        except Exception as e:
            logger.warning(f"Cookie 登录失败: {e}")
            return False
    
    async def _full_login(self, page: Page, context: BrowserContext) -> bool:
        """执行完整登录流程
        
        Args:
            page: 页面对象
            context: 浏览器上下文
            
        Returns:
            登录是否成功
        """
        try:
        # 1. 访问登录页
            logger.info(f"访问登录页: {self.login_url}")
            await page.goto(self.login_url, timeout=30000)
            await page.wait_for_load_state("domcontentloaded")
        
        # 2. 输入账号密码
        await self._input_credentials(page)
        
        # 3. 处理验证码（如有）
            await self._handle_captcha(page)
        
            # 4. 点击登录按钮
            await self._click_login_button(page)
        
            # 5. 等待登录完成
            await asyncio.sleep(3)
        
            # 6. 验证登录成功
            if not await self._verify_login_success(page):
                return False
            
            # 7. 保存 Cookie
            await self._save_cookies(context)
            
            logger.success("登录成功")
            return True
        
        except Exception as e:
            logger.error(f"登录失败: {e}")
            await page.screenshot(path=f"data/temp/login_error.png")
            return False
    
    async def _input_credentials(self, page: Page) -> None:
        """输入账号密码
        
        Args:
            page: 页面对象
        """
        logger.info("输入账号密码...")
        
        # 注意：这些选择器需要使用 codegen 获取实际值
        username_selector = 'input[name="username"]'  # 示例，需要实际调整
        password_selector = 'input[name="password"]'  # 示例，需要实际调整
        
        # 输入用户名
        await page.fill(username_selector, self.username)
        await asyncio.sleep(0.5)
        
        # 输入密码
        await page.fill(password_selector, self.password)
        await asyncio.sleep(0.5)
        
        logger.debug("账号密码已输入")
    
    async def _handle_captcha(self, page: Page) -> None:
        """处理验证码（人工介入）
        
        Args:
            page: 页面对象
        """
        # 检查是否有验证码
        captcha_selector = 'div.captcha'  # 示例，需要实际调整
        
        try:
            captcha = await page.query_selector(captcha_selector)
            if captcha:
                logger.warning("检测到验证码，需要人工处理")
                logger.info("请在浏览器窗口中完成验证码...")
                
                # 等待用户完成验证码（最多60秒）
                await page.wait_for_selector(
                    captcha_selector,
                    state="hidden",
                    timeout=60000
                )
                logger.info("验证码已完成")
        except Exception:
            # 没有验证码或已经消失
            pass
    
    async def _click_login_button(self, page: Page) -> None:
        """点击登录按钮
        
        Args:
            page: 页面对象
        """
        logger.info("点击登录按钮...")
        
        login_button_selector = 'button[type="submit"]'  # 示例，需要实际调整
        
        await page.click(login_button_selector)
        logger.debug("已点击登录按钮，等待跳转...")
    
    async def _verify_login_success(self, page: Page) -> bool:
        """验证登录成功
        
        检查页面特征判断是否登录成功
        
        Args:
            page: 页面对象
            
        Returns:
            是否登录成功
        """
        try:
            # 方法1：检查 URL
            current_url = page.url
            if "seller.temu.com" in current_url and "/login" not in current_url:
                logger.debug("URL 检查通过")
                return True
            
            # 方法2：检查特征元素（需要实际调整）
            # 例如：用户名显示、侧边栏等
            # user_element = await page.query_selector('.user-info')
            # if user_element:
            #     logger.debug("特征元素检查通过")
            #     return True
            
            return False
            
        except Exception as e:
            logger.error(f"验证登录失败: {e}")
        return False
    
    async def _save_cookies(self, context: BrowserContext) -> None:
        """保存 Cookie
        
        Args:
            context: 浏览器上下文
        """
        try:
            cookies = await context.cookies()
            self.cookie_file.parent.mkdir(parents=True, exist_ok=True)
            self.cookie_file.write_text(json.dumps(cookies, indent=2))
            logger.info(f"Cookie 已保存: {self.cookie_file}")
        except Exception as e:
            logger.warning(f"保存 Cookie 失败: {e}")
```

#### 测试登录

```bash
cd /Users/candy/beimeng_workspace
PYTHONPATH=/Users/candy/beimeng_workspace/apps/temu-auto-publish:$PYTHONPATH \
uv run python -m apps.temu-auto-publish login
```

---

## 下午任务（3-4小时）

### 4.2 访问妙手采集箱 ⚠️ 新增

根据 **SOP 步骤 1**，登录后需要访问妙手采集箱。

#### 创建妙手控制器基础

**新文件**：`src/browser/miaoshou_controller.py`

```python
"""
@PURPOSE: 妙手采集箱控制器，负责导航到妙手工具并操作
@OUTLINE:
  - class MiaoshouController: 妙手采集箱控制器
    - async def navigate_to_collection_box(): 导航到采集箱
    - async def navigate_to_store_front(): 访问前端店铺
    - async def verify_collection_box(): 验证采集箱页面
@GOTCHAS:
  - 妙手工具可能需要特殊权限或订阅
  - URL 可能会变化，需要定期验证
@DEPENDENCIES:
  - 内部: browser_manager
  - 外部: playwright, loguru
@RELATED: login_controller.py
"""

import asyncio
from playwright.async_api import Page
from loguru import logger


class MiaoshouController:
    """妙手采集箱控制器"""
    
    def __init__(self):
        """初始化妙手控制器"""
        # TODO: 使用 codegen 获取实际 URL
        self.collection_box_url = "待确认"  # 妙手采集箱URL
        self.store_front_button = "待确认"  # 访问店铺按钮选择器
    
    async def navigate_to_store_front(self, page: Page) -> bool:
        """访问前端店铺（SOP 步骤 1）
        
        从 Temu 商家后台点击「一键访问店铺」
        
        Args:
            page: 页面对象
            
        Returns:
            是否成功访问
        """
        logger.info("SOP 步骤1：访问前端店铺")
        
        try:
            # 确保在商家后台首页
            if "/seller" not in page.url:
                await page.goto("https://seller.temu.com", timeout=30000)
                await page.wait_for_load_state("domcontentloaded")
            
            # 点击「一键访问店铺」按钮
            # TODO: 使用 codegen 获取实际选择器
            store_button_selector = self.store_front_button
            
            await page.click(store_button_selector)
            logger.info("已点击访问店铺按钮")
            
            # 等待新页面或弹窗
            await asyncio.sleep(2)
            
            # 验证是否成功
            if await self._verify_store_front(page):
                logger.success("成功访问前端店铺")
        return True
            else:
                logger.error("访问前端店铺失败")
                return False
                
        except Exception as e:
            logger.error(f"访问店铺失败: {e}")
            await page.screenshot(path="data/temp/store_front_error.png")
            return False
        
    async def navigate_to_collection_box(self, page: Page) -> bool:
        """导航到妙手采集箱
        
        Args:
            page: 页面对象
            
        Returns:
            是否成功进入采集箱
        """
        logger.info("导航到妙手采集箱...")
        
        try:
            # 方法1：直接访问 URL（如果知道）
            if self.collection_box_url != "待确认":
                await page.goto(self.collection_box_url, timeout=30000)
                await page.wait_for_load_state("domcontentloaded")
            
            # 方法2：通过导航菜单（需要实际调研）
            # TODO: 使用 codegen 录制导航路径
            
            # 验证是否进入采集箱
            if await self.verify_collection_box(page):
                logger.success("成功进入妙手采集箱")
                return True
            else:
                logger.error("未能进入采集箱页面")
                return False
                
        except Exception as e:
            logger.error(f"导航到采集箱失败: {e}")
            await page.screenshot(path="data/temp/collection_box_error.png")
            return False
    
    async def verify_collection_box(self, page: Page) -> bool:
        """验证是否在采集箱页面
        
        Args:
            page: 页面对象
            
        Returns:
            是否在采集箱页面
        """
        try:
            # 方法1：检查 URL
            if "collection" in page.url or "采集箱" in page.url:
            return True
            
            # 方法2：检查特征元素
            # TODO: 使用 codegen 获取特征选择器
            # collection_box_title = await page.query_selector('h1:has-text("采集箱")')
            # if collection_box_title:
            #     return True
            
            return False
            
        except Exception as e:
            logger.error(f"验证采集箱页面失败: {e}")
            return False
    
    async def _verify_store_front(self, page: Page) -> bool:
        """验证是否成功进入前端店铺
        
        Args:
            page: 页面对象
            
        Returns:
            是否在店铺页面
        """
        try:
            # 检查 URL 或页面特征
            current_url = page.url
            # TODO: 确认店铺页面的 URL 模式
            if "temu.com" in current_url:
                return True
            return False
        except Exception:
    return False
```

#### 测试妙手访问

创建测试脚本 `examples/test_miaoshou_access.py`：

```python
"""测试妙手采集箱访问"""

import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
from playwright_stealth.stealth import Stealth

from config.settings import settings
from src.browser.browser_manager import BrowserManager
from src.browser.login_controller import LoginController
from src.browser.miaoshou_controller import MiaoshouController


async def test_miaoshou_access():
    """测试完整流程：登录 → 访问店铺 → 进入妙手"""
    
    async with async_playwright() as p:
        # 1. 启动浏览器
        browser_mgr = BrowserManager()
        browser, context, page = await browser_mgr.launch()
        
        print("=" * 60)
        print("测试妙手采集箱访问")
        print("=" * 60)
        
        try:
            # 2. 登录
            login_ctrl = LoginController(
            username=settings.temu_username,
                password=settings.temu_password,
                cookie_file=Path("data/temp/temu_cookies.json")
            )
            
            if not await login_ctrl.login(page, context):
                print("❌ 登录失败")
                return
            
            print("✓ 登录成功")
            
            # 3. 访问妙手
            miaoshou_ctrl = MiaoshouController()
            
            # 3.1 访问前端店铺
            if not await miaoshou_ctrl.navigate_to_store_front(page):
                print("❌ 访问店铺失败")
                return
            
            print("✓ 访问店铺成功")
            
            # 3.2 进入采集箱
            if not await miaoshou_ctrl.navigate_to_collection_box(page):
                print("❌ 进入采集箱失败")
                return
            
            print("✓ 进入采集箱成功")
            
            print("\n" + "=" * 60)
            print("✓✓✓ 所有测试通过！")
            print("=" * 60)
            
            # 等待观察
            input("\n按回车键关闭浏览器...")
            
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(test_miaoshou_access())
```

运行测试：
```bash
cd /Users/candy/beimeng_workspace
PYTHONPATH=/Users/candy/beimeng_workspace/apps/temu-auto-publish:$PYTHONPATH \
uv run python apps/temu-auto-publish/examples/test_miaoshou_access.py
```

---

## 选择器获取指南

### 使用 Playwright Codegen

```bash
# 1. 启动 codegen
uv run playwright codegen https://seller.temu.com/login

# 2. 手动操作并记录选择器：
#    - 登录页面元素
#    - 访问店铺按钮
#    - 妙手采集箱入口
#    - 采集箱主要功能区

# 3. 保存生成的代码到文件
# config/miaoshou_selectors.json
```

### 选择器配置文件

创建 `config/miaoshou_selectors.json`：

```json
{
  "login": {
    "username_input": "待使用codegen获取",
    "password_input": "待使用codegen获取",
    "login_button": "待使用codegen获取",
    "captcha_container": "待使用codegen获取"
  },
  "seller_backend": {
    "store_front_button": "待使用codegen获取",
    "user_info": "待使用codegen获取"
  },
  "miaoshou": {
    "collection_box_url": "待确认实际URL",
    "collection_box_title": "待使用codegen获取",
    "search_input": "待使用codegen获取",
    "collect_button": "待使用codegen获取"
  }
}
```

---

## 验收标准 ✅

### 必须完成
- [ ] 登录 Temu 商家后台成功
- [ ] Cookie 保存和复用正常
- [ ] 验证码处理流程清晰（人工介入）
- [ ] 成功访问前端店铺
- [ ] 成功进入妙手采集箱
- [ ] 所有选择器已用 codegen 获取

### 测试 Checklist
```bash
# 1. 测试登录（无 Cookie）
rm data/temp/temu_cookies.json
uv run python -m apps.temu-auto-publish login

# 2. 测试登录（有 Cookie）
uv run python -m apps.temu-auto-publish login

# 3. 测试妙手访问
uv run python apps/temu-auto-publish/examples/test_miaoshou_access.py
```

---

## 注意事项

1. **选择器维护**
   - 使用 codegen 获取真实选择器
   - 定期验证选择器有效性
   - 使用多重定位策略（text + role + xpath）

2. **验证码处理**
   - MVP 阶段：人工完成
   - Phase 2：接入验证码识别服务

3. **Cookie 管理**
   - 有效期约 24 小时（SOP）
   - 自动保存和加载
   - 过期后自动重新登录

4. **妙手工具访问**
   - 可能需要特殊权限
   - URL 可能会变化
   - 需要实际测试确认

---

## 下一步

完成 Day 4 后，继续 [Day 5-7：搜索采集和编辑流程](day5-7-search-and-edit.md)
