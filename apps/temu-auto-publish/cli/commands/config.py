"""
@PURPOSE: CLI 配置命令 - 管理和查看配置
@OUTLINE:
  - config_app: Typer 配置命令组
  - show(): 显示配置
  - validate(): 验证配置
  - init(): 初始化配置模板
  - edit(): 编辑配置(TODO)
@DEPENDENCIES:
  - 内部: config.settings
  - 外部: typer, rich, pyyaml
"""

import json
from pathlib import Path

import typer
import yaml
from config.settings import settings
from rich.console import Console
from rich.syntax import Syntax

config_app = typer.Typer(
    name="config",
    help="配置管理",
)

console = Console()


@config_app.command("show")
def show(
    env: str | None = typer.Option(None, "--env", help="环境名称"),
    format: str = typer.Option("yaml", "--format", "-f", help="输出格式(yaml/json)"),
):
    """显示当前配置.

    Examples:
        temu-auto-publish config show
        temu-auto-publish config show --env prod
        temu-auto-publish config show -f json
    """
    console.print("\n[bold blue]⚙️  配置信息[/bold blue]\n")

    # 显示环境
    current_env = env or settings.environment
    console.print(f"[bold]环境:[/bold] {current_env}\n")

    # 获取配置
    config_dict = settings.to_dict()

    # 格式化输出
    if format == "json":
        output = json.dumps(config_dict, indent=2, ensure_ascii=False)
        syntax = Syntax(output, "json", theme="monokai", line_numbers=True)
    else:  # yaml
        output = yaml.dump(config_dict, allow_unicode=True, default_flow_style=False)
        syntax = Syntax(output, "yaml", theme="monokai", line_numbers=True)

    console.print(syntax)


@config_app.command("validate")
def validate(
    config_file: Path = typer.Argument(..., help="配置文件路径"),
):
    """验证配置文件.

    Examples:
        temu-auto-publish config validate config/environments/prod.yaml
    """
    console.print("\n[bold blue]✅ 验证配置[/bold blue]\n")

    if not config_file.exists():
        console.print(f"[red]✗[/red] 文件不存在: {config_file}")
        raise typer.Exit(1) from None

    console.print(f"验证文件: {config_file}")

    try:
        # 加载配置
        with config_file.open("r", encoding="utf-8") as f:
            config = yaml.safe_load(f) if config_file.suffix in [".yaml", ".yml"] else json.load(f)

        console.print("[green]✓[/green] 文件格式正确")

        # 验证必需字段
        required_fields = ["environment", "debug", "logging", "browser", "retry"]
        missing_fields = [f for f in required_fields if f not in config]

        if missing_fields:
            console.print(f"[yellow]⚠[/yellow] 缺少字段: {', '.join(missing_fields)}")
        else:
            console.print("[green]✓[/green] 所有必需字段存在")

        # 验证环境名称
        env_name = config.get("environment")
        valid_envs = ["development", "staging", "production"]

        if env_name not in valid_envs:
            console.print(f"[red]✗[/red] 无效的环境名称: {env_name}")
            console.print(f"  有效值: {', '.join(valid_envs)}")
        else:
            console.print(f"[green]✓[/green] 环境名称正确: {env_name}")

        console.print("\n[green]✓ 配置文件有效[/green]")

    except yaml.YAMLError as e:
        console.print(f"[red]✗[/red] YAML 语法错误: {e}")
        raise typer.Exit(1) from None
    except json.JSONDecodeError as e:
        console.print(f"[red]✗[/red] JSON 语法错误: {e}")
        raise typer.Exit(1) from None
    except Exception as e:
        console.print(f"[red]✗[/red] 验证失败: {e}")
        raise typer.Exit(1) from None


@config_app.command("init")
def init(
    template: str = typer.Option("dev", "--template", "-t", help="模板类型(dev/staging/prod)"),
    output: Path = typer.Option(Path("config.yaml"), "--output", "-o", help="输出文件路径"),
):
    """初始化配置文件模板.

    Examples:
        temu-auto-publish config init -t dev
        temu-auto-publish config init -t prod -o my-config.yaml
    """
    console.print("\n[bold blue]📝 初始化配置[/bold blue]\n")

    if template not in ["dev", "staging", "prod"]:
        console.print(f"[red]✗[/red] 无效的模板类型: {template}")
        console.print("  有效值: dev, staging, prod")
        raise typer.Exit(1) from None

    # 源模板文件
    template_file = (
        Path(__file__).parent.parent.parent / "config" / "environments" / f"{template}.yaml"
    )

    if not template_file.exists():
        console.print(f"[red]✗[/red] 模板文件不存在: {template_file}")
        raise typer.Exit(1) from None

    # 复制模板
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(template_file.read_text(encoding="utf-8"), encoding="utf-8")

        console.print(f"[green]✓[/green] 配置文件已创建: {output}")
        console.print(f"  基于模板: {template}")
        console.print("\n请根据实际情况修改配置文件")

    except Exception as e:
        console.print(f"[red]✗[/red] 创建失败: {e}")
        raise typer.Exit(1) from None
