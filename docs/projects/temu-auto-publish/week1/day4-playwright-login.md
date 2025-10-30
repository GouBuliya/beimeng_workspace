# Day 4：Playwright 登录流程

**目标**：完成 Temu 后台自动登录，包括 Cookie 保存和验证码处理

**技术**：Playwright + Cookie 持久化 + 异步编程

---

## 前置准备（30分钟）

### 4.0 了解 Temu 后台登录机制

#### 研究任务
- [ ] 手动登录 Temu 商家后台（记录完整步骤）
- [ ] 观察登录表单元素
  - 用户名输入框（CSS 选择器或 XPath）
  - 密码输入框
  - 登录按钮
  - 验证码类型（图片/滑块/无）
- [ ] 检查登录后的特征
  - URL 变化
  - 页面特征元素（如用户名显示）
  - Cookie 信息（开发者工具 → Application → Cookies）
- [ ] 测试 Cookie 有效期
  - 记录哪些 Cookie 是认证必需的
  - 测试 Cookie 能保持多久

**使用 Playwright Codegen**：
```bash
# 启动录制工具，自动生成代码
uv run playwright codegen https://seller.temu.com/login

# 手动操作登录流程，Playwright 会生成对应代码
# 保存生成的选择器和操作步骤
```

---

## 上午任务（3-4小时）

### 4.1 实现基础登录流程

参考已有的 `src/browser/login_controller.py`，它已经实现了：
- `LoginController` 类：负责登录流程控制
- Cookie 管理（保存/加载）
- 登录状态验证
- 异常处理

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
"""

import asyncio
from playwright.async_api import Page, BrowserContext
from loguru import logger


class LoginController:
    """登录控制器"""
    
    async def login(self, page: Page, context: BrowserContext) -> bool:
        """主登录入口
        
        优先使用 Cookie，失败则执行完整登录
        """
        # 1. 尝试 Cookie 登录
        if await self._try_cookie_login(page, context):
            return True
        
        # 2. 执行完整登录
        return await self._full_login(page, context)
    
    async def _try_cookie_login(self, page: Page, context: BrowserContext) -> bool:
        """尝试使用 Cookie 登录"""
        cookie_file = Path("data/temp/temu_cookies.json")
        
        if not cookie_file.exists():
            logger.info("Cookie 文件不存在，跳过")
            return False
        
        # 加载 Cookie
        cookies = json.loads(cookie_file.read_text())
        await context.add_cookies(cookies)
        
        # 访问首页验证
        await page.goto("https://seller.temu.com")
        
        # 检查是否登录成功
        return await self._verify_login_success(page)
    
    async def _full_login(self, page: Page, context: BrowserContext) -> bool:
        """完整登录流程"""
        # 1. 访问登录页
        await page.goto("https://seller.temu.com/login")
        
        # 2. 输入账号密码
        await self._input_credentials(page)
        
        # 3. 处理验证码（如有）
        if await self._has_captcha(page):
            await self._handle_captcha(page)
        
        # 4. 点击登录
        await page.click("button[type='submit']")  # TODO: 使用实际选择器
        
        # 5. 等待跳转
        await page.wait_for_url("**/dashboard**", timeout=30000)
        
        # 6. 验证成功
        if await self._verify_login_success(page):
            # 保存 Cookie
            await self._save_cookies(context)
            return True
        
        return False
```

#### 任务清单
- [ ] 使用 `playwright codegen` 获取准确的选择器
- [ ] 完善 `login_controller.py` 中的 TODO 部分
- [ ] 测试登录流程（至少 3 次成功）
- [ ] **验证标准**：能稳定完成登录，正确判断登录状态

---

## 下午任务（3-4小时）

### 4.2 Cookie 管理优化

参考已有的 `src/browser/cookie_manager.py`，它已经实现：
- Cookie 保存/加载
- Cookie 有效期检查
- Cookie 清理

#### Cookie 持久化策略

```python
"""
@PURPOSE: 管理Playwright浏览器Cookie，实现登录状态持久化
@OUTLINE:
  - class CookieManager: Cookie管理器
    - async def save_cookies(): 保存Cookie到JSON文件
    - async def load_cookies(): 从JSON文件加载Cookie
    - def is_cookie_valid(): 检查Cookie是否有效（时间戳）
    - def clear_cookies(): 清除Cookie文件
