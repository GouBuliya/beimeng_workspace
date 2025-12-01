#!/usr/bin/env python3
"""
@PURPOSE: 生产环境验证脚本 - 在部署前验证系统配置和环境
@OUTLINE:
  - class ProductionValidator: 生产环境验证器
  - def validate_environment(): 验证环境变量
  - def validate_dependencies(): 验证依赖
  - def validate_config_files(): 验证配置文件
  - def validate_directories(): 验证目录结构
  - def validate_credentials(): 验证登录凭证
  - def validate_browser(): 验证浏览器
  - def run_smoke_test(): 运行冒烟测试
  - def main(): 主入口
@DEPENDENCIES:
  - 内部: health_checker, notification_service
  - 外部: typer, rich
"""

import asyncio
import json
import os
import sys
from pathlib import Path

import typer
import yaml
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.health_checker import get_health_checker

console = Console()


class ProductionValidator:
    """生产环境验证器.

    验证项包括:
    1. 环境变量配置
    2. Python依赖
    3. 配置文件
    4. 目录结构
    5. 登录凭证
    6. 浏览器可用性
    7. 网络连接
    8. 通知服务

    Examples:
        >>> validator = ProductionValidator()
        >>> result = validator.validate_all()
        >>> if result["success"]:
        ...     print("验证通过")
    """

    def __init__(self, config_path: Path | None = None):
        """初始化验证器.

        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path or project_root / "config" / "production.yaml"
        self.config = self._load_config()
        self.results: list[tuple[str, bool, str]] = []  # (项目, 是否通过, 消息)

    def _load_config(self) -> dict:
        """加载配置文件."""
        if not self.config_path.exists():
            console.print(f"[yellow]⚠[/yellow] 配置文件不存在: {self.config_path}")
            return {}

        try:
            with open(self.config_path, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            console.print(f"[red]✗[/red] 加载配置文件失败: {e}")
            return {}

    def validate_environment(self) -> bool:
        """验证环境变量."""
        console.print("\n[bold cyan]1. 验证环境变量[/bold cyan]")

        required_vars = [
            ("MIAOSHOU_USERNAME", "妙手ERP用户名"),
            ("MIAOSHOU_PASSWORD", "妙手ERP密码"),
        ]

        optional_vars = [
            ("OPENAI_API_KEY", "OpenAI API密钥(用于AI标题生成)"),
            ("SMTP_USERNAME", "SMTP用户名(用于邮件通知)"),
            ("SMTP_PASSWORD", "SMTP密码(用于邮件通知)"),
        ]

        all_pass = True

        # 检查必需变量
        for var_name, description in required_vars:
            value = os.getenv(var_name)
            if value:
                console.print(f"  [green]✓[/green] {var_name}: {description}")
                self.results.append((f"环境变量: {var_name}", True, description))
            else:
                console.print(f"  [red]✗[/red] {var_name}: {description} (未设置)")
                self.results.append((f"环境变量: {var_name}", False, f"{description} 未设置"))
                all_pass = False

        # 检查可选变量
        for var_name, description in optional_vars:
            value = os.getenv(var_name)
            if value:
                console.print(f"  [green]✓[/green] {var_name}: {description}")
            else:
                console.print(f"  [yellow]⚠[/yellow] {var_name}: {description} (未设置,可选)")

        return all_pass

    def validate_dependencies(self) -> bool:
        """验证Python依赖."""
        console.print("\n[bold cyan]2. 验证Python依赖[/bold cyan]")

        required_deps = [
            "playwright",
            "pandas",
            "openpyxl",
            "pydantic",
            "typer",
            "aiohttp",
            "loguru",
            "apscheduler",
            "psutil",
        ]

        all_pass = True

        for dep in required_deps:
            try:
                __import__(dep)
                console.print(f"  [green]✓[/green] {dep}")
                self.results.append((f"依赖: {dep}", True, "已安装"))
            except ImportError:
                console.print(f"  [red]✗[/red] {dep} (未安装)")
                self.results.append((f"依赖: {dep}", False, "未安装"))
                all_pass = False

        # 检查Playwright浏览器
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                p.chromium.launch(headless=True)
            console.print("  [green]✓[/green] Playwright Chromium 浏览器")
            self.results.append(("Playwright浏览器", True, "Chromium已安装"))
        except Exception as e:
            console.print(f"  [red]✗[/red] Playwright Chromium 浏览器: {e}")
            self.results.append(("Playwright浏览器", False, f"Chromium未安装: {e}"))
            all_pass = False

        return all_pass

    def validate_config_files(self) -> bool:
        """验证配置文件."""
        console.print("\n[bold cyan]3. 验证配置文件[/bold cyan]")

        required_files = [
            (".env", "环境变量配置"),
            ("config/browser_config.json", "浏览器配置"),
            ("config/miaoshou_selectors.json", "妙手选择器配置"),
            ("config/production.yaml", "生产环境配置"),
        ]

        all_pass = True

        for file_path, description in required_files:
            full_path = project_root / file_path
            if full_path.exists():
                console.print(f"  [green]✓[/green] {file_path}: {description}")
                self.results.append((f"配置文件: {file_path}", True, description))
            else:
                console.print(f"  [red]✗[/red] {file_path}: {description} (不存在)")
                self.results.append((f"配置文件: {file_path}", False, f"{description} 不存在"))
                all_pass = False

        return all_pass

    def validate_directories(self) -> bool:
        """验证目录结构."""
        console.print("\n[bold cyan]4. 验证目录结构[/bold cyan]")

        required_dirs = [
            "data/input",
            "data/output",
            "data/temp",
            "data/logs",
            "data/metrics",
            "data/workflow_states",
        ]

        all_pass = True

        for dir_path in required_dirs:
            full_path = project_root / dir_path
            if full_path.exists() and full_path.is_dir():
                console.print(f"  [green]✓[/green] {dir_path}")
                self.results.append((f"目录: {dir_path}", True, "存在"))
            else:
                # 尝试创建
                try:
                    full_path.mkdir(parents=True, exist_ok=True)
                    console.print(f"  [yellow]⚠[/yellow] {dir_path} (已创建)")
                    self.results.append((f"目录: {dir_path}", True, "已创建"))
                except Exception as e:
                    console.print(f"  [red]✗[/red] {dir_path}: 创建失败 ({e})")
                    self.results.append((f"目录: {dir_path}", False, f"创建失败: {e}"))
                    all_pass = False

        return all_pass

    async def validate_credentials(self) -> bool:
        """验证登录凭证."""
        console.print("\n[bold cyan]5. 验证登录凭证[/bold cyan]")

        username = os.getenv("MIAOSHOU_USERNAME")
        password = os.getenv("MIAOSHOU_PASSWORD")

        if not username or not password:
            console.print("  [red]✗[/red] 登录凭证未配置")
            self.results.append(("登录凭证", False, "未配置"))
            return False

        console.print(f"  [green]✓[/green] 用户名: {username}")
        console.print(f"  [green]✓[/green] 密码: {'*' * len(password)}")
        self.results.append(("登录凭证", True, f"用户名: {username}"))

        # TODO: 可以添加实际登录测试
        # 但这可能耗时较长,且可能影响账号,所以暂时跳过

        return True

    async def validate_health(self) -> bool:
        """执行健康检查."""
        console.print("\n[bold cyan]6. 执行健康检查[/bold cyan]")

        health_checker = get_health_checker()

        with Progress(
            SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console
        ) as progress:
            progress.add_task("检查中...", total=None)
            result = await health_checker.check_all(include_network=True)

        status = result.get("status", "unknown")
        summary = result.get("summary", {})

        if status == "healthy":
            console.print("  [green]✓[/green] 健康检查通过")
            self.results.append(("健康检查", True, "所有检查通过"))
            return True
        elif status == "degraded":
            console.print(
                f"  [yellow]⚠[/yellow] 健康检查有警告 (WARNING: {summary.get('warning_count', 0)})"
            )
            self.results.append(("健康检查", True, f"有{summary.get('warning_count', 0)}个警告"))
            return True
        else:
            console.print(f"  [red]✗[/red] 健康检查失败 (ERROR: {summary.get('error_count', 0)})")

            # 显示错误详情
            for component, check in result.get("checks", {}).items():
                if check.get("status") == "error":
                    console.print(f"    [red]•[/red] {component}: {check.get('message', '')}")

            self.results.append(("健康检查", False, f"{summary.get('error_count', 0)}个错误"))
            return False

    def validate_notification_config(self) -> bool:
        """验证通知配置."""
        console.print("\n[bold cyan]7. 验证通知配置[/bold cyan]")

        notification_config = self.config.get("notification", {})

        if not notification_config:
            console.print("  [yellow]⚠[/yellow] 未配置通知服务(可选)")
            return True

        # 检查各渠道配置
        has_any_channel = False

        # 钉钉
        dingtalk = notification_config.get("dingtalk", {})
        if dingtalk.get("enabled"):
            webhook = dingtalk.get("webhook_url")
            if webhook:
                console.print("  [green]✓[/green] 钉钉通知已配置")
                has_any_channel = True
            else:
                console.print("  [yellow]⚠[/yellow] 钉钉通知已启用但未配置Webhook URL")

        # 企业微信
        wecom = notification_config.get("wecom", {})
        if wecom.get("enabled"):
            webhook = wecom.get("webhook_url")
            if webhook:
                console.print("  [green]✓[/green] 企业微信通知已配置")
                has_any_channel = True
            else:
                console.print("  [yellow]⚠[/yellow] 企业微信通知已启用但未配置Webhook URL")

        # 邮件
        email = notification_config.get("email", {})
        if email.get("enabled"):
            required_fields = [
                "smtp_host",
                "smtp_port",
                "username",
                "password",
                "from_addr",
                "to_addrs",
            ]
            if all(email.get(field) for field in required_fields):
                console.print("  [green]✓[/green] 邮件通知已配置")
                has_any_channel = True
            else:
                console.print("  [yellow]⚠[/yellow] 邮件通知已启用但配置不完整")

        if not has_any_channel:
            console.print("  [yellow]⚠[/yellow] 没有启用任何通知渠道(可选)")

        self.results.append(("通知配置", True, "已检查"))
        return True

    async def run_smoke_test(self) -> bool:
        """运行冒烟测试(可选)."""
        console.print("\n[bold cyan]8. 运行冒烟测试[/bold cyan]")
        console.print("  [yellow]i[/yellow] 冒烟测试已跳过(需要手动执行)")
        console.print("  运行命令: python scripts/run_production.py --dry-run <input_file>")
        return True

    async def validate_all(self) -> dict:
        """执行所有验证."""
        console.print(f"\n[bold blue]{'=' * 60}[/bold blue]")
        console.print("[bold blue]Temu自动发布系统 - 生产环境验证[/bold blue]")
        console.print(f"[bold blue]{'=' * 60}[/bold blue]")

        results = {
            "environment": self.validate_environment(),
            "dependencies": self.validate_dependencies(),
            "config_files": self.validate_config_files(),
            "directories": self.validate_directories(),
            "credentials": await self.validate_credentials(),
            "health": await self.validate_health(),
            "notification": self.validate_notification_config(),
            "smoke_test": await self.run_smoke_test(),
        }

        # 显示总结
        self._display_summary(results)

        all_pass = all(results.values())

        return {"success": all_pass, "results": results, "details": self.results}

    def _display_summary(self, results: dict[str, bool]):
        """显示验证总结."""
        console.print(f"\n[bold blue]{'=' * 60}[/bold blue]")
        console.print("[bold blue]验证总结[/bold blue]")
        console.print(f"[bold blue]{'=' * 60}[/bold blue]\n")

        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("验证项", style="cyan", width=30)
        table.add_column("结果", width=10)
        table.add_column("说明", no_wrap=False)

        for key, passed in results.items():
            name_map = {
                "environment": "环境变量",
                "dependencies": "Python依赖",
                "config_files": "配置文件",
                "directories": "目录结构",
                "credentials": "登录凭证",
                "health": "健康检查",
                "notification": "通知配置",
                "smoke_test": "冒烟测试",
            }

            name = name_map.get(key, key)
            status = "[green]✓ 通过[/green]" if passed else "[red]✗ 失败[/red]"

            # 查找相关详情
            details = [d for d in self.results if name in d[0]]
            if details:
                failed_count = sum(1 for d in details if not d[1])
                if failed_count > 0:
                    desc = f"{failed_count}个检查失败"
                else:
                    desc = f"{len(details)}个检查通过"
            else:
                desc = ""

            table.add_row(name, status, desc)

        console.print(table)
        console.print()

        # 总体结果
        all_pass = all(results.values())
        if all_pass:
            console.print("[green]✅ 所有验证通过,系统可以上线![/green]")
        else:
            console.print("[red]❌ 部分验证失败,请修复后再上线![/red]")
            console.print("\n失败的检查项:")
            for item, passed, message in self.results:
                if not passed:
                    console.print(f"  [red]•[/red] {item}: {message}")


app = typer.Typer(help="生产环境验证工具")


@app.command()
def validate(
    config: Path | None = typer.Option(None, "--config", "-c", help="配置文件路径"),
    output: Path | None = typer.Option(None, "--output", "-o", help="输出验证报告到JSON文件"),
):
    """执行生产环境验证.

    Examples:
        python scripts/validate_production.py validate
        python scripts/validate_production.py validate --output report.json
    """
    # 加载.env
    from dotenv import load_dotenv

    env_file = project_root / ".env"
    if env_file.exists():
        load_dotenv(env_file)

    # 执行验证
    validator = ProductionValidator(config_path=config)
    result = asyncio.run(validator.validate_all())

    # 保存报告
    if output:
        try:
            with open(output, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            console.print(f"\n[green]✓[/green] 验证报告已保存: {output}")
        except Exception as e:
            console.print(f"\n[red]✗[/red] 保存报告失败: {e}")

    # 返回退出码
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    app()
