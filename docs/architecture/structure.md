# 项目架构

## 概述

Beimeng Workspace 采用 **Monorepo** 架构，所有应用、脚本和包都在一个统一的代码仓库中。

## 目录结构说明

### `.ai/` - AI Agent 专用目录

核心的 AI 友好机制所在地：

- **context.json**: 项目的全局元数据和组件索引
- **schemas/**: JSON Schema 定义
  - `context.schema.json`: 全局上下文的 schema
  - `component.schema.json`: 组件元数据的 schema
- **prompts/**: AI 交互的 prompt 模板
  - `create_component.md`: 创建组件的指导
  - `code_review.md`: 代码审查清单

### `apps/` - 应用目录

完整的应用程序，可能包含多个模块：

- **web/**: Web 应用（FastAPI, Django 等）
- **cli/**: 命令行工具（Typer）
  - `hello/`: 示例 CLI 应用

**规范**：
- 每个应用有独立目录
- 包含 README.md, .ai.json, examples/
- 可以作为 Python 模块运行

### `scripts/` - 脚本目录

独立的脚本文件，通常是单一用途：

- **automation/**: 自动化脚本
- **data_processing/**: 数据处理脚本
  - `transform/`: 数据转换示例
- **tools/**: 工具脚本
  - `update_ai_context.py`: 更新 AI 上下文

**规范**：
- 可以是单个文件或目录
- 相关脚本放在同一子目录
- 提供清晰的 CLI 接口

### `packages/` - 内部包

可复用的库和组件：

- **common/**: 通用组件
  - `logger.py`: 日志配置
  - `config.py`: 配置管理
  - `utils.py`: 工具函数

**规范**：
- 作为库被其他组件导入
- 不应包含应用逻辑
- 保持通用性和可复用性

### `docs/` - 文档

项目文档：

- **architecture/**: 架构文档
- **guides/**: 使用指南
- **templates/**: 文档模板
- **api/**: 自动生成的 API 文档

## 依赖关系

```
apps/cli/hello
    ↓ 导入
packages/common
    ↓ 使用
第三方包 (typer, pydantic, etc.)
```

**原则**：
- Apps 可以导入 packages
- Scripts 可以导入 packages
- Packages 之间可以相互导入（避免循环）
- 不允许反向依赖（packages 不导入 apps/scripts）

## 配置文件

### `pyproject.toml`

核心配置文件，包含：
- 项目元数据
- 依赖声明
- 工具配置（ruff, mypy, pytest）

### `mkdocs.yml`

文档站点配置：
- 主题和外观
- 导航结构
- 插件配置

### `.pre-commit-config.yaml`

Git hooks 配置：
- 代码格式化
- Lint 检查
- JSON Schema 验证

## 数据流

```
输入 (JSON/YAML)
    ↓
验证 (Pydantic)
    ↓
处理 (业务逻辑)
    ↓
输出 (JSON/YAML)
```

所有组件遵循统一的数据流模式。

## 扩展性

### 添加新应用

```bash
mkdir -p apps/my-new-app
# 添加 README.md, .ai.json, main.py, examples/
python scripts/tools/update_ai_context.py
```

### 添加新脚本

```bash
mkdir -p scripts/category/my-script
# 添加必需文件
python scripts/tools/update_ai_context.py
```

### 添加新包

```bash
mkdir -p packages/my-package
# 添加 __init__.py 和模块文件
```

## 工程化实践

### 代码质量

- **Ruff**: 快速的 linting 和 formatting
- **MyPy**: 静态类型检查
- **Pytest**: 单元测试和集成测试
- **Pre-commit**: 提交前自动检查

### 文档

- **MkDocs**: 用户文档和指南
- **pdoc**: API 文档自动生成
- **Docstrings**: Google Style

### 版本管理

- **语义化版本**: MAJOR.MINOR.PATCH
- **Git**: 清晰的提交历史
- **标签**: 标记重要版本

## 性能考虑

- 单个文件不超过 1000 行
- 模块化设计，按需加载
- 使用 uv 快速安装和管理依赖
- 异步操作使用 asyncio

## 安全性

- 不在代码中硬编码密钥
- 使用 .env 文件管理敏感配置
- pre-commit hooks 检测私钥泄漏
- 依赖定期更新

