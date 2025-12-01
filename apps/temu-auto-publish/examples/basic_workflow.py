"""
@PURPOSE: 基础工作流示例,演示如何使用temu-auto-publish系统处理选品表
@OUTLINE:
  - def main(): 运行基础工作流示例
  - 步骤1: 配置路径
  - 步骤2: 处理Excel文件
  - 步骤3: 输出结果
@DEPENDENCIES:
  - 内部: config.settings, src.data_processor
@RELATED: test_env.py
"""

from config.settings import settings
from loguru import logger
from src.data_processor.processor import DataProcessor


def main():
    """运行基础工作流示例."""
    logger.info("=" * 60)
    logger.info("Temu 自动发布 - 基础工作流示例")
    logger.info("=" * 60)

    # 确保目录存在
    settings.ensure_directories()

    # 配置路径
    excel_file = settings.get_absolute_path("examples/sample_data/products_sample.xlsx")
    output_file = settings.get_absolute_path("data/output/task_example.json")

    # 检查文件是否存在
    if not excel_file.exists():
        logger.warning(f"示例文件不存在: {excel_file}")
        logger.info("请创建示例 Excel 文件,包含以下列:")
        logger.info("  - 商品名称")
        logger.info("  - 成本价")
        logger.info("  - 类目")
        logger.info("  - 关键词")
        logger.info("  - 备注")
        return

    # 创建处理器
    processor = DataProcessor(
        price_multiplier=settings.price_multiplier,
        supply_multiplier=settings.supply_price_multiplier,
    )

    try:
        # 处理 Excel
        logger.info(f"\n读取文件: {excel_file}")
        task_data = processor.process_excel(excel_file, output_file)

        # 显示结果
        logger.success("\n✓ 处理完成!")
        logger.info(f"  任务 ID: {task_data.task_id}")
        logger.info(f"  产品数量: {len(task_data.products)}")
        logger.info(f"  输出文件: {output_file}")

        # 显示前 3 个产品
        logger.info("\n前 3 个产品:")
        for product in task_data.products[:3]:
            logger.info(f"  {product.id}: {product.original_name}")
            logger.info(f"    成本: ¥{product.cost_price}")
            logger.info(f"    建议售价: ¥{product.suggested_price}")
            logger.info(f"    供货价: ¥{product.supply_price}")

    except Exception as e:
        logger.error(f"\n✗ 处理失败: {e}")
        raise


if __name__ == "__main__":
    main()
