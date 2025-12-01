"""
@PURPOSE: 交互式导出 Temu 登录 Cookie, 供 Playwright 上下文复用
@OUTLINE:
  - class CookieExporter: 管理浏览器上下文并导出 cookie
  - def export_cookies(): Typer CLI 命令
  - if __name__ == "__main__": CLI 入口
@DEPENDENCIES:
  - 外部: playwright, typer, loguru
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from loguru import logger
from playwright.sync_api import Browser, BrowserContext, Playwright, sync_playwright

DEFAULT_OUTPUT = Path("data/input/temu_cookies.json")
TEMU_HOME_URL = "https://www.temu.com/"

app = typer.Typer(help="导出 Temu 登录 Cookie", no_args_is_help=True)


class CookieExporter:
    """封装 Playwright 浏览器启动和 cookie 导出逻辑."""

    def __init__(
        self,
        *,
        output_file: Path,
        headless: bool = False,
        channel: Optional[str] = None,
        auto_close: bool = True,
    ) -> None:
        self.output_file = output_file
        self.headless = headless
        self.channel = channel
        self.auto_close = auto_close

    def run(self) -> None:
        """启动浏览器等待登录, 然后导出 cookie."""
        with sync_playwright() as playwright:
            browser = self._launch_browser(playwright)
            context = browser.new_context()
            page = context.new_page()

            logger.info("打开 Temu 首页: {}", TEMU_HOME_URL)
            page.goto(TEMU_HOME_URL, wait_until="domcontentloaded")

            typer.echo("\n请在弹出的浏览器窗口中完成 Temu 登录。")
            typer.echo("确认已登录后切回终端, 按 Enter 键导出 cookie。\n")
            typer.prompt("按 Enter 继续", default="", show_default=False)

            cookies = context.cookies()
            self._write_to_file(cookies)

            typer.echo(f"\n✅ Cookie 已导出到: {self.output_file.resolve()}\n")

            if self.auto_close:
                context.close()
                browser.close()
            else:
                typer.echo("浏览器窗口已保留, 可自行关闭。")

    def _launch_browser(self, playwright: Playwright) -> Browser:
        launch_kwargs: dict[str, object] = {"headless": self.headless}
        if self.channel:
            launch_kwargs["channel"] = self.channel
            launch_kwargs["args"] = [
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--start-maximized",
            ]
            logger.info(
                f"启动 Chromium 浏览器 (channel={self.channel}, headless={self.headless})"
            )
        else:
            logger.info("启动 Chromium 浏览器 (headless={})", self.headless)

        return playwright.chromium.launch(**launch_kwargs)

    def _write_to_file(self, cookies: list[dict]) -> None:
        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        with self.output_file.open("w", encoding="utf-8") as file:
            json.dump(cookies, file, ensure_ascii=False, indent=2)
        logger.success("成功导出 {} 条 cookie", len(cookies))


@app.command()
def export_cookies(
    output: Path = typer.Option(
        DEFAULT_OUTPUT,
        "--output",
        "-o",
        help="Cookie 输出路径 (JSON)",
    ),
    headless: bool = typer.Option(
        False,
        "--headless/--no-headless",
        help="是否使用无头模式运行浏览器",
    ),
    channel: Optional[str] = typer.Option(
        None,
        "--channel",
        help="使用指定浏览器渠道 (例如: chrome, msedge)",
    ),
    keep_browser: bool = typer.Option(
        False,
        "--keep-browser/--auto-close",
        help="导出后是否保留浏览器窗口",
    ),
) -> None:
    """交互式导出 Temu 登录 cookie."""
    exporter = CookieExporter(
        output_file=output,
        headless=headless,
        channel=channel,
        auto_close=not keep_browser,
    )
    exporter.run()


if __name__ == "__main__":
    app()
