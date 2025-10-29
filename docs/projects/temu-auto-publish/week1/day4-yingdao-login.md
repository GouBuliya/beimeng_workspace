# Day 4：影刀登录流程

**目标**：完成 Temu 后台自动登录，包括 Cookie 保存和验证码处理

---

## 前置准备（30分钟）

### 4.0 了解 Temu 后台登录机制

#### 研究任务
- [ ] 手动登录 Temu 商家后台（记录完整步骤）
- [ ] 观察登录表单元素
  - 用户名输入框
  - 密码输入框
  - 登录按钮
  - 验证码类型（图片/滑块/无）
- [ ] 检查登录后的特征
  - URL 变化
  - 页面特征元素（如用户名显示）
  - Cookie 信息
- [ ] 测试 Cookie 有效期
  - 清除 Cookie 后是否需要重新登录
  - Cookie 能保持多久

---

## 上午任务（3-4小时）

### 4.1 影刀录制基础登录流程

#### 创建新流程
- [ ] 在影刀中创建新流程："Temu后台登录"
- [ ] 配置流程参数：
  - 输入：`username`, `password`
  - 输出：`login_status`, `error_message`

#### 录制步骤
1. **打开浏览器**
   - [ ] 录制：打开 Chrome 浏览器
   - [ ] 设置：窗口大小 1920x1080
   - [ ] 导航到：Temu 商家后台登录页

2. **输入凭证**
   - [ ] 录制：点击用户名输入框
   - [ ] 录制：输入用户名（使用变量 `${username}`）
   - [ ] 录制：点击密码输入框
   - [ ] 录制：输入密码（使用变量 `${password}`）
   - [ ] **注意**：录制时使用测试账号，后续替换为变量

3. **点击登录**
   - [ ] 录制：点击登录按钮
   - [ ] 添加等待：页面加载完成（最多 10 秒）

4. **验证登录成功**
   - [ ] 录制：检查是否出现特定元素（如用户名、首页标识）
   - [ ] 添加条件判断：
     ```
     如果 找到元素("用户名显示")
       设置变量 login_status = "success"
     否则
       设置变量 login_status = "failed"
       截图保存到 data/temp/login_error.png
     ```

#### 任务清单
- [ ] 录制完整登录流程（无验证码情况）
- [ ] 使用变量参数化用户名和密码
- [ ] 添加登录结果判断
- [ ] 测试运行 3 次，成功率 100%
- [ ] **验证标准**：能稳定完成登录，正确判断登录状态

---

## 下午任务（3-4小时）

### 4.2 Cookie 管理机制

#### Cookie 保存流程
在影刀中添加 Cookie 保存步骤：

1. **登录成功后保存 Cookie**
   - [ ] 添加 JavaScript 执行节点：
     ```javascript
     // 获取所有 Cookie
     const cookies = document.cookie;
     // 保存到文件
     const fs = require('fs');
     fs.writeFileSync(
       'data/temp/temu_cookies.json',
       JSON.stringify({
         cookies: cookies,
         timestamp: new Date().toISOString()
       })
     );
     ```
   - [ ] 或使用影刀的"浏览器-保存Cookie"节点

2. **检查 Cookie 是否存在**
   - [ ] 在登录流程开始前添加检查：
     ```
     如果 文件存在("data/temp/temu_cookies.json")
       读取 Cookie 文件
       如果 Cookie 未过期（< 24小时）
         跳过登录，直接使用 Cookie
     ```

3. **加载已保存的 Cookie**
   - [ ] 添加 Cookie 加载节点
   - [ ] 刷新页面验证 Cookie 有效性
   - [ ] 如果失效，重新登录

#### Python 辅助脚本
创建 `src/yingdao/cookie_manager.py`：

