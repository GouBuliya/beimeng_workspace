"""
@PURPOSE: 定义 Web Panel 所需的表单字段与提示信息
@OUTLINE:
  - dataclass FormField: 表单字段结构
  - FORM_FIELDS: 所有 Web 表单字段元数据
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

FieldKind = Literal["file", "path", "toggle", "choice"]


@dataclass(frozen=True, slots=True)
class FormField:
    """Web Panel 表单字段描述."""

    name: str
    label: str
    help_text: str
    kind: FieldKind
    default: str | bool | None = None
    required: bool = False
    placeholder: str | None = None
    options: list[tuple[str, str]] | None = None
    accept: str | None = None


FORM_FIELDS: tuple[FormField, ...] = (
    FormField(
        name="selection_file",
        label="选品表文件",
        help_text="点击选择最新的 Excel/CSV 选品表, 系统会自动保存到 data/input。",
        kind="file",
        required=False,
        accept=".xlsx,.xls,.csv",
    ),
    FormField(
        name="selection_path",
        label="或已有文件路径",
        help_text="若文件已位于服务器, 可直接粘贴绝对路径 (例如 C:\\选品\\10月新品.xlsx)。",
        kind="path",
        placeholder="例如 C:\\data\\temu\\selection.xlsx 或 /Users/xxx/selection.xlsx",
    ),
    FormField(
        name="outer_package_file",
        label="外包装图片 (可选)",
        help_text="上传 .png/.jpg/.jpeg/.webp 等图片，供批量编辑第 7.5 步复用。",
        kind="file",
        required=False,
        accept=".png,.jpg,.jpeg,.webp",
    ),
    FormField(
        name="outer_package_path",
        label="或外包装图片路径",
        help_text="若文件已在服务器，可填写绝对路径（示例: C:\\assets\\packaging.png）。",
        kind="path",
        placeholder="例如 C:\\assets\\packaging.png 或 /data/packaging.png",
    ),
    FormField(
        name="manual_file",
        label="说明书 PDF (可选)",
        help_text="上传产品说明书 PDF，供批量编辑第 7.18 步使用。",
        kind="file",
        required=False,
        accept=".pdf",
    ),
    FormField(
        name="manual_path",
        label="或说明书文件路径",
        help_text="已存在的 PDF 绝对路径（示例: C:\\docs\\manual.pdf）。未配置时使用默认模板。",
        kind="path",
        placeholder="例如 C:\\docs\\manual.pdf 或 /data/manuals/booklet.pdf",
    ),
    FormField(
        name="headless_mode",
        label="浏览器模式",
        help_text="若不确定请选择“跟随配置”, 仅在需要看见浏览器过程时切换为“显示窗口”。",
        kind="choice",
        default="auto",
        options=[
            ("auto", "跟随配置 (推荐)"),
            ("on", "显示窗口"),
            ("off", "隐藏窗口"),
        ],
    ),
    FormField(
        name="use_ai_titles",
        label="启用 AI 标题生成",
        help_text="自动尝试生成更优标题, 失败时会回退为手动标题。",
        kind="toggle",
        default=False,
    ),
    FormField(
        name="use_codegen_first_edit",
        label="使用录制的首次编辑流程",
        help_text="勾选后将使用稳定录制脚本, 关闭后使用实时操作 (便于排查)。",
        kind="toggle",
        default=True,
    ),
    FormField(
        name="use_codegen_batch_edit",
        label="使用录制的批量编辑流程",
        help_text="默认使用 18 步录制流程, 如遇异常可关闭改为手动流程。",
        kind="toggle",
        default=True,
    ),
    FormField(
        name="skip_first_edit",
        label="跳过首次编辑",
        help_text="已手动完成首次编辑时可开启, 系统会直接进入认领阶段。",
        kind="toggle",
        default=False,
    ),
    FormField(
        name="only_claim",
        label="仅执行认领",
        help_text="仅验证认领步骤, 自动跳过首次编辑/批量编辑/发布。",
        kind="toggle",
        default=False,
    ),
)
