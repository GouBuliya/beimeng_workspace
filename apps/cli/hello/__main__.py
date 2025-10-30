"""
@PURPOSE: 使hello可以作为模块运行
@OUTLINE:
  - 导入并运行main.py中的app
@DEPENDENCIES:
  - 内部: apps.cli.hello.main
"""

from apps.cli.hello.main import app

if __name__ == "__main__":
    app()

