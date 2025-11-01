"""
商品采集功能测试脚本（SOP步骤1-3）

功能：
1. 测试选品表读取
2. 测试Temu店铺访问
3. 测试商品搜索和采集
4. 生成采集报告

使用方法:
    python run_collection_test.py
"""

import asyncio
import os
import sys
from pathlib import Path

# 添加项目根目录到sys.path
sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger

from src.browser.browser_manager import BrowserManager
from src.browser.login_controller import LoginController
from src.data_processor.selection_table_reader import SelectionTableReader
from src.workflows.collection_workflow import CollectionWorkflow


async def test_selection_table_reader():
    """测试1: 选品表读取功能."""
    logger.info("\n" + "=" * 80)
    logger.info("【测试1】选品表读取功能")
    logger.info("=" * 80 + "\n")
    
    reader = SelectionTableReader()
    
    # 创建示例选品表
    sample_file = Path(__file__).parent / "data" / "input" / "sample_selection.xlsx"
    sample_file.parent.mkdir(parents=True, exist_ok=True)
    
    if not sample_file.exists():
        logger.info("创建示例选品表...")
        reader.create_sample_excel(str(sample_file), num_samples=3)
    
    # 读取选品表
    try:
        products = reader.read_excel(str(sample_file))
        logger.success(f"✓ 成功读取 {len(products)} 个产品")
        
        for i, product in enumerate(products):
            logger.info(f"\n产品 {i+1}:")
            logger.info(f"  负责人: {product.owner}")
            logger.info(f"  名称: {product.product_name}")
            logger.info(f"  型号: {product.model_number}")
            logger.info(f"  规格: {product.color_spec}")
            logger.info(f"  采集数量: {product.collect_count}")
        
        return True
    except Exception as e:
        logger.error(f"✗ 选品表读取失败: {e}")
        return False


async def test_collection_workflow():
    """测试2: 完整采集工作流."""
    logger.info("\n" + "=" * 80)
    logger.info("【测试2】完整采集工作流")
    logger.info("=" * 80 + "\n")
    
    # 加载.env环境变量
    try:
        from dotenv import load_dotenv
        env_path = Path(__file__).parent / ".env"
        load_dotenv(env_path, override=True)
        logger.info(f"✓ 环境变量已从 {env_path} 加载")
    except ImportError:
        logger.warning("⚠️  python-dotenv未安装")
    except Exception as e:
        logger.warning(f"⚠️  加载.env失败: {e}")
    
    # 获取账号信息
    temu_url = os.getenv("TEMU_SHOP_URL", "https://agentseller.temu.com/")
    temu_username = os.getenv("TEMU_USERNAME")
    temu_password = os.getenv("TEMU_PASSWORD")
    
    if not temu_username or not temu_password:
        logger.error("✗ 未配置TEMU账号信息（TEMU_USERNAME, TEMU_PASSWORD）")
        logger.info("  请在.env文件中配置Temu账号信息")
        return False
    
    logger.info(f"Temu账号: {temu_username}")
    
    # 初始化浏览器
    browser_manager = BrowserManager(headless=False)
    
    try:
        # 启动浏览器
        await browser_manager.start()
        page = browser_manager.page
        
        # 登录Temu
        logger.info("\n>>> 登录Temu商家后台...")
        login_ctrl = LoginController(browser_manager)
        
        if not await login_ctrl.login_temu(temu_url, temu_username, temu_password):
            logger.error("✗ Temu登录失败")
            return False
        
        logger.success("✓ Temu登录成功")
        
        # 准备选品表
        selection_table = Path(__file__).parent / "data" / "input" / "sample_selection.xlsx"
        
        if not selection_table.exists():
            logger.warning("⚠️  选品表不存在，先创建示例选品表")
            reader = SelectionTableReader()
            reader.create_sample_excel(str(selection_table), num_samples=2)
        
        # 执行采集工作流
        logger.info("\n>>> 开始执行采集工作流...")
        workflow = CollectionWorkflow()
        
        result = await workflow.execute(
            page=page,
            selection_table_path=str(selection_table),
            skip_visit_store=False,  # 测试完整流程
            save_report=True
        )
        
        # 显示结果
        logger.info("\n" + "=" * 80)
        logger.info("【采集结果】")
        logger.info("=" * 80)
        logger.info(f"总产品数: {result['summary']['total_products']}")
        logger.info(f"成功: {result['summary']['success']}")
        logger.info(f"失败: {result['summary']['failed']}")
        logger.info(f"总链接数: {result['summary']['total_links']}")
        
        if result['report_file']:
            logger.info(f"报告文件: {result['report_file']}")
            
            # 额外导出妙手导入链接
            from src.workflows.collection_workflow import CollectionResult
            
            collection_results = [
                CollectionResult(
                    product=None,  # 简化，从dict重建
                    collected_links=p['collected_links'],
                    success=p['success']
                )
                for p in result['products']
            ]
            
            # 生成妙手导入链接文件
            links_file = workflow.export_links_for_miaoshou(
                collection_results,
                output_file=str(Path(result['report_file']).parent / "miaoshou_links.txt")
            )
            logger.info(f"妙手导入链接: {links_file}")
        
        logger.info("=" * 80 + "\n")
        
        # 等待用户查看
        logger.info(">>> 测试完成，浏览器将在5秒后关闭...")
        await asyncio.sleep(5)
        
        return True
        
    except Exception as e:
        logger.error(f"✗ 采集工作流测试失败: {e}")
        logger.exception("详细错误:")
        return False
    finally:
        await browser_manager.close()


async def main():
    """主测试流程."""
    logger.info("\n" + "=" * 100)
    logger.info(" " * 30 + "商品采集功能测试")
    logger.info("=" * 100 + "\n")
    
    # 测试1: 选品表读取
    test1_ok = await test_selection_table_reader()
    
    if not test1_ok:
        logger.error("❌ 测试1失败，停止后续测试")
        return
    
    logger.success("✅ 测试1通过\n")
    
    # 询问是否继续测试2
    logger.info("─" * 80)
    logger.info("测试2将启动浏览器并执行真实采集流程")
    logger.info("需要配置Temu账号信息（.env文件）")
    logger.info("─" * 80)
    
    # 自动继续测试2
    logger.info("\n>>> 5秒后自动开始测试2...\n")
    await asyncio.sleep(5)
    
    # 测试2: 完整采集工作流
    test2_ok = await test_collection_workflow()
    
    if not test2_ok:
        logger.error("❌ 测试2失败")
        return
    
    logger.success("✅ 测试2通过\n")
    
    # 最终总结
    logger.info("\n" + "=" * 100)
    logger.info(" " * 35 + "测试总结")
    logger.info("=" * 100)
    logger.success("✅ 所有测试通过！")
    logger.info("=" * 100 + "\n")


if __name__ == "__main__":
    asyncio.run(main())

