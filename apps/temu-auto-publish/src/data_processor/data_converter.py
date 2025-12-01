"""
@PURPOSE: 数据格式转换器，负责在不同工作流阶段之间转换数据格式
@OUTLINE:
  - class DataConverter: 数据转换器主类
  - @staticmethod selection_to_collection(): 选品表 → 采集输入
  - @staticmethod collection_to_edit(): 采集结果 → 首次编辑输入
  - @staticmethod edit_to_claim(): 首次编辑结果 → 认领输入
@GOTCHAS:
  - 必须保持数据一致性，特别是型号编号
  - 价格计算使用标准公式（成本价×倍数）
  - 所有转换都需要验证必填字段
@DEPENDENCIES:
  - 内部: data_processor.selection_table_reader
  - 外部: pydantic
@RELATED: selection_table_reader.py, collection_workflow.py
@CHANGELOG:
  - 2025-11-01: 初始创建，实现完整数据转换功能
"""

from typing import Dict, List, Optional

from loguru import logger

from src.data_processor.selection_table_reader import ProductSelectionRow


class DataConverter:
    """数据格式转换器.

    负责在不同阶段之间转换数据格式，确保数据流畅传递：
    1. Excel选品表 → 采集输入
    2. 采集结果 → 首次编辑输入
    3. 首次编辑结果 → 认领输入

    Examples:
        >>> from src.workflows.collection_workflow import CollectionResult
        >>>
        >>> # 转换1: 选品表 → 采集输入
        >>> products = reader.read_excel("selection.xlsx")
        >>> collection_input = DataConverter.selection_to_collection(products)
        >>>
        >>> # 转换2: 采集结果 → 首次编辑输入
        >>> edit_input = DataConverter.collection_to_edit(
        ...     collection_results,
        ...     products
        ... )
    """

    @staticmethod
    def selection_to_collection(products: List[ProductSelectionRow]) -> List[Dict]:
        """选品表 → 采集输入格式转换.

        将Excel选品表数据转换为采集控制器所需的格式。

        Args:
            products: 选品表产品列表

        Returns:
            采集输入格式列表，每个元素包含：
            - keyword: 搜索关键词（产品名称）
            - collect_count: 采集数量
            - model_number: 型号编号
            - owner: 负责人

        Examples:
            >>> products = reader.read_excel("selection.xlsx")
            >>> collection_input = DataConverter.selection_to_collection(products)
            >>> print(collection_input[0]["keyword"])
            '药箱收纳盒'
        """
        logger.info(f"转换选品表数据 → 采集输入格式 ({len(products)} 个产品)")

        collection_input = []

        for product in products:
            input_data = {
                "keyword": product.product_name,
                "collect_count": product.collect_count,
                "model_number": product.model_number,
                "owner": product.owner,
                "color_spec": product.color_spec,
                "size_chart_url": product.size_chart,
                "product_image_url": product.product_image,
            }
            collection_input.append(input_data)

            logger.debug(
                f"  - {product.product_name} ({product.model_number}): 采集{product.collect_count}个"
            )

        logger.success(f"✓ 转换完成，共 {len(collection_input)} 个产品")
        return collection_input

    @staticmethod
    def collection_to_edit(
        collection_results: List[Dict],
        selection_products: List[ProductSelectionRow],
        default_cost: float = 150.0,
        default_stock: int = 100,
    ) -> List[Dict]:
        """采集结果 → 首次编辑输入格式转换.

        将采集结果转换为首次编辑控制器所需的格式。

        Args:
            collection_results: 采集结果列表
            selection_products: 原始选品表数据（用于补充信息）
            default_cost: 默认成本价（如果选品表未提供）
            default_stock: 默认库存（如果选品表未提供）

        Returns:
            首次编辑输入格式列表，每个元素包含：
            - index: 产品索引
            - keyword: 关键词
            - model_number: 型号编号
            - cost: 成本价
            - stock: 库存
            - collected_links: 采集的链接列表

        Examples:
            >>> edit_input = DataConverter.collection_to_edit(
            ...     collection_results,
            ...     products
            ... )
            >>> print(edit_input[0]["model_number"])
            'A0049'
        """
        logger.info(f"转换采集结果 → 首次编辑输入格式 ({len(collection_results)} 个产品)")

        edit_input = []

        # 创建选品表的快速查找映射（通过产品名称）
        selection_map = {product.product_name: product for product in selection_products}

        for i, result in enumerate(collection_results):
            # 获取产品基本信息
            product_info = result.get("product", {})
            product_name = product_info.get("product_name", "")
            model_number = product_info.get("model_number", f"A{str(i + 1).zfill(4)}")

            # 从选品表获取额外信息
            selection_product = selection_map.get(product_name)

            # 构建编辑输入数据
            edit_data = {
                "index": i,
                "keyword": product_name,
                "model_number": model_number,
                "cost": default_cost + i * 10,  # 递增成本价用于测试
                "stock": default_stock,
                "collected_links": result.get("collected_links", []),
                "owner": product_info.get("owner", "未指定"),
                "collect_count": product_info.get("collect_count", 5),
            }

            # 补充选品表中的额外信息（如果有）
            if selection_product:
                edit_data["color_spec"] = selection_product.color_spec
                edit_data["size_chart_url"] = selection_product.size_chart
                edit_data["product_image_url"] = selection_product.product_image

            edit_input.append(edit_data)

            links_count = len(edit_data["collected_links"])
            logger.debug(
                f"  - 产品 {i + 1}: {product_name} ({model_number}) - {links_count} 个链接"
            )

        logger.success(f"✓ 转换完成，共 {len(edit_input)} 个产品")
        return edit_input

    @staticmethod
    def edit_to_claim(edit_results: Dict, claim_times: int = 4) -> List[Dict]:
        """首次编辑结果 → 认领输入格式转换.

        将首次编辑结果转换为认领控制器所需的格式。

        Args:
            edit_results: 首次编辑结果字典
            claim_times: 每个产品的认领次数

        Returns:
            认领输入格式列表

        Examples:
            >>> claim_input = DataConverter.edit_to_claim(edit_results, claim_times=4)
            >>> print(len(claim_input))
            5
        """
        logger.info("转换首次编辑结果 → 认领输入格式")

        edited_count = edit_results.get("edited_count", 0)

        claim_input = []
        for i in range(edited_count):
            claim_data = {
                "index": i,
                "claim_times": claim_times,
            }
            claim_input.append(claim_data)

        logger.success(f"✓ 转换完成，共 {len(claim_input)} 个产品待认领")
        return claim_input

    @staticmethod
    def validate_collection_results(results: List[Dict], expected_count: int) -> Dict:
        """验证采集结果的完整性.

        检查采集结果是否满足要求：
        1. 产品数量是否正确
        2. 每个产品是否有足够的链接
        3. 必填字段是否完整

        Args:
            results: 采集结果列表
            expected_count: 期望的产品数量

        Returns:
            验证结果字典：
            - valid: 是否验证通过
            - issues: 问题列表
            - summary: 汇总信息
        """
        logger.info(f"验证采集结果 (期望 {expected_count} 个产品)...")

        validation = {
            "valid": True,
            "issues": [],
            "summary": {
                "total_products": len(results),
                "expected_products": expected_count,
                "products_with_links": 0,
                "total_links": 0,
            },
        }

        if len(results) < expected_count:
            validation["valid"] = False
            validation["issues"].append(f"产品数量不足: {len(results)} < {expected_count}")

        for i, result in enumerate(results):
            links = result.get("collected_links", [])
            if len(links) > 0:
                validation["summary"]["products_with_links"] += 1
                validation["summary"]["total_links"] += len(links)
            else:
                validation["valid"] = False
                validation["issues"].append(f"产品 {i + 1} 没有采集到链接")

        if validation["valid"]:
            logger.success("✓ 采集结果验证通过")
        else:
            logger.warning(f"⚠️  采集结果存在 {len(validation['issues'])} 个问题")
            for issue in validation["issues"]:
                logger.warning(f"  - {issue}")

        return validation

    @staticmethod
    def merge_collection_and_selection(
        collection_results: List[Dict], selection_products: List[ProductSelectionRow]
    ) -> List[Dict]:
        """合并采集结果和选品表数据.

        将采集到的链接和选品表中的详细信息合并，
        生成完整的产品数据。

        Args:
            collection_results: 采集结果
            selection_products: 选品表数据

        Returns:
            合并后的完整产品数据列表
        """
        logger.info("合并采集结果和选品表数据...")

        merged_data = []

        # 创建选品表映射
        selection_map = {product.product_name: product for product in selection_products}

        for result in collection_results:
            product_info = result.get("product", {})
            product_name = product_info.get("product_name", "")

            selection_product = selection_map.get(product_name)

            if selection_product:
                # 合并数据
                merged = {
                    "product_name": product_name,
                    "model_number": selection_product.model_number,
                    "owner": selection_product.owner,
                    "color_spec": selection_product.color_spec,
                    "collect_count": selection_product.collect_count,
                    "collected_links": result.get("collected_links", []),
                    "collected_count": len(result.get("collected_links", [])),
                    "success": result.get("success", False),
                    "size_chart_url": selection_product.size_chart,
                    "product_image_url": selection_product.product_image,
                }
                merged_data.append(merged)

                logger.debug(f"  - {product_name}: {merged['collected_count']} 个链接")
            else:
                logger.warning(f"  ⚠️  未找到选品表数据: {product_name}")

        logger.success(f"✓ 合并完成，共 {len(merged_data)} 个产品")
        return merged_data
