"""
@PURPOSE: CLI 工作流命令 - 执行和管理工作流
@OUTLINE:
  - workflow_app: Typer 工作流命令组
  - run(): 执行工作流
  - resume(): 恢复工作流
  - list(): 列出工作流历史
  - status(): 查看工作流状态
@GOTCHAS:
  - 非交互式设计,所有参数通过命令行或配置文件提供
  - 工作流执行需要浏览器,确保 Playwright 已安装
@DEPENDENCIES:
  - 内部: src.core.executor, src.workflows, src.browser
  - 外部: typer, rich
"""

import asyncio
import json
import os
from pathlib import Path

import typer
from config.settings import settings
from dotenv import load_dotenv
from loguru import logger
from rich.console import Console
from rich.table import Table

# 加载 .env 文件
env_file = Path(__file__).parent.parent.parent / ".env"
if env_file.exists():
    load_dotenv(env_file)
import builtins
import contextlib

from src.browser.login_controller import LoginController
from src.core.executor import WorkflowExecutor
from src.workflows.complete_publish_workflow import CompletePublishWorkflow

workflow_app = typer.Typer(
    name="workflow",
    help="工作流执行和管理",
)

console = Console()


@workflow_app.command("run")
def run(
    products_file: Path | None = typer.Option(None, "--products", "-p", help="产品数据文件(JSON)"),
    config_file: Path | None = typer.Option(
        None, "--config", "-c", help="工作流配置文件(YAML/JSON)"
    ),
    workflow_id: str | None = typer.Option(None, "--id", help="自定义工作流ID"),
    enable_batch_edit: bool = typer.Option(
        True, "--batch-edit/--no-batch-edit", help="启用批量编辑"
    ),
    enable_publish: bool = typer.Option(False, "--publish/--no-publish", help="启用发布(默认关闭)"),
    shop_name: str | None = typer.Option(None, "--shop", help="店铺名称"),
    staff_name: str | None = typer.Option(None, "--staff", help="人员名称(用于筛选采集箱中的产品)"),
    use_ai_titles: bool = typer.Option(
        True, "--use-ai-titles/--no-ai-titles", help="是否使用AI生成产品标题(默认启用)"
    ),
    output: Path | None = typer.Option(None, "--output", "-o", help="结果输出文件"),
):
    """执行完整工作流(5→20→批量编辑→发布).

    Examples:
        # 使用默认产品数据
        temu-auto-publish workflow run

        # 指定产品文件
        temu-auto-publish workflow run -p products.json

        # 启用发布
        temu-auto-publish workflow run --publish --shop "店铺A"

        # 自定义工作流ID
        temu-auto-publish workflow run --id my-workflow-001

        # 禁用AI标题生成
        temu-auto-publish workflow run --no-ai-titles

        # 筛选特定人员并使用AI标题
        temu-auto-publish workflow run --staff "张三" --use-ai-titles
    """
    console.print("\n[bold blue]🚀 Temu 自动发布 - 工作流执行[/bold blue]\n")

    # 加载产品数据
    if products_file and products_file.exists():
        try:
            products = json.loads(products_file.read_text(encoding="utf-8"))
            console.print(f"[green]✓[/green] 已加载产品数据: {len(products)} 个产品")
        except Exception as e:
            console.print(f"[red]✗[/red] 加载产品数据失败: {e}")
            raise typer.Exit(1) from None
    else:
        # 使用默认演示数据
        products = [
            {
                "keyword": "药箱收纳盒",
                "model_number": f"A000{i}",
                "cost": 10.0 + i,
                "stock": 100,
            }
            for i in range(1, 6)
        ]
        console.print(f"[yellow]⚠[/yellow] 使用默认演示数据: {len(products)} 个产品")

    # 如果指定了人员名称,添加到产品数据中
    if staff_name:
        for product in products:
            product["staff_name"] = staff_name
        console.print(f"[green]✓[/green] 人员筛选: {staff_name}")

    # 加载配置
    config = {}
    if config_file and config_file.exists():
        import yaml

        try:
            with config_file.open("r", encoding="utf-8") as f:
                if config_file.suffix in [".yaml", ".yml"]:
                    config = yaml.safe_load(f)
                else:
                    config = json.load(f)
            console.print(f"[green]✓[/green] 已加载配置文件: {config_file.name}")
        except Exception as e:
            console.print(f"[red]✗[/red] 加载配置失败: {e}")
            raise typer.Exit(1) from None

    # 获取登录凭证
    username = os.getenv("MIAOSHOU_USERNAME") or os.getenv("TEMU_USERNAME")
    password = os.getenv("MIAOSHOU_PASSWORD") or os.getenv("TEMU_PASSWORD")

    if not username or not password:
        console.print("[red]✗[/red] 未找到登录凭证")
        console.print("  请设置环境变量或在 .env 文件中配置:")
        console.print("  - MIAOSHOU_USERNAME / TEMU_USERNAME")
        console.print("  - MIAOSHOU_PASSWORD / TEMU_PASSWORD")
        raise typer.Exit(1) from None

    console.print(f"[green]✓[/green] 登录账号: {username}")

    # 显示工作流配置
    console.print("\n[bold]工作流配置:[/bold]")
    console.print(f"  批量编辑: {'✓ 启用' if enable_batch_edit else '✗ 禁用'}")
    console.print(f"  发布: {'✓ 启用' if enable_publish else '✗ 禁用'}")
    console.print(f"  AI标题生成: {'✓ 启用' if use_ai_titles else '✗ 禁用'}")
    if shop_name:
        console.print(f"  店铺: {shop_name}")
    if staff_name:
        console.print(f"  人员筛选: {staff_name}")
    console.print(f"  环境: {settings.environment}")
    console.print(f"  重试: {settings.retry.max_attempts} 次")

    # 执行工作流
    console.print("\n[bold cyan]开始执行工作流...[/bold cyan]\n")

    result = asyncio.run(
        _execute_workflow(
            products=products,
            config=config,
            workflow_id=workflow_id,
            username=username,
            password=password,
            enable_batch_edit=enable_batch_edit,
            enable_publish=enable_publish,
            shop_name=shop_name,
            use_ai_titles=use_ai_titles,
        )
    )

    # 显示结果
    console.print("\n" + "=" * 80)
    console.print("[bold]执行结果[/bold]")
    console.print("=" * 80 + "\n")

    if result["success"]:
        console.print("[green]✓ 工作流执行成功![/green]\n")
    else:
        console.print("[red]✗ 工作流执行失败[/red]\n")

    # 阶段结果
    for stage_name, stage_result in result.items():
        if stage_name.startswith("stage") and isinstance(stage_result, dict):
            status = "✓" if stage_result.get("success") else "✗"
            console.print(f"{status} {stage_name}: {stage_result.get('message', '')}")

    # 保存结果
    if output:
        try:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
            console.print(f"\n[green]✓[/green] 结果已保存: {output}")
        except Exception as e:
            console.print(f"\n[red]✗[/red] 保存结果失败: {e}")

    # 退出码
    if not result["success"]:
        raise typer.Exit(1) from None