```python
"""Cookie 管理器"""

import json
from pathlib import Path
from datetime import datetime, timedelta
from loguru import logger


class CookieManager:
    """Cookie 管理器"""
    
    def __init__(self, cookie_file: str = "data/temp/temu_cookies.json"):
        self.cookie_file = Path(cookie_file)
        self.max_age = timedelta(hours=24)  # Cookie 最大有效期
    
    def is_valid(self) -> bool:
        """检查 Cookie 是否有效
        
        Returns:
            True 如果 Cookie 存在且未过期
        """
        if not self.cookie_file.exists():
            logger.info("Cookie 文件不存在")
            return False
        
        try:
            with open(self.cookie_file) as f:
                data = json.load(f)
            
            # 检查时间戳
            saved_time = datetime.fromisoformat(data["timestamp"])
            age = datetime.now() - saved_time
            
            if age > self.max_age:
                logger.info(f"Cookie 已过期（{age.total_seconds() / 3600:.1f} 小时）")
                return False
            
            logger.success(f"Cookie 有效（已保存 {age.total_seconds() / 3600:.1f} 小时）")
            return True
            
        except Exception as e:
            logger.error(f"读取 Cookie 失败: {e}")
            return False
    
    def clear(self):
        """清除 Cookie 文件"""
        if self.cookie_file.exists():
            self.cookie_file.unlink()
            logger.info("Cookie 已清除")


# 测试代码
if __name__ == "__main__":
    manager = CookieManager()
    
    if manager.is_valid():
        print("✓ Cookie 有效，可以跳过登录")
    else:
        print("✗ Cookie 无效，需要重新登录")
```

#### 任务清单
- [ ] 实现 Cookie 保存功能
- [ ] 实现 Cookie 加载功能
- [ ] 创建 Python Cookie 管理器
- [ ] 测试 Cookie 有效期（手动修改时间戳测试）
- [ ] **验证标准**：使用保存的 Cookie 能跳过登录直接进入后台

### 4.3 验证码处理方案

#### 方案研究
- [ ] 确认 Temu 登录是否有验证码
  - 图片验证码
  - 滑块验证码
  - 无验证码（IP 信任）

#### MVP 方案：手动介入
如果有验证码，MVP 阶段采用：

1. **暂停等待人工**
   - [ ] 在验证码出现位置添加：
     ```
     弹窗提示("请手动完成验证码")
     等待用户点击"继续"按钮
     ```

2. **超时处理**
   - [ ] 设置超时时间（如 2 分钟）
   - [ ] 超时后标记登录失败

#### 优化方案：AI 识别（可选）
如果时间允许，可以尝试：

1. **图片验证码识别**
   ```python
   # 使用 qwen-vl 或 OCR 服务
   def solve_captcha(image_path: str) -> str:
       # 调用视觉模型识别
       pass
   ```

2. **滑块验证码**
   - 研究现有的滑块验证码解决方案
   - 或使用第三方打码平台

#### 任务清单
- [ ] 确认验证码类型
- [ ] 实现 MVP 手动方案
- [ ] （可选）研究 AI 识别方案
- [ ] 记录验证码出现频率（用于评估影响）

### 4.4 完善登录流程

#### 异常处理
添加各种异常情况的处理：

1. **网络超时**
   - [ ] 每个网络操作添加超时设置（10-30秒）
   - [ ] 超时后重试（最多 3 次）

2. **元素未找到**
   - [ ] 关键元素添加"等待出现"（最多 10 秒）
   - [ ] 失败后截图并记录日志

3. **登录失败**
   - [ ] 检测常见失败提示（用户名密码错误、账号冻结等）
   - [ ] 将错误信息返回给 Python

#### 日志记录
- [ ] 在影刀中添加日志节点：
  ```
  每个关键步骤后：
    输出日志("登录流程 - [步骤名] - 完成")
  ```

- [ ] Python 端记录：
  ```python
  logger.info("开始登录")
  # 调用影刀
  logger.success("登录成功")
  ```

#### 参数化配置
创建 `config/yingdao_config.json`：

```json
{
  "login": {
    "url": "https://seller.temu.com/login",
    "timeout": 30,
    "retry_times": 3,
    "cookie_max_age_hours": 24,
    "captcha_wait_timeout": 120
  },
  "browser": {
    "headless": false,
    "window_size": "1920x1080"
  }
}
```

#### 任务清单
- [ ] 添加异常处理
- [ ] 完善日志记录
- [ ] 创建配置文件
- [ ] 测试各种失败场景
- [ ] **验证标准**：所有异常都能正确处理并返回清晰的错误信息

---

## 整合测试（1小时）

### 4.5 Python-影刀登录集成

创建 `src/yingdao/login_controller.py`：

