"""
@PURPOSE: 实现完整的商品采集工作流（SOP步骤1-3）
@OUTLINE:
  - class CollectionWorkflow: 采集工作流控制器
  - async def execute(): 执行完整采集流程
  - async def _collect_single_product(): 采集单个产品
  - def generate_report(): 生成采集报告
@GOTCHAS:
  - 采集过程中需要验证商品规格一致性
  - 妙手插件交互可能需要人工介入
  - 采集结果需要保存为JSON便于后续步骤使用
@DEPENDENCIES:
  - 内部: CollectionController, SelectionTableReader
  - 外部: playwright, loguru
@RELATED: five_to_twenty_workflow.py, full_publish_workflow.py
@CHANGELOG:
  - 2025-11-01: 初始创建，实现完整采集工作流
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger
from playwright.async_api import Page

from src.browser.collection_controller import CollectionController
from src.data_processor.selection_table_reader import (
    ProductSelectionRow,
    SelectionTableReader,
)


class CollectionResult:
    """采集结果数据结构.
    
    Attributes:
        product: 产品信息
        collected_links: 采集的链接列表
        success: 是否成功
        error: 错误信息
        timestamp: 采集时间
    """
    
    def __init__(
        self,
        product: ProductSelectionRow,
        collected_links: List[Dict],
        success: bool = True,
        error: Optional[str] = None
    ):
        self.product = product
        self.collected_links = collected_links
        self.success = success
        self.error = error
        self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        """转换为字典."""
        return {
            "product": {
                "owner": self.product.owner,
                "product_name": self.product.product_name,
                "model_number": self.product.model_number,
                "color_spec": self.product.color_spec,
                "collect_count": self.product.collect_count,
            },
            "collected_links": self.collected_links,
            "success": self.success,
            "error": self.error,
            "timestamp": self.timestamp,
        }


class CollectionWorkflow:
    """商品采集工作流（SOP步骤1-3）.
    
    负责执行完整的商品采集流程：
    1. 读取选品表
    2. 访问Temu前端店铺
    3. 逐个产品搜索和采集
    4. 生成采集报告
    
    Examples:
        >>> workflow = CollectionWorkflow()
        >>> results = await workflow.execute(
        ...     page,
        ...     selection_table_path="data/selection.xlsx"
        ... )
        >>> print(f"成功采集 {len(results)} 个产品")
    """
    
    def __init__(
        self,
        output_dir: Optional[str] = None
    ):
        """初始化采集工作流.
        
        Args:
            output_dir: 输出目录（保存采集结果）
        """
        self.collection_ctrl = CollectionController()
        self.table_reader = SelectionTableReader()
        
        # 设置输出目录
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            self.output_dir = Path(__file__).parent.parent.parent / "data" / "output" / "collection"
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("采集工作流初始化完成")
        logger.debug(f"  输出目录: {self.output_dir}")
    
    async def execute(
        self,
        page: Page,
        selection_table_path: str,
        skip_visit_store: bool = False,
        save_report: bool = True
    ) -> Dict:
        """执行完整采集流程.
        
        Args:
            page: Playwright页面对象
            selection_table_path: 选品表Excel文件路径
            skip_visit_store: 是否跳过访问店铺步骤（如果已在店铺页面）
            save_report: 是否保存采集报告
            
        Returns:
            采集结果字典，包含：
            - products: 采集的产品列表
            - summary: 汇总统计
            - report_file: 报告文件路径
            
        Raises:
            FileNotFoundError: 选品表文件不存在
            RuntimeError: 采集流程失败
            
        Examples:
            >>> workflow = CollectionWorkflow()
            >>> result = await workflow.execute(page, "data/selection.xlsx")
            >>> print(result["summary"]["total_products"])
            10
        """
        logger.info("\n" + "=" * 80)
        logger.info("【商品采集工作流】开始执行（SOP步骤1-3）")
        logger.info("=" * 80 + "\n")
        
        # 读取选品表
        logger.info(f">>> 读取选品表: {selection_table_path}")
        try:
            products = self.table_reader.read_excel(selection_table_path)
            logger.success(f"✓ 选品表读取成功，共 {len(products)} 个产品")
        except Exception as e:
            logger.error(f"✗ 读取选品表失败: {e}")
            raise
        
        if len(products) == 0:
            logger.warning("⚠️ 选品表中没有有效产品")
            return {
                "products": [],
                "summary": {"total_products": 0, "success": 0, "failed": 0},
                "report_file": None
            }
        
        # SOP步骤1: 访问前端店铺
        if not skip_visit_store:
            logger.info("\n" + "▶" * 60)
            logger.info("【SOP步骤1】访问Temu前端店铺")
            logger.info("▶" * 60 + "\n")
            
            if not await self.collection_ctrl.visit_store(page):
                logger.error("✗ 访问店铺失败")
                raise RuntimeError("无法访问Temu店铺")
        else:
            logger.info("⏭️  跳过访问店铺步骤（假设已在店铺页面）")
        
        # 逐个产品采集
        collection_results: List[CollectionResult] = []
        
        for i, product in enumerate(products):
            logger.info("\n" + "─" * 80)
            logger.info(f"处理产品 {i+1}/{len(products)}: {product.product_name}")
            logger.info(f"  型号: {product.model_number}")
            logger.info(f"  采集数量: {product.collect_count}")
            logger.info("─" * 80 + "\n")
            
            try:
                result = await self._collect_single_product(page, product)
                collection_results.append(result)
                
                if result.success:
                    logger.success(f"✓ 产品 {product.product_name} 采集成功")
                else:
                    logger.warning(f"⚠️ 产品 {product.product_name} 采集失败: {result.error}")
                
            except Exception as e:
                logger.error(f"✗ 产品 {product.product_name} 采集异常: {e}")
                result = CollectionResult(
                    product=product,
                    collected_links=[],
                    success=False,
                    error=str(e)
                )
                collection_results.append(result)
        
        # 生成汇总统计
        summary = self._generate_summary(collection_results)
        
        # 保存报告
        report_file = None
        if save_report:
            report_file = self.save_report(collection_results, summary)
        
        # 显示汇总
        logger.info("\n" + "=" * 80)
        logger.info("【采集工作流】完成")
        logger.info("=" * 80)
        logger.info(f"总产品数: {summary['total_products']}")
        logger.info(f"成功: {summary['success']} ({summary['success_rate']:.1f}%)")
        logger.info(f"失败: {summary['failed']}")
        logger.info(f"总链接数: {summary['total_links']}")
        if report_file:
            logger.info(f"报告已保存: {report_file}")
        logger.info("=" * 80 + "\n")
        
        return {
            "products": [r.to_dict() for r in collection_results],
            "summary": summary,
            "report_file": report_file
        }
    
    async def _collect_single_product(
        self,
        page: Page,
        product: ProductSelectionRow
    ) -> CollectionResult:
        """采集单个产品（SOP步骤2-3）.
        
        Args:
            page: Playwright页面对象
            product: 产品信息
            
        Returns:
            采集结果
        """
        try:
            # SOP步骤2: 站内搜索同款商品
            logger.info(f">>> SOP步骤2: 搜索同款商品 - {product.product_name}")
            
            if not await self.collection_ctrl.search_products(page, product.product_name):
                return CollectionResult(
                    product=product,
                    collected_links=[],
                    success=False,
                    error="搜索失败，未找到商品"
                )
            
            # SOP步骤3: 采集N个同款商品链接
            logger.info(f">>> SOP步骤3: 采集 {product.collect_count} 个链接")
            
            collected_links = await self.collection_ctrl.collect_links(
                page,
                count=product.collect_count
            )
            
            if len(collected_links) == 0:
                return CollectionResult(
                    product=product,
                    collected_links=[],
                    success=False,
                    error="采集失败，未获取到链接"
                )
            
            # 成功
            logger.info(f"✓ 成功采集 {len(collected_links)} 个链接")
            
            # 可选：添加到妙手采集箱
            # 注意：这一步可能需要妙手插件支持，暂时跳过
            # await self.collection_ctrl.add_to_collection_box(page, [link["url"] for link in collected_links])
            
            return CollectionResult(
                product=product,
                collected_links=collected_links,
                success=True
            )
            
        except Exception as e:
            logger.error(f"采集产品 {product.product_name} 失败: {e}")
            return CollectionResult(
                product=product,
                collected_links=[],
                success=False,
                error=str(e)
            )
    
    def _generate_summary(self, results: List[CollectionResult]) -> Dict:
        """生成汇总统计.
        
        Args:
            results: 采集结果列表
            
        Returns:
            汇总统计字典
        """
        total = len(results)
        success = sum(1 for r in results if r.success)
        failed = total - success
        total_links = sum(len(r.collected_links) for r in results)
        
        return {
            "total_products": total,
            "success": success,
            "failed": failed,
            "success_rate": (success / total * 100) if total > 0 else 0,
            "total_links": total_links,
            "average_links_per_product": (total_links / success) if success > 0 else 0,
        }
    
    def save_report(
        self,
        results: List[CollectionResult],
        summary: Dict
    ) -> str:
        """保存采集报告.
        
        Args:
            results: 采集结果列表
            summary: 汇总统计
            
        Returns:
            报告文件路径
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = self.output_dir / f"collection_report_{timestamp}.json"
        
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "summary": summary,
            "results": [r.to_dict() for r in results]
        }
        
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
        
        logger.debug(f"采集报告已保存: {report_file}")
        
        return str(report_file)
    
    def export_links_for_miaoshou(
        self,
        results: List[CollectionResult],
        output_file: Optional[str] = None
    ) -> str:
        """导出链接列表供妙手ERP导入.
        
        生成一个包含所有采集链接的文本文件，便于手动导入到妙手ERP。
        
        Args:
            results: 采集结果列表
            output_file: 输出文件路径（可选）
            
        Returns:
            输出文件路径
        """
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = str(self.output_dir / f"miaoshou_links_{timestamp}.txt")
        
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("# 妙手ERP采集链接导入清单\n")
            f.write(f"# 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("#" + "=" * 60 + "\n\n")
            
            for result in results:
                if not result.success:
                    continue
                
                f.write(f"## 产品: {result.product.product_name} ({result.product.model_number})\n")
                f.write(f"## 采集数量: {len(result.collected_links)}\n\n")
                
                for i, link in enumerate(result.collected_links):
                    f.write(f"{i+1}. {link['url']}\n")
                    f.write(f"   标题: {link.get('title', 'N/A')}\n")
                    f.write(f"   价格: {link.get('price', 'N/A')}\n\n")
                
                f.write("\n" + "-" * 60 + "\n\n")
        
        logger.info(f"✓ 妙手导入链接已导出: {output_file}")
        
        return output_file

