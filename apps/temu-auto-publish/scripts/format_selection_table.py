"""
@PURPOSE: 格式化原始选品表Excel文件，转换为标准格式
@OUTLINE:
  - def parse_complex_excel(): 解析复杂的多行格式Excel
  - def convert_to_standard_format(): 转换为标准选品表格式
  - def main(): 主函数
@GOTCHAS:
  - 原始Excel中一个产品可能占多行（主行+规格行）
  - 需要向下填充产品名称和标题后缀
  - 规格信息需要合并
@DEPENDENCIES:
  - 外部: pandas, openpyxl
"""

import argparse
import sys
from pathlib import Path
from typing import List, Dict

import pandas as pd
from loguru import logger


def parse_complex_excel(input_file: str) -> pd.DataFrame:
    """解析复杂格式的Excel文件.
    
    处理以下格式：
    - 产品名称在第一行，后续行为空
    - 标题后缀可能在第一行或后续行
    - 规格分布在多行
    
    Args:
        input_file: 输入Excel文件路径
        
    Returns:
        解析后的DataFrame
    """
    logger.info(f"读取Excel文件: {input_file}")
    
    # 读取所有数据
    df = pd.read_excel(input_file)
    
    logger.info(f"✓ 读取成功，共 {len(df)} 行，{len(df.columns)} 列")
    logger.debug(f"列名: {df.columns.tolist()}")
    
    return df


def convert_to_standard_format(df: pd.DataFrame) -> pd.DataFrame:
    """转换为标准选品表格式.
    
    标准格式要求：
    - 主品负责人
    - 产品名称
    - 标题后缀
    - 产品颜色/规格
    - 采集数量
    
    Args:
        df: 原始DataFrame
        
    Returns:
        标准格式的DataFrame
    """
    logger.info("开始转换为标准格式...")
    
    # 提取关键列
    key_columns = {
        '到货情况': '到货情况',
        '产品名称': '产品名称',
        '标题后缀': '标题后缀',
        '产品颜色/规格': '产品颜色/规格',
        '    进货价': '进货价',
    }
    
    # 检查列是否存在
    missing_cols = [col for col in key_columns.keys() if col not in df.columns]
    if missing_cols:
        logger.warning(f"缺失列: {missing_cols}")
    
    # 创建工作副本
    work_df = df[list(key_columns.keys())].copy()
    work_df.columns = list(key_columns.values())
    
    # 向下填充产品名称和标题后缀
    logger.info("向下填充产品名称和标题后缀...")
    work_df['产品名称'] = work_df['产品名称'].ffill()
    work_df['标题后缀'] = work_df['标题后缀'].ffill()
    
    # 过滤掉无效行（没有规格信息的）
    logger.info("过滤无效行...")
    work_df = work_df[work_df['产品颜色/规格'].notna()].copy()
    
    # 添加采集数量（默认5个）
    work_df['采集数量'] = 5
    
    # 添加负责人（默认为空，需要手动填写）
    work_df['主品负责人'] = ''
    
    # 重新排列列顺序
    standard_df = work_df[[
        '主品负责人',
        '产品名称',
        '标题后缀',
        '产品颜色/规格',
        '采集数量'
    ]].copy()
    
    # 清理数据
    logger.info("清理数据...")
    standard_df = standard_df.dropna(subset=['产品名称', '标题后缀'])
    
    logger.success(f"✓ 转换完成，共 {len(standard_df)} 条有效数据")
    
    return standard_df


