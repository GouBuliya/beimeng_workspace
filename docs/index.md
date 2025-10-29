# Beimeng Workspace - 项目概览

欢迎使用 Beimeng Workspace！这是一个专为 AI Agent 开发优化的 Python Monorepo 脚手架。

## 项目概况

- **类型**: Python Monorepo
- **包管理**: uv
- **Python版本**: 3.12+
- **状态**: ✅ 已初始化并可用

## 快速命令

```bash
# 同步依赖
uv sync

# 运行示例 CLI
uv run python -m apps.cli.hello greet World

# 运行数据转换脚本
echo '{"data": ["hello"]}' | uv run python scripts/data_processing/transform/main.py

# 更新 AI 上下文
uv run python scripts/tools/update_ai_context.py

# 代码质量检查
uv run ruff check .
uv run ruff format .
uv run mypy .

# 运行测试
uv run pytest
```

## 目录说明

| 目录 | 说明 | 示例 |
|------|------|------|
| `.ai/` | AI Agent 专用机制 | context.json, schemas, prompts |
| `apps/` | 完整应用 | apps/cli/hello |
| `scripts/` | 独立脚本 | scripts/data_processing/transform |
| `packages/` | 可复用库 | packages/common |
| `docs/` | 项目文档 | guides, architecture |

## 核心特性

### 1. 结构化上下文 (.ai/context.json)
- 全局项目元数据
- 自动组件索引
- AI 可快速理解项目结构

### 2. 自文档化
每个组件包含：
- README.md（人类可读）
- .ai.json（AI 可解析）
- examples/（可执行示例）

### 3. 标准化接口
- CLI: Typer 框架
- I/O: JSON/YAML
- 配置: Pydantic Settings

## 创建新组件

### 新应用

```bash
mkdir -p apps/my-category/my-app
cd apps/my-category/my-app

# 复制模板
cp ../../../docs/templates/README.template.md README.md
cp ../../../docs/templates/.ai.template.json .ai.json

# 创建代码
touch __init__.py main.py __main__.py
mkdir examples

# 更新上下文
python ../../../scripts/tools/update_ai_context.py
```

### 新脚本

```bash
mkdir -p scripts/category/my-script
cd scripts/category/my-script

# 创建文件
cp ../../../docs/templates/README.template.md README.md
cp ../../../docs/templates/.ai.template.json .ai.json
touch main.py
mkdir examples

# 更新上下文
python ../../../scripts/tools/update_ai_context.py
```

## AI 开发工作流

1. **查看全局上下文**
   ```bash
   cat .ai/context.json
   ```

2. **理解组件**
   ```bash
   cat apps/cli/hello/.ai.json
   cat apps/cli/hello/README.md
   ```

3. **运行示例**
   ```bash
   python apps/cli/hello/examples/basic_usage.py
   ```

4. **使用组件**
   ```bash
   python -m apps.cli.hello greet World --format json
   ```

## 代码质量

项目配置了完整的代码质量工具：

- **Ruff**: 快速的 linter 和 formatter
- **MyPy**: 静态类型检查
- **Pytest**: 测试框架
- **Pre-commit**: Git hooks 自动检查

```bash
# 运行所有检查
uv run pre-commit run --all-files
```

## 文档

- [快速开始](docs/guides/quickstart.md)
- [AI 开发指南](docs/guides/ai-development.md)
- [项目架构](docs/architecture/structure.md)

## 已有组件

### 应用

1. **hello-cli** (apps/cli/hello/)
   - 简单的 CLI 工具示例
   - 展示最佳实践
   - 支持 JSON 输出

### 脚本

1. **data-transform** (scripts/data_processing/transform/)
   - 数据转换脚本
   - 支持管道操作
   - 演示标准化接口

### 包

1. **common** (packages/common/)
   - 通用工具库
   - logger, config 模块
   - 跨组件复用

## 开发规范

1. **文件限制**: 单个文件不超过 1000 行
2. **文档要求**: README + .ai.json + examples/
3. **类型安全**: 完整的类型提示
4. **标准接口**: JSON/YAML I/O
5. **测试覆盖**: 关键逻辑需要测试

## 获取帮助

- 查看 [快速开始指南](docs/guides/quickstart.md)
- 参考示例组件
- 查阅 [AI 开发指南](docs/guides/ai-development.md)
- 使用 `.ai/prompts/` 中的模板

## Git 工作流

```bash
# 创建分支
git checkout -b feature/my-feature

# 开发并提交
git add .
git commit -m "feat: add my feature"

# 推送
git push origin feature/my-feature
```

---

**项目已就绪！开始构建你的应用吧！** 🚀

