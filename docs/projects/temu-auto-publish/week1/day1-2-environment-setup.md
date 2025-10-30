# Day 1-2：环境准备和基础配置

**目标**：完成 Playwright + Python 开发环境搭建和项目初始化

**技术栈**：Python 3.12 + Playwright + asyncio

---

## Day 1：Python 和 Playwright 环境

### 上午任务（2-3小时）

#### 1.1 Python 环境确认
- [ ] 确认 Python 版本（要求 3.12+）
  ```bash
  python --version  # 应该显示 3.12.x
  ```
- [ ] 确认已安装 uv 包管理器
  ```bash
  uv --version
  # 如未安装：curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
- [ ] 确认在 beimeng_workspace 目录下

#### 1.2 项目结构创建
```bash
cd /Users/candy/beimeng_workspace
mkdir -p apps/temu-auto-publish/{src,config,data/{input,output,temp,logs},examples,tests}
cd apps/temu-auto-publish

# 创建子模块目录
mkdir -p src/{browser,data_processor,models}
mkdir -p data/temp/screenshots

# 创建基础文件
touch __init__.py __main__.py
touch src/{__init__.py,browser/__init__.py,data_processor/__init__.py,models/__init__.py}
```

#### 1.3 安装核心依赖
在 beimeng_workspace 根目录，更新 `pyproject.toml` 添加 temu 依赖组：

```bash
# 安装依赖
cd /Users/candy/beimeng_workspace
uv sync --extra temu --extra dev

# 安装 Playwright 浏览器
uv run playwright install chromium
```

**核心依赖包括**：
- `playwright` - 浏览器自动化
- `playwright-stealth` - 反检测
- `pandas`, `openpyxl` - Excel 处理
- `pydantic`, `pydantic-settings` - 数据验证和配置
- `loguru` - 日志
- `typer`, `rich` - CLI 和终端美化

### 下午任务（2-3小时）

#### 1.4 测试 Playwright 环境
创建测试脚本 `examples/test_playwright.py`：

```python
"""测试 Playwright 环境"""

import asyncio
from playwright.async_api import async_playwright


async def test_playwright():
    """测试 Playwright 基本功能"""
    async with async_playwright() as p:
        print("✓ Playwright 已安装")
        
        # 启动浏览器
        browser = await p.chromium.launch(headless=False)
        print("✓ Chromium 浏览器已启动")
        
        # 创建页面
        page = await browser.new_page()
        print("✓ 新页面已创建")
        
        # 访问测试网站
        await page.goto("https://www.baidu.com")
        print("✓ 页面导航成功")
        
        # 截图
        await page.screenshot(path="data/temp/test.png")
        print("✓ 截图保存成功")
        
        # 关闭浏览器
        await browser.close()
        print("✓ 浏览器已关闭")
        
        print("\n✓✓✓ Playwright 环境测试通过！")


if __name__ == "__main__":
    asyncio.run(test_playwright())
```

运行测试：
```bash
cd apps/temu-auto-publish
uv run python examples/test_playwright.py
```

- [ ] 运行测试脚本
- [ ] **验证标准**：浏览器正常启动，能访问网页，截图保存成功

#### 1.5 测试反检测功能
创建 `examples/test_stealth.py`：

```python
"""测试 playwright-stealth 反检测"""

import asyncio
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async


async def test_stealth():
    """测试反检测功能"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        
        # 应用反检测补丁
        await stealth_async(context)
        print("✓ 反检测补丁已应用")
        
        page = await context.new_page()
        
        # 访问反爬虫检测网站
        await page.goto("https://bot.sannysoft.com/")
        await page.wait_for_load_state("networkidle")
        
        print("✓ 访问反爬虫检测网站")
        print("  请手动查看页面，检查是否通过检测")
        print("  （WebDriver: 应该显示 false）")
        
        input("\n按回车键关闭浏览器...")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(test_stealth())
```

---

## Day 2：配置和数据结构

### 上午任务（2-3小时）

#### 2.1 创建配置系统
创建 `config/settings.py`：

```python
"""应用配置管理，使用Pydantic Settings管理配置，支持从.env文件加载"""

from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Temu 自动发布应用配置"""

    # Temu 账号配置
    temu_username: str = Field(default="", description="Temu 用户名")
    temu_password: str = Field(default="", description="Temu 密码")

    # 路径配置
    data_input_dir: str = Field(default="data/input", description="输入目录")
    data_output_dir: str = Field(default="data/output", description="输出目录")
    data_temp_dir: str = Field(default="data/temp", description="临时目录")
    data_logs_dir: str = Field(default="data/logs", description="日志目录")

    # Playwright 浏览器配置
    browser_headless: bool = Field(default=False, description="浏览器无头模式")
    browser_config_file: str = Field(
        default="config/browser_config.json", description="浏览器配置文件"
    )

    # 业务规则配置
    price_multiplier: float = Field(default=7.5, description="价格倍率（2.5×3）")
    supply_price_multiplier: float = Field(default=10.0, description="供货价倍率")
    collect_count: int = Field(default=5, ge=1, le=10, description="采集数量")

    # 日志配置
    log_level: str = Field(default="INFO", description="日志级别")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    def get_absolute_path(self, relative_path: str) -> Path:
        """将相对路径转换为绝对路径"""
        base_dir = Path(__file__).parent.parent
        return base_dir / relative_path

    def ensure_directories(self) -> None:
        """确保所有必需的目录存在"""
        for dir_path in [
            self.data_input_dir,
            self.data_output_dir,
            self.data_temp_dir,
            self.data_logs_dir,
        ]:
            full_path = self.get_absolute_path(dir_path)
            full_path.mkdir(parents=True, exist_ok=True)