```python
"""登录控制器"""

import json
import subprocess
from pathlib import Path
from loguru import logger

from .cookie_manager import CookieManager


class LoginController:
    """登录控制器"""
    
    def __init__(self, config_path: str = "config/yingdao_config.json"):
        self.config_path = Path(config_path)
        self.cookie_manager = CookieManager()
        self.load_config()
    
    def load_config(self):
        """加载配置"""
        with open(self.config_path) as f:
            self.config = json.load(f)
        logger.info("配置已加载")
    
    def call_yingdao(self, flow_name: str, params: dict) -> dict:
        """调用影刀流程
        
        Args:
            flow_name: 流程名称
            params: 参数字典
        
        Returns:
            执行结果
            
        Note:
            这里需要根据影刀的实际调用方式实现
            可能是命令行、API 或文件交互
        """
        # 示例：通过 JSON 文件交互
        task_file = Path("data/temp/yingdao_task.json")
        result_file = Path("data/temp/yingdao_result.json")
        
        # 写入任务
        with open(task_file, "w") as f:
            json.dump({
                "flow": flow_name,
                "params": params
            }, f)
        
        logger.info(f"调用影刀流程: {flow_name}")
        
        # 等待影刀执行（实际应该有更好的方式）
        # 这里简化处理
        input("请在影刀中运行流程，完成后按回车...")
        
        # 读取结果
        if result_file.exists():
            with open(result_file) as f:
                result = json.load(f)
            return result
        else:
            raise FileNotFoundError("未找到影刀执行结果")
    
    def login(self, username: str, password: str) -> bool:
        """执行登录
        
        Args:
            username: 用户名
            password: 密码
        
        Returns:
            True 如果登录成功
        """
        logger.info("=" * 60)
        logger.info("开始登录流程")
        logger.info("=" * 60)
        
        # 1. 检查 Cookie
        if self.cookie_manager.is_valid():
            logger.success("✓ 使用已保存的 Cookie，跳过登录")
            return True
        
        # 2. 执行登录
        logger.info("Cookie 无效，开始登录...")
        
        try:
            result = self.call_yingdao("Temu后台登录", {
                "username": username,
                "password": password
            })
            
            if result.get("login_status") == "success":
                logger.success("✓ 登录成功")
                return True
            else:
                error_msg = result.get("error_message", "未知错误")
                logger.error(f"✗ 登录失败: {error_msg}")
                return False
        
        except Exception as e:
            logger.error(f"登录过程出错: {e}")
            return False


# 测试代码
if __name__ == "__main__":
    from config.settings import settings
    
    controller = LoginController()
    success = controller.login(
        username=settings.temu_username,
        password=settings.temu_password
    )
    
    if success:
        print("✓ 登录流程测试通过")
    else:
        print("✗ 登录失败")
```

#### 任务清单
- [ ] 实现 `login_controller.py`
- [ ] 确定影刀的调用方式（命令行/API/文件）
- [ ] 完整测试登录流程
  - 首次登录（无 Cookie）
  - 使用 Cookie 登录
  - Cookie 过期后重新登录
- [ ] **验证标准**：Python 能完整控制登录流程，所有情况都能正确处理

---

## Day 4 交付物

### 必须完成 ✅
1. 影刀登录流程 - 能稳定登录 Temu 后台
2. Cookie 管理 - 保存、加载、验证有效性
3. Python 登录控制器 - 能调用影刀执行登录
4. 异常处理 - 网络超时、元素未找到等
5. 测试通过 - 至少 5 次连续成功登录

### 测试checklist 📋
```
☐ 首次登录成功
☐ Cookie 保存成功
☐ 使用 Cookie 跳过登录
☐ Cookie 过期后重新登录
☐ 密码错误能正确提示
☐ 网络超时能重试
☐ （如有验证码）手动介入流程顺畅
```

### 文件清单 📁
```
src/yingdao/
  ├── cookie_manager.py
  ├── login_controller.py
  └── __init__.py

config/
  └── yingdao_config.json

data/temp/
  ├── temu_cookies.json
  ├── login_error.png（如果有失败）
  ├── yingdao_task.json
  └── yingdao_result.json

影刀流程/
  └── Temu后台登录.flow
```

---

## 可能遇到的问题

### 影刀无法启动浏览器
- **现象**：点击运行后浏览器不打开
- **解决**：检查 Chrome 是否已安装，影刀浏览器驱动是否正常

### Cookie 保存失败
- **现象**：文件不存在或为空
- **解决**：检查文件写入权限，确认 JavaScript 执行成功

### 元素定位不稳定
- **现象**：有时能找到元素，有时不能
- **解决**：使用更稳定的定位方式（如 ID、data-属性），增加等待时间

### 验证码频繁出现
- **现象**：每次登录都要验证码
- **解决**：
  - 使用固定 IP
  - 延长操作间隔
  - 联系平台加白名单

---

## 下一步
完成 Day 4 后，继续 [Day 5：影刀搜索采集](day5-yingdao-search.md)

