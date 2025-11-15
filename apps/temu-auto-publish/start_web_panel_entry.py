"""
@PURPOSE: 一键启动 Temu Web Panel, 供 PyInstaller 打包使用
@OUTLINE:
  - resolve_app(): 复用 CLI 中的 create_app
  - main(): 启动 uvicorn, 自动打开浏览器
"""

from __future__ import annotations

import threading
import time
import webbrowser
from typing import Final

import uvicorn
from web_panel.cli import create_app

HOST: Final[str] = "127.0.0.1"
PORT: Final[int] = 8899


def _open_browser(url: str) -> None:
    time.sleep(1.5)
    webbrowser.open(url, new=1, autoraise=True)


def main() -> None:
    """启动 Temu Web Panel."""

    app = create_app()
    url = f"http://{HOST}:{PORT}"
    threading.Thread(target=_open_browser, args=(url,), daemon=True).start()
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()
