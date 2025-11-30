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

## 📚 模块文档

- `src/browser/README.md`：浏览器控制器、Codegen 与调试指南
- `src/workflows/README.md`：工作流阶段划分与 orchestrator 说明
- `src/data_processor/README.md`：选品表、价格、AI 标题处理逻辑

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

# 媒体外链配置（可选）
# SKU 图片与视频可通过以下前缀拼接；尺寸图需在选品表中直接提供完整 URL
PRODUCT_IMAGE_BASE_URL=https://miaoshou-tuchuang-beimeng.oss-cn-hangzhou.aliyuncs.com/10月新品可推/
VIDEO_BASE_URL=https://miaoshou-tuchuang-beimeng.oss-cn-hangzhou.aliyuncs.com/video/
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

> **媒体配置说明**
>
> - 选品表必须新增列 `尺寸图链接`（或 `尺寸图URL/size_chart_url/size_chart_image_url`），填写可直接访问的图片外链。
> - 可选新增列 `视频链接`（或 `视频URL/video_url/product_video_url`），用于提供产品视频的网络地址。
> - 系统始终使用 `VIDEO_BASE_URL` + 型号编号（如 `A026.mp4`）拼接生成 OSS 视频 URL；仅当未配置 `VIDEO_BASE_URL` 时才回退到表格中的链接。
> - 请确保外链对象具备公共读权限或生成有效签名 URL，否则首次编辑将无法完成上传。

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

### ♻️ 持续运行脚本：`run_until_empty.py`

当需要“盯盘式”持续发布时，可使用新脚本自动循环运行完整发布工作流，直到选品表被清空或发现格式异常：

```bash
cd apps/temu-auto-publish
python run_until_empty.py \
  --input data/input/selection.xlsx \
  --batch-size 20 \
  --interval 15 \
  --headless
```

- `SelectionTableQueue` 会把 Excel 当成队列处理：每次 `pop` 取出前 `batch_size` 条，剩余数据立即写回；失败时调用 `return_batch` 即可回滚到表头。
- `--interval` 控制批次间的等待秒数，适合人工在中途往 Excel 添补数据。
- `--archive/--no-archive` 控制是否把已处理批次归档到 `data/output/processed/`，方便稽核。
- 当选品表为空或 pandas 无法解析表格时，脚本会安全退出并给出日志提示。

## 🖥️ Web 管理面板 (零指令入口)

面向运营/质检等非技术角色，提供"上传文件 → 点击开始"的完整引导。

- **首次安装**：  
  - Windows：双击 `apps/temu-auto-publish/install_web_panel.bat`  
  - macOS：双击 `apps/temu-auto-publish/install_web_panel.command`
- **日常运行**：  
  - Windows：双击 `apps/temu-auto-publish/start_web_panel.bat`  
  - macOS：双击 `apps/temu-auto-publish/start_web_panel.command`
- **命令行方式**（如需自定义 host/port）：  
  ```bash
  uv run python apps/temu-auto-publish/web_panel/cli.py start --host 0.0.0.0 --port 9000
  ```

启动后浏览器会自动打开 Web UI，界面包含参数提示、进度状态、实时日志、环境自检按钮以及示例选品表下载链接，真正做到电脑小白也能独立操作。

- "仅运行一次流程" 开关默认开启，表示执行单轮完整 SOP。
- 关闭后 Web Panel 会进入守护模式：配合 `SelectionTableQueue` 自动循环取数、出错回滚、选品表归档，直到 Excel 空/格式异常。

## 🐳 Docker 容器化部署

使用 Docker 容器可以**固定配置和环境**，确保在任何机器上都能稳定运行。

### 环境要求

- Docker 20.10+
- Docker Compose 2.0+
- 至少 8GB 内存
- 至少 10GB 磁盘空间

### 快速启动

#### Windows

```batch
# 1. 构建镜像
docker\docker-start.bat build

# 2. 启动生产环境
docker\docker-start.bat prod

# 3. 访问 Web Panel
# http://localhost:8000
```

#### Linux / macOS

```bash
# 给脚本执行权限
chmod +x docker/docker-start.sh

# 构建并启动
./docker/docker-start.sh build
./docker/docker-start.sh prod
```

### 运行模式

| 模式 | 命令 | 说明 |
|------|------|------|
| 生产模式 | `docker-start prod` | 无界面，适合后台运行 |
| 调试模式 | `docker-start debug` | 带 VNC，可远程查看浏览器 |
| 停止服务 | `docker-start stop` | 停止所有容器 |

### 调试模式（VNC 可视化）

调试模式支持通过 VNC 远程查看浏览器界面：

```batch
docker\docker-start.bat debug
```

访问方式：
- **Web Panel**: http://localhost:8001
- **VNC (浏览器)**: http://localhost:6080/vnc.html
- **VNC (客户端)**: vnc://localhost:5900

### 常用 Docker 命令

```bash
# 查看日志
docker-compose logs -f

# 进入容器
docker-compose exec temu-app bash

# 在容器中运行工作流
docker-compose exec temu-app python main.py --input data/input/test.xlsx

# 重启服务
docker-compose restart
```

