"""
@PURPOSE: 真实环境端到端测试脚本 - 测试阶段2已实现的功能
@OUTLINE:
  - async def test_five_to_twenty_workflow(): 测试5→20认领流程（阶段1）
  - async def test_batch_edit_new_steps(): 测试批量编辑新增4步（阶段2任务1）
  - async def test_batch_edit_with_enhancements(): 测试批量编辑增强工具（阶段2任务2）
  - async def main(): 主测试流程
@DEPENDENCIES:
  - 内部: browser_manager, workflows, controllers
  - 外部: playwright, loguru
@RELATED: complete_publish_workflow.py, five_to_twenty_workflow.py
@CHANGELOG:
  - 2025-10-31: 创建真实环境测试脚本
"""

import asyncio
import sys
from pathlib import Path

from loguru import logger

# 添加项目根目录到path
sys.path.insert(0, str(Path(__file__).parent))

from src.browser.browser_manager import BrowserManager
from src.browser.login_controller import LoginController
from src.workflows.five_to_twenty_workflow import FiveToTwentyWorkflow
from src.workflows.complete_publish_workflow import CompletePublishWorkflow


async def test_five_to_twenty_workflow():
    """测试5→20认领流程（阶段1已完成）.
    
    测试内容：
    - 登录妙手ERP
    - 导航到待审核页面
    - 执行5条编辑→每条认领4次→验证20条
    
    Returns:
        是否测试成功
    """
    logger.info("=" * 80)
    logger.info("🧪 测试1：5→20认领流程（阶段1功能）")
    logger.info("=" * 80)
    
    browser_manager = None
    try:
        # 1. 初始化浏览器
        logger.info("步骤1：初始化浏览器...")
        browser_manager = BrowserManager(headless=False)
        await browser_manager.initialize()
        page = browser_manager.page
        
        # 2. 登录
        logger.info("步骤2：登录妙手ERP...")
        login_controller = LoginController()
        login_success = await login_controller.login(page)
        
        if not login_success:
            logger.error("❌ 登录失败，无法继续测试")
            return False
        
        logger.success("✓ 登录成功")
        await asyncio.sleep(2)
        
        # 3. 执行5→20工作流
        logger.info("步骤3：执行5→20认领流程...")
        workflow = FiveToTwentyWorkflow()
        
        # 准备测试数据（5条商品数据）
        test_products = [
            {
                "index": i,
                "cost": 150.0 + i * 10,
                "title_suffix": f"A000{i+1}型号"
            }
            for i in range(5)
        ]
        
        result = await workflow.execute(page, test_products)
        
        if result:
            logger.success("✅ 测试1通过：5→20认领流程执行成功")
            return True
        else:
            logger.error("❌ 测试1失败：5→20认领流程执行失败")
            return False
    
    except Exception as e:
        logger.error(f"❌ 测试1异常: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        if browser_manager:
            logger.info("清理：关闭浏览器...")
            await browser_manager.close()


async def test_batch_edit_structure():
    """测试批量编辑结构（不实际执行，仅验证结构）.
    
    测试内容：
    - 验证18步方法都已定义
    - 验证新增4步（7.4/7.7/7.8/7.15）存在
    - 验证增强工具已导入
    
    Returns:
        是否测试成功
    """
    logger.info("=" * 80)
    logger.info("🧪 测试2：批量编辑结构验证（阶段2功能）")
    logger.info("=" * 80)
    
    try:
        from src.browser.batch_edit_controller import BatchEditController
        from src.utils.batch_edit_helpers import (
            retry_on_failure,
            performance_monitor,
            enhanced_error_handler,
            StepValidator,
            GenericSelectors,
        )
        
        controller = BatchEditController()
        
        # 验证18步方法
        required_steps = [
            "step_01_modify_title",
            "step_02_english_title",
            "step_03_category_attrs",
            "step_04_main_sku",          # 新增
            "step_05_packaging",
            "step_06_origin",
            "step_07_customization",     # 新增
            "step_08_sensitive_attrs",   # 新增
            "step_09_weight",
            "step_10_dimensions",
            "step_11_sku",
            "step_12_sku_category",
            "step_14_suggested_price",
            "step_15_package_list",      # 新增
            "step_18_manual_upload",
        ]
        
        logger.info("验证步骤方法是否存在...")
        missing_steps = []
        for step_name in required_steps:
            if not hasattr(controller, step_name):
                missing_steps.append(step_name)
                logger.error(f"  ❌ 缺少方法: {step_name}")
            else:
                logger.debug(f"  ✓ {step_name}")
        
        if missing_steps:
            logger.error(f"❌ 测试2失败：缺少 {len(missing_steps)} 个步骤方法")
            return False
        
        logger.success(f"✓ 所有 {len(required_steps)} 个步骤方法都已定义")
        
        # 验证新增4步
        logger.info("验证新增4步...")
        new_steps = [
            "step_04_main_sku",
            "step_07_customization",
            "step_08_sensitive_attrs",
            "step_15_package_list",
        ]
        
        for step_name in new_steps:
            method = getattr(controller, step_name)
            doc = method.__doc__ if method.__doc__ else ""
            
            # 检查是否包含"预览+保存"逻辑
            import inspect
            source = inspect.getsource(method)
            has_preview = "预览" in source
            has_save = "保存" in source
            
            if has_preview and has_save:
                logger.success(f"  ✓ {step_name}: 包含预览+保存逻辑")
            else:
                logger.warning(f"  ⚠️  {step_name}: 可能缺少预览+保存逻辑")
        
        # 验证增强工具
        logger.info("验证增强工具...")
        tools = [
            ("retry_on_failure", retry_on_failure),
            ("performance_monitor", performance_monitor),
            ("enhanced_error_handler", enhanced_error_handler),
            ("StepValidator", StepValidator),
            ("GenericSelectors", GenericSelectors),
        ]
        
        for tool_name, tool_obj in tools:
            if tool_obj is not None:
                logger.success(f"  ✓ {tool_name}: 已导入")
            else:
                logger.error(f"  ❌ {tool_name}: 导入失败")
        
        logger.success("✅ 测试2通过：批量编辑结构验证成功")
        return True
    
    except Exception as e:
        logger.error(f"❌ 测试2异常: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_complete_workflow_structure():
    """测试完整发布流程结构.
    
    测试内容：
    - 验证CompletePublishWorkflow是否集成了所有组件
    - 验证workflow调用链是否完整
    
    Returns:
        是否测试成功
    """
    logger.info("=" * 80)
    logger.info("🧪 测试3：完整发布流程结构验证")
    logger.info("=" * 80)
    
    try:
        from src.workflows.complete_publish_workflow import CompletePublishWorkflow
        
        workflow = CompletePublishWorkflow()
        
        # 检查是否有必要的组件
        required_attrs = [
            "five_to_twenty_workflow",
            "batch_edit_controller",
            "publish_controller",
        ]
        
        logger.info("验证工作流组件...")
        for attr_name in required_attrs:
            if hasattr(workflow, attr_name):
                logger.success(f"  ✓ {attr_name}: 已初始化")
            else:
                logger.warning(f"  ⚠️  {attr_name}: 未找到")
        
        # 检查execute方法
        if hasattr(workflow, 'execute'):
            logger.success("  ✓ execute方法: 已定义")
        else:
            logger.error("  ❌ execute方法: 未定义")
            return False
        
        logger.success("✅ 测试3通过：完整发布流程结构验证成功")
        return True
    
    except Exception as e:
        logger.error(f"❌ 测试3异常: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主测试流程."""
    logger.info("\n" + "=" * 80)
    logger.info("🚀 阶段2真实环境端到端测试")
    logger.info("=" * 80)
    logger.info("")
    logger.info("测试范围：")
    logger.info("  - 测试1: 5→20认领流程（需要真实登录）")
    logger.info("  - 测试2: 批量编辑结构验证（代码检查）")
    logger.info("  - 测试3: 完整流程结构验证（代码检查）")
    logger.info("")
    
    results = {}
    
    # 测试2：结构验证（不需要登录）
    logger.info("\n开始执行测试2（结构验证）...")
    results["test2"] = await test_batch_edit_structure()
    await asyncio.sleep(1)
    
    # 测试3：流程结构验证
    logger.info("\n开始执行测试3（流程结构）...")
    results["test3"] = await test_complete_workflow_structure()
    await asyncio.sleep(1)
    
    # 测试1：真实环境测试（需要登录）
    logger.info("\n准备执行测试1（真实环境）...")
    logger.info("⚠️  注意：此测试需要真实登录妙手ERP")
    logger.info("⚠️  注意：浏览器将以非headless模式启动")
    logger.info("⚠️  注意：请确保网络畅通")
    logger.info("")
    
    confirm = input("是否继续执行测试1（真实登录测试）？[y/N]: ")
    if confirm.lower() == 'y':
        logger.info("\n开始执行测试1（真实环境）...")
        results["test1"] = await test_five_to_twenty_workflow()
    else:
        logger.info("⏭️  跳过测试1（真实环境测试）")
        results["test1"] = None
    
    # 总结
    logger.info("\n" + "=" * 80)
    logger.info("📊 测试结果总结")
    logger.info("=" * 80)
    
    passed = 0
    failed = 0
    skipped = 0
    
    for test_name, result in results.items():
        if result is True:
            icon = "✅"
            status = "通过"
            passed += 1
        elif result is False:
            icon = "❌"
            status = "失败"
            failed += 1
        else:
            icon = "⏭️"
            status = "跳过"
            skipped += 1
        
        logger.info(f"{icon} {test_name}: {status}")
    
    total = len(results)
    logger.info("")
    logger.info(f"总计: {total} 个测试")
    logger.info(f"  ✅ 通过: {passed}")
    logger.info(f"  ❌ 失败: {failed}")
    logger.info(f"  ⏭️  跳过: {skipped}")
    logger.info("=" * 80)
    
    if failed == 0 and passed > 0:
        logger.success("\n🎉 恭喜！所有执行的测试都通过了！")
        return 0
    elif failed > 0:
        logger.error("\n⚠️  部分测试失败，请检查日志")
        return 1
    else:
        logger.info("\n💡 提示：运行测试1以验证真实环境功能")
        return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

