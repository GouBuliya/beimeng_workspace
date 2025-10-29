# Temu 商品发布自动化系统

> 使用 Python + 影刀 RPA 混合架构的 Temu 商品自动发布系统

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Pydantic](https://img.shields.io/badge/Pydantic-v2-green.svg)](https://docs.pydantic.dev/)

## 📋 项目概述

本项目采用 **Python + 影刀 RPA** 混合架构，实现 Temu 商品发布流程的自动化：

- ✅ **Excel 选品表处理** - 自动读取、验证和转换
- ✅ **价格自动计算** - 建议售价和供货价
- ✅ **AI 标题生成** - 多种模式可选
- 🚧 **自动登录** - Cookie 管理，减少重复登录
- 🚧 **搜索采集** - 站内搜索并采集同款链接
- 🚧 **批量编辑** - 18步编辑流程
- 🚧 **批量发布** - 一键发布到多店铺

## 🏗️ 架构设计

```
选品表(Excel) → Python读取处理 → 生成任务数据(JSON)
                                        ↓
影刀执行浏览器操作 ← Python调度 ← 任务队列
         ↓
     结果反馈(JSON) → Python记录日志 → 数据统计
```

### 核心优势

- **数据处理层（Python）**: 灵活、可测试、易扩展
- **RPA 执行层（影刀）**: 高效的浏览器自动化，支持录制
- **文件交互**: 通过 JSON 文件解耦，便于调试和维护

## 🚀 快速开始

### 1. 安装依赖

```bash
cd /Users/candy/beimeng_workspace

# 安装 temu 相关依赖
uv sync --extra temu --extra dev
```

### 2. 配置环境

```bash
# 复制配置模板
cp apps/temu-auto-publish/.env.example apps/temu-auto-publish/.env

# 编辑配置
vim apps/temu-auto-publish/.env
```

填写以下信息：
```env
TEMU_USERNAME=your_username
TEMU_PASSWORD=your_password
PRICE_MULTIPLIER=7.5
COLLECT_COUNT=5
```

### 3. 准备测试数据

创建选品表 `data/input/products_sample.xlsx`，包含以下列：

| 商品名称 | 成本价 | 类目 | 关键词 | 备注 |
|---------|--------|------|--------|------|
| 智能手表运动防水 | 150 | 电子产品/智能穿戴 | 智能手表 | 测试 |

### 4. 运行测试

```bash
# 查看系统状态
uv run python -m apps.temu-auto-publish status

# 测试 Excel 读取
uv run python -m apps.temu-auto-publish dev excel data/input/products_sample.xlsx

# 测试价格计算
uv run python -m apps.temu-auto-publish dev price 150

# 处理选品表生成任务
uv run python -m apps.temu-auto-publish process data/input/products_sample.xlsx
```

## 📁 项目结构

```
apps/temu-auto-publish/
├── src/
│   ├── data_processor/      # 数据处理模块
│   │   ├── excel_reader.py    # Excel 读取
│   │   ├── price_calculator.py # 价格计算
│   │   ├── title_generator.py  # 标题生成
│   │   └── processor.py        # 流程整合
│   ├── yingdao/             # 影刀控制器
│   │   ├── cookie_manager.py   # Cookie 管理
│   │   ├── login_controller.py # 登录控制
│   │   └── ...
│   └── models/              # 数据模型
│       ├── task.py            # 任务数据模型
│       └── result.py          # 结果数据模型
├── config/                  # 配置文件
│   ├── settings.py          # 应用配置
│   └── yingdao_config.json  # 影刀配置
├── data/                    # 数据目录
│   ├── input/              # Excel 输入
│   ├── output/             # JSON 输出
│   ├── temp/               # 临时文件
│   └── logs/               # 日志文件
├── examples/               # 示例脚本
├── tests/                  # 测试
├── __main__.py            # CLI 入口
├── .env.example           # 环境变量模板
├── .ai.json               # AI 元数据
└── README.md              # 本文件
```

## 🎯 CLI 命令

### 主命令

```bash
# 处理选品表（完整流程）
python -m apps.temu-auto-publish process <excel_file>

# 测试登录
python -m apps.temu-auto-publish login

# 查看系统状态
python -m apps.temu-auto-publish status
```

### 开发命令

```bash
# 测试 Excel 读取
python -m apps.temu-auto-publish dev excel <file>

# 测试价格计算
python -m apps.temu-auto-publish dev price <cost>
```

## 📊 数据格式

### 输入: Excel 选品表

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| 商品名称 | 文本 | ✓ | 商品的原始名称 |
| 成本价 | 数字 | ✓ | 单位：元，保留2位小数 |
| 类目 | 文本 | ✓ | 类目路径，如"电子产品/智能穿戴" |
| 关键词 | 文本 | ✓ | 站内搜索关键词 |
| 备注 | 文本 | ✗ | 其他说明信息 |

### 输出: JSON 任务数据

```json
{
  "task_id": "20251029_143000",
  "created_at": "2025-10-29T14:30:00+08:00",
  "status": "pending",
  "products": [
    {
      "id": "P001",
      "keyword": "智能手表",
      "original_name": "智能手表运动防水",
      "ai_title": "[TEMU_AI:智能手表]",
      "cost_price": 150.00,
      "suggested_price": 1125.00,
      "supply_price": 1500.00,
      "category": "电子产品/智能穿戴",
      "status": "pending"
    }
  ]
}
```

详细格式规范请参考: [数据格式文档](../../docs/projects/temu-auto-publish/guides/data-format.md)

## 🛠️ 开发指南

### 影刀流程开发

1. 在影刀中创建流程
2. 配置输入输出参数
3. 录制浏览器操作
4. 添加错误处理
5. 测试并优化

参考文档：
- [Day 4: 登录流程](../../docs/projects/temu-auto-publish/week1/day4-yingdao-login.md)
- [Day 5-7: 搜索和编辑](../../docs/projects/temu-auto-publish/week1/day5-7-search-and-edit.md)

### Python 模块开发

1. 在 `src/` 下创建模块
2. 定义 Pydantic 数据模型
3. 编写业务逻辑
4. 添加完整的 docstring
5. 编写单元测试

所有模块都使用：
- ✅ **类型提示**: 完整的类型标注
- ✅ **数据验证**: Pydantic 模型
- ✅ **日志记录**: Loguru
- ✅ **错误处理**: 清晰的异常信息

## 📝 配置说明

### 应用配置 (.env)

```env
# Temu 账号
TEMU_USERNAME=your_username
TEMU_PASSWORD=your_password

# 业务规则
PRICE_MULTIPLIER=7.5          # 建议售价 = 成本 × 7.5
SUPPLY_PRICE_MULTIPLIER=10.0  # 供货价 = 成本 × 10
COLLECT_COUNT=5               # 采集同款数量

# 日志
LOG_LEVEL=INFO
```

### 影刀配置 (yingdao_config.json)

```json
{
  "login": {
    "timeout": 30,
    "retry_times": 3,
    "cookie_max_age_hours": 24
  },
  "search": {
    "timeout": 10,
    "wait_after_search": 3
  },
  "browser": {
    "headless": false,
    "window_size": "1920x1080"
  }
}
```

## 🧪 测试

```bash
# 运行所有测试
uv run pytest apps/temu-auto-publish/tests/

# 运行特定测试
uv run pytest apps/temu-auto-publish/tests/test_excel_reader.py

# 查看覆盖率
uv run pytest --cov=apps/temu-auto-publish
```

## 📖 完整文档

- [项目实施方案](../../docs/projects/temu-auto-publish/index.md)
- [快速开始指南](../../docs/projects/temu-auto-publish/guides/quickstart.md)
- [数据格式规范](../../docs/projects/temu-auto-publish/guides/data-format.md)
- [Week 1 详细任务](../../docs/projects/temu-auto-publish/week1/)

## 🗺️ 开发路线图

### ✅ Week 1 (Day 1-7)
- [x] 项目结构创建
- [x] 数据处理层（Excel、价格、标题）
- [ ] 影刀登录流程
- [ ] 搜索采集流程
- [ ] 首次编辑流程

### 🚧 Week 2 (Day 8-14)
- [ ] 批量编辑 18 步
- [ ] 批量发布
- [ ] Python 流程编排

### 📅 Week 3 (Day 15-17)
- [ ] 完整测试
- [ ] 文档整理
- [ ] 项目交付

## 🤝 贡献指南

遵循 beimeng_workspace 的开发规范：

1. 代码风格：使用 ruff 格式化
2. 类型检查：通过 mypy 检查
3. 文档：Google Style docstrings
4. 提交：遵循 conventional commits

```bash
# 格式化代码
uv run ruff format apps/temu-auto-publish

# Lint 检查
uv run ruff check apps/temu-auto-publish --fix

# 类型检查
uv run mypy apps/temu-auto-publish
```

## ⚠️ 注意事项

1. **不要频繁登录** - 使用 Cookie 管理
2. **控制请求频率** - 添加延迟避免反爬
3. **保护账号安全** - 不要泄露 .env 文件
4. **定期检查流程** - 页面变化需要更新影刀流程

## 📄 License

MIT License - 详见 LICENSE 文件

## 🙏 致谢

- [影刀 RPA](https://www.yingdao.com/) - 浏览器自动化工具
- [Pydantic](https://docs.pydantic.dev/) - 数据验证
- [Typer](https://typer.tiangolo.com/) - CLI 框架
- [Loguru](https://github.com/Delgan/loguru) - 日志库

---

**项目状态**: 🚧 开发中 (Day 3 完成)

如有问题，请参考 [详细文档](../../docs/projects/temu-auto-publish/) 或提交 Issue。