### 数据持久化

以下目录会自动挂载到主机，数据不会丢失：

| 主机目录 | 容器目录 | 用途 |
|---------|---------|------|
| `./data/input` | `/app/data/input` | 输入文件（Excel、图片） |
| `./data/output` | `/app/data/output` | 输出结果 |
| `./data/logs` | `/app/data/logs` | 日志文件 |
| `./data/workflow_states` | `/app/data/workflow_states` | 工作流状态 |
| `./config` | `/app/config` | 配置文件 |

> 📖 详细文档请参考 [Docker 部署指南](docs/DOCKER.md)

### Windows 下载即用打包

提供两种打包方式：

#### 方式一：单文件安装程序（推荐给用户）

创建包含所有依赖的单个 exe 安装程序，用户无需安装任何东西：

```batch
cd apps\temu-auto-publish

# 一键打包（生成 ~300MB 安装程序）
installer\build_all.bat
```

输出：
- `dist/TemuWebPanel_Setup_x.x.x.exe` - 安装程序
- `dist/TemuWebPanel_Portable.7z` - 便携版压缩包

> 详细说明请参考 [安装包构建指南](installer/README.md)

#### 方式二：轻量打包（需要用户有 Python 环境）

```bash
# 安装打包工具
uv pip install pyinstaller

# 运行打包
uv run python apps/temu-auto-publish/build_windows_exe.py
```

打包后的 `TemuWebPanel.exe` 支持双击即用：首次运行会自动打开浏览器指向 `http://127.0.0.1:8899`。

## 📁 项目结构

```
apps/temu-auto-publish/
├── src/
│   ├── browser/                     # 浏览器自动化核心（含 README.md、legacy/）
│   │   ├── browser_manager.py         # Playwright 生命周期与等待策略注入
│   │   ├── login_controller.py        # 妙手登录 + Cookie 管理
│   │   ├── collection_controller.py   # 采集/认领流程
│   │   ├── miaoshou_controller.py     # 妙手采集箱交互
│   │   ├── first_edit_controller.py   # 首次编辑弹窗
│   │   ├── batch_edit_controller.py   # 批量编辑 18 步（改进版主实现）
│   │   ├── publish_controller.py      # 店铺选择与供货价设置
│   │   ├── image_manager.py           # 媒体资源校验
│   │   ├── utils/                     # 智能等待、定位器、批量编辑辅助
│   │   └── legacy/                    # 旧版控制器（兼容参考）
│   ├── workflows/                 # 业务编排（含 README.md、legacy/）
│   │   ├── complete_publish_workflow.py # 最新完整工作流
│   │   ├── five_to_twenty_workflow.py   # 5→20 首次编辑+认领流程
│   │   └── legacy/                     # v1/v2 历史实现
│   ├── data_processor/            # 数据处理与生成（含 README.md）
│   │   ├── selection_table_reader.py    # 选品表解析与校验
│   │   ├── product_data_reader.py       # 工作流输入构建
│   │   ├── price_calculator.py          # 建议售价/供货价计算
│   │   ├── ai_title_generator.py        # AI 标题生成与回退
│   │   └── random_generator.py          # 物流信息随机化
│   ├── core/                      # 重试、健康检查、指标收集等核心能力
│   ├── models/                    # 数据模型定义（task/result 等）
│   └── utils/                     # 通用工具模块
├── config/                        # Pydantic Settings、浏览器与选择器配置
├── data/                          # 输入 CSV/Excel、媒体样本、调试产物
├── docker/                        # Docker 容器化相关文件
│   ├── docker-start.bat             # Windows 启动脚本
│   ├── docker-start.sh              # Linux/Mac 启动脚本
│   ├── build-exe.bat                # Windows exe 打包脚本
│   └── entrypoint-debug.sh          # 调试容器入口
├── docs/                          # 对外文档（使用指南、调试说明）
├── scripts/                       # 辅助脚本（如 update_ai_context、下载媒体）
├── tests/                         # pytest 用例（待对齐新版接口）
├── web_panel/                     # FastAPI Web 管理面板
├── Dockerfile                     # 生产环境镜像
├── Dockerfile.debug               # 调试环境镜像（含 VNC）
├── Dockerfile.windows             # Windows 打包镜像
├── docker-compose.yml             # 服务编排配置
├── .env.example                   # 环境变量模板
└── README.md                      # 本文件
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
    "window_width": 1280,
    "window_height": 720,
    "device_scale_factor": 1.0
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

- `device_scale_factor` 默认强制为 1.0 (标准 100% 缩放)。如果你在高分屏或非 1.0 缩放环境中录制了像素脚本, 可以修改 `browser_config.json`, 或者设置环境变量 `TEMU_BROWSER_DEVICE_SCALE_FACTOR` 来覆盖运行时缩放。`TEMU_PIXEL_REFERENCE_DPR` 依旧会同步为最终使用的缩放, 以便像素识别流程保持一致。

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

