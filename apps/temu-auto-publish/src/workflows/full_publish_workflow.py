"""
@PURPOSE: 实现完整的商品发布工作流(包含采集步骤)
@OUTLINE:
  - class FullPublishWorkflow: 完整发布工作流(SOP步骤1-11)
  - async def execute(): 执行完整工作流
@DEPENDENCIES:
  - 内部: browser.collection_controller, workflows.complete_publish_workflow
  - 外部: playwright
@RELATED: complete_publish_workflow.py, collection_controller.py
"""


from loguru import logger
from playwright.async_api import Page
from src.browser.collection_controller import CollectionController
from src.workflows.complete_publish_workflow import CompletePublishWorkflow


class FullPublishWorkflow:
    """完整发布工作流(SOP步骤1-11).

    包含:
    - 步骤1-3:采集商品链接
    - 步骤4-6:5→20工作流
    - 步骤7:批量编辑
    - 步骤8-11:发布

    Examples:
        >>> workflow = FullPublishWorkflow()
        >>> result = await workflow.execute(page, products_data)
    """

    def __init__(self):
        """初始化完整工作流."""
        self.collection_ctrl = CollectionController()
        self.publish_workflow = CompletePublishWorkflow()
        logger.info("完整发布工作流已初始化(SOP步骤1-11)")

    async def execute(
        self,
        page: Page,
        products_data: list[dict],
        enable_batch_edit: bool = True,
        enable_publish: bool = False,
        shop_name: str | None = None,
    ) -> dict:
        """执行完整发布工作流.

        Args:
            page: Playwright页面对象
            products_data: 产品数据列表,每个产品包含:
                - keyword: 搜索关键词
                - collect_count: 采集数量(默认5)
                - ... 其他字段同 CompletePublishWorkflow
            enable_batch_edit: 是否启用批量编辑
            enable_publish: 是否启用发布
            shop_name: 店铺名称(发布时需要)

        Returns:
            工作流执行结果

        Examples:
            >>> products = [
            ...     {
            ...         "keyword": "药箱收纳盒",
            ...         "collect_count": 5,
            ...         "cost": 10.0,
            ...         "stock": 100
            ...     }
            ... ]
            >>> result = await workflow.execute(page, products)
        """
        logger.info("\n" + "=" * 100)
        logger.info("开始执行完整发布工作流(SOP步骤1-11)")
        logger.info("=" * 100 + "\n")

        try:
            all_results = []

            for product in products_data:
                keyword = product.get("keyword")
                collect_count = product.get("collect_count", 5)

                logger.info(f"\n处理产品: {keyword}")
                logger.info(f"采集数量: {collect_count}")

                # ========== 阶段0:采集商品链接(SOP步骤1-3)==========
                logger.info("\n" + "▶" * 50)
                logger.info("[阶段0/4]采集商品链接(SOP步骤1-3)")
                logger.info("▶" * 50)

                # 步骤1:访问前端店铺
                if not await self.collection_ctrl.visit_store(page):
                    raise Exception("访问店铺失败")

                # 步骤2-3:搜索并采集
                collected_links = await self.collection_ctrl.search_and_collect(
                    page, keyword=keyword, count=collect_count
                )

                if len(collected_links) == 0:
                    logger.error(f"✗ 产品 {keyword} 采集失败,跳过")
                    continue

                logger.success(f"✓ 成功采集 {len(collected_links)} 个商品链接")

                # 将采集的链接添加到妙手采集箱
                # 注意:这一步可能需要使用妙手插件,暂时记录链接
                product["collected_links"] = [link["url"] for link in collected_links]
                product["collected_info"] = collected_links

                logger.info(f"产品 {keyword} 的采集链接:")
                for i, link in enumerate(collected_links):
                    logger.info(f"  {i + 1}. {link['title']}")
                    logger.debug(f"     URL: {link['url']}")

                all_results.append(
                    {"keyword": keyword, "collected_links": collected_links, "status": "collected"}
                )

            # ========== 阶段1-3:执行后续工作流(SOP步骤4-11)==========
            logger.info("\n" + "▶" * 50)
            logger.info("[阶段1-3/4]执行后续工作流(SOP步骤4-11)")
            logger.info("▶" * 50)

            # 调用现有的 CompletePublishWorkflow
            publish_result = await self.publish_workflow.execute(
                page,
                products_data,
                enable_batch_edit=enable_batch_edit,
                enable_publish=enable_publish,
                shop_name=shop_name,
            )

            # 合并结果
            final_result = {
                "collection_results": all_results,
                "publish_results": publish_result,
                "status": "success",
                "total_products": len(products_data),
                "collected_count": len(all_results),
            }

            logger.info("\n" + "=" * 100)
            logger.info("完整发布工作流执行完成")
            logger.info(f"总产品数: {len(products_data)}")
            logger.info(f"采集成功: {len(all_results)}")
            logger.info("=" * 100 + "\n")

            return final_result

        except Exception as e:
            logger.error(f"完整工作流执行失败: {e}")
            raise
