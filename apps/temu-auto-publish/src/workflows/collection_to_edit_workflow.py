"""
@PURPOSE: 从采集到首次编辑的完整集成工作流（SOP步骤1-4）
@OUTLINE:
  - class CollectionToEditWorkflow: 采集到编辑集成工作流
  - async def execute(): 执行完整流程
  - async def _stage_collect_from_temu(): 阶段1-Temu采集
  - async def _stage_add_to_miaoshou(): 阶段2-添加到妙手
  - async def _stage_navigate_to_collection_box(): 阶段3-导航采集箱
  - async def _stage_verify_collection(): 阶段4-验证采集结果
  - async def _stage_first_edit(): 阶段5-首次编辑
@GOTCHAS:
  - 需要在Temu和妙手之间切换页面context
  - 妙手插件可能无法识别，需要fallback方案
  - 每个阶段都要有完整的错误处理和重试机制
@DEPENDENCIES:
  - 内部: CollectionController, MiaoshouController, FiveToTwentyWorkflow, DataConverter
  - 外部: playwright, loguru
@RELATED: collection_workflow.py, five_to_twenty_workflow.py
@CHANGELOG:
  - 2025-11-01: 初始创建，实现采集到编辑的完整自动化流程
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger
from playwright.async_api import Page

from src.browser.collection_controller import CollectionController
from src.browser.miaoshou_controller import MiaoshouController
from src.data_processor.data_converter import DataConverter
from src.data_processor.selection_table_reader import (
    ProductSelectionRow,
    SelectionTableReader,
)
from src.workflows.five_to_twenty_workflow import FiveToTwentyWorkflow


class CollectionToEditWorkflow:
    """从采集到首次编辑的完整集成工作流（SOP步骤1-4）.
    
    实现从Excel选品表到妙手首次编辑完成的全自动化流程：
    
    阶段0: 读取选品表
    阶段1: Temu采集（SOP步骤1-3）
      1.1 访问Temu店铺
      1.2 搜索商品
      1.3 采集5个链接
    
    阶段2: 添加到妙手（关键衔接点）
      2.1 逐个访问商品详情页
      2.2 点击妙手插件"采集"
      2.3 验证采集成功
    
    阶段3: 导航到妙手采集箱
      3.1 切换到妙手ERP
      3.2 导航到公用采集箱
      3.3 筛选和切换tab
    
    阶段4: 验证采集结果（可选）
      4.1 检查商品数量
      4.2 验证商品信息
    
    阶段5: 首次编辑（SOP步骤4）
      5.1 逐个编辑5个产品
      5.2 AI生成标题
      5.3 设置价格和库存
      5.4 保存修改
    
    Attributes:
        collection_ctrl: 采集控制器
        miaoshou_ctrl: 妙手控制器
        five_to_twenty: 5→20工作流
        table_reader: 选品表读取器
        output_dir: 输出目录
    
    Examples:
        >>> workflow = CollectionToEditWorkflow()
        >>> result = await workflow.execute(
        ...     page,
        ...     selection_table_path="data/input/selection.xlsx",
        ...     enable_validation=True
        ... )
        >>> print(f"成功编辑 {result['stage5_result']['edited_count']} 个产品")
    """
    
    def __init__(
        self,
        use_ai_titles: bool = True,
        output_dir: Optional[str] = None,
        debug_mode: bool = False
    ):
        """初始化集成工作流.
        
        Args:
            use_ai_titles: 是否使用AI生成标题
            output_dir: 输出目录（保存中间结果和报告）
            debug_mode: 是否启用调试模式（逐步执行）
        """
        self.collection_ctrl = CollectionController()
        self.miaoshou_ctrl = MiaoshouController()
        self.five_to_twenty = FiveToTwentyWorkflow(use_ai_titles=use_ai_titles, debug_mode=debug_mode)
        self.table_reader = SelectionTableReader()
        self.use_ai_titles = use_ai_titles
        self.debug_mode = debug_mode
        
        # 设置输出目录
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            self.output_dir = Path(__file__).parent.parent.parent / "data" / "output" / "collection_to_edit"
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("【采集到编辑集成工作流】初始化完成")
        logger.info(f"  AI标题生成: {'启用' if use_ai_titles else '禁用'}")
        logger.info(f"  输出目录: {self.output_dir}")
    
    async def execute(
        self,
        page: Page,
        selection_table_path: str,
        filter_by_user: Optional[str] = None,
        enable_validation: bool = True,
        enable_plugin_collection: bool = True,
        save_intermediate_results: bool = True,
        skip_temu_collection: bool = True
    ) -> Dict:
        """执行从采集到首次编辑的完整流程（工业化版本）.
        
        Args:
            page: Playwright页面对象
            selection_table_path: Excel选品表文件路径
            filter_by_user: 妙手采集箱用户筛选（如"张三(zhangsan123)"）
            enable_validation: 是否启用采集结果验证
            enable_plugin_collection: 是否使用妙手插件采集
            save_intermediate_results: 是否保存中间结果
            skip_temu_collection: 是否跳过Temu采集（简化模式，默认True）
            
        Returns:
            执行结果字典，包含：
            - success: 是否成功
            - stages: 各阶段结果
            - summary: 汇总统计
            - report_file: 报告文件路径
            - errors: 错误列表
            
        Raises:
            FileNotFoundError: 选品表文件不存在
            RuntimeError: 关键阶段失败
        """
        logger.info("\n" + "=" * 100)
        logger.info(" " * 25 + "【采集到编辑完整集成工作流】")
        logger.info("=" * 100)
        logger.info(f"选品表: {selection_table_path}")
        logger.info(f"AI标题生成: {'启用' if self.use_ai_titles else '禁用'}")
        logger.info(f"采集验证: {'启用' if enable_validation else '禁用'}")
        logger.info(f"妙手插件: {'启用' if enable_plugin_collection else '禁用'}")
        logger.info(f"运行模式: {'简化模式（跳过Temu采集）' if skip_temu_collection else '完整模式'}")
        logger.info("=" * 100 + "\n")
        
        # 初始化结果
        result = {
            "success": False,
            "stages": {},
            "summary": {
                "total_products": 0,
                "collected_products": 0,
                "added_to_miaoshou": 0,
                "edited_products": 0,
                "start_time": datetime.now().isoformat(),
                "end_time": None,
            },
            "errors": [],
            "report_file": None
        }
        
        try:
            # ========== 阶段0: 读取选品表 ==========
            logger.info("▶" * 50)
            logger.info("【阶段0/5】读取Excel选品表")
            logger.info("▶" * 50 + "\n")
            
            products = self.table_reader.read_excel(selection_table_path)
            result["summary"]["total_products"] = len(products)
            
            if len(products) == 0:
                raise ValueError("选品表中没有有效产品")
            
            logger.success(f"✓ 阶段0完成：读取 {len(products)} 个产品\n")
            result["stages"]["stage0"] = {"products_count": len(products)}
            
            # ========== 简化模式：跳过Temu采集 ==========
            if skip_temu_collection:
                logger.info("=" * 100)
                logger.info("⏭️  【简化模式】跳过阶段1-2: Temu采集")
                logger.info("=" * 100)
                logger.info("ℹ️  假设商品已通过妙手插件手动采集到采集箱")
                logger.info("ℹ️  将直接从妙手采集箱读取并编辑商品")
                logger.info("=" * 100 + "\n")
                
                result["stages"]["stage1"] = {"skipped": True, "reason": "简化模式"}
                result["stages"]["stage2"] = {"skipped": True, "reason": "简化模式"}
                
                # 直接跳到阶段3
            else:
                # ========== 阶段1: Temu采集（SOP步骤1-3） ==========
                stage1_result = await self._stage_collect_from_temu(page, products)
                result["stages"]["stage1"] = stage1_result
                
                if not stage1_result["success"]:
                    raise RuntimeError("阶段1失败：Temu采集失败")
                
                result["summary"]["collected_products"] = stage1_result["success_count"]
                
                # 保存中间结果
                if save_intermediate_results:
                    self._save_intermediate_result("stage1_collection", stage1_result)
                
                # ========== 阶段2: 添加到妙手（关键衔接点） ==========
                if enable_plugin_collection:
                    stage2_result = await self._stage_add_to_miaoshou(
                        page,
                        stage1_result["collected_links"]
                    )
                    result["stages"]["stage2"] = stage2_result
                    
                    if not stage2_result["success"]:
                        logger.warning("⚠️  阶段2警告：部分商品未能添加到妙手")
                        logger.warning(f"   成功: {stage2_result['success_count']}/{stage2_result['total']}")
                        
                        # 如果完全失败，提示用户手动操作
                        if stage2_result["success_count"] == 0:
                            logger.error("✗ 阶段2失败：无法自动添加到妙手采集箱")
                            logger.info("💡 请手动完成以下操作：")
                            logger.info("   1. 打开Temu商品详情页")
                            logger.info("   2. 点击妙手插件的「采集商品」按钮")
                            logger.info("   3. 确认商品已添加到妙手采集箱")
                            logger.info("   4. 完成后按Enter继续...")
                            # input()  # 等待用户手动操作
                            # 注意：在自动化测试中应该跳过此步骤
                    
                    result["summary"]["added_to_miaoshou"] = stage2_result["success_count"]
                    
                    if save_intermediate_results:
                        self._save_intermediate_result("stage2_add_to_miaoshou", stage2_result)
                else:
                    logger.info("⏭️  跳过阶段2：妙手插件采集已禁用")
                    result["stages"]["stage2"] = {"skipped": True}
            
            # ========== 阶段3: 导航到妙手采集箱 ==========
            stage3_result = await self._stage_navigate_to_collection_box(
                page,
                filter_by_user=filter_by_user
            )
            result["stages"]["stage3"] = stage3_result
            
            if not stage3_result["success"]:
                raise RuntimeError("阶段3失败：无法导航到妙手采集箱")
            
            # ========== 阶段4: 验证采集结果（可选） ==========
            if enable_validation:
                stage4_result = await self._stage_verify_collection(
                    page,
                    expected_count=len(products),
                    product_keywords=[p.product_name for p in products]
                )
                result["stages"]["stage4"] = stage4_result
                
                if not stage4_result["success"]:
                    logger.warning("⚠️  阶段4警告：采集结果验证未通过")
            else:
                logger.info("⏭️  跳过阶段4：采集验证已禁用\n")
                result["stages"]["stage4"] = {"skipped": True}
            
            # ========== 阶段5: 首次编辑（SOP步骤4） ==========
            stage5_result = await self._stage_first_edit(
                page,
                products,
                skip_temu_collection=skip_temu_collection
            )
            result["stages"]["stage5"] = stage5_result
            
            if not stage5_result["success"]:
                raise RuntimeError("阶段5失败：首次编辑失败")
            
            result["summary"]["edited_products"] = stage5_result["edited_count"]
            
            # 标记成功
            result["success"] = True
            result["summary"]["end_time"] = datetime.now().isoformat()
            
            # 保存最终报告
            report_file = self._save_final_report(result)
            result["report_file"] = report_file
            
            # 显示最终总结
            self._display_final_summary(result)
            
            return result
            
        except Exception as e:
            logger.error(f"\n❌ 工作流执行失败: {e}")
            logger.exception("详细错误信息:")
            result["errors"].append(str(e))
            result["summary"]["end_time"] = datetime.now().isoformat()
            
            # 保存失败报告
            report_file = self._save_final_report(result)
            result["report_file"] = report_file
            
            return result
    
    async def _stage_collect_from_temu(
        self,
        page: Page,
        products: List[ProductSelectionRow]
    ) -> Dict:
        """阶段1: Temu采集（SOP步骤1-3）.
        
        执行完整的Temu商品采集流程。
        注意：此方法需要在新tab中打开Temu前端。
        """
        logger.info("\n" + "▶" * 50)
        logger.info("【阶段1/5】Temu商品采集（SOP步骤1-3）")
        logger.info("▶" * 50 + "\n")
        
        result = {
            "success": False,
            "success_count": 0,
            "failed_count": 0,
            "collected_links": [],
            "errors": []
        }
        
        try:
            # 获取browser context以便打开新tab
            context = page.context
            
            # 打开新tab用于Temu采集
            logger.info(">>> 打开新tab用于Temu采集...")
            temu_page = await context.new_page()
            
            try:
                # SOP步骤1: 访问Temu前端店铺
                logger.info(">>> SOP步骤1: 访问Temu前端...")
                temu_url = "https://www.temu.com"
                await temu_page.goto(temu_url, wait_until="networkidle", timeout=30000)
                await temu_page.wait_for_timeout(2000)
                
                logger.success(f"✓ 成功打开Temu前端: {temu_url}\n")
                
                # SOP步骤2-3: 逐个产品搜索和采集
                for i, product in enumerate(products):
                    logger.info(f">>> 处理产品 {i+1}/{len(products)}: {product.product_name}")
                    
                    try:
                        # 步骤2: 搜索商品
                        if not await self.collection_ctrl.search_products(temu_page, product.product_name):
                            logger.error(f"✗ 搜索失败: {product.product_name}")
                            result["failed_count"] += 1
                            continue
                        
                        # 步骤3: 采集链接
                        links = await self.collection_ctrl.collect_links(
                            temu_page,
                            count=product.collect_count
                        )
                        
                        if len(links) > 0:
                            result["success_count"] += 1
                            result["collected_links"].extend([link["url"] for link in links])
                            logger.success(f"✓ 产品 {i+1} 采集成功：{len(links)} 个链接\n")
                        else:
                            result["failed_count"] += 1
                            logger.error(f"✗ 产品 {i+1} 采集失败：未获取到链接\n")
                        
                    except Exception as e:
                        logger.error(f"✗ 产品 {i+1} 采集异常: {e}\n")
                        result["failed_count"] += 1
                        result["errors"].append(f"产品{i+1}({product.product_name}): {e}")
            
            finally:
                # 关闭Temu tab
                logger.info(">>> 关闭Temu tab...")
                await temu_page.close()
            
            result["success"] = result["success_count"] > 0
            
            logger.info("=" * 80)
            logger.success(f"✓ 阶段1完成：成功采集 {result['success_count']}/{len(products)} 个产品")
            logger.info(f"  总链接数: {len(result['collected_links'])}")
            logger.info("=" * 80 + "\n")
            
            return result
            
        except Exception as e:
            logger.error(f"阶段1失败: {e}")
            logger.exception("详细错误:")
            result["errors"].append(str(e))
            return result
    
    async def _stage_add_to_miaoshou(
        self,
        page: Page,
        product_urls: List[str]
    ) -> Dict:
        """阶段2: 添加到妙手采集箱（关键衔接点）.
        
        使用妙手插件将Temu商品添加到妙手ERP采集箱。
        """
        logger.info("\n" + "▶" * 50)
        logger.info("【阶段2/5】添加到妙手采集箱（关键衔接）")
        logger.info("▶" * 50 + "\n")
        
        try:
            result = await self.collection_ctrl.add_to_miaoshou_collection_box(
                page,
                product_urls,
                max_retries=3,
                use_plugin=True
            )
            
            result["success"] = result["success_count"] > 0
            
            logger.info("=" * 80)
            if result["success"]:
                logger.success(f"✓ 阶段2完成：成功添加 {result['success_count']}/{result['total']} 个商品到妙手")
            else:
                logger.warning(f"⚠️  阶段2警告：添加到妙手失败")
            logger.info("=" * 80 + "\n")
            
            return result
            
        except Exception as e:
            logger.error(f"阶段2失败: {e}")
            return {
                "success": False,
                "success_count": 0,
                "total": len(product_urls),
                "error": str(e)
            }
    
    async def _stage_navigate_to_collection_box(
        self,
        page: Page,
        filter_by_user: Optional[str] = None
    ) -> Dict:
        """阶段3: 导航到妙手采集箱.
        
        切换到妙手ERP并导航到公用采集箱。
        """
        logger.info("\n" + "▶" * 50)
        logger.info("【阶段3/5】导航到妙手采集箱")
        logger.info("▶" * 50 + "\n")
        
        try:
            success = await self.miaoshou_ctrl.navigate_and_filter_collection_box(
                page,
                filter_by_user=filter_by_user,
                switch_to_tab="all"
            )
            
            result = {
                "success": success,
                "filter_by_user": filter_by_user
            }
            
            if success:
                logger.success("✓ 阶段3完成：成功导航到妙手采集箱\n")
            else:
                logger.error("✗ 阶段3失败：导航失败\n")
            
            return result
            
        except Exception as e:
            logger.error(f"阶段3失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _stage_verify_collection(
        self,
        page: Page,
        expected_count: int,
        product_keywords: List[str]
    ) -> Dict:
        """阶段4: 验证采集结果（可选）.
        
        验证妙手采集箱中的商品是否正确。
        """
        logger.info("\n" + "▶" * 50)
        logger.info("【阶段4/5】验证采集结果")
        logger.info("▶" * 50 + "\n")
        
        try:
            result = await self.miaoshou_ctrl.verify_collected_products(
                page,
                expected_count=expected_count,
                product_keywords=product_keywords,
                check_details=False
            )
            
            if result["success"]:
                logger.success("✓ 阶段4完成：采集结果验证通过\n")
            else:
                logger.warning("⚠️  阶段4警告：采集结果验证未通过\n")
            
            return result
            
        except Exception as e:
            logger.error(f"阶段4失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _stage_first_edit(
        self,
        page: Page,
        products: List[ProductSelectionRow],
        skip_temu_collection: bool = True
    ) -> Dict:
        """阶段5: 首次编辑（SOP步骤4）.
        
        执行妙手采集箱中5个产品的首次编辑。
        
        Args:
            page: 页面对象
            products: 选品表产品列表（使用真实Excel数据）
            skip_temu_collection: 是否为简化模式
        """
        logger.info("\n" + "▶" * 50)
        logger.info("【阶段5/5】首次编辑（SOP步骤4）")
        logger.info("▶" * 50 + "\n")
        
        try:
            # 构建产品数据（使用Excel真实数据）
            products_data = []
            for i, product in enumerate(products[:5]):  # 取前5个
                product_data = {
                    "keyword": product.product_name,
                    "model_number": product.model_number,
                    "cost": product.cost_price if product.cost_price else 150.0,
                    "stock": 100,  # 可从Excel扩展
                    "color_spec": product.color_spec,
                    "size_chart_url": product.size_chart_url,
                    "product_image_url": product.product_image_url,
                    "actual_photo_url": product.actual_photo_url,
                }
                products_data.append(product_data)
            
            if products_data:
                logger.info(f"使用Excel数据编辑 {len(products_data)} 个产品:")
                for i, pd in enumerate(products_data, 1):
                    cost_str = f"¥{pd['cost']:.2f}" if pd['cost'] else "未设置"
                    logger.info(f"  产品{i}: {pd['keyword']} ({pd['model_number']}) - 成本{cost_str}")
                    if pd.get('size_chart_url'):
                        logger.debug(f"    - 尺寸图: {pd['size_chart_url'][:50]}...")
                    if pd.get('product_image_url'):
                        logger.debug(f"    - 产品图: {pd['product_image_url'][:50]}...")
                    if pd.get('actual_photo_url'):
                        logger.debug(f"    - 实拍图: {pd['actual_photo_url'][:50]}...")
                logger.info("")
            
            # 执行首次编辑（不包括认领）
            result = await self.five_to_twenty.execute(
                page,
                products_data if products_data else None,
                claim_times=0  # 暂时不执行认领，只做首次编辑
            )
            
            if result.get("edited_count", 0) > 0:
                logger.success(f"✓ 阶段5完成：成功编辑 {result['edited_count']}/{len(products_data) if products_data else 5} 个产品\n")
            else:
                logger.error("✗ 阶段5失败：首次编辑失败\n")
            
            return result
            
        except Exception as e:
            logger.error(f"阶段5失败: {e}")
            return {
                "success": False,
                "edited_count": 0,
                "error": str(e)
            }
    
    def _save_intermediate_result(self, stage_name: str, result: Dict) -> str:
        """保存中间结果到文件.
        
        Args:
            stage_name: 阶段名称
            result: 结果数据
            
        Returns:
            保存的文件路径
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{stage_name}_{timestamp}.json"
        filepath = self.output_dir / filename
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        logger.debug(f"中间结果已保存: {filepath}")
        return str(filepath)
    
    def _save_final_report(self, result: Dict) -> str:
        """保存最终报告.
        
        Args:
            result: 完整结果数据
            
        Returns:
            报告文件路径
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"collection_to_edit_report_{timestamp}.json"
        filepath = self.output_dir / filename
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        logger.info(f"\n📄 完整报告已保存: {filepath}")
        return str(filepath)
    
    def _display_final_summary(self, result: Dict) -> None:
        """显示最终总结.
        
        Args:
            result: 完整结果数据
        """
        logger.info("\n" + "=" * 100)
        logger.info(" " * 35 + "【执行总结】")
        logger.info("=" * 100)
        
        summary = result["summary"]
        
        # 时间统计
        start_time = datetime.fromisoformat(summary["start_time"])
        end_time = datetime.fromisoformat(summary["end_time"])
        duration = (end_time - start_time).total_seconds()
        
        logger.info(f"总产品数: {summary['total_products']}")
        logger.info(f"采集成功: {summary['collected_products']}")
        logger.info(f"添加到妙手: {summary['added_to_miaoshou']}")
        logger.info(f"编辑完成: {summary['edited_products']}")
        logger.info(f"执行时间: {duration:.1f}秒")
        
        if result["success"]:
            logger.success("\n✅ 工作流执行成功！")
        else:
            logger.error("\n❌ 工作流执行失败")
            if result["errors"]:
                logger.error("错误列表:")
                for error in result["errors"]:
                    logger.error(f"  - {error}")
        
        logger.info("=" * 100 + "\n")

