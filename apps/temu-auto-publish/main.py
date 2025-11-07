"""
@PURPOSE: 提供 Temu 发布工作流的 CLI 入口, 强制通过参数指定选品表
@OUTLINE:
  - 定义 Typer 应用入口
  - run() 命令: 解析 CLI 参数并执行 CompletePublishWorkflow
@GOTCHAS:
  - 必须使用 --input/-i 指定选品表 Excel 文件
  - 可选参数继承工作流的行为配置
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from src.workflows.complete_publish_workflow import CompletePublishWorkflow

app = typer.Typer(help="Temu 完整发布工作流 CLI")


@app.command()
def run(
    input: Path = typer.Option(
        ...,
        "--input",
        "-i",
        exists=True,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
        help="选品表 Excel 文件路径",
    ),
    headless: Optional[bool] = typer.Option(
        None,
        "--headless",
        help="手动覆盖配置文件中的 headless 设置",
    ),
    use_ai_titles: bool = typer.Option(
        False,
        "--use-ai-titles/--no-use-ai-titles",
        help="是否启用 AI 标题生成 (默认关闭)",
    ),
    use_codegen_first_edit: bool = typer.Option(
        True,
        "--use-codegen-first-edit/--no-use-codegen-first-edit",
        help="是否使用 Codegen 录制的首次编辑逻辑",
    ),
    use_codegen_batch_edit: bool = typer.Option(
        True,
        "--use-codegen-batch-edit/--no-use-codegen-batch-edit",
        help="是否使用 Codegen 录制的批量编辑逻辑",
    ),
    skip_first_edit: bool = typer.Option(
        False,
        "--skip-first-edit",
        help="直接跳过首次编辑阶段, 仅执行后续流程",
    ),
) -> None:
    """执行 Temu 完整发布工作流."""

    workflow = CompletePublishWorkflow(
        selection_table=input,
        headless=headless,
        use_ai_titles=use_ai_titles,
        use_codegen_first_edit=use_codegen_first_edit,
        use_codegen_batch_edit=use_codegen_batch_edit,
        skip_first_edit=skip_first_edit,
    )
    workflow.execute()


if __name__ == "__main__":
    app()
