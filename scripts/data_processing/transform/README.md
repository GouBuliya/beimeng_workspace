# 数据处理脚本示例

> 展示如何创建符合规范的数据处理脚本

## 概述

这是一个简单的数据处理脚本示例，展示：

- 标准化的输入输出（JSON/YAML）
- Pydantic 数据验证
- 完整的错误处理
- 结构化日志
- AI-friendly 接口

## 使用方法

```bash
# 处理 JSON 数据
python scripts/data_processing/transform/main.py --input data.json --output result.json

# 使用标准输入/输出
cat data.json | python scripts/data_processing/transform/main.py | jq .
```

## 配置

### 环境变量

- `TRANSFORM_LOG_LEVEL`: 日志级别（默认: INFO）

## 示例

查看 `examples/` 目录。

