"""
@PURPOSE: Temu自动发布系统CLI入口，提供命令行接口
@OUTLINE:
  - app: Typer应用实例
  - def process(): 处理Excel选品表主命令
  - def login_test(): 测试登录功能
  - def info(): 显示系统信息
@DEPENDENCIES:
  - 内部: config.settings, src.data_processor, src.browser
  - 外部: typer, rich
"""

import asyncio
import sys
from pathlib import Path

# 添加当前目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

import typer
from loguru import logger
from rich.console import Console
from rich.panel import Panel

from config.settings import settings
from src.data_processor.processor import DataProcessor
from src.browser.login_controller import LoginController

app = typer.Typer(
    name="temu-auto-publish",
    help="Temu 商品发布自动化系统",
    add_completion=False,
)

console = Console()


@app.command()
def process(
    excel_file: Path = typer.Argument(..., help="选品表 Excel 文件路径"),
    output_dir: Path = typer.Option(None, "--output", "-o", help="输出目录"),
):
    """处理选品表，生成任务数据（完整流程）.

    Examples:
        temu-auto-publish process data/input/products.xlsx
        temu-auto-publish process products.xlsx -o data/output
    """
    console.print(Panel.fit("🚀 Temu 自动发布系统", style="bold blue"))

    if not excel_file.exists():
        console.print(f"[red]✗ 文件不存在: {excel_file}[/red]")
        raise typer.Exit(1)

    # 设置输出路径
    if output_dir is None:
        output_dir = settings.get_absolute_path(settings.data_output_dir)
    output_file = output_dir / "task.json"

    # 处理 Excel
    processor = DataProcessor(
        price_multiplier=settings.price_multiplier,
        supply_multiplier=settings.supply_price_multiplier,
    )

    try:
        task_data = processor.process_excel(excel_file, output_file)
        console.print(f"\n[green]✓ 处理完成！[/green]")
        console.print(f"  任务 ID: {task_data.task_id}")
        console.print(f"  产品数量: {len(task_data.products)}")
        console.print(f"  输出文件: {output_file}")
    except Exception as e:
        console.print(f"[red]✗ 处理失败: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def login(
    username: str = typer.Option(None, "--username", "-u", help="用户名"),
    password: str = typer.Option(None, "--password", "-p", help="密码"),
    force: bool = typer.Option(False, "--force", "-f", help="强制重新登录"),
    headless: bool = typer.Option(False, "--headless", help="无头模式"),
):
    """测试 Temu 登录（使用 Playwright）.

    Examples:
        temu-auto-publish login
        temu-auto-publish login -u user -p pass
        temu-auto-publish login --force --headless
    """
    console.print(Panel.fit("🔐 Temu 登录测试 (Playwright)", style="bold blue"))

    # 使用配置或命令行参数
    username = username or settings.temu_username
    password = password or settings.temu_password

    if not username or not password:
        console.print("[red]✗ 请提供用户名和密码[/red]")
        console.print("  方式1: 命令行 -u user -p pass")
        console.print("  方式2: 配置 .env 文件")
        raise typer.Exit(1)

    # 执行登录
    async def _login():
        controller = LoginController()
        return await controller.login(username, password, force=force, headless=headless)

    success = asyncio.run(_login())

    if success:
        console.print("[green]✓ 登录成功！[/green]")
    else:
        console.print("[red]✗ 登录失败[/red]")
        raise typer.Exit(1)


@app.command()
def status():
    """查看系统状态和配置.

    Examples:
        temu-auto-publish status
    """
    console.print(Panel.fit("📊 系统状态", style="bold blue"))

    # 配置信息
    console.print("\n[bold]配置信息:[/bold]")
    console.print(f"  价格倍率: {settings.price_multiplier}")
    console.print(f"  供货价倍率: {settings.supply_price_multiplier}")
    console.print(f"  采集数量: {settings.collect_count}")
    console.print(f"  日志级别: {settings.log_level}")

    # 目录信息
    console.print("\n[bold]目录配置:[/bold]")
    console.print(f"  输入目录: {settings.data_input_dir}")
    console.print(f"  输出目录: {settings.data_output_dir}")
    console.print(f"  临时目录: {settings.data_temp_dir}")
    console.print(f"  日志目录: {settings.data_logs_dir}")

    # Cookie 状态
    from src.browser.cookie_manager import CookieManager

    manager = CookieManager()
    cookie_status = "✓ 有效" if manager.is_valid() else "✗ 无效/不存在"
    console.print(f"\n[bold]Cookie 状态:[/bold] {cookie_status}")

    # 浏览器配置
    console.print("\n[bold]浏览器配置:[/bold]")
    console.print(f"  无头模式: {settings.browser_headless}")
    console.print(f"  配置文件: {settings.browser_config_file}")


# 开发命令组
dev_app = typer.Typer(help="开发和测试命令")
app.add_typer(dev_app, name="dev")


@dev_app.command("excel")
def dev_excel(file_path: Path = typer.Argument(..., help="Excel 文件路径")):
    """测试 Excel 读取.

    Examples:
        temu-auto-publish dev excel data/input/products.xlsx
    """
    console.print(Panel.fit("📊 Excel 读取测试", style="bold blue"))

    from src.data_processor.excel_reader import ExcelReader

    try:
        reader = ExcelReader(file_path)
        products = reader.read()

        console.print(f"\n[green]✓ 读取成功！[/green]")
        console.print(f"  产品数量: {len(products)}")
        console.print("\n前 3 个产品:")
        for p in products[:3]:
            console.print(f"  - {p.name} (¥{p.cost_price})")
    except Exception as e:
        console.print(f"[red]✗ 读取失败: {e}[/red]")
        raise typer.Exit(1)


@dev_app.command("price")
def dev_price(cost: float = typer.Argument(..., help="成本价")):
    """测试价格计算.

    Examples:
        temu-auto-publish dev price 100
        temu-auto-publish dev price 150.5
    """
    console.print(Panel.fit("💰 价格计算测试", style="bold blue"))

    from src.data_processor.price_calculator import PriceResult

    result = PriceResult.calculate(
        cost, settings.price_multiplier, settings.supply_price_multiplier
    )

    console.print(f"\n成本价: ¥{result.cost_price}")
    console.print(f"建议售价: ¥{result.suggested_price} (×{result.multiplier})")
    console.print(f"供货价: ¥{result.supply_price}")


if __name__ == "__main__":
    app()