"""

import json
from pathlib import Path
from datetime import datetime, timedelta
from playwright.async_api import BrowserContext


class CookieManager:
    """Cookie 管理器"""
    
    def __init__(self, cookie_file: str = "data/temp/temu_cookies.json"):
        self.cookie_file = Path(cookie_file)
        self.max_age = timedelta(hours=24)  # Cookie 最大有效期
    
    async def save_cookies(self, context: BrowserContext) -> None:
        """保存 Cookie"""
        cookies = await context.cookies()
        
        data = {
            "cookies": cookies,
            "timestamp": datetime.now().isoformat(),
            "user_agent": await context.browser.version()
        }
        
        self.cookie_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2)
        )
        logger.info(f"Cookie 已保存: {len(cookies)} 个")
    
    async def load_cookies(self, context: BrowserContext) -> bool:
        """加载 Cookie"""
        if not self.is_cookie_valid():
            return False
        
        data = json.loads(self.cookie_file.read_text())
        await context.add_cookies(data["cookies"])
        
        logger.info(f"Cookie 已加载: {len(data['cookies'])} 个")
        return True
    
    def is_cookie_valid(self) -> bool:
        """检查 Cookie 是否有效"""
        if not self.cookie_file.exists():
            return False
        
        data = json.loads(self.cookie_file.read_text())
        saved_time = datetime.fromisoformat(data["timestamp"])
        age = datetime.now() - saved_time
        
        return age < self.max_age
```

#### 任务清单
- [ ] 测试 Cookie 保存和加载
- [ ] 测试 Cookie 过期检查（修改时间戳测试）
- [ ] 测试 Cookie 清理功能
- [ ] **验证标准**：使用保存的 Cookie 能跳过登录直接进入后台

### 4.3 验证码处理方案

#### MVP 方案：手动介入

```python
async def _handle_captcha(self, page: Page) -> None:
    """处理验证码（人工介入）"""
    logger.warning("检测到验证码，需要人工处理")
    
    # 播放提示音（可选）
    print("\a")  # 系统提示音
    
    # 截图保存
    screenshot_path = f"data/temp/captcha_{int(time.time())}.png"
    await page.screenshot(path=screenshot_path)
    logger.info(f"验证码截图已保存: {screenshot_path}")
    
    # 等待用户手动完成
    logger.info("=" * 60)
    logger.info("请在浏览器中完成验证码")
    logger.info("完成后，验证码会自动消失，脚本将继续执行")
    logger.info("=" * 60)
    
    # 等待验证码消失（最多 2 分钟）
    try:
        await page.wait_for_selector(
            "div.captcha",  # TODO: 使用实际的验证码容器选择器
            state="hidden",
            timeout=120000
        )
        logger.success("验证码已完成")
    except TimeoutError:
        logger.error("验证码处理超时")
        raise
```

#### 优化方案（可选）

如果验证码频繁出现，可以考虑：

1. **图片验证码识别**
   - 使用 qwen-vl 等视觉模型
   - 或第三方 OCR 服务（如 2captcha）

2. **滑块验证码**
   - 研究滑块轨迹算法
   - 或使用第三方打码平台

3. **预防验证码出现**
   - 使用固定 IP
   - 控制操作频率
   - 模拟真实用户行为（随机延迟）

#### 任务清单
- [ ] 确认验证码类型和出现频率
- [ ] 实现 MVP 手动方案
- [ ] 测试验证码处理流程
- [ ] 记录验证码出现模式

### 4.4 异常处理和日志

#### 异常处理清单

```python
async def _full_login(self, page: Page, context: BrowserContext) -> bool:
    """完整登录流程（带异常处理）"""
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            # 访问登录页
            await page.goto(
                "https://seller.temu.com/login",
                timeout=30000,
                wait_until="domcontentloaded"
            )
            
            # 等待关键元素出现
            await page.wait_for_selector(
                "input[name='username']",  # TODO: 实际选择器
                timeout=10000
            )
            
            # 执行登录...
            
            return True
            
        except TimeoutError as e:
            retry_count += 1
            logger.warning(f"登录超时，重试 {retry_count}/{max_retries}: {e}")
            await asyncio.sleep(2)
            
        except Exception as e:
            logger.error(f"登录失败: {e}")
            await page.screenshot(path=f"data/temp/login_error_{int(time.time())}.png")
            break
    
    return False
```

#### 日志策略

```python
# 在 LoginController 开始处配置日志
logger.add(
    "data/logs/login_{time}.log",
    rotation="1 day",
    retention="7 days",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}"
)

# 关键步骤记录
logger.info("=" * 60)
logger.info("开始登录流程")
logger.debug(f"用户名: {username}")
logger.info("1. 检查 Cookie...")
logger.info("2. 访问登录页...")
logger.success("✓ 登录成功")
```

---

## 整合测试（1小时）

### 4.5 端到端测试

创建 `tests/test_login_controller.py`（已存在，需完善）：

```python
"""登录控制器测试"""

import pytest
import asyncio
from playwright.async_api import async_playwright

from src.browser.browser_manager import BrowserManager
from src.browser.login_controller import LoginController
from config.settings import settings


@pytest.mark.asyncio
async def test_full_login():
    """测试完整登录流程"""
    async with async_playwright() as p:
        # 1. 启动浏览器
        browser_manager = BrowserManager(p)
        page = await browser_manager.start()
        
        # 2. 执行登录
        login_controller = LoginController()
        success = await login_controller.login(
            page,
            page.context,
            username=settings.temu_username,
            password=settings.temu_password
        )
        
        assert success, "登录应该成功"
        
        # 3. 验证 Cookie 已保存
        cookie_file = Path("data/temp/temu_cookies.json")
        assert cookie_file.exists(), "Cookie 文件应该存在"
        
        # 4. 关闭浏览器
        await browser_manager.close()


@pytest.mark.asyncio
async def test_cookie_login():
    """测试 Cookie 登录"""
    # 前提：已有有效的 Cookie 文件
    
    async with async_playwright() as p:
        browser_manager = BrowserManager(p)
        page = await browser_manager.start()
        
        login_controller = LoginController()
        success = await login_controller.login(page, page.context)
        
        assert success, "Cookie 登录应该成功"
        
        await browser_manager.close()
```

运行测试：
```bash
# 运行所有登录测试
uv run pytest tests/test_login_controller.py -v

# 运行特定测试
uv run pytest tests/test_login_controller.py::test_full_login -v
```

#### 测试 Checklist
```
☐ 首次登录成功（无 Cookie）
☐ Cookie 保存成功（文件存在且有效）
☐ 使用 Cookie 登录成功（跳过输入密码）
☐ Cookie 过期后自动重新登录
☐ 密码错误能正确提示
☐ 网络超时能自动重试
☐ 验证码出现时能正确处理
☐ 所有异常都有日志记录
```

---

## Day 4 交付物

### 必须完成 ✅
1. ✅ Playwright 登录流程 - 能稳定登录 Temu 后台
2. ✅ Cookie 管理 - 保存、加载、验证有效性
3. ✅ 异常处理 - 网络超时、元素未找到等
4. ✅ 验证码处理 - MVP 手动方案
5. ✅ 单元测试 - 至少 2 个测试用例通过

### 文件清单 📁
```
src/browser/
  ├── browser_manager.py      # 浏览器管理器（已完成）
  ├── login_controller.py     # 登录控制器（需完善选择器）
  └── cookie_manager.py       # Cookie 管理器（已完成）

tests/
  └── test_login_controller.py  # 登录测试

data/temp/
  ├── temu_cookies.json       # Cookie 持久化文件
  └── captcha_*.png           # 验证码截图（如有）

data/logs/
  └── login_*.log             # 登录日志
```

### 核心文件状态
- ✅ `browser_manager.py` - 已完成，支持启动/关闭/截图
- ⚠️ `login_controller.py` - 框架已完成，需填充选择器
- ✅ `cookie_manager.py` - 已完成
- ⚠️ `test_login_controller.py` - 需完善测试用例

---

## 可能遇到的问题

### 元素定位不稳定
- **现象**：有时能找到元素，有时不能
- **解决**：
  1. 使用 `playwright codegen` 获取稳定选择器
  2. 优先使用 `data-testid` 或 `id` 属性
  3. 增加 `wait_for_selector` 等待时间
  4. 使用多重选择器作为 fallback

### Cookie 加载后仍需登录
- **现象**：加载 Cookie 后访问首页仍跳转到登录页
- **解决**：
  - 检查 Cookie domain 是否正确
  - 确认 Cookie 包含所有必需字段
  - 可能需要设置 User-Agent

### 验证码频繁出现
- **现象**：每次登录都要验证码
- **解决**：
  - 使用固定 IP（避免频繁切换）
  - 延长操作间隔（模拟人类）
  - 使用 playwright-stealth（已集成）
  - 联系平台技术支持加白名单

### 登录后立即被踢出
- **现象**：登录成功但几秒后又跳转到登录页
- **解决**：
  - 检查是否触发了风控
  - 确认浏览器指纹是否正常
  - 尝试使用 persistent context（保留浏览器数据）

---

## 与影刀方案的对比

| 项目 | 影刀方案 | Playwright 方案 |
|------|---------|----------------|
| 登录方式 | 录制 + 回放 | 纯代码 |
| Cookie 管理 | 手动或影刀节点 | 代码化管理 |
| 验证码处理 | 弹窗等待 | 异步等待 |
| 调试 | 黑盒，难调试 | IDE 断点调试 |
| 异常处理 | 有限 | 完全可控 |
| 日志 | 影刀日志 | Loguru 结构化日志 |

**Playwright 的优势**：
- ✅ 完全代码化，可版本控制
- ✅ 异步高效，支持并发
- ✅ 调试友好，IDE 集成
- ✅ 灵活扩展，易维护

---

## 下一步
完成 Day 4 后，继续 [Day 5-7：搜索采集和编辑](day5-7-search-and-edit.md)