def validate_output(df: pd.DataFrame) -> bool:
    """验证输出数据的有效性.
    
    Args:
        df: 待验证的DataFrame
        
    Returns:
        是否通过验证
    """
    logger.info("验证输出数据...")
    
    issues = []
    
    # 检查必填列
    required_cols = ['主品负责人', '产品名称', '标题后缀', '产品颜色/规格', '采集数量']
    for col in required_cols:
        if col not in df.columns:
            issues.append(f"缺少必填列: {col}")
    
    # 检查空值
    for col in ['产品名称', '标题后缀', '产品颜色/规格']:
        null_count = df[col].isna().sum()
        if null_count > 0:
            issues.append(f"列 '{col}' 有 {null_count} 个空值")
    
    # 检查采集数量
    if '采集数量' in df.columns:
        invalid_counts = df[~df['采集数量'].between(1, 100)]
        if len(invalid_counts) > 0:
            issues.append(f"有 {len(invalid_counts)} 行的采集数量不在1-100范围内")
    
    if issues:
        logger.warning("⚠️  发现以下问题:")
        for issue in issues:
            logger.warning(f"  - {issue}")
        return False
    
    logger.success("✓ 数据验证通过")
    return True


def show_preview(df: pd.DataFrame, n: int = 10):
    """显示数据预览.
    
    Args:
        df: DataFrame
        n: 显示行数
    """
    logger.info(f"\n{'='*80}")
    logger.info(f"📋 数据预览（前{n}行）")
    logger.info(f"{'='*80}")
    print(df.head(n).to_string(index=False))
    
    logger.info(f"\n{'='*80}")
    logger.info(f"📊 数据统计")
    logger.info(f"{'='*80}")
    logger.info(f"总行数: {len(df)}")
    logger.info(f"产品数: {df['产品名称'].nunique()}")
    logger.info(f"规格数: {len(df)}")
    logger.info(f"\n产品列表（前10个）:")
    for i, prod in enumerate(df['产品名称'].unique()[:10], 1):
        count = len(df[df['产品名称'] == prod])
        logger.info(f"  {i}. {prod} ({count}个规格)")


def main():
    """主函数."""
    parser = argparse.ArgumentParser(
        description="格式化10月品Excel选品表",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 基本用法
  python format_selection_table.py ../../10月品.xlsx
  
  # 指定输出文件
  python format_selection_table.py ../../10月品.xlsx -o selection_formatted.xlsx
  
  # 只预览不保存
  python format_selection_table.py ../../10月品.xlsx --preview-only
        """
    )
    
    parser.add_argument(
        'input_file',
        help='输入Excel文件路径'
    )
    
    parser.add_argument(
        '-o', '--output',
        default='selection_formatted.xlsx',
        help='输出文件名（默认: selection_formatted.xlsx）'
    )
    
    parser.add_argument(
        '--preview-only',
        action='store_true',
        help='只预览数据，不保存文件'
    )
    
    parser.add_argument(
        '--preview-lines',
        type=int,
        default=10,
        help='预览行数（默认: 10）'
    )
    
    args = parser.parse_args()
    
    try:
        # 解析Excel
        df = parse_complex_excel(args.input_file)
        
        # 转换格式
        standard_df = convert_to_standard_format(df)
        
        # 验证
        validate_output(standard_df)
        
        # 预览
        show_preview(standard_df, args.preview_lines)
        
        # 保存
        if not args.preview_only:
            output_path = Path(args.output)
            if not output_path.is_absolute():
                # 保存到data/input目录
                output_path = Path(__file__).parent.parent / 'data' / 'input' / output_path
            
            output_path.parent.mkdir(parents=True, exist_ok=True)
            standard_df.to_excel(output_path, index=False)
            
            logger.success(f"\n✅ 文件已保存: {output_path}")
            logger.info(f"   总行数: {len(standard_df)}")
            logger.info(f"   产品数: {standard_df['产品名称'].nunique()}")
            logger.info(f"\n💡 使用方法:")
            logger.info(f"   python run_collection_to_edit_test.py --selection {output_path}")
        else:
            logger.info("\n⏭️  预览模式：未保存文件")
    
    except FileNotFoundError:
        logger.error(f"❌ 文件不存在: {args.input_file}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ 处理失败: {e}")
        logger.exception("详细错误:")
        sys.exit(1)


if __name__ == "__main__":
    main()

