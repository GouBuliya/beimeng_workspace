# 快速开始

本指南将帮助你快速上手 Beimeng Workspace。

## 前置要求

- Python 3.12 或更高版本
- [uv](https://github.com/astral-sh/uv) 包管理器

## 安装 uv

### macOS/Linux

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Windows

```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 使用 pip

```bash
pip install uv
```

## 初始化项目

```bash
# 进入项目目录
cd beimeng_workspace

# 同步依赖
uv sync

# 安装开发依赖
uv pip install -e ".[dev,docs]"

# 安装 pre-commit hooks
uv run pre-commit install
```

## 验证安装

```bash
# 检查 Python 版本
python --version

# 运行示例 CLI
uv run python -m apps.cli.hello greet World
# 输出: Hello, World!

# 运行数据转换脚本
echo '{"data": ["hello", "world"]}' | uv run python scripts/data_processing/transform/main.py
```

## 第一个应用

### 1. 创建目录结构

```bash
# 创建新的 CLI 应用
mkdir -p apps/cli/my-first-app
cd apps/cli/my-first-app
```

### 2. 从模板开始

```bash
# 复制模板
cp ../../../docs/templates/README.template.md README.md
cp ../../../docs/templates/.ai.template.json .ai.json

# 创建代码文件
touch __init__.py
touch main.py
mkdir examples
```

### 3. 编写代码

创建 `main.py`:

```python
#!/usr/bin/env python3
"""我的第一个应用"""

import typer
from rich.console import Console

app = typer.Typer()
console = Console()

@app.command()
def hello(name: str) -> None:
    """向某人问好"""
    console.print(f"你好, {name}!")

if __name__ == "__main__":
    app()
```

创建 `__main__.py`:

```python
from apps.cli.my_first_app.main import app

if __name__ == "__main__":
    app()
```

### 4. 更新元数据

编辑 `.ai.json`，填写组件信息。

### 5. 测试运行

```bash
# 运行应用
python -m apps.cli.my_first_app hello "World"

# 更新 AI 上下文
python ../../../scripts/tools/update_ai_context.py
```

## 第一个脚本

### 1. 创建脚本

```bash
mkdir -p scripts/automation/hello-script
cd scripts/automation/hello-script
```

### 2. 创建主文件

```python
#!/usr/bin/env python3
"""简单的自动化脚本"""

import json
import sys
from pydantic import BaseModel

class Input(BaseModel):
    message: str

class Output(BaseModel):
    result: str
    status: str

def main():
    # 从 stdin 读取 JSON
    data = json.load(sys.stdin)
    input_data = Input(**data)
    
    # 处理
    result = f"Processed: {input_data.message}"
    
    # 输出 JSON
    output = Output(result=result, status="success")
    print(output.model_dump_json(indent=2))

if __name__ == "__main__":
    main()
```

### 3. 测试

```bash
echo '{"message": "Hello"}' | python main.py
```

## 常用命令

### 代码质量

```bash
# 格式化代码
uv run ruff format .

# Lint 检查
uv run ruff check .

# 修复 lint 问题
uv run ruff check --fix .

# 类型检查
uv run mypy .

# 运行所有检查
uv run pre-commit run --all-files
```

### 测试

```bash
# 运行所有测试
uv run pytest

# 带覆盖率报告
uv run pytest --cov

# 测试特定文件
uv run pytest apps/cli/hello/tests/
```

### 文档

```bash
# 启动文档服务器（实时预览）
uv run mkdocs serve

# 构建文档
uv run mkdocs build

# 生成 API 文档
uv run pdoc --html --output-dir docs/api .
```

### AI 上下文

```bash
# 更新全局上下文
uv run python scripts/tools/update_ai_context.py

# 查看上下文
cat .ai/context.json | jq .
```

## 开发工作流

### 标准流程

1. **创建分支**
   ```bash
   git checkout -b feature/my-feature
   ```

2. **开发**
   - 编写代码
   - 添加文档
   - 创建测试

3. **验证**
   ```bash
   uv run ruff format .
   uv run ruff check --fix .
   uv run mypy .
   uv run pytest
   ```

4. **更新上下文**
   ```bash
   uv run python scripts/tools/update_ai_context.py
   ```

5. **提交**
   ```bash
   git add .
   git commit -m "feat: add my feature"
   ```

6. **推送**
   ```bash
   git push origin feature/my-feature
   ```

## 故障排除

### uv sync 失败

```bash
# 清除缓存
uv cache clean

# 重新同步
uv sync
```

### 导入错误

确保在项目根目录运行：

```bash
# 设置 PYTHONPATH
export PYTHONPATH=.

# 或使用 uv run
uv run python -m your.module
```

### pre-commit 失败

```bash
# 手动运行检查
uv run pre-commit run --all-files

# 跳过 hooks（不推荐）
git commit --no-verify
```

## 下一步

- 阅读 [AI Agent 开发指南](ai-development.md)
- 查看 [项目架构](../architecture/structure.md)
- 探索 [示例项目](../../apps/cli/hello/)
- 学习 [最佳实践](conventions.md)

## 获取帮助

- 查看文档: `docs/`
- 查看示例: `apps/cli/hello/`, `scripts/data_processing/transform/`
- 查看 prompt 模板: `.ai/prompts/`

