"""
采集到首次编辑完整流程测试（端到端）

功能：
1. 测试从Excel选品表到妙手首次编辑的完整自动化流程
2. 包含所有5个阶段的集成测试
3. 生成详细的执行报告

使用方法:
    python run_collection_to_edit_test.py
    
    或指定选品表:
    python run_collection_to_edit_test.py --selection data/input/my_selection.xlsx
"""

import argparse
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
from src.workflows.collection_to_edit_workflow import CollectionToEditWorkflow


async def main(args):
    """主测试流程."""
    logger.info("\n" + "=" * 100)
    logger.info(" " * 20 + "【采集到编辑完整流程测试】")
    logger.info("=" * 100 + "\n")
    
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
    
    miaoshou_url = os.getenv("MIAOSHOU_URL", "https://erp.91miaoshou.com/sub_account/users")
    miaoshou_username = os.getenv("MIAOSHOU_USERNAME")
    miaoshou_password = os.getenv("MIAOSHOU_PASSWORD")
    
    if not all([miaoshou_username, miaoshou_password]):
        logger.error("✗ 未配置完整的妙手ERP账号信息")
        logger.info("请在.env文件中配置:")
        logger.info("  - MIAOSHOU_USERNAME, MIAOSHOU_PASSWORD")
        return False
    
    # 准备选品表
    selection_table = Path(args.selection) if args.selection else Path(__file__).parent / "data" / "input" / "selection.xlsx"
    
    if not selection_table.exists():
        logger.warning("⚠️  选品表不存在，创建示例选品表...")
        reader = SelectionTableReader()
        selection_table.parent.mkdir(parents=True, exist_ok=True)
        reader.create_sample_excel(str(selection_table), num_samples=2)
        logger.info(f"✓ 示例选品表已创建: {selection_table}")
    
    # 初始化登录控制器
    login_controller = None
    browser_manager = None
    
    try:
        logger.info("\n" + "─" * 80)
        logger.info("步骤1: 初始化并登录妙手ERP")
        logger.info("─" * 80 + "\n")
        
        # 创建登录控制器（会自动创建browser_manager）
        login_controller = LoginController()
        
        # 登录妙手ERP
        logger.info(">>> 登录妙手ERP...")
        if not await login_controller.login(
            username=miaoshou_username,
            password=miaoshou_password,
            force=False,
            headless=False
        ):
            logger.error("✗ 妙手ERP登录失败")
            return False
        
        logger.success("✓ 妙手ERP登录成功\n")
        
        # 获取browser_manager和page
        browser_manager = login_controller.browser_manager
        page = browser_manager.page
        
        # 执行完整工作流
        logger.info("\n" + "─" * 80)
        logger.info("步骤2: 执行采集到编辑完整流程")
        logger.info("─" * 80 + "\n")
        
        workflow = CollectionToEditWorkflow(use_ai_titles=True)
        
        result = await workflow.execute(
            page=page,
            selection_table_path=str(selection_table),
            filter_by_user=miaoshou_username if args.filter_user else None,
            enable_validation=args.enable_validation,
            enable_plugin_collection=args.enable_plugin,
            save_intermediate_results=True
        )
        
        # 显示结果
        logger.info("\n" + "=" * 100)
        logger.info(" " * 35 + "【测试结果】")
        logger.info("=" * 100)
        
        if result["success"]:
            logger.success("✅ 测试通过！完整流程执行成功")
            logger.info(f"\n报告文件: {result['report_file']}")
        else:
            logger.error("❌ 测试失败")
            logger.info(f"\n报告文件: {result['report_file']}")
            if result["errors"]:
                logger.error("\n错误列表:")
                for error in result["errors"]:
                    logger.error(f"  - {error}")
        
        logger.info("=" * 100 + "\n")
        
        # 等待用户查看
        if not args.no_wait:
            logger.info(">>> 测试完成，浏览器将在5秒后关闭...")
            await asyncio.sleep(5)
        
        return result["success"]
        
    except Exception as e:
        logger.error(f"✗ 测试执行失败: {e}")
        logger.exception("详细错误:")
        return False
    finally:
        if login_controller and login_controller.browser_manager:
            await login_controller.browser_manager.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="采集到编辑完整流程测试")
    
    parser.add_argument(
        "--selection",
        type=str,
        help="Excel选品表路径（默认: data/input/selection.xlsx）"
    )
    
    parser.add_argument(
        "--no-wait",
        action="store_true",
        help="测试完成后不等待，立即关闭"
    )
    
    parser.add_argument(
        "--filter-user",
        action="store_true",
        help="在妙手采集箱中筛选当前用户"
    )
    
    parser.add_argument(
        "--enable-validation",
        action="store_true",
        default=True,
        help="启用采集结果验证（默认: 启用）"
    )
    
    parser.add_argument(
        "--enable-plugin",
        action="store_true",
        default=True,
        help="启用妙手插件自动采集（默认: 启用）"
    )
    
    args = parser.parse_args()
    
    # 运行测试
    success = asyncio.run(main(args))
    
    # 退出码
    sys.exit(0 if success else 1)