# 全局配置实例
settings = Settings()
```

创建 `.env.example` 模板：
```env
# Temu 账号配置
TEMU_USERNAME=your_username
TEMU_PASSWORD=your_password

# 浏览器配置
BROWSER_HEADLESS=False

# 业务规则
PRICE_MULTIPLIER=7.5
SUPPLY_PRICE_MULTIPLIER=10.0
COLLECT_COUNT=5

# 日志
LOG_LEVEL=INFO
```

- [ ] 创建配置文件
- [ ] 创建 `.env` 文件（不提交到 Git）
- [ ] 测试配置加载

#### 2.2 创建浏览器配置
创建 `config/browser_config.json`：

```json
{
  "browser": {
    "type": "chromium",
    "headless": false,
    "window_width": 1920,
    "window_height": 1080,
    "locale": "zh-CN",
    "timezone": "Asia/Shanghai"
  },
  "stealth": {
    "enabled": true
  },
  "timeouts": {
    "default": 30000,
    "navigation": 60000,
    "wait_for_selector": 10000
  }
}
```

### 下午任务（2-3小时）

#### 2.3 定义数据模型
参考已完成的 `src/models/task.py` 和 `src/models/result.py`

这些文件已经实现，包含：
- `ProductInput`: 选品表输入数据
- `TaskProduct`: 任务商品数据
- `TaskData`: 完整任务数据
- `SearchResult`: 搜索采集结果
- `EditResult`: 编辑结果
- `PublishResult`: 发布结果
- `BrowserResult`: 浏览器操作结果基类

#### 2.4 Git 配置
创建/更新 `.gitignore`：

```gitignore
# 数据文件
data/input/*.xlsx
data/output/*.json
data/temp/*
!data/temp/.gitkeep
data/logs/*
!data/logs/.gitkeep

# 环境变量
.env

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.pytest_cache/
.coverage
htmlcov/

# IDE
.vscode/
.idea/
*.swp
*.swo

# 系统文件
.DS_Store
Thumbs.db
```

提交初始代码：
```bash
git add apps/temu-auto-publish
git commit -m "feat(temu): 初始化 Playwright 自动化项目

- Python 3.12 + Playwright + asyncio 架构
- 完整的配置系统（Pydantic Settings）
- 数据模型定义（Pydantic v2）
- 项目结构符合工作区规范"
```

#### 2.5 创建环境测试脚本
参考已有的 `examples/test_env.py`，它已经测试：
- 所有 Python 依赖导入
- 项目模块导入
- 配置加载

运行测试：
```bash
uv run python examples/test_env.py
```

---

## Day 1-2 交付物

### 必须完成 ✅
1. ✅ Python 3.12 环境已确认
2. ✅ Playwright 已安装并测试通过
3. ✅ playwright-stealth 反检测已测试
4. ✅ 项目目录结构已创建
5. ✅ 配置系统已实现（.env + browser_config.json）
6. ✅ 数据模型已定义（Pydantic）
7. ✅ Git 仓库已配置并完成首次提交

### 测试 Checklist 📋
```
☐ python --version 显示 3.12+
☐ uv run playwright --version 正常显示
☐ test_playwright.py 测试通过
☐ test_stealth.py 通过反检测测试
☐ test_env.py 所有导入测试通过
☐ settings 能正确加载配置
☐ Git 首次提交完成
```

### 目录结构 📁
```
apps/temu-auto-publish/
├── __init__.py
├── __main__.py
├── .env                    # 不提交
├── .env.example           # 配置模板
├── README.md
├── config/
│   ├── __init__.py
│   ├── settings.py        # Pydantic 配置
│   └── browser_config.json # 浏览器配置
├── src/
│   ├── __init__.py
│   ├── browser/           # 浏览器自动化模块
│   │   └── __init__.py
│   ├── data_processor/    # 数据处理模块
│   │   └── __init__.py
│   └── models/            # 数据模型
│       ├── __init__.py
│       ├── task.py
│       └── result.py
├── data/
│   ├── input/            # Excel 输入
│   ├── output/           # JSON 输出
│   ├── temp/             # 临时文件和截图
│   └── logs/             # 日志文件
├── examples/
│   ├── test_playwright.py
│   ├── test_stealth.py
│   └── test_env.py
└── tests/                # 单元测试
    └── __init__.py
```

---

## 可能遇到的问题

### Playwright 安装失败
- **现象**：`playwright install` 报错
- **解决**：
  ```bash
  # 使用国内镜像
  export PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright/
  uv run playwright install chromium
  ```

### playwright-stealth 导入失败
- **现象**：`ImportError: No module named 'playwright_stealth'`
- **解决**：确认已安装，或手动安装：
  ```bash
  uv pip install playwright-stealth
  ```

### 浏览器启动慢
- **现象**：浏览器启动需要很长时间
- **解决**：正常现象，首次启动需要下载浏览器二进制文件

### 配置加载失败
- **现象**：`ValidationError`
- **解决**：检查 .env 文件格式，确保没有中文引号

---

## 与影刀方案的对比

| 项目 | 影刀方案 | Playwright 方案 |
|------|---------|----------------|
| 工具 | 影刀 RPA（第三方） | Playwright（纯代码） |
| 学习曲线 | 低（录制功能） | 中（需要编码） |
| 可控性 | 低（黑盒） | 高（完全可控） |
| 调试 | 困难 | 容易（IDE 调试） |
| 成本 | 可能需要授权费 | 完全免费 |
| 维护性 | 低 | 高（代码化） |
| 扩展性 | 受限 | 灵活 |

---

## 下一步
完成 Day 1-2 后，继续 [Day 3：Python 数据处理层](day3-data-processing.md)
