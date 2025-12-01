"""
@PURPOSE: 格式化产品 Excel 文件,自动匹配产品图片路径
@OUTLINE:
  - format_excel(): 主函数,格式化 Excel 并匹配图片
  - find_product_image(): 自动查找产品图片
  - validate_image_paths(): 验证图片路径是否存在
"""

import re
import sys
from pathlib import Path

import pandas as pd
import typer
from loguru import logger
from rich.console import Console
from rich.table import Table

app = typer.Typer()
console = Console()


def find_product_image(
    product_name: str,
    suffix: str,
    spec_index: int,
    image_dir: Path,
) -> str:
    """自动查找产品图片。

    Args:
        product_name: 产品名称。
        suffix: 标题后缀。
        spec_index: 规格序号(从1开始)。
        image_dir: 图片目录。

    Returns:
        相对于 data/image/ 的图片路径,如果未找到返回空字符串。
    """
    # 尝试的文件名模式(按优先级)
    patterns = [
        f"{suffix}_{spec_index}",  # A026_1
        f"{suffix}",  # A026 (单规格)
        f"{product_name}_{spec_index}",  # 卫生间收纳柜_1
        f"{product_name}",  # 卫生间收纳柜 (单规格)
    ]

    # 支持的扩展名
    extensions = [".jpg", ".jpeg", ".png", ".webp"]

    for pattern in patterns:
        for ext in extensions:
            img_path = image_dir / f"{pattern}{ext}"
            if img_path.exists():
                # 返回相对于 data/image/ 的路径
                return f"products/{img_path.name}"

    return ""


