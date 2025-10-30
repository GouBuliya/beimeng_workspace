# MCP 服务器配置指南

## 安装依赖

首先需要安装 MCP Python SDK：

```bash
pip install mcp
# 或使用 uv
uv pip install mcp
```

## Cursor MCP 配置

### 方法 1: 使用启动脚本（推荐）

在 Cursor 的 MCP 配置文件中添加：

```json
{
  "mcpServers": {
    "file-info": {
      "command": "python3",
      "args": [
        "/Users/candy/beimeng_workspace/packages/mcp_file_info/run_server.py"
      ]
    }
  }
}
```

### 方法 2: 直接使用 Python 模块

```json
{
  "mcpServers": {
    "file-info": {
      "command": "python3",
      "args": [
        "-c",
        "import sys; sys.path.insert(0, '/Users/candy/beimeng_workspace'); from packages.mcp_file_info.mcp_server import main; import asyncio; asyncio.run(main())"
      ]
    }
  }
}
```

### 方法 3: 使用环境变量

```json
{
  "mcpServers": {
    "file-info": {
      "command": "python3",
      "args": ["-m", "packages.mcp_file_info.mcp_server"],
      "cwd": "/Users/candy/beimeng_workspace",
      "env": {
        "PYTHONPATH": "/Users/candy/beimeng_workspace"
      }
    }
  }
}
```

## 验证配置

### 1. 测试服务器导入

```bash
cd /Users/candy/beimeng_workspace
python3 packages/mcp_file_info/run_server.py
```

如果成功，服务器将等待 stdio 输入（这是正常的，按 Ctrl+C 退出）。

### 2. 手动测试 MCP 工具

创建测试脚本 `test_mcp_tools.py`：

```python
import sys
sys.path.insert(0, '/Users/candy/beimeng_workspace')

from packages.mcp_file_info.parser import FileInfoParser

parser = FileInfoParser()

# 模拟 MCP 工具调用
file_path = "packages/mcp_file_info/examples/sample_files/example.py"
metadata = parser.parse_file(file_path)

print("get_file_metadata 响应:")
print({
    "file_path": metadata.file_path,
    "has_metadata": metadata.has_metadata,
    "fields": metadata.fields,
    "is_complete": metadata.is_complete()
})

print("\nget_specific_metadata 响应:")
print({
    "file_path": metadata.file_path,
    "requested_fields": ["PURPOSE", "DEPENDENCIES"],
    "fields": metadata.get_fields(["PURPOSE", "DEPENDENCIES"])
})
```

## 在 Cursor 中使用

配置完成后，在 Cursor 中你可以：

### 1. 获取文件全部元信息

```
使用 get_file_metadata 工具
参数: { "file_path": "path/to/your/file.py" }
```

### 2. 获取特定字段

```
使用 get_specific_metadata 工具
参数: {
  "file_path": "path/to/your/file.py",
  "fields": ["PURPOSE", "OUTLINE", "DEPENDENCIES"]
}
```

## 故障排除

### 问题: ModuleNotFoundError: No module named 'packages'

**原因**: Python 无法找到 packages 模块

**解决方案**:
1. 使用 `run_server.py` 启动脚本（推荐）
2. 设置 PYTHONPATH 环境变量
3. 使用完整路径的 Python 命令

### 问题: ModuleNotFoundError: No module named 'mcp'

**原因**: MCP SDK 未安装

**解决方案**:
```bash
pip install mcp
```

### 问题: 服务器启动后立即退出

**原因**: MCP 服务器需要通过 stdio 协议通信

**解决方案**: 这是正常行为。服务器会等待来自 Cursor 的连接。

## 配置文件位置

Cursor MCP 配置文件通常位于：

- macOS: `~/Library/Application Support/Cursor/User/globalStorage/anysphere.cursor-mcp/settings.json`
- Linux: `~/.config/Cursor/User/globalStorage/anysphere.cursor-mcp/settings.json`
- Windows: `%APPDATA%\Cursor\User\globalStorage\anysphere.cursor-mcp\settings.json`

## 日志调试

查看 MCP 服务器日志：

- 在 Cursor 中打开 MCP 日志面板
- 查看 `anysphere.cursor-mcp.MCP user-file-info` 输出
- 检查错误消息

## 无 MCP 依赖使用

如果不需要 MCP 服务器功能，可以直接作为 Python 库使用：

```python
import sys
sys.path.insert(0, '/Users/candy/beimeng_workspace')

from packages.mcp_file_info import FileInfoParser

parser = FileInfoParser()
metadata = parser.parse_file("your_file.py")

# 使用元信息...
```

