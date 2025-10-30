# MCP File Info - 文件元信息工具

一个强大的 MCP（Model Context Protocol）工具，用于提取和解析源代码文件头部的元数据注释。

## 功能特性

- ✅ 支持多种编程语言（Python, TypeScript, JavaScript, Java, C++, Go, Rust 等）
- ✅ 标准化的元信息协议
- ✅ 灵活的字段定义系统
- ✅ 完整的类型提示和验证
- ✅ 易于集成的 MCP 服务器
- ✅ 批量文件处理能力

## 快速开始

### 安装依赖

```bash
# 在项目根目录
uv pip install pydantic pydantic-settings mcp
```

### 基本使用

#### 作为 Python 库使用

```python
from packages.mcp_file_info import FileInfoParser

# 创建解析器
parser = FileInfoParser()

# 解析单个文件
metadata = parser.parse_file("example.py")

# 检查是否包含元信息
if metadata.has_metadata:
    print(f"目的: {metadata.get_field('PURPOSE')}")
    print(f"大纲: {metadata.get_field('OUTLINE')}")
    
# 批量解析
results = parser.parse_multiple_files([
    "file1.py",
    "file2.ts",
    "file3.go"
])
```

#### 作为 MCP 服务器使用

```bash
# 启动 MCP 服务器
python -m packages.mcp_file_info.mcp_server
```

在 Cursor 或其他 MCP 客户端中配置：

```json
{
  "mcpServers": {
    "file-info": {
      "command": "python",
      "args": ["-m", "packages.mcp_file_info.mcp_server"],
      "cwd": "/path/to/beimeng_workspace"
    }
  }
}
```

## 文件元信息协议

### 协议概述

所有源代码文件应在文件最开始包含元信息注释块，使用特定关键字标记不同类型的信息。

### 支持的字段

| 字段 | 必填 | 说明 |
|------|------|------|
| `@PURPOSE:` | ✅ | 文件的核心作用和功能 |
| `@OUTLINE:` | ✅ | 文件的结构大纲 |
| `@GOTCHAS:` | ❌ | 易出错点、注意事项 |
| `@TECH_DEBT:` | ❌ | 已知的技术债务 |
| `@DEPENDENCIES:` | ❌ | 关键依赖关系 |
| `@CHANGELOG:` | ❌ | 重要修改历史 |
| `@AUTHOR:` | ❌ | 作者信息 |
| `@RELATED:` | ❌ | 相关文件引用 |

### 格式示例

#### Python 文件

```python
"""
@PURPOSE: 实现用户认证和授权功能
@OUTLINE:
  - class AuthService: 主认证服务类
  - def login(username, password): 用户登录
  - def verify_token(token): 验证JWT令牌
@GOTCHAS:
  - 密码必须在存储前进行哈希处理
  - Token过期时间为24小时，需要定期刷新
@TECH_DEBT:
  - TODO: 添加多因素认证支持
  - TODO: 实现OAuth2.0集成
@DEPENDENCIES:
  - 内部: packages.common.logger, packages.common.config
  - 外部: jwt, bcrypt
@RELATED: user_service.py, permission_manager.py
"""

# 代码开始...
```

#### TypeScript 文件

```typescript
/**
 * @PURPOSE: 实现前端路由管理和导航守卫
 * @OUTLINE:
 *   - class Router: 核心路由管理器
 *   - function setupGuards(): 配置导航守卫
 *   - function handleNavigation(): 处理路由跳转
 * @GOTCHAS:
 *   - 路由守卫必须返回boolean或Promise<boolean>
 *   - 避免在守卫中进行重定向循环
 * @DEPENDENCIES:
 *   - 外部: vue-router, pinia
 */

// 代码开始...
```

## MCP 工具

### 1. get_file_metadata

获取文件的全部元信息。

**参数：**
- `file_path` (string): 文件路径

**返回：**
```json
{
  "file_path": "example.py",
  "has_metadata": true,
  "is_complete": true,
  "fields": {
    "PURPOSE": "实现用户认证和授权功能",
    "OUTLINE": "- class AuthService: 主认证服务类\n- def login(username, password): 用户登录",
    "GOTCHAS": "密码必须在存储前进行哈希处理"
  }
}
```

### 2. get_specific_metadata

获取文件的特定元信息字段。

**参数：**
- `file_path` (string): 文件路径
- `fields` (array): 要获取的字段名称列表

