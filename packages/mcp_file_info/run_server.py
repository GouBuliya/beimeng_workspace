#!/usr/bin/env python3
"""
@PURPOSE: MCP File Info 服务器启动脚本
@OUTLINE:
  - 设置正确的 Python 路径
  - 启动 MCP 服务器
@DEPENDENCIES:
  - 内部: packages.mcp_file_info
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
workspace_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(workspace_root))

# 现在可以导入并启动服务器
if __name__ == "__main__":
    import asyncio

    from packages.mcp_file_info.mcp_server import main

    asyncio.run(main())
