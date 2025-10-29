"""
__main__.py - 使 hello 可以作为模块运行

允许使用 python -m apps.cli.hello 运行
"""

from apps.cli.hello.main import app

if __name__ == "__main__":
    app()

