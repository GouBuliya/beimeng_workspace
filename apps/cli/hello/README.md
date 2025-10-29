# Hello CLI

> 一个简单的 CLI 工具示例，展示最佳实践

## 概述

这是一个示例 CLI 应用，展示如何在 beimeng-workspace 中创建符合规范的命令行工具。它演示了：

- 使用 Typer 构建 CLI
- Pydantic 配置管理
- 完整的类型提示
- Google Style docstring
- JSON/YAML 输入输出
- 日志记录

## 特性

- 支持 JSON 和文本输出格式
- 完整的错误处理
- 结构化日志
- AI-friendly 接口设计

## 使用方法

### 基础用法

```bash
# 简单问候
python -m apps.cli.hello greet "World"

# JSON 输出
python -m apps.cli.hello greet "World" --format json

# 从配置文件读取
python -m apps.cli.hello greet "World" --config config.yaml
```

### API 用法

```python
from apps.cli.hello.main import greet_user

result = greet_user("World", greeting="Hello")
print(result)
```

## 配置

### 环境变量

- `HELLO_DEFAULT_GREETING`: 默认问候语（默认: "Hello"）
- `HELLO_LOG_LEVEL`: 日志级别（默认: "INFO"）

### 配置文件

```yaml
# config.yaml
greeting: "你好"
format: "json"
```

## 示例

查看 `examples/` 目录获取更多示例。

## 开发

```bash
# 运行
python -m apps.cli.hello greet "World"

# 测试
pytest apps/cli/hello/tests/

# 类型检查
mypy apps/cli/hello/
```

