#!/usr/bin/env python3
"""
@PURPOSE: 生产环境主脚本 - 执行完整的SOP步骤4-11工作流
@OUTLINE:
  - class ProductionRunner: 生产环境运行器
  - async def run(): 执行完整工作流
  - async def load_input_data(): 加载输入数据(Excel/JSON)
  - async def pre_execution_checks(): 执行前健康检查
  - async def execute_workflow(): 执行工作流
  - async def post_execution_actions(): 执行后操作(通知/清理)
  - def main(): 主入口函数
@GOTCHAS:
  - 需要先加载.env文件
  - 健康检查失败时根据配置决定是否继续
  - 确保资源总是被正确清理
@DEPENDENCIES:
  - 内部: 所有workflow和controller模块
  - 外部: typer, yaml, pandas
@RELATED: scheduler_daemon.py, validate_production.py
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import typer
import yaml
from dotenv import load_dotenv
from loguru import logger
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.settings import settings
from src.browser.login_controller import LoginController
from src.core.health_checker import get_health_checker
from src.core.notification_service import (
    WorkflowResult,
    configure_notifications,
    get_notification_service,
)
from src.data_processor.selection_table_reader import SelectionTableReader
from src.workflows.complete_publish_workflow import CompletePublishWorkflow

console = Console()


class ProductionRunner:
    """生产环境运行器.

    负责执行完整的生产环境工作流,包括:
    1. 健康检查
    2. 数据加载
    3. 登录
    4. 工作流执行
    5. 结果通知
    6. 资源清理

    Attributes:
        config: 配置字典
        input_path: 输入文件路径
        input_type: 输入类型(excel/json)
        dry_run: 是否dry-run模式

    Examples:
        >>> runner = ProductionRunner(
        ...     input_path="data/input/selection.xlsx",
        ...     input_type="excel"
        ... )
        >>> result = await runner.run()
    """

    def __init__(
        self,
        input_path: Path,
        input_type: str,
        config_path: Path | None = None,
        staff_name: str | None = None,
        enable_batch_edit: bool = True,
        enable_publish: bool = True,
        use_ai_titles: bool = True,
        dry_run: bool = False,
        skip_health_check: bool = False,
    ):
        """初始化生产环境运行器.

        Args:
            input_path: 输入文件路径
            input_type: 输入类型(excel/json)
            config_path: 配置文件路径(可选)
            staff_name: 人员名称(可选)
            enable_batch_edit: 是否启用批量编辑
            enable_publish: 是否启用发布
            use_ai_titles: 是否使用AI生成标题
            dry_run: 是否dry-run模式
            skip_health_check: 是否跳过健康检查
        """
        self.input_path = input_path
        self.input_type = input_type
        self.config_path = config_path or project_root / "config" / "production.yaml"
        self.staff_name = staff_name
        self.enable_batch_edit = enable_batch_edit
        self.enable_publish = enable_publish
        self.use_ai_titles = use_ai_titles
        self.dry_run = dry_run
        self.skip_health_check = skip_health_check

        # 加载配置
        self.config = self._load_config()

        # 初始化通知服务
        if self.config.get("notification"):
            configure_notifications(self.config["notification"])

        # 运行器状态
        self.login_controller: LoginController | None = None
        self.workflow_id: str = f"workflow_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.start_time: datetime | None = None

        logger.info(f"生产环境运行器已初始化 (工作流ID: {self.workflow_id})")

    def _load_config(self) -> dict:
        """加载配置文件.

        Returns:
            配置字典
        """
        if not self.config_path.exists():
            logger.warning(f"配置文件不存在: {self.config_path}, 使用默认配置")
            return {}

        try:
            with open(self.config_path, encoding="utf-8") as f:
                config = yaml.safe_load(f)
            logger.info(f"✓ 已加载配置文件: {self.config_path}")
            return config or {}
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            return {}

    async def load_input_data(self) -> list[dict]:
        """加载输入数据.

        Returns:
            产品数据列表

        Raises:
            FileNotFoundError: 输入文件不存在
            ValueError: 输入数据格式错误
        """
        console.print("\n[bold cyan]📂 加载输入数据...[/bold cyan]")

        if not self.input_path.exists():
            raise FileNotFoundError(f"输入文件不存在: {self.input_path}")

        if self.input_type == "excel":
            # 使用SelectionTableReader读取Excel
            reader = SelectionTableReader()
            products = reader.read_excel(str(self.input_path))

            # 转换为标准格式
            products_data = []
            for product_row in products:
                product_dict = {
                    "product_name": product_row.product_name,
                    "model_number": product_row.model_number,
                    "cost_price": product_row.cost_price or 15.0,
                    "color_spec": product_row.color_spec,
                    "collect_count": product_row.collect_count,
                    "owner": product_row.owner,
                }
                if self.staff_name:
                    product_dict["staff_name"] = self.staff_name
                products_data.append(product_dict)

            console.print(f"[green]✓[/green] 已从Excel加载 {len(products_data)} 个产品")

            # SOP工作流每次处理5个产品,如果超过5个,只取前5个
            if len(products_data) > 5:
                console.print("[yellow]⚠[/yellow] 产品数量超过5个,本次只处理前5个产品")
                console.print(f"   剩余 {len(products_data) - 5} 个产品将在后续批次处理")
                products_data = products_data[:5]

            return products_data

        elif self.input_type == "json":
            # 读取JSON文件
            with open(self.input_path, encoding="utf-8") as f:
                data = json.load(f)

            # 支持两种JSON格式
            if isinstance(data, list):
                products_data = data
            elif isinstance(data, dict) and "products" in data:
                products_data = data["products"]
                # 如果JSON中指定了staff_name,使用它
                if "staff_name" in data and not self.staff_name:
                    self.staff_name = data["staff_name"]
            else:
                raise ValueError("JSON格式错误,应为产品列表或包含'products'字段的对象")

            # 添加staff_name
            if self.staff_name:
                for product in products_data:
                    if "staff_name" not in product:
                        product["staff_name"] = self.staff_name

            console.print(f"[green]✓[/green] 已从JSON加载 {len(products_data)} 个产品")
            return products_data

        else:
            raise ValueError(f"不支持的输入类型: {self.input_type}")

    async def pre_execution_checks(self) -> bool:
        """执行前健康检查.

        Returns:
            是否通过健康检查
        """
        if self.skip_health_check:
            console.print("[yellow]⚠[/yellow] 已跳过健康检查")
            return True

        console.print("\n[bold cyan]🔍 执行健康检查...[/bold cyan]")

        health_checker = get_health_checker()

        with Progress(
            SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console
        ) as progress:
            progress.add_task("检查中...", total=None)

            health_result = await health_checker.check_all(include_network=True)

        # 显示检查结果
        status = health_result["status"]
        summary = health_result["summary"]

        if status == "healthy":
            console.print(
                f"[green]✓[/green] 健康检查通过 "
                f"(OK: {summary['ok_count']}, "
                f"WARNING: {summary['warning_count']}, "
                f"ERROR: {summary['error_count']})"
            )
            return True
        elif status == "degraded":
            console.print(
                f"[yellow]⚠[/yellow] 健康检查有警告 (WARNING: {summary['warning_count']})"
            )

            # 检查配置决定是否继续
            on_unhealthy = self.config.get("health_check", {}).get("on_unhealthy", "warn")
            if on_unhealthy == "abort":
                console.print("[red]✗[/red] 健康检查配置为失败中止")
                return False
            else:
                console.print("[yellow]→[/yellow] 继续执行(有风险)")
                return True
        else:
            console.print(f"[red]✗[/red] 健康检查失败 (ERROR: {summary['error_count']})")

            # 显示错误详情
            for component, check in health_result["checks"].items():
                if check["status"] == "error":
                    console.print(f"  [red]•[/red] {component}: {check['message']}")

            # 检查配置决定是否继续
            on_unhealthy = self.config.get("health_check", {}).get("on_unhealthy", "abort")
            if on_unhealthy == "ignore":
                console.print("[yellow]→[/yellow] 忽略错误,继续执行(非常危险!)")
                return True
            else:
                console.print("[red]→[/red] 中止执行")
                return False

    async def execute_workflow(self, products_data: list[dict]) -> dict:
        """执行完整工作流.

        Args:
            products_data: 产品数据列表

        Returns:
            执行结果字典
        """
        console.print("\n[bold cyan]🚀 开始执行工作流...[/bold cyan]")

        if self.dry_run:
            console.print("[yellow]⚠[/yellow] DRY-RUN模式,不会实际执行")
            return {"success": True, "dry_run": True, "message": "DRY-RUN模式,未实际执行"}

        try:
            # 1. 初始化登录控制器
            console.print("\n[bold]步骤1: 初始化浏览器...[/bold]")
            self.login_controller = LoginController()
            await self.login_controller.browser_manager.start()
            page = self.login_controller.browser_manager.page

            # 2. 登录
            console.print("[bold]步骤2: 登录妙手ERP...[/bold]")
            username = os.getenv("MIAOSHOU_USERNAME")
            password = os.getenv("MIAOSHOU_PASSWORD")

            if not username or not password:
                raise ValueError("未设置登录凭证(MIAOSHOU_USERNAME/MIAOSHOU_PASSWORD)")

            if not await self.login_controller.login(username, password):
                raise Exception("登录失败")

            console.print(f"[green]✓[/green] 登录成功: {username}")

            # 3. 创建并执行工作流
            console.print("[bold]步骤3: 执行完整工作流...[/bold]")
            workflow = CompletePublishWorkflow(use_ai_titles=self.use_ai_titles)

            result = await workflow.execute(
                page=page,
                products_data=products_data,
                shop_name=None,  # TODO: 从配置或参数获取
                enable_batch_edit=self.enable_batch_edit,
                enable_publish=self.enable_publish,
            )

            return result

        except Exception as e:
            logger.error(f"工作流执行失败: {e}")
            logger.exception("详细错误:")
            return {"success": False, "error": str(e)}

    async def post_execution_actions(self, result: dict):
        """执行后操作.

        Args:
            result: 工作流执行结果
        """
        # 1. 发送通知
        if (
            self.config.get("notification", {}).get("triggers", {}).get("on_success")
            and result.get("success")
        ) or (
            self.config.get("notification", {}).get("triggers", {}).get("on_failure")
            and not result.get("success")
        ):
            await self._send_notification(result)

        # 2. 保存结果
        await self._save_result(result)

        # 3. 清理临时文件(可选)
        # TODO: 实现临时文件清理

    async def _send_notification(self, result: dict):
        """发送通知.

        Args:
            result: 工作流执行结果
        """
        try:
            console.print("\n[bold cyan]📢 发送通知...[/bold cyan]")

            notification_service = get_notification_service()

            # 构建WorkflowResult
            workflow_result = WorkflowResult(
                workflow_id=self.workflow_id,
                success=result.get("success", False),
                start_time=self.start_time.isoformat() if self.start_time else "",
                end_time=datetime.now().isoformat(),
                stages=[
                    {
                        "name": "阶段1 (5→20)",
                        "success": result.get("stage1_result", {}).get("success", False),
                        "message": result.get("stage1_result", {}).get("message", ""),
                    },
                    {
                        "name": "阶段2 (批量编辑)",
                        "success": result.get("stage2_result", {}).get("success", False),
                        "message": result.get("stage2_result", {}).get("message", ""),
                    },
                    {
                        "name": "阶段3 (发布)",
                        "success": result.get("stage3_result", {}).get("success", False),
                        "message": result.get("stage3_result", {}).get("message", ""),
                    },
                ],
                errors=result.get("errors", []),
            )

            send_results = await notification_service.send_workflow_result(workflow_result)

            # 显示发送结果
            for channel, success in send_results.items():
                status = "✓" if success else "✗"
                console.print(f"  {status} {channel}: {'成功' if success else '失败'}")

        except Exception as e:
            logger.error(f"发送通知失败: {e}")
            console.print(f"[yellow]⚠[/yellow] 通知发送失败: {e}")

    async def _save_result(self, result: dict):
        """保存执行结果.

        Args:
            result: 工作流执行结果
        """
        try:
            output_dir = settings.get_absolute_path(settings.data_output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

            result_file = output_dir / f"{self.workflow_id}_result.json"

            # 添加元数据
            result_with_meta = {
                "workflow_id": self.workflow_id,
                "start_time": self.start_time.isoformat() if self.start_time else None,
                "end_time": datetime.now().isoformat(),
                "input_path": str(self.input_path),
                "input_type": self.input_type,
                "staff_name": self.staff_name,
                "enable_batch_edit": self.enable_batch_edit,
                "enable_publish": self.enable_publish,
                "use_ai_titles": self.use_ai_titles,
                "dry_run": self.dry_run,
                "result": result,
            }

            with open(result_file, "w", encoding="utf-8") as f:
                json.dump(result_with_meta, f, indent=2, ensure_ascii=False)

            console.print(f"[green]✓[/green] 结果已保存: {result_file}")

        except Exception as e:
            logger.error(f"保存结果失败: {e}")
            console.print(f"[yellow]⚠[/yellow] 保存结果失败: {e}")

    async def cleanup(self):
        """清理资源."""
        if self.login_controller:
            try:
                await self.login_controller.browser_manager.close()
                console.print("[green]✓[/green] 浏览器已关闭")
            except Exception as e:
                logger.error(f"关闭浏览器失败: {e}")

    async def run(self) -> int:
        """运行完整流程.

        Returns:
            退出码(0=成功, 1=失败)
        """
        self.start_time = datetime.now()

        console.print(f"\n[bold blue]{'=' * 60}[/bold blue]")
        console.print("[bold blue]Temu自动发布系统 - 生产环境[/bold blue]")
        console.print(f"[bold blue]{'=' * 60}[/bold blue]")
        console.print(f"\n工作流ID: {self.workflow_id}")
        console.print(f"开始时间: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        console.print(f"输入文件: {self.input_path}")
        console.print(f"输入类型: {self.input_type}")
        if self.staff_name:
            console.print(f"人员筛选: {self.staff_name}")
        console.print(f"批量编辑: {'✓ 启用' if self.enable_batch_edit else '✗ 禁用'}")
        console.print(f"发布: {'✓ 启用' if self.enable_publish else '✗ 禁用'}")
        console.print(f"AI标题: {'✓ 启用' if self.use_ai_titles else '✗ 禁用'}")
        if self.dry_run:
            console.print("[yellow]模式: DRY-RUN (不会实际执行)[/yellow]")

        try:
            # 1. 健康检查
            if not await self.pre_execution_checks():
                console.print("\n[red]✗ 健康检查未通过,中止执行[/red]")
                return 1

            # 2. 加载输入数据
            products_data = await self.load_input_data()

            # 3. 执行工作流
            result = await self.execute_workflow(products_data)

            # 4. 执行后操作
            await self.post_execution_actions(result)

            # 5. 显示最终结果
            end_time = datetime.now()
            duration = (end_time - self.start_time).total_seconds()

            console.print(f"\n[bold blue]{'=' * 60}[/bold blue]")
            console.print("[bold blue]执行完成[/bold blue]")
            console.print(f"[bold blue]{'=' * 60}[/bold blue]")
            console.print(f"\n结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
            console.print(f"总耗时: {int(duration // 60)}分{int(duration % 60)}秒")

            if result.get("success"):
                console.print("[green]✓ 执行成功![/green]")
                return 0
            else:
                console.print("[red]✗ 执行失败[/red]")
                if "error" in result:
                    console.print(f"错误: {result['error']}")
                return 1

        except KeyboardInterrupt:
            console.print("\n[yellow]⚠ 用户中断执行[/yellow]")
            return 130  # SIGINT exit code

        except Exception as e:
            console.print(f"\n[red]✗ 执行异常: {e}[/red]")
            logger.exception("详细错误:")
            return 1

        finally:
            # 总是清理资源
            await self.cleanup()


# ========== CLI命令定义 ==========

app = typer.Typer(help="Temu自动发布系统 - 生产环境主脚本")


@app.command()
def run(
    input_file: Path = typer.Argument(..., help="输入文件路径(Excel或JSON)"),
    input_type: str | None = typer.Option(
        None, "--type", "-t", help="输入类型(excel/json),不指定则根据文件扩展名自动判断"
    ),
    config: Path | None = typer.Option(
        None, "--config", "-c", help="配置文件路径(默认: config/production.yaml)"
    ),
    staff_name: str | None = typer.Option(
        None, "--staff-name", "-s", help="人员名称(用于筛选采集箱中的产品)"
    ),
    batch_edit: bool = typer.Option(True, "--batch-edit/--no-batch-edit", help="是否启用批量编辑"),
    publish: bool = typer.Option(True, "--publish/--no-publish", help="是否启用发布"),
    ai_titles: bool = typer.Option(True, "--ai-titles/--no-ai-titles", help="是否使用AI生成标题"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Dry-run模式,不实际执行"),
    skip_health_check: bool = typer.Option(False, "--skip-health-check", help="跳过健康检查"),
):
    """运行生产环境工作流.

    Examples:
        # 使用Excel输入
        python scripts/run_production.py data/input/selection.xlsx

        # 使用JSON输入,指定人员
        python scripts/run_production.py config/products.json --staff-name 张三

        # Dry-run模式测试
        python scripts/run_production.py products.json --dry-run

        # 仅执行批量编辑,不发布
        python scripts/run_production.py selection.xlsx --no-publish
    """
    # 加载.env文件
    env_file = project_root / ".env"
    if env_file.exists():
        load_dotenv(env_file)

    # 自动判断输入类型
    if input_type is None:
        suffix = input_file.suffix.lower()
        if suffix in [".xlsx", ".xls"]:
            input_type = "excel"
        elif suffix == ".json":
            input_type = "json"
        else:
            console.print("[red]✗ 无法判断输入类型,请使用--type指定[/red]")
            raise typer.Exit(1)

    # 创建运行器
    runner = ProductionRunner(
        input_path=input_file,
        input_type=input_type,
        config_path=config,
        staff_name=staff_name,
        enable_batch_edit=batch_edit,
        enable_publish=publish,
        use_ai_titles=ai_titles,
        dry_run=dry_run,
        skip_health_check=skip_health_check,
    )

    # 运行
    exit_code = asyncio.run(runner.run())
    raise typer.Exit(exit_code)


if __name__ == "__main__":
    app()
