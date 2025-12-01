"""
@PURPOSE: CLI 主入口 - Temu 自动发布系统命令行工具
@OUTLINE:
  - app: Typer 主应用
  - 集成所有命令组（workflow/monitor/debug/config）
  - 版本信息和帮助
@GOTCHAS:
  - 使用前需要配置登录凭证（.env文件）
  - 确保 Playwright 浏览器已安装
@DEPENDENCIES:
  - 内部: cli.commands.*
  - 外部: typer, rich
"""

import sys
from pathlib import Path

import typer
from loguru import logger
from rich.console import Console

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from cli.commands.config import config_app
from cli.commands.debug import debug_app
from cli.commands.health import health_app
from cli.commands.monitor import monitor_app
from cli.commands.workflow import workflow_app
from config.settings import settings

# 配置日志
from src.utils.logger_setup import setup_logger

setup_logger()

# 创建主应用
app = typer.Typer(
    name="temu-auto-publish",
    help="Temu 自动发布系统 v2.0 - SOTA 工业级",
    add_completion=False,
    rich_markup_mode="rich",
)

console = Console()

# 添加命令组
app.add_typer(workflow_app, name="workflow")
app.add_typer(monitor_app, name="monitor")
app.add_typer(debug_app, name="debug")
app.add_typer(config_app, name="config")
app.add_typer(health_app, name="health")


@app.command()
def version():
    """显示版本信息.

    Examples:
        temu-auto-publish version
    """
    console.print("\n[bold cyan]Temu 自动发布系统[/bold cyan]")
    console.print("版本: [bold]2.0.0[/bold]")
    console.print("类型: [bold]SOTA 工业级[/bold]")
    console.print("\n环境配置:")
    console.print(f"  环境: {settings.environment}")
    console.print(f"  Python: {sys.version.split()[0]}")
    console.print(f"  工作目录: {Path.cwd()}")


@app.command()
def status():
    """显示系统状态.

    Examples:
        temu-auto-publish status
    """
    console.print("\n[bold blue]📊 系统状态[/bold blue]\n")

    # 环境信息
    console.print("[bold]环境配置:[/bold]")
    console.print(f"  环境: {settings.environment}")
    console.print(f"  调试模式: {'✓ 启用' if settings.debug.enabled else '✗ 禁用'}")
    console.print(f"  日志级别: {settings.logging.level}")
    console.print(f"  浏览器无头: {'✓ 是' if settings.browser.headless else '✗ 否'}")

    # 业务配置
    console.print("\n[bold]业务配置:[/bold]")
    console.print(f"  价格倍率: {settings.business.price_multiplier}x")
    console.print(f"  供货价倍率: {settings.business.supply_price_multiplier}x")
    console.print(f"  采集数量: {settings.business.collect_count}")
    console.print(f"  认领次数: {settings.business.claim_count}")

    # 重试配置
    console.print("\n[bold]重试配置:[/bold]")
    console.print(f"  启用: {'✓ 是' if settings.retry.enabled else '✗ 否'}")
    console.print(f"  最大尝试: {settings.retry.max_attempts} 次")
    console.print(f"  退避因子: {settings.retry.backoff_factor}x")

    # 目录状态
    console.print("\n[bold]目录状态:[/bold]")

    dirs = [
        ("输入", settings.data_input_dir),
        ("输出", settings.data_output_dir),
        ("临时", settings.data_temp_dir),
        ("日志", settings.data_logs_dir),
        ("调试", settings.debug.debug_dir),
        ("指标", settings.metrics.storage_dir),
        ("状态", settings.workflow.state_dir),
    ]

    for name, dir_path in dirs:
        full_path = settings.get_absolute_path(dir_path)
        exists = "✓" if full_path.exists() else "✗"
        console.print(f"  {name}: {exists} {dir_path}")

    # 登录凭证
    console.print("\n[bold]登录凭证:[/bold]")
    import os

    username = os.getenv("MIAOSHOU_USERNAME") or os.getenv("TEMU_USERNAME")
    if username:
        console.print(f"  用户名: ✓ {username}")
    else:
        console.print(f"  用户名: ✗ 未配置")
        console.print("  [yellow]请在 .env 文件中设置 MIAOSHOU_USERNAME/TEMU_USERNAME[/yellow]")


@app.command()
def setup():
    """初始化设置向导.

    Examples:
        temu-auto-publish setup
    """
    console.print("\n[bold cyan]🛠️  Temu 自动发布系统 - 初始化向导[/bold cyan]\n")

    console.print("此向导将帮助你完成初始配置。\n")

    # 1. 检查环境
    console.print("[bold]步骤 1/4:[/bold] 检查环境")

    # 检查 Python 版本
    import sys

    python_version = sys.version_info
    if python_version >= (3, 12):
        console.print(f"  ✓ Python 版本: {python_version.major}.{python_version.minor}")
    else:
        console.print(f"  ✗ Python 版本过低: {python_version.major}.{python_version.minor}")
        console.print("    需要 Python 3.12 或更高版本")
        raise typer.Exit(1)

    # 检查 Playwright
    try:
        import playwright

        console.print(f"  ✓ Playwright 已安装")
    except ImportError:
        console.print("  ✗ Playwright 未安装")
        console.print("    运行: pip install playwright && playwright install chromium")
        raise typer.Exit(1)

    # 2. 创建目录
    console.print("\n[bold]步骤 2/4:[/bold] 创建目录")
    settings.ensure_directories()
    console.print("  ✓ 所有目录已创建")

    # 3. 配置文件
    console.print("\n[bold]步骤 3/4:[/bold] 配置文件")

    env_file = Path(".env")
    if env_file.exists():
        console.print("  ✓ .env 文件已存在")
    else:
        console.print("  创建 .env 文件...")

        username = typer.prompt("  请输入妙手ERP用户名")
        password = typer.prompt("  请输入密码", hide_input=True)

        env_content = f"""# Temu 自动发布系统配置
# 登录凭证
MIAOSHOU_USERNAME={username}
MIAOSHOU_PASSWORD={password}

# 运行环境 (development/staging/production)
ENVIRONMENT=development
"""
        env_file.write_text(env_content, encoding="utf-8")
        console.print("  ✓ .env 文件已创建")

    # 4. 测试登录
    console.print("\n[bold]步骤 4/4:[/bold] 测试登录")

    test_login = typer.confirm("  是否测试登录？")

    if test_login:
        console.print("  测试登录中...")
        # TODO: 调用登录测试
        console.print("  [yellow]登录测试功能正在开发中...[/yellow]")

    # 完成
    console.print("\n[bold green]✓ 初始化完成！[/bold green]")
    console.print("\n下一步:")
    console.print("  1. 查看状态: [cyan]temu-auto-publish status[/cyan]")
    console.print("  2. 执行工作流: [cyan]temu-auto-publish workflow run[/cyan]")
    console.print("  3. 查看帮助: [cyan]temu-auto-publish --help[/cyan]")


@app.callback()
def main():
    """Temu 自动发布系统 v2.0 - SOTA 工业级命令行工具.

    主要功能：
      - workflow: 执行和管理工作流
      - monitor: 监控和指标分析
      - debug: 调试功能管理
      - config: 配置管理

    快速开始：
      1. 初始化: temu-auto-publish setup
      2. 查看状态: temu-auto-publish status
      3. 执行工作流: temu-auto-publish workflow run

    文档：
      https://github.com/your-org/temu-auto-publish
    """
    pass


if __name__ == "__main__":
    app()
