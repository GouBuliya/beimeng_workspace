# Beimeng Workspace

> AI-Friendly Python Monorepo - 一个为 AI Agent 开发优化的 Python 工作空间

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![uv](https://img.shields.io/badge/uv-latest-green.svg)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

## 概述

Beimeng Workspace 是一个现代化的 Python monorepo 脚手架，专门设计用于包含多种应用、脚本和文档的项目。它特别针对 **AI Agent 开发**进行了优化，提供了结构化上下文、自动发现和标准化接口。

### 核心特性

- 🚀 **使用 uv 管理** - 快速的包管理和环境隔离
- 🤖 **AI Agent 友好** - 结构化上下文、JSON Schema、自动发现机制
- 📦 **Monorepo 架构** - 统一管理多个应用、脚本和包
- 🔧 **工程化标准** - Ruff、MyPy、pre-commit hooks
- 📚 **完善的文档** - 每个组件都有详细的文档和示例
- 🎯 **最佳实践** - 展示现代 Python 开发的最佳实践

## 项目结构

```
beimeng_workspace/
├── .ai/                          # AI Agent 专用目录
│   ├── context.json              # 项目全局上下文
│   ├── schemas/                  # JSON Schema 定义
│   └── prompts/                  # Prompt 模板
├── apps/                         # 应用目录
│   ├── web/                      # Web 应用
│   └── cli/                      # CLI 工具
│       └── hello/                # 示例 CLI 应用
├── scripts/                      # 独立脚本
│   ├── automation/               # 自动化脚本
│   ├── data_processing/          # 数据处理脚本
│   │   └── transform/            # 示例转换脚本
│   └── tools/                    # 工具脚本
│       └── update_ai_context.py  # 更新 AI 上下文
├── packages/                     # 可复用的内部包
│   └── common/                   # 通用组件库
├── docs/                         # 文档
│   ├── architecture/             # 架构文档
│   ├── guides/                   # 指南
│   ├── templates/                # 文档模板
│   └── api/                      # API 文档
├── pyproject.toml                # 项目配置
├── mkdocs.yml                    # 文档配置
└── README.md                     # 本文件
```

## 快速开始

### 前置要求

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) - 推荐的包管理器

### 安装 uv

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# 或使用 pip
pip install uv
```

### 设置环境

```bash
# 克隆或进入项目目录
cd beimeng_workspace

# 同步依赖
uv sync

# 安装开发依赖
uv pip install -e ".[dev,docs]"

# 安装 pre-commit hooks
uv run pre-commit install
```

### 运行示例

```bash
# 运行 CLI 示例
uv run python -m apps.cli.hello greet World

# 运行数据转换脚本
uv run python scripts/data_processing/transform/main.py --help

# 更新 AI 上下文
uv run python scripts/tools/update_ai_context.py
```

## AI Agent 开发机制

本项目实现了三个核心的 AI-friendly 机制：

### 1. 结构化上下文系统

- **`.ai/context.json`**: 项目的全局元数据，包含所有组件的索引
- **自动发现**: 使用 `update_ai_context.py` 自动扫描和更新组件信息
- **统一视图**: AI Agent 可以快速了解项目的整体结构

```bash
# 更新上下文
uv run python scripts/tools/update_ai_context.py
```

### 2. 自文档化规范

每个组件都必须包含：

- `README.md` - 人类可读的详细文档
- `.ai.json` - AI 可解析的结构化元数据（遵循 JSON Schema）
- `examples/` - 可执行的使用示例
- Google Style docstrings - 完整的 API 文档

示例 `.ai.json`:

```json
{
  "$schema": "../../.ai/schemas/component.schema.json",
  "name": "my-component",
  "type": "app",
  "version": "0.1.0",
  "description": "组件描述",
  "interface": {
    "cli": {...},
    "input": {...},
    "output": {...}
  },
  "examples": [...],
  "ai_hints": {
    "common_use_cases": [...],
    "gotchas": [...]
  }
}
```

### 3. 标准化接口设计

- **CLI**: 统一使用 Typer 框架
- **输入输出**: 标准 JSON/YAML 格式
- **配置**: Pydantic Settings 管理
- **类型安全**: 完整的类型提示和验证

## 开发指南

### 创建新组件

使用文档模板：

```bash
# 查看模板
ls docs/templates/

# README 模板
docs/templates/README.template.md

# .ai.json 模板
docs/templates/.ai.template.json
```

### 代码质量

```bash
# 格式化代码
uv run ruff format .

# Lint 检查
uv run ruff check .

# 类型检查
uv run mypy .

# 运行所有检查（pre-commit）
uv run pre-commit run --all-files
```

### 测试

```bash
# 运行测试
uv run pytest

# 带覆盖率
uv run pytest --cov

# 只测试特定组件
uv run pytest apps/cli/hello/tests/
```

### 文档

```bash
# 生成 API 文档
uv run pdoc --html --output-dir docs/api .

# 启动文档服务器
uv run mkdocs serve

# 构建文档
uv run mkdocs build
```

## 开发规范

1. **单个文件不超过 1000 行** - 保持代码模块化
2. **小步快跑，步步验证** - 频繁测试和验证
3. **完整的文档** - 每个组件都要有完善的文档
4. **类型安全** - 使用类型提示和 Pydantic 验证
5. **Git 保存进度** - 经常提交，保持清晰的历史

## 工具和技术栈

- **包管理**: [uv](https://github.com/astral-sh/uv)
- **Linting/Formatting**: [Ruff](https://github.com/astral-sh/ruff)
- **类型检查**: [MyPy](https://mypy.readthedocs.io/)
- **测试**: [Pytest](https://pytest.org/)
- **CLI 框架**: [Typer](https://typer.tiangolo.com/)
- **配置管理**: [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- **日志**: [Loguru](https://github.com/Delgan/loguru)
- **文档**: [MkDocs](https://www.mkdocs.org/) + [pdoc](https://pdoc.dev/)

## 示例项目

- **apps/cli/hello**: 简单的 CLI 工具示例
- **scripts/data_processing/transform**: 数据转换脚本
- **packages/common**: 通用组件库

## 贡献指南

1. Fork 本项目
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

## 许可证

MIT License

## 链接

- [文档](docs/)
- [架构设计](docs/architecture/)
- [开发指南](docs/guides/)
- [AI Agent 开发指南](docs/guides/ai-development.md)

