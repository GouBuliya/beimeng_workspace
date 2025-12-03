"""
@PURPOSE: 提供 Temu 发布工作流的 CLI 入口, 强制通过参数指定选品表
@OUTLINE:
  - 定义 Typer 应用入口
  - run() 命令: 解析 CLI 参数并执行 CompletePublishWorkflow
@GOTCHAS:
  - 必须使用 --input/-i 指定选品表 Excel 文件
  - 可选参数继承工作流的行为配置
  - 程序结束时自动导出选择器命中报告到 data/temp
"""

from __future__ import annotations

from pathlib import Path

import typer
from src.utils.selector_hit_recorder import export_selector_report
from src.workflows.complete_publish_workflow import CompletePublishWorkflow

app = typer.Typer(help="Temu 完整发布工作流 CLI")

INPUT_OPTION = typer.Option(
    ...,
    "--input",
    "-i",
    exists=True,
    file_okay=True,
    dir_okay=False,
    resolve_path=True,
    help="选品表 Excel 文件路径",
)

HEADLESS_OPTION = typer.Option(
    None,
    "--headless",
    help="手动覆盖配置文件中的 headless 设置",
)

USE_AI_TITLES_OPTION = typer.Option(
    False,
    "--use-ai-titles/--no-use-ai-titles",
    help="是否启用 AI 标题生成 (默认关闭)",
)

USE_CODEGEN_BATCH_EDIT_OPTION = typer.Option(
    True,
    "--use-codegen-batch-edit/--no-use-codegen-batch-edit",
    help="是否使用 Codegen 录制的批量编辑逻辑",
)

SKIP_FIRST_EDIT_OPTION = typer.Option(
    False,
    "--skip-first-edit",
    help="直接跳过首次编辑阶段, 仅执行后续流程",
)

ONLY_CLAIM_OPTION = typer.Option(
    False,
    "--only-claim",
    help="仅测试认领阶段, 自动跳过首次编辑/批量编辑/发布",
)

USE_API_BATCH_EDIT_OPTION = typer.Option(
    True,
    "--use-api-batch-edit/--no-use-api-batch-edit",
    help="是否使用 API 方式执行批量编辑 (更快速, 支持文件上传, 默认开启)",
)


@app.command()
def run(
    input: Path = INPUT_OPTION,
    headless: bool | None = HEADLESS_OPTION,
    use_ai_titles: bool = USE_AI_TITLES_OPTION,
    use_codegen_batch_edit: bool = USE_CODEGEN_BATCH_EDIT_OPTION,
    skip_first_edit: bool = SKIP_FIRST_EDIT_OPTION,
    only_claim: bool = ONLY_CLAIM_OPTION,
    use_api_batch_edit: bool = USE_API_BATCH_EDIT_OPTION,
) -> None:
    """执行 Temu 完整发布工作流."""
    try:
        workflow = CompletePublishWorkflow(
            selection_table=input,
            headless=headless,
            use_ai_titles=use_ai_titles,
            use_codegen_batch_edit=use_codegen_batch_edit,
            skip_first_edit=skip_first_edit,
            only_claim=only_claim,
            use_api_batch_edit=use_api_batch_edit,
        )
        workflow.execute()
    finally:
        # 无论成功或失败,都导出选择器命中报告
        export_selector_report("D:/codespace/beimeng_workspace/data/temp")


if __name__ == "__main__":
    app()
