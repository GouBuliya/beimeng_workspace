"""
@PURPOSE: 提供浏览器自动化调试辅助工具, 包含日志,快照与同步调试入口
@OUTLINE:
  - async def capture_debug_artifacts(): 保存截图与HTML
  - def log_payload_preview(): 使用 Rich 输出结构化数据
  - async def maybe_pause_for_inspector(): 条件触发 Playwright Inspector
  - def run_with_optional_syncer(): 将异步 Playwright 调试脚本同步执行
@DEPENDENCIES:
  - 外部: playwright, rich, loguru
"""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Awaitable, Callable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger
from playwright.async_api import Page
from rich.console import Console
from rich.table import Table


async def capture_debug_artifacts(
    page: Page,
    *,
    step: str,
    output_dir: Path,
) -> dict[str, str]:
    """保存当前页面的截图和HTML, 便于调试回溯.

    Args:
        page: Playwright 页面对象.
        step: 当前步骤名称, 用于生成文件名前缀.
        output_dir: 输出目录.

    Returns:
        包含截图与HTML路径的字典.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_step = step.replace(" ", "_").replace("/", "-")
    output_dir.mkdir(parents=True, exist_ok=True)

    screenshot_path = output_dir / f"{timestamp}_{safe_step}.png"
    html_path = output_dir / f"{timestamp}_{safe_step}.html"

    await page.screenshot(path=str(screenshot_path), full_page=True)
    html_content = await page.content()
    html_path.write_text(html_content, encoding="utf-8")

    logger.debug(
        "调试资源已保存 | screenshot={} | html={}",
        screenshot_path,
        html_path,
    )
    return {"screenshot": str(screenshot_path), "html": str(html_path)}


def log_payload_preview(payload: Mapping[str, Any], *, title: str = "First Edit Payload") -> None:
    """使用 Rich 表格展示结构化 payload, 便于快速校验."""
    console = Console()
    table = Table(title=title)
    table.add_column("Key", style="cyan", no_wrap=True)
    table.add_column("Value", style="magenta")

    for key, value in payload.items():
        formatted = (
            json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
        )
        table.add_row(str(key), formatted)

    console.print(table)


async def maybe_pause_for_inspector(page: Page, *, enabled: bool | None = None) -> None:
    """条件触发 Playwright Inspector, 支持环境变量 PLAYWRIGHT_DEBUG=1."""
    should_pause = enabled if enabled is not None else os.getenv("PLAYWRIGHT_DEBUG") == "1"
    if not should_pause:
        return

    logger.info("PLAYWRIGHT_DEBUG=1 -> 调用 page.pause() 打开 Inspector")
    await page.pause()


def run_with_optional_syncer(
    async_fn: Callable[..., Awaitable[Any]], *args: Any, **kwargs: Any
) -> Any:
    """尝试使用 syncer 将异步函数同步执行, 未安装时回退到 asyncio.run."""
    try:
        from syncer import sync
    except ImportError:
        logger.debug("syncer 未安装, 使用 asyncio.run 执行 {}", async_fn.__name__)
        return asyncio.run(async_fn(*args, **kwargs))

    sync_callable = sync(async_fn)
    return sync_callable(*args, **kwargs)