@workflow_app.command("resume")
def resume(
    state_file: Path = typer.Argument(..., help="工作流状态文件"),
    output: Path | None = typer.Option(None, "--output", "-o", help="结果输出文件"),
):
    """从状态文件恢复并继续执行工作流.

    Examples:
        temu-auto-publish workflow resume data/workflow_states/workflow_xxx.json
        temu-auto-publish workflow resume state.json -o result.json
    """
    console.print("\n[bold blue]🔄 工作流恢复[/bold blue]\n")

    if not state_file.exists():
        console.print(f"[red]✗[/red] 状态文件不存在: {state_file}")
        raise typer.Exit(1) from None

    console.print(f"[green]✓[/green] 加载状态文件: {state_file.name}")

    # TODO: 实现恢复逻辑
    console.print("[yellow]⚠[/yellow] 恢复功能正在开发中...")


@workflow_app.command("list")
def list_workflows(
    limit: int = typer.Option(10, "--limit", "-n", help="显示数量"),
    status: str | None = typer.Option(None, "--status", help="按状态筛选"),
):
    """列出工作流执行历史.

    Examples:
        temu-auto-publish workflow list
        temu-auto-publish workflow list -n 20
        temu-auto-publish workflow list --status completed
    """
    console.print("\n[bold blue]📋 工作流历史[/bold blue]\n")

    # 查找状态文件
    state_dir = settings.get_absolute_path(settings.workflow.state_dir)

    if not state_dir.exists():
        console.print("[yellow]⚠[/yellow] 暂无工作流历史")
        return

    state_files = sorted(state_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[
        :limit
    ]

    if not state_files:
        console.print("[yellow]⚠[/yellow] 暂无工作流历史")
        return

    # 创建表格
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("工作流ID", style="cyan")
    table.add_column("状态", style="green")
    table.add_column("当前阶段")
    table.add_column("开始时间")
    table.add_column("更新时间")

    for state_file in state_files:
        try:
            state_data = json.loads(state_file.read_text(encoding="utf-8"))

            # 筛选状态
            if status and state_data.get("status") != status:
                continue

            table.add_row(
                state_data.get("workflow_id", "")[:16],
                state_data.get("status", ""),
                state_data.get("current_stage", "-"),
                state_data.get("start_time", "")[:19],
                state_data.get("update_time", "")[:19],
            )
        except Exception as e:
            logger.warning(f"读取状态文件失败: {e}")

    console.print(table)
    console.print(f"\n共 {len(state_files)} 个工作流")


@workflow_app.command("status")
def workflow_status(
    workflow_id: str = typer.Argument(..., help="工作流ID"),
):
    """查看工作流详细状态.

    Examples:
        temu-auto-publish workflow status workflow_abc123
    """
    console.print(f"\n[bold blue]📊 工作流状态: {workflow_id}[/bold blue]\n")

    # 查找状态文件
    state_dir = settings.get_absolute_path(settings.workflow.state_dir)
    state_files = list(state_dir.glob(f"{workflow_id}*.json"))

    if not state_files:
        console.print(f"[red]✗[/red] 未找到工作流: {workflow_id}")
        raise typer.Exit(1) from None

    state_file = state_files[0]
    state_data = json.loads(state_file.read_text(encoding="utf-8"))

    # 显示详细信息
    console.print(f"[bold]工作流ID:[/bold] {state_data.get('workflow_id')}")
    console.print(f"[bold]状态:[/bold] {state_data.get('status')}")
    console.print(f"[bold]当前阶段:[/bold] {state_data.get('current_stage', '-')}")
    console.print(f"[bold]开始时间:[/bold] {state_data.get('start_time')}")
    console.print(f"[bold]更新时间:[/bold] {state_data.get('update_time')}")

    # 已完成阶段
    completed = state_data.get("completed_stages", [])
    if completed:
        console.print("\n[bold]已完成阶段:[/bold]")
        for stage in completed:
            console.print(f"  ✓ {stage}")

    # 失败阶段
    failed = state_data.get("failed_stages", [])
    if failed:
        console.print("\n[bold]失败阶段:[/bold]")
        for stage in failed:
            console.print(f"  ✗ {stage}")

    # 检查点数据
    checkpoint = state_data.get("checkpoint_data", {})
    if checkpoint:
        console.print("\n[bold]检查点数据:[/bold]")
        for key, value in checkpoint.items():
            console.print(f"  {key}: {value}")


# ========== 辅助函数 ==========


async def _execute_workflow(
    products: list,
    config: dict,
    workflow_id: str | None,
    username: str,
    password: str,
    enable_batch_edit: bool,
    enable_publish: bool,
    shop_name: str | None,
    use_ai_titles: bool = True,
) -> dict:
    """执行工作流(内部函数)."""
    login_ctrl = None

    try:
        # 初始化
        logger.info("初始化浏览器...")
        login_ctrl = LoginController()
        await login_ctrl.browser_manager.start()
        page = login_ctrl.browser_manager.page

        # 登录
        logger.info("登录...")
        if not await login_ctrl.login(username, password):
            return {"success": False, "error": "登录失败"}

        # 创建执行器
        executor = WorkflowExecutor()

        # 创建工作流
        workflow = CompletePublishWorkflow(use_ai_titles=use_ai_titles)

        # 执行
        async def _run_workflow(page, config, workflow_id, **kwargs):
            return await workflow.execute(
                page=page,
                products_data=products,
                shop_name=shop_name,
                enable_batch_edit=enable_batch_edit,
                enable_publish=enable_publish,
            )

        result = await executor.execute(
            workflow_func=_run_workflow,
            page=page,
            config=config,
            workflow_id=workflow_id,
        )

        return result

    except Exception as e:
        logger.error(f"工作流执行失败: {e}")
        return {"success": False, "error": str(e)}

    finally:
        if login_ctrl:
            with contextlib.suppress(builtins.BaseException):
                await login_ctrl.browser_manager.close()