@app.command()
def format_excel(
    input_file: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        help="输入的原始 Excel 文件路径",
    ),
    output_file: Path = typer.Option(
        None,
        "--output",
        "-o",
        help="输出的格式化 Excel 文件路径(默认: 原文件名_格式化.xlsx)",
    ),
    auto_match_images: bool = typer.Option(
        True,
        "--auto-match/--no-auto-match",
        help="是否自动匹配产品图片",
    ),
) -> None:
    """格式化产品 Excel 文件,便于脚本调用。

    功能:
    - 规范化列名和数据结构
    - 自动匹配产品图片路径
    - 验证图片文件是否存在
    - 生成统计报告
    """
    logger.info("开始格式化 Excel 文件: {}", input_file)

    # 确定输出文件路径
    if output_file is None:
        output_file = input_file.parent / f"{input_file.stem}_格式化.xlsx"

    # 读取原始 Excel
    try:
        df = pd.read_excel(input_file)
    except Exception as e:
        logger.error("读取 Excel 文件失败: {}", e)
        raise typer.Exit(1) from e

    logger.info(f"原始数据: {len(df)} 行 x {len(df.columns)} 列")

    # 创建标准化的数据结构
    formatted_data = []
    current_product_info = {}
    spec_counters = {}  # 记录每个产品的规格计数器

    for _idx, row in df.iterrows():
        # 如果是新产品(产品名称不为空)
        if pd.notna(row["产品名称"]):
            current_product_info = {
                "到货情况": row["到货情况"] if pd.notna(row["到货情况"]) else "",
                "产品名称": row["产品名称"],
                "标题后缀": row["标题后缀"] if pd.notna(row["标题后缀"]) else "",
                "进货价": row["    进货价"] if pd.notna(row["    进货价"]) else "",
                "核价价格": row["核价价格"] if pd.notna(row["核价价格"]) else "",
                "发货地": row["发货地"] if pd.notna(row["发货地"]) else "",
            }
            # 重置该产品的规格计数器
            product_key = row["产品名称"]
            spec_counters[product_key] = 0

        # 如果有规格信息,创建一条记录
        if pd.notna(row["产品颜色/规格"]) and current_product_info:
            record = current_product_info.copy()
            record["产品颜色/规格"] = row["产品颜色/规格"]

            # 规格序号递增
            product_key = current_product_info["产品名称"]
            spec_counters[product_key] += 1
            record["规格序号"] = spec_counters[product_key]

            # 提取图片 ID (如果有)
            product_img = row.get("产品图")
            image_id = ""
            if pd.notna(product_img) and isinstance(product_img, str):
                # 尝试从 =DISPIMG("ID_xxx",1) 中提取 ID
                match = re.search(r"ID_([A-F0-9]+)", product_img)
                if match:
                    image_id = match.group(1)
                    logger.debug(
                        f"提取图片ID: {record['产品名称']} 规格{record['规格序号']} -> ID_{image_id}"
                    )

            record["图片ID"] = image_id
            record["图片路径"] = ""  # 待填充

            formatted_data.append(record)

    # 创建新的 DataFrame
    formatted_df = pd.DataFrame(formatted_data)

    # 重新排列列顺序
    columns_order = [
        "产品名称",
        "标题后缀",
        "产品颜色/规格",
        "规格序号",
        "图片ID",
        "图片路径",
        "到货情况",
        "进货价",
        "核价价格",
        "发货地",
    ]
    formatted_df = formatted_df[columns_order]

    # 自动匹配图片
    if auto_match_images:
        logger.info("开始自动匹配产品图片...")
        image_dir = input_file.parents[1] / "image" / "products"
        image_dir.mkdir(parents=True, exist_ok=True)

        matched_count = 0
        for idx, row in formatted_df.iterrows():
            if not row["图片路径"]:  # 只处理未填写图片路径的行
                img_path = find_product_image(
                    product_name=row["产品名称"],
                    suffix=row["标题后缀"],
                    spec_index=row["规格序号"],
                    image_dir=image_dir,
                )
                if img_path:
                    formatted_df.at[idx, "图片路径"] = img_path
                    matched_count += 1

        logger.success(f"✓ 自动匹配到 {matched_count} 个产品图片")

    # 保存到新文件
    try:
        # 将所有NaN替换为空字符串,避免Excel中显示为空单元格
        formatted_df = formatted_df.fillna("")
        formatted_df.to_excel(output_file, index=False, engine="openpyxl")
        logger.success(f"✓ 格式化完成! 输出文件: {output_file}")
    except Exception as e:
        logger.error("保存 Excel 文件失败: {}", e)
        raise typer.Exit(1) from e

    # 统计报告
    total_records = len(formatted_df)
    total_products = formatted_df["产品名称"].nunique()
    has_image_id_count = (formatted_df["图片ID"] != "").sum()
    has_image_count = (formatted_df["图片路径"] != "").sum()
    no_image_count = total_records - has_image_count

    # 创建统计表格
    table = Table(title="📊 格式化统计报告", show_header=True)
    table.add_column("指标", style="cyan", no_wrap=True)
    table.add_column("数值", style="magenta")

    table.add_row("总记录数", str(total_records))
    table.add_row("产品数量", str(total_products))
    table.add_row(
        "有图片ID", f"{has_image_id_count} ({has_image_id_count / total_records * 100:.1f}%)"
    )
    table.add_row("已匹配图片", f"{has_image_count} ({has_image_count / total_records * 100:.1f}%)")
    table.add_row("缺失图片", f"{no_image_count} ({no_image_count / total_records * 100:.1f}%)")

    console.print(table)

    # 显示缺失图片的产品
    if no_image_count > 0:
        console.print("\n⚠️  以下产品缺失图片:", style="yellow bold")
        missing_df = formatted_df[formatted_df["图片路径"] == ""]
        for _, row in missing_df.iterrows():
            console.print(f"  • {row['产品名称']} ({row['标题后缀']}) - {row['产品颜色/规格']}")

        console.print(
            f"\n💡 提示: 请将图片放入 {image_dir} 目录,文件名格式:",
            style="blue",
        )
        console.print(f"  - {{标题后缀}}_{{规格序号}}.jpg  (例如: A026_1.jpg)")
        console.print(f"  - 然后重新运行此脚本")

    # 显示产品列表
    console.print("\n📦 产品列表:", style="green bold")
    for product_name in formatted_df["产品名称"].unique():
        spec_count = len(formatted_df[formatted_df["产品名称"] == product_name])
        suffix = formatted_df[formatted_df["产品名称"] == product_name]["标题后缀"].iloc[0]
        console.print(f"  • {product_name} ({suffix}): {spec_count} 个规格")


if __name__ == "__main__":
    app()
