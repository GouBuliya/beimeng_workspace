# AI Agent 开发指南

本指南详细说明如何在 Beimeng Workspace 中进行 AI Agent 友好的开发。

## AI Agent 开发的三大核心机制

### 1. 结构化上下文系统

#### 全局上下文 (.ai/context.json)

项目的全局元数据文件，AI Agent 可以通过它快速了解整个项目：

```json
{
  "version": "1.0.0",
  "project": {
    "name": "beimeng-workspace",
    "description": "项目描述",
    "structure": "monorepo"
  },
  "components": {
    "apps": [...],
    "scripts": [...],
    "packages": [...]
  },
  "conventions": {...},
  "ai_features": {...}
}
```

**优势**：
- AI 可以一次性了解所有组件
- 自动发现新组件
- 追踪组件间依赖关系

#### 自动更新工具

```bash
# 扫描项目并更新 context.json
python scripts/tools/update_ai_context.py
```

**何时运行**：
- 创建新组件后
- 修改组件元数据后
- 添加新依赖后

### 2. 自文档化规范

#### 必需文件

每个组件必须包含以下文件：

1. **README.md** - 人类可读文档
   - 概述和用途
   - 安装和依赖
   - 使用方法和示例
   - 配置说明
   - API 文档

2. **.ai.json** - AI 可解析元数据
   - 遵循 JSON Schema
   - 定义接口（CLI/API）
   - 提供示例
   - AI 提示（ai_hints）

