# Common Package

> 可复用的通用组件和工具库

## 概述

这个包包含项目中多个组件共享的通用功能，包括：

- 日志配置
- 配置管理基类
- 通用工具函数
- 数据验证模型

## 模块

### `logger.py`
统一的日志配置和管理

### `config.py`
配置管理基类和工具

### `models.py`
通用的 Pydantic 模型

### `utils.py`
通用工具函数

## 使用

```python
from packages.common.logger import setup_logger
from packages.common.config import BaseAppConfig

# 设置日志
logger = setup_logger("my_app")

# 使用配置基类
class MyConfig(BaseAppConfig):
    api_key: str
```

