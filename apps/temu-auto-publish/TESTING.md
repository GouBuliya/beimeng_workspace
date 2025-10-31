# 浏览器测试环境配置指南

## 概述

本项目使用 Playwright 进行浏览器自动化测试，包括单元测试和集成测试两类。

## 测试分类

### 1. 单元测试（Unit Tests）
- **标记**: 无需特殊标记或 `@pytest.mark.unit`
- **运行**: `uv run pytest -m "not integration"`
- **特点**: 不需要真实浏览器环境，测试业务逻辑
- **覆盖**: 数据处理、价格计算、随机生成等模块

### 2. 集成测试（Integration Tests）
- **标记**: `@pytest.mark.integration`
- **运行**: `uv run pytest -m integration`
- **特点**: 需要真实浏览器环境，测试完整流程
- **覆盖**: 登录、导航、产品编辑等浏览器操作

## 环境配置

### 步骤1：安装 Playwright 浏览器

```bash
# 在项目根目录运行
cd apps/temu-auto-publish
uv run playwright install chromium
```

### 步骤2：配置环境变量

创建 `.env` 文件（从 `.env.example` 复制）：

```bash
cp .env.example .env
```

编辑 `.env` 文件，配置以下变量：

```env
# 妙手ERP账号配置（用于集成测试）
MIAOSHOU_USERNAME=your_username
MIAOSHOU_PASSWORD=your_password

# 浏览器配置
BROWSER_HEADLESS=false

# 业务规则配置
PRICE_MULTIPLIER=10.0
SUPPLY_PRICE_MULTIPLIER=7.5
COLLECT_COUNT=5
CLAIM_COUNT=4

# 日志配置
LOG_LEVEL=INFO
```

### 步骤3：验证配置

```bash
# 运行环境检查
uv run python run_integration_tests.py
```

## 运行测试

### 运行所有单元测试（推荐，快速）
```bash
uv run pytest -v
```

默认配置已排除集成测试，只运行单元测试。

### 运行特定模块的单元测试
```bash
# 测试价格计算器
uv run pytest tests/test_price_calculator.py -v

# 测试随机数据生成器
uv run pytest tests/test_random_generator.py -v

# 测试浏览器管理器
uv run pytest tests/test_browser_manager.py -v
```

### 运行集成测试（需要浏览器环境）
```bash
# 方式1: 使用脚本（推荐，会自动检查环境）
uv run python run_integration_tests.py

# 方式2: 直接使用pytest
uv run pytest -m integration -v
```

### 运行特定的集成测试
```bash
# 测试登录功能
uv run pytest tests/test_controllers.py::test_login -m integration -v

# 测试完整编辑流程
uv run pytest tests/test_complete_edit_flow.py -m integration -v
```

## Pytest 配置说明

### pytest.ini 主要配置

```ini
[pytest]
# 异步测试自动检测
asyncio_mode = auto

# 默认排除集成测试
addopts = -m "not integration"

# 标记定义
markers =
    integration: 集成测试（需要浏览器环境）
    slow: 慢速测试
    unit: 单元测试
```

### conftest.py 配置

- 自动配置 pytest-asyncio
- 添加项目根目录到 Python 路径
- 注册自定义标记

## 测试覆盖率

### 查看覆盖率报告
```bash
# 运行测试并生成覆盖率报告
uv run pytest --cov=src --cov-report=html

# 在浏览器中查看详细报告
open htmlcov/index.html
```

### 当前覆盖率

- **总体覆盖率**: 20%
- **数据处理模块**: 62-83%
- **浏览器控制模块**: 7-15%（需要集成测试环境）

## 常见问题

### Q: 为什么集成测试失败？

**A**: 集成测试需要以下条件：
1. Playwright 浏览器已安装
2. `.env` 文件已正确配置
3. 有效的登录凭据
4. 稳定的网络连接

### Q: 如何跳过某些测试？

**A**: 使用 pytest 标记：
```bash
# 跳过集成测试
uv run pytest -m "not integration"

# 跳过慢速测试
uv run pytest -m "not slow"

# 只运行单元测试
uv run pytest -m unit
```

### Q: 测试时浏览器无法启动？

**A**: 检查以下几点：
1. 运行 `uv run playwright install chromium` 安装浏览器
2. 确保系统没有其他进程占用端口
3. 检查防火墙设置

### Q: 如何调试失败的测试？

**A**: 使用 pytest 调试选项：
```bash
# 显示详细输出
uv run pytest -v -s

# 在第一个失败处停止
uv run pytest -x

# 进入 pdb 调试器
uv run pytest --pdb

# 显示完整的错误跟踪
uv run pytest --tb=long
```

## CI/CD 集成

在 CI/CD 环境中，建议：

1. **只运行单元测试**（快速反馈）：
   ```yaml
   - run: uv run pytest -m "not integration" --cov
   ```

2. **在特定环境运行集成测试**：
   ```yaml
   - run: uv run playwright install chromium
   - run: uv run pytest -m integration --no-cov
   ```

## 最佳实践

1. **开发时**: 频繁运行单元测试 (`uv run pytest`)
2. **提交前**: 运行完整的单元测试套件
3. **发布前**: 运行集成测试验证完整流程
4. **添加新功能**: 同时添加单元测试和集成测试
5. **修复 Bug**: 先写失败的测试，再修复代码

## 相关文件

- `pytest.ini` - Pytest 配置
- `conftest.py` - Pytest fixtures 和配置
- `.env.example` - 环境变量模板
- `run_integration_tests.py` - 集成测试运行脚本
- `tests/` - 单元测试目录
- `examples/` - 示例和集成测试