**示例：**
```json
{
  "file_path": "example.py",
  "fields": ["PURPOSE", "DEPENDENCIES"]
}
```

**返回：**
```json
{
  "file_path": "example.py",
  "has_metadata": true,
  "requested_fields": ["PURPOSE", "DEPENDENCIES"],
  "fields": {
    "PURPOSE": "实现用户认证和授权功能",
    "DEPENDENCIES": "内部: packages.common.logger\n外部: jwt, bcrypt"
  }
}
```

## 支持的语言

| 语言 | 文件扩展名 | 注释语法 |
|------|-----------|---------|
| Python | .py | `"""` 或 `#` |
| JavaScript | .js, .jsx | `/* */` 或 `//` |
| TypeScript | .ts, .tsx | `/* */` 或 `//` |
| Java | .java | `/* */` 或 `//` |
| C/C++ | .c, .cpp, .h, .hpp | `/* */` 或 `//` |
| Go | .go | `/* */` 或 `//` |
| Rust | .rs | `/* */` 或 `//` |
| Ruby | .rb | `=begin...=end` 或 `#` |
| Shell | .sh, .bash | `#` |
| YAML | .yaml, .yml | `#` |
| HTML/XML | .html, .xml | `<!-- -->` |
| CSS/SCSS | .css, .scss | `/* */` |

## 配置

可以通过环境变量配置解析器行为：

```bash
# 最大读取行数（默认100）
export MCP_FILEINFO_MAX_LINES_TO_READ=200

# 是否移除注释标记（默认true）
export MCP_FILEINFO_STRIP_COMMENT_MARKERS=true

# 是否规范化空白字符（默认true）
export MCP_FILEINFO_NORMALIZE_WHITESPACE=true
```

或在代码中配置：

```python
from packages.mcp_file_info import FileInfoParser, ParserConfig

config = ParserConfig(
    max_lines_to_read=200,
    strip_comment_markers=True,
    normalize_whitespace=True
)

parser = FileInfoParser(config=config)
```

## API 文档

### FileInfoParser

主解析器类。

**方法：**

- `parse_file(file_path: str | Path) -> FileMetadata`
  - 解析单个文件并返回元信息
  
- `parse_multiple_files(file_paths: list[str | Path]) -> dict[str, FileMetadata]`
  - 批量解析多个文件

### FileMetadata

元信息数据模型。

**属性：**
- `file_path: str` - 文件路径
- `has_metadata: bool` - 是否包含元信息
- `fields: dict[str, str]` - 元信息字段字典
- `raw_content: str` - 原始注释内容
- `error: str | None` - 错误信息

**方法：**
- `get_field(field_name: str) -> str` - 获取单个字段
- `get_fields(field_names: list[str]) -> dict[str, str]` - 获取多个字段
- `is_complete() -> bool` - 检查必填字段是否完整
- `missing_required_fields() -> list[str]` - 获取缺失的必填字段

## 最佳实践

1. **始终包含必填字段**：确保所有文件都有 `@PURPOSE` 和 `@OUTLINE`

2. **保持 PURPOSE 简洁**：用1-2句话说明核心功能即可

3. **OUTLINE 要具体**：列出主要的类、函数、导出内容

4. **及时更新元信息**：当文件结构发生重大变化时更新元信息

5. **使用 GOTCHAS 记录陷阱**：帮助其他开发者避免常见错误

6. **记录技术债务**：使用 TECH_DEBT 字段跟踪待优化项

## 测试

```bash
# 运行所有测试
pytest packages/mcp-file-info/tests/

# 运行特定测试
pytest packages/mcp-file-info/tests/test_parser.py

# 查看测试覆盖率
pytest --cov=packages/mcp-file-info --cov-report=html
```

## 故障排除

### 文件无法识别

确认文件扩展名是否在支持列表中。可以通过以下方式查看：

```python
from packages.mcp_file_info import SUPPORTED_EXTENSIONS
print(SUPPORTED_EXTENSIONS)
```

### 元信息未被解析

1. 检查元信息注释是否在文件最开始（前100行内）
2. 确认使用了正确的注释语法
3. 确认字段名称拼写正确（必须大写）
4. 确认字段名后有冒号 `:`

### MCP 服务器无法启动

1. 确认安装了 mcp 包：`pip install mcp`
2. 检查 Python 路径是否正确
3. 查看服务器日志获取详细错误信息

## 贡献

欢迎提交 Issue 和 Pull Request！

## 许可证

MIT License

