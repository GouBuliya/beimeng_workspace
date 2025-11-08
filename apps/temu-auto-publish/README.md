# Temu 商品发布自动化系统

> 使用 Python + Playwright 的纯代码浏览器自动化方案

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Playwright](https://img.shields.io/badge/Playwright-1.48+-green.svg)](https://playwright.dev/python/)
[![Pydantic](https://img.shields.io/badge/Pydantic-v2-green.svg)](https://docs.pydantic.dev/)

## 📋 项目概述

本项目采用 **Python + Playwright** 纯代码方案，实现妙手ERP商品发布流程的自动化：

### ✅ 已完成功能 (SOP 步骤1-6)

- ✅ **自动登录** - Cookie管理，智能登录检测
- ✅ **导航系统** - 自动导航到公用采集箱和各个功能模块
- ✅ **AI标题生成** - 支持qwen3-vl-plus多模态模型，逐个生成优化标题
- ✅ **首次编辑** - 自动编辑5个产品（标题、价格、库存、重量、尺寸）
- ✅ **类目核对** - 自动检查商品类目合规性
- ✅ **图片管理** - 生产级图片删除/上传/验证功能
- ✅ **认领流程** - 自动认领产品（5个产品×4次=20个产品）
- ✅ **价格计算** - 智能价格计算器（建议售价、供货价）
- ✅ **数据处理** - Excel选品表读取和处理

### 🚧 开发中功能 (SOP 步骤7-11)

- 🚧 **批量编辑18步** - 二次编辑流程（18个步骤，工具已完成）
- 🚧 **选择店铺** - 多店铺选择功能
- 🚧 **设置供货价** - 批量设置供货价
- 🚧 **批量发布** - 一键发布到店铺
- 🚧 **发布统计** - 发布记录查询和统计

### 📋 待开发功能 (SOP 步骤1-3)

- 📋 **站内搜索** - 结合选品表搜索同款
- 📋 **采集链接** - 一次性采集5个同款链接
- 📋 **插件集成** - 集成妙手浏览器插件

## 🏗️ 架构设计

```
选品表(Excel) → Python读取处理 → 生成任务数据(JSON)
                                        ↓
              Playwright 浏览器自动化 ← Python 异步控制
                          ↓
                 结果记录(JSON) → 数据统计
```

### 核心优势

- **纯 Python 实现**: 无需外部 RPA 工具，代码完全可控
- **异步高效**: 使用 asyncio 和 Playwright 异步 API
- **反检测能力**: playwright-stealth 降低被识别风险
- **易于调试**: 完整的日志和截图功能
- **可维护性强**: 清晰的代码结构和类型提示

## 🚀 快速开始

### 1. 安装依赖

```bash
cd /Users/candy/beimeng_workspace

# 安装 temu 相关依赖（包含 Playwright）
uv sync --extra temu --extra dev

# 安装浏览器（Chromium）
uv run playwright install chromium
```

### 2. 配置环境

创建 `.env` 文件：

```bash
cd apps/temu-auto-publish
cp .env.example .env
vim .env
```

填写以下配置：

```env
# 妙手ERP账号配置
MIAOSHOU_URL=https://erp.91miaoshou.com/sub_account/users
MIAOSHOU_USERNAME=your_username
MIAOSHOU_PASSWORD=your_password

# AI标题生成配置（使用阿里云DashScope）
DASHSCOPE_API_KEY=your_api_key
OPENAI_MODEL=qwen3-vl-plus
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# Temu店铺账号配置（可选）
TEMU_SHOP_URL=https://agentseller.temu.com/
TEMU_USERNAME=your_temu_username
TEMU_PASSWORD=your_temu_password

# 尺寸图外链配置（可选）
# 若选品表未提供尺寸图 URL，将以该前缀+文件名自动拼接
SIZE_CHART_BASE_URL=https://miaoshou-tuchuang-beimeng.oss-cn-hangzhou.aliyuncs.com/10月新品可推/
```

### 3. 运行测试

#### 简化模式（推荐）⭐

**适用场景**: 商品已手动添加到妙手采集箱

```bash
cd apps/temu-auto-publish

# 基础运行
python run_collection_to_edit_test.py

# 调试模式（显示详细日志）
python run_collection_to_edit_test.py --debug

# 自动关闭（不等待）
python run_collection_to_edit_test.py --no-wait
```

**简化模式特点**:
- ✅ 无需处理Temu反爬虫机制
- ✅ 直接编辑采集箱中的商品
- ✅ 符合实际工作流程（用户手动筛选商品）
- ✅ 稳定可靠，只操作妙手ERP
- ✅ 自动AI标题生成和产品信息填写

**工作流程**:
1. 登录妙手ERP
2. 导航到公用采集箱
3. 切换到"全部"tab
4. 读取前5个商品
5. 逐个首次编辑（AI生成标题、设置价格/库存等）
6. 保存并生成报告

#### 完整模式（实验性）

**适用场景**: 从Temu采集到妙手首次编辑的全流程

```bash
# 需要先配置Temu账号和妙手插件
python run_collection_to_edit_test.py --no-skip-collection
```

**注意**: 完整模式需要处理Temu登录和验证码，目前仍在开发中。

---

创建选品表 `data/input/products_sample.xlsx`，包含以下列：

| 商品名称 | 成本价 | 类目 | 关键词 | 备注 |
|---------|--------|------|--------|------|
| 智能手表运动防水 | 150 | 电子产品/智能穿戴 | 智能手表 | 测试 |

> **尺寸图配置说明**
>
> - 选品表可新增列 `尺寸图链接`（或 `尺寸图URL/size_chart_url/size_chart_image_url`），填写可直接访问的图片外链。
> - 若未提供上述列，系统会读取 `实拍图数组` 的首个文件名，并与 `SIZE_CHART_BASE_URL` 拼接生成尺寸图 URL。
> - 请确保 OSS 对象具备公共读权限或使用签名 URL，否则首次编辑将无法完成图片上传。

### 4. 运行测试

```bash
# 运行5→20认领流程完整测试
cd apps/temu-auto-publish
python3 run_real_test.py

# 测试将自动执行：
# 1. 登录妙手ERP
# 2. 导航到公用采集箱
# 3. 首次编辑5个产品（AI标题生成、类目核对、价格库存设置）
# 4. 每个产品认领4次（共20个产品）
# 5. 验证认领成功
```

## 📁 项目结构

```
apps/temu-auto-publish/
├── src/
│   ├── browser/                # 浏览器自动化核心
│   │   ├── browser_manager.py    # Playwright浏览器管理
│   │   ├── login_controller.py   # 登录控制器
│   │   ├── miaoshou_controller.py# 妙手ERP控制器
│   │   ├── first_edit_controller.py # 首次编辑控制器
│   │   ├── batch_edit_controller.py # 批量编辑控制器
│   │   ├── publish_controller.py    # 发布控制器
│   │   ├── collection_controller.py # 采集控制器
│   │   └── image_manager.py         # 图片管理器
│   ├── workflows/              # 业务流程
│   │   ├── five_to_twenty_workflow.py    # 5→20认领流程
│   │   ├── complete_publish_workflow.py  # 完整发布流程
│   │   └── full_publish_workflow.py      # 全流程工作流
│   ├── data_processor/         # 数据处理模块
│   │   ├── excel_reader.py      # Excel读取器
│   │   ├── price_calculator.py  # 价格计算器
│   │   ├── ai_title_generator.py# AI标题生成器
│   │   └── data_generator.py    # 随机数据生成器
│   ├── automation_tools/       # 自动化增强工具
│   │   ├── retry_decorator.py   # 重试装饰器
│   │   ├── performance_monitor.py # 性能监控
│   │   ├── error_handler.py     # 错误处理器
│   │   └── step_validator.py    # 步骤验证器
│   └── models/                 # 数据模型
│       ├── task.py              # 任务模型
│       └── result.py            # 结果模型
├── config/                     # 配置文件
│   ├── settings.py             # 应用配置
│   ├── miaoshou_selectors_v2.json # 妙手选择器配置
│   └── browser_config.json     # 浏览器配置
├── docs/                       # 文档
│   ├── AI_TITLE_GENERATION.md  # AI标题生成文档
│   ├── COLLECTION.md           # 采集功能文档
│   ├── DEBUG_GUIDE.md          # 调试指南
│   └── STATE_DETECTOR_GUIDE.md # 状态检测器指南
├── tests/                      # 测试
│   ├── unit/                   # 单元测试
│   └── integration/            # 集成测试
├── run_real_test.py           # 真实环境测试脚本
├── .env.example               # 环境变量模板
├── .env                       # 环境变量配置（需创建）
├── QUICKSTART.md              # 快速开始指南
└── README.md                  # 本文件
```

## 🎯 核心功能说明

### 5→20认领流程 (SOP 步骤4-6)

自动化执行商品首次编辑和认领流程：

1. **导航到公用采集箱** - 自动进入「全部」tab
2. **首次编辑5个产品**：
   - AI生成优化标题（qwen3-vl-plus模型）
   - 核对商品类目合规性
   - 设置价格和库存
   - 上传尺寸图和视频（可选）
3. **认领流程** - 每个产品认领4次
4. **验证结果** - 确认20个产品已认领成功

### AI标题生成

支持多种AI模型：
- **qwen3-vl-plus** - 阿里云通义千问多模态模型（推荐）
- **qwen-plus** - 阿里云通义千问标准模型
- **gpt-3.5-turbo** - OpenAI模型
- **claude** - Anthropic模型

AI自动提取热搜词，生成符合TEMU/亚马逊平台规则的中文标题。

### 类目核对

自动检查商品类目是否合规：
- ✅ 支持的类目：家居用品、收纳整理等
- ❌ 不支持的类目：药品、医疗器械、电子产品等

### 价格计算

智能价格计算器：
```
建议售价 = 成本价 × 10
供货价 = 成本价 × 7.5
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

### Playwright 自动化开发

1. 了解页面结构（使用浏览器开发者工具）
2. 编写选择器定位元素
3. 实现业务逻辑
4. 添加错误处理和重试机制
5. 测试并优化性能

参考文档：
- [Playwright 官方文档](https://playwright.dev/python/)
- [项目实施方案](../../docs/projects/temu-auto-publish/index.md)
- [数据格式规范](../../docs/projects/temu-auto-publish/guides/data-format.md)

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

# 浏览器配置
BROWSER_HEADLESS=False        # 无头模式
BROWSER_CONFIG_FILE=config/browser_config.json

# 业务规则
PRICE_MULTIPLIER=7.5          # 建议售价 = 成本 × 7.5
SUPPLY_PRICE_MULTIPLIER=10.0  # 供货价 = 成本 × 10
COLLECT_COUNT=5               # 采集同款数量

# 日志
LOG_LEVEL=INFO
```

### 浏览器配置 (browser_config.json)

```json
{
  "browser": {
    "type": "chromium",
    "headless": false,
    "window_width": 1920,
    "window_height": 1080
  },
  "stealth": {
    "enabled": true
  },
  "timeouts": {
    "default": 30000,
    "navigation": 60000
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

### ✅ Phase 1: 基础架构与核心功能 (已完成)
- [x] Playwright浏览器管理器
- [x] Cookie管理和智能登录
- [x] 导航系统（妙手ERP各模块）
- [x] 首次编辑控制器（FirstEditController）
- [x] AI标题生成器（支持多模态模型）
- [x] 类目核对功能
- [x] 图片管理器（生产级）
- [x] 价格计算器
- [x] 5→20认领流程完整实现
- [x] 数据处理层（Excel、价格、标题）
- [x] 自动化增强工具（重试、监控、验证）

### 🚧 Phase 2: 批量编辑与发布 (开发中)
- [x] 批量编辑控制器基础框架
- [x] 批量编辑18步工具集（retry、monitor、error_handler）
- [ ] 批量编辑18步端到端测试
- [ ] 选择店铺功能（步骤8）
- [ ] 设置供货价功能（步骤9）
- [ ] 批量发布功能（步骤10）
- [ ] 发布记录查询和统计（步骤11）

### 📅 Phase 3: 采集与完整流程 (计划中)
- [ ] 站内搜索功能（步骤2）
- [ ] 一次性采集5个链接（步骤3）
- [ ] 妙手插件集成（步骤1）
- [ ] 完整的端到端测试（步骤1-11）
- [ ] 性能优化和并发处理
- [ ] 监控报警系统

### 📚 Phase 4: 文档与优化 (持续进行)
- [x] 代码文件元信息协议100%合规
- [ ] 完善文档体系（用户手册、API文档）
- [ ] 故障排查指南
- [ ] 最佳实践文档

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

1. **反检测机制**：
   - 已集成 playwright-stealth
   - 自动添加随机延迟（200-500ms）
   - 使用真实的浏览器指纹
   
2. **Cookie管理**：
   - 自动保存和加载Cookie
   - Cookie有效期约24小时
   - 智能检测登录状态
   
3. **错误处理**：
   - 完整的错误日志记录
   - 失败时自动截图
   - 重试机制（最多3次）
   
4. **AI模型配置**：
   - 推荐使用qwen3-vl-plus（支持多模态）
   - 需要配置DASHSCOPE_API_KEY
   - API调用自动限流避免频率限制
   
5. **选择器维护**：
   - 选择器配置在 `config/miaoshou_selectors_v2.json`
   - 使用文本定位器提高稳定性
   - 如果妙手ERP界面更新，可能需要更新选择器

## 🔧 故障排查

### 常见问题

**Q: 登录失败？**
- 检查`.env`中的账号密码是否正确
- 尝试删除`data/cookies/miaoshou_cookies.json`重新登录
- 检查网络连接

**Q: AI标题生成失败？**
- 检查`DASHSCOPE_API_KEY`是否正确
- 检查API Key是否有余额
- 查看日志中的具体错误信息

**Q: 元素定位失败？**
- 妙手ERP界面可能更新
- 使用Playwright Codegen重新录制选择器
- 更新`config/miaoshou_selectors_v2.json`

**Q: 类目核对读取不到信息？**
- 类目字段选择器需要在实际环境调试
- 不影响主流程，会默认认为合规

### 调试工具

```bash
# 使用Playwright Codegen录制操作
uv run playwright codegen https://erp.91miaoshou.com

# 查看详细日志
tail -f data/logs/temu_automation.log

# 使用浏览器开发者工具检查元素
# 推荐Chrome DevTools的Elements面板
```

## 📄 License

MIT License - 详见 LICENSE 文件

## 🙏 致谢

- [Playwright](https://playwright.dev/python/) - 强大的浏览器自动化库
- [playwright-stealth](https://github.com/AtuboDad/playwright_stealth) - 反检测工具
- [Pydantic](https://docs.pydantic.dev/) - 数据验证
- [Typer](https://typer.tiangolo.com/) - CLI 框架
- [Loguru](https://github.com/Delgan/loguru) - 日志库

---

**项目状态**: ✅ 简化模式完成 | 🚧 完整模式开发中

**当前功能**:
- ✅ 简化模式：妙手采集箱 → AI标题生成 → 首次编辑（完全自动化）
- 🚧 完整模式：Temu采集 → 妙手首次编辑（实验性功能）

**测试状态**: 
- ✅ 简化模式已通过完整测试（包含AI标题生成、类目核对、价格设置等）
- ✅ 支持调试模式，日志详细完整
- ✅ 生成JSON报告和统计信息

**下一步计划**: 
1. 完善Temu采集功能（处理登录和验证码）
2. 实现SOP步骤7-11（批量编辑18步 + 发布流程）

如有问题，请参考文档：
- [快速开始](QUICKSTART.md)
- [AI标题生成](docs/AI_TITLE_GENERATION.md)
- [调试指南](docs/DEBUG_GUIDE.md)
- [商品发布SOP](../../docs/projects/temu-auto-publish/guides/商品发布SOP-IT专用.md)