3. **examples/** - 可执行示例
   - 至少一个可运行的示例
   - 展示常见用例
   - 可以直接复制使用

4. **Docstrings** - Google Style
   - 所有函数和类
   - 包含 Args, Returns, Raises
   - 提供 Examples

#### .ai.json 结构

```json
{
  "$schema": "../../.ai/schemas/component.schema.json",
  "name": "component-name",
  "type": "app|script|package|tool",
  "version": "0.1.0",
  "description": "简短描述",
  "purpose": "详细用途说明",
  "entry_point": "main.py",
  "interface": {
    "cli": {
      "command": "python -m ...",
      "arguments": [...],
      "options": {...}
    },
    "input": {
      "format": "json",
      "schema": {...}
    },
    "output": {
      "format": "json",
      "schema": {...}
    }
  },
  "dependencies": {...},
  "examples": [...],
  "tags": [...],
  "ai_hints": {
    "common_use_cases": [...],
    "gotchas": [...],
    "related_components": [...]
  }
}
```

**关键字段说明**：

- `interface`: 定义如何使用组件
- `examples`: 提供具体的使用示例
- `ai_hints`: 给 AI Agent 的额外提示
  - `common_use_cases`: 常见使用场景
  - `gotchas`: 需要注意的事项
  - `related_components`: 相关组件

### 3. 标准化接口设计

#### CLI 规范

使用 **Typer** 框架：

```python
import typer
from typing import Optional
from pathlib import Path

app = typer.Typer()

@app.command()
def main(
    input_file: Path = typer.Argument(..., help="输入文件"),
    output: Optional[Path] = typer.Option(None, "--output", "-o"),
    format: str = typer.Option("json", "--format", "-f"),
) -> None:
    """命令描述"""
    pass

if __name__ == "__main__":
    app()
```

**优势**：
- 自动生成帮助文档
- 类型验证
- 一致的用户体验

#### 输入输出规范

**优先使用 JSON/YAML**：

```python
from pydantic import BaseModel

class InputData(BaseModel):
    """输入数据模型"""
    field1: str
    field2: int

class OutputData(BaseModel):
    """输出数据模型"""
    result: str
    status: str

# 读取
input_data = InputData(**json.load(sys.stdin))

# 输出
output = OutputData(result="success", status="ok")
print(output.model_dump_json(indent=2))
```

**优势**：
- AI 可以轻松解析
- 适合管道操作
- 类型安全

#### 配置管理

使用 **Pydantic Settings**：

```python
from pydantic import Field
from pydantic_settings import BaseSettings

class AppConfig(BaseSettings):
    """应用配置"""
    api_key: str = Field(..., description="API密钥")
    timeout: int = Field(default=30)
    
    class Config:
        env_prefix = "APP_"
        env_file = ".env"

config = AppConfig()
```

**优势**：
- 环境变量支持
- 类型验证
- .env 文件支持

## 最佳实践

### 1. 创建新组件的流程

```bash
# 1. 创建目录结构
mkdir -p apps/my-app
cd apps/my-app

# 2. 从模板开始
cp ../../docs/templates/README.template.md README.md
cp ../../docs/templates/.ai.template.json .ai.json

# 3. 填写模板内容

# 4. 创建主代码
touch main.py

# 5. 创建示例
mkdir examples
touch examples/basic_usage.py

# 6. 更新 AI 上下文
python ../../scripts/tools/update_ai_context.py

# 7. 验证
python -m apps.my_app --help
```

### 2. 使用 Prompt 模板

查看 `.ai/prompts/` 目录中的模板：

```bash
# 创建组件时
cat .ai/prompts/create_component.md

# 代码审查时
cat .ai/prompts/code_review.md
```

### 3. 保持文档同步

使用 pre-commit hooks：

```yaml
# .pre-commit-config.yaml
- repo: https://github.com/python-jsonschema/check-jsonschema
  hooks:
    - id: check-jsonschema
      name: Validate .ai.json files
      files: \.ai\.json$
      args: [--schemafile, .ai/schemas/component.schema.json]
```

### 4. 编写 AI-Friendly 代码

**DO ✅**:

```python
def process_data(data: list[str], operation: str) -> dict[str, Any]:
    """处理数据
    
    Args:
        data: 输入数据列表
        operation: 操作类型 (uppercase|lowercase|reverse)
        
    Returns:
        包含结果和元数据的字典
        
    Examples:
        >>> process_data(["hello"], "uppercase")
        {'result': ['HELLO'], 'count': 1}
    """
    # 实现...
```

**DON'T ❌**:

```python
def process(d, op):  # 没有类型提示和文档
    # 没有注释
    return [x.upper() for x in d]
```

## AI Agent 工作流

### 发现组件

```bash
# AI 读取全局上下文
cat .ai/context.json

# 找到感兴趣的组件
jq '.components.apps[] | select(.name == "hello-cli")' .ai/context.json
```

### 理解组件

```bash
# 读取 AI 元数据
cat apps/cli/hello/.ai.json

# 查看人类文档
cat apps/cli/hello/README.md

# 运行示例
python apps/cli/hello/examples/basic_usage.py
```

### 使用组件

```bash
# 根据 .ai.json 中的 interface 调用
python -m apps.cli.hello greet "World" --format json
```

## 工具和辅助

### JSON Schema 验证

```bash
# 安装验证工具
uv pip install check-jsonschema

# 验证 .ai.json
check-jsonschema --schemafile .ai/schemas/component.schema.json apps/cli/hello/.ai.json
```

### 自动生成文档

```bash
# API 文档
uv run pdoc --html --output-dir docs/api .

# MkDocs 文档
uv run mkdocs serve
```

### 更新依赖

```bash
# 添加依赖到 pyproject.toml，然后
uv sync
```

## 常见问题

### Q: 为什么要用 .ai.json？

A: 它提供了一个机器可读的接口定义，让 AI Agent 可以：
- 快速理解组件功能
- 知道如何调用
- 获取使用示例
- 了解常见陷阱

### Q: 如何保持文档同步？

A: 
1. 使用 pre-commit hooks 验证
2. 在 CI 中检查
3. 定期运行 `update_ai_context.py`

### Q: .ai.json 是否会变得冗长？

A: 适度的详细程度是好的。重点关注：
- 清晰的接口定义
- 实用的示例
- 有价值的 ai_hints

## 总结

AI-Friendly 开发的核心是：

1. **结构化** - 使用 JSON Schema 定义清晰的结构
2. **可发现** - 自动索引和上下文系统
3. **标准化** - 一致的接口和格式
4. **文档化** - 人类和机器都能理解

遵循这些原则，你的代码将更容易被 AI Agent 理解和使用！

