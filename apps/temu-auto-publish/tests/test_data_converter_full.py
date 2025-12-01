"""
@PURPOSE: data_converter 模块的完整单元测试
@OUTLINE:
  - TestDataConverterSelectionToCollection: selection_to_collection 测试
  - TestDataConverterCollectionToEdit: collection_to_edit 测试
  - TestDataConverterEditToClaim: edit_to_claim 测试
  - TestDataConverterValidateCollection: validate_collection_results 测试
  - TestDataConverterMerge: merge_collection_and_selection 测试
@DEPENDENCIES:
  - 外部: pytest
  - 内部: src.data_processor.data_converter
"""

from unittest.mock import MagicMock


def create_mock_product(
    product_name: str = "测试产品",
    model_number: str = "A0001",
    owner: str = "测试负责人",
    collect_count: int = 5,
    color_spec: str = "红色",
    size_chart: str = "http://example.com/size.jpg",
    product_image: str = "http://example.com/image.jpg",
) -> MagicMock:
    """创建 mock 的 ProductSelectionRow 对象."""
    mock = MagicMock()
    mock.product_name = product_name
    mock.model_number = model_number
    mock.owner = owner
    mock.collect_count = collect_count
    mock.color_spec = color_spec
    mock.size_chart = size_chart
    mock.product_image = product_image
    return mock


# ==================== selection_to_collection 测试 ====================
class TestDataConverterSelectionToCollection:
    """selection_to_collection 方法测试"""

    def test_convert_single_product(self):
        """测试单个产品转换"""
        from src.data_processor.data_converter import DataConverter

        products = [create_mock_product()]

        result = DataConverter.selection_to_collection(products)

        assert len(result) == 1
        assert result[0]["keyword"] == "测试产品"
        assert result[0]["collect_count"] == 5
        assert result[0]["model_number"] == "A0001"
        assert result[0]["owner"] == "测试负责人"

    def test_convert_multiple_products(self):
        """测试多个产品转换"""
        from src.data_processor.data_converter import DataConverter

        products = [
            create_mock_product(product_name="产品A", model_number="A0001"),
            create_mock_product(product_name="产品B", model_number="A0002"),
            create_mock_product(product_name="产品C", model_number="A0003"),
        ]

        result = DataConverter.selection_to_collection(products)

        assert len(result) == 3
        assert result[0]["keyword"] == "产品A"
        assert result[1]["keyword"] == "产品B"
        assert result[2]["keyword"] == "产品C"

    def test_convert_empty_list(self):
        """测试空列表转换"""
        from src.data_processor.data_converter import DataConverter

        products = []

        result = DataConverter.selection_to_collection(products)

        assert len(result) == 0

    def test_convert_preserves_color_spec(self):
        """测试保留颜色规格"""
        from src.data_processor.data_converter import DataConverter

        products = [create_mock_product(color_spec="蓝色/大码")]

        result = DataConverter.selection_to_collection(products)

        assert result[0]["color_spec"] == "蓝色/大码"

    def test_convert_preserves_size_chart_url(self):
        """测试保留尺码图 URL"""
        from src.data_processor.data_converter import DataConverter

        products = [create_mock_product(size_chart="http://example.com/chart.png")]

        result = DataConverter.selection_to_collection(products)

        assert result[0]["size_chart_url"] == "http://example.com/chart.png"

    def test_convert_preserves_product_image_url(self):
        """测试保留产品图 URL"""
        from src.data_processor.data_converter import DataConverter

        products = [create_mock_product(product_image="http://example.com/prod.jpg")]

        result = DataConverter.selection_to_collection(products)

        assert result[0]["product_image_url"] == "http://example.com/prod.jpg"


# ==================== collection_to_edit 测试 ====================
class TestDataConverterCollectionToEdit:
    """collection_to_edit 方法测试"""

    def test_convert_with_links(self):
        """测试带链接的转换"""
        from src.data_processor.data_converter import DataConverter

        collection_results = [
            {
                "product": {
                    "product_name": "测试产品",
                    "model_number": "A0001",
                    "owner": "负责人A",
                },
                "collected_links": ["http://link1.com", "http://link2.com"],
            }
        ]
        selection_products = [create_mock_product(product_name="测试产品")]

        result = DataConverter.collection_to_edit(collection_results, selection_products)

        assert len(result) == 1
        assert result[0]["index"] == 0
        assert result[0]["keyword"] == "测试产品"
        assert result[0]["model_number"] == "A0001"
        assert len(result[0]["collected_links"]) == 2

    def test_convert_with_default_cost_and_stock(self):
        """测试默认成本价和库存"""
        from src.data_processor.data_converter import DataConverter

        collection_results = [
            {"product": {"product_name": "产品A"}, "collected_links": []},
        ]
        selection_products = [create_mock_product(product_name="产品A")]

        result = DataConverter.collection_to_edit(
            collection_results,
            selection_products,
            default_cost=200.0,
            default_stock=50,
        )

        assert result[0]["cost"] == 200.0  # 200.0 + 0 * 10
        assert result[0]["stock"] == 50

    def test_convert_cost_increments_by_index(self):
        """测试成本价按索引递增"""
        from src.data_processor.data_converter import DataConverter

        collection_results = [
            {"product": {"product_name": "产品A"}, "collected_links": []},
            {"product": {"product_name": "产品B"}, "collected_links": []},
            {"product": {"product_name": "产品C"}, "collected_links": []},
        ]
        selection_products = [
            create_mock_product(product_name="产品A"),
            create_mock_product(product_name="产品B"),
            create_mock_product(product_name="产品C"),
        ]

        result = DataConverter.collection_to_edit(
            collection_results,
            selection_products,
            default_cost=100.0,
        )

        assert result[0]["cost"] == 100.0  # 100 + 0 * 10
        assert result[1]["cost"] == 110.0  # 100 + 1 * 10
        assert result[2]["cost"] == 120.0  # 100 + 2 * 10

    def test_convert_without_selection_match(self):
        """测试无选品表匹配的情况"""
        from src.data_processor.data_converter import DataConverter

        collection_results = [
            {"product": {"product_name": "未匹配产品"}, "collected_links": []},
        ]
        selection_products = [create_mock_product(product_name="其他产品")]

        result = DataConverter.collection_to_edit(collection_results, selection_products)

        # 应该仍然返回结果,但没有选品表中的额外信息
        assert len(result) == 1
        assert result[0]["keyword"] == "未匹配产品"
        assert "color_spec" not in result[0]

    def test_convert_fills_missing_model_number(self):
        """测试缺失型号自动生成"""
        from src.data_processor.data_converter import DataConverter

        collection_results = [
            {"product": {"product_name": "产品A"}, "collected_links": []},  # 无 model_number
        ]
        selection_products = []

        result = DataConverter.collection_to_edit(collection_results, selection_products)

        # 应该自动生成 A0001
        assert result[0]["model_number"] == "A0001"

    def test_convert_empty_results(self):
        """测试空结果转换"""
        from src.data_processor.data_converter import DataConverter

        result = DataConverter.collection_to_edit([], [])

        assert len(result) == 0


# ==================== edit_to_claim 测试 ====================
class TestDataConverterEditToClaim:
    """edit_to_claim 方法测试"""

    def test_convert_with_default_claim_times(self):
        """测试默认认领次数"""
        from src.data_processor.data_converter import DataConverter

        edit_results = {"edited_count": 3}

        result = DataConverter.edit_to_claim(edit_results)

        assert len(result) == 3
        for i, claim in enumerate(result):
            assert claim["index"] == i
            assert claim["claim_times"] == 4  # 默认值

    def test_convert_with_custom_claim_times(self):
        """测试自定义认领次数"""
        from src.data_processor.data_converter import DataConverter

        edit_results = {"edited_count": 2}

        result = DataConverter.edit_to_claim(edit_results, claim_times=6)

        assert len(result) == 2
        assert result[0]["claim_times"] == 6
        assert result[1]["claim_times"] == 6

    def test_convert_zero_edited_count(self):
        """测试零编辑数量"""
        from src.data_processor.data_converter import DataConverter

        edit_results = {"edited_count": 0}

        result = DataConverter.edit_to_claim(edit_results)

        assert len(result) == 0

    def test_convert_missing_edited_count(self):
        """测试缺失 edited_count 字段"""
        from src.data_processor.data_converter import DataConverter

        edit_results = {}  # 无 edited_count

        result = DataConverter.edit_to_claim(edit_results)

        assert len(result) == 0  # 应该默认为 0

    def test_convert_large_edited_count(self):
        """测试大量编辑数量"""
        from src.data_processor.data_converter import DataConverter

        edit_results = {"edited_count": 100}

        result = DataConverter.edit_to_claim(edit_results, claim_times=2)

        assert len(result) == 100
        assert all(item["claim_times"] == 2 for item in result)
        assert result[99]["index"] == 99


# ==================== validate_collection_results 测试 ====================
class TestDataConverterValidateCollection:
    """validate_collection_results 方法测试"""

    def test_validate_success(self):
        """测试验证成功"""
        from src.data_processor.data_converter import DataConverter

        results = [
            {"collected_links": ["http://link1.com", "http://link2.com"]},
            {"collected_links": ["http://link3.com"]},
        ]

        validation = DataConverter.validate_collection_results(results, expected_count=2)

        assert validation["valid"] is True
        assert len(validation["issues"]) == 0
        assert validation["summary"]["total_products"] == 2
        assert validation["summary"]["products_with_links"] == 2
        assert validation["summary"]["total_links"] == 3

    def test_validate_insufficient_products(self):
        """测试产品数量不足"""
        from src.data_processor.data_converter import DataConverter

        results = [{"collected_links": ["http://link1.com"]}]

        validation = DataConverter.validate_collection_results(results, expected_count=5)

        assert validation["valid"] is False
        assert any("产品数量不足" in issue for issue in validation["issues"])

    def test_validate_missing_links(self):
        """测试缺少链接"""
        from src.data_processor.data_converter import DataConverter

        results = [
            {"collected_links": ["http://link1.com"]},
            {"collected_links": []},  # 无链接
        ]

        validation = DataConverter.validate_collection_results(results, expected_count=2)

        assert validation["valid"] is False
        assert any("没有采集到链接" in issue for issue in validation["issues"])

    def test_validate_empty_results(self):
        """测试空结果"""
        from src.data_processor.data_converter import DataConverter

        validation = DataConverter.validate_collection_results([], expected_count=5)

        assert validation["valid"] is False
        assert validation["summary"]["total_products"] == 0

    def test_validate_counts_links_correctly(self):
        """测试正确统计链接数量"""
        from src.data_processor.data_converter import DataConverter

        results = [
            {"collected_links": ["a", "b", "c"]},
            {"collected_links": ["d", "e"]},
            {"collected_links": ["f"]},
        ]

        validation = DataConverter.validate_collection_results(results, expected_count=3)

        assert validation["summary"]["total_links"] == 6
        assert validation["summary"]["products_with_links"] == 3


# ==================== merge_collection_and_selection 测试 ====================
class TestDataConverterMerge:
    """merge_collection_and_selection 方法测试"""

    def test_merge_matching_products(self):
        """测试匹配产品合并"""
        from src.data_processor.data_converter import DataConverter

        collection_results = [
            {
                "product": {"product_name": "测试产品"},
                "collected_links": ["http://link1.com"],
                "success": True,
            }
        ]
        selection_products = [
            create_mock_product(
                product_name="测试产品",
                model_number="A0001",
                owner="负责人",
                color_spec="红色",
                collect_count=5,
            )
        ]

        result = DataConverter.merge_collection_and_selection(
            collection_results, selection_products
        )

        assert len(result) == 1
        assert result[0]["product_name"] == "测试产品"
        assert result[0]["model_number"] == "A0001"
        assert result[0]["owner"] == "负责人"
        assert result[0]["color_spec"] == "红色"
        assert result[0]["collect_count"] == 5
        assert result[0]["collected_count"] == 1
        assert result[0]["success"] is True

    def test_merge_no_match(self):
        """测试无匹配产品"""
        from src.data_processor.data_converter import DataConverter

        collection_results = [
            {"product": {"product_name": "未知产品"}, "collected_links": []},
        ]
        selection_products = [create_mock_product(product_name="其他产品")]

        result = DataConverter.merge_collection_and_selection(
            collection_results, selection_products
        )

        # 无匹配时不添加到结果
        assert len(result) == 0

    def test_merge_multiple_products(self):
        """测试多个产品合并"""
        from src.data_processor.data_converter import DataConverter

        collection_results = [
            {"product": {"product_name": "产品A"}, "collected_links": ["a", "b"], "success": True},
            {"product": {"product_name": "产品B"}, "collected_links": ["c"], "success": False},
        ]
        selection_products = [
            create_mock_product(product_name="产品A", model_number="A0001"),
            create_mock_product(product_name="产品B", model_number="A0002"),
        ]

        result = DataConverter.merge_collection_and_selection(
            collection_results, selection_products
        )

        assert len(result) == 2
        assert result[0]["collected_count"] == 2
        assert result[0]["success"] is True
        assert result[1]["collected_count"] == 1
        assert result[1]["success"] is False

    def test_merge_empty_inputs(self):
        """测试空输入"""
        from src.data_processor.data_converter import DataConverter

        result = DataConverter.merge_collection_and_selection([], [])

        assert len(result) == 0

    def test_merge_preserves_all_fields(self):
        """测试保留所有字段"""
        from src.data_processor.data_converter import DataConverter

        collection_results = [
            {"product": {"product_name": "产品"}, "collected_links": ["link1"], "success": True}
        ]
        selection_products = [
            create_mock_product(
                product_name="产品",
                size_chart="http://size.jpg",
                product_image="http://image.jpg",
            )
        ]

        result = DataConverter.merge_collection_and_selection(
            collection_results, selection_products
        )

        assert result[0]["size_chart_url"] == "http://size.jpg"
        assert result[0]["product_image_url"] == "http://image.jpg"


# ==================== 边界条件和错误处理测试 ====================
class TestDataConverterEdgeCases:
    """边界条件测试"""

    def test_selection_to_collection_with_special_characters(self):
        """测试特殊字符产品名"""
        from src.data_processor.data_converter import DataConverter

        products = [create_mock_product(product_name="测试/产品 (新款)")]

        result = DataConverter.selection_to_collection(products)

        assert result[0]["keyword"] == "测试/产品 (新款)"

    def test_collection_to_edit_with_empty_product_info(self):
        """测试空产品信息"""
        from src.data_processor.data_converter import DataConverter

        collection_results = [
            {"product": {}, "collected_links": []},  # 空 product 字典
        ]

        result = DataConverter.collection_to_edit(collection_results, [])

        assert len(result) == 1
        assert result[0]["keyword"] == ""  # 空字符串
        assert result[0]["model_number"] == "A0001"  # 自动生成

    def test_validate_with_missing_collected_links_key(self):
        """测试缺失 collected_links 键"""
        from src.data_processor.data_converter import DataConverter

        results = [
            {},  # 无 collected_links 键
        ]

        validation = DataConverter.validate_collection_results(results, expected_count=1)

        # 应该将缺失键视为空链接
        assert validation["valid"] is False
        assert any("没有采集到链接" in issue for issue in validation["issues"])

    def test_merge_with_partial_matches(self):
        """测试部分匹配"""
        from src.data_processor.data_converter import DataConverter

        collection_results = [
            {"product": {"product_name": "产品A"}, "collected_links": ["a"]},
            {"product": {"product_name": "产品B"}, "collected_links": ["b"]},
            {"product": {"product_name": "产品C"}, "collected_links": ["c"]},
        ]
        selection_products = [
            create_mock_product(product_name="产品A"),
            create_mock_product(product_name="产品C"),
            # 产品B 不在选品表中
        ]

        result = DataConverter.merge_collection_and_selection(
            collection_results, selection_products
        )

        # 只有匹配的产品会被合并
        assert len(result) == 2
        product_names = [r["product_name"] for r in result]
        assert "产品A" in product_names
        assert "产品C" in product_names
        assert "产品B" not in product_names


# ==================== 集成测试 ====================
class TestDataConverterIntegration:
    """数据转换器集成测试"""

    def test_full_workflow_conversion(self):
        """测试完整工作流转换"""
        from src.data_processor.data_converter import DataConverter

        # 步骤1: 选品表 → 采集输入
        products = [
            create_mock_product(product_name="产品A", model_number="A0001", collect_count=3),
            create_mock_product(product_name="产品B", model_number="A0002", collect_count=5),
        ]

        collection_input = DataConverter.selection_to_collection(products)
        assert len(collection_input) == 2
        assert collection_input[0]["collect_count"] == 3
        assert collection_input[1]["collect_count"] == 5

        # 步骤2: 模拟采集结果
        collection_results = [
            {
                "product": {"product_name": "产品A", "model_number": "A0001"},
                "collected_links": ["http://a1.com", "http://a2.com", "http://a3.com"],
            },
            {
                "product": {"product_name": "产品B", "model_number": "A0002"},
                "collected_links": ["http://b1.com", "http://b2.com"],
            },
        ]

        # 步骤3: 采集结果 → 编辑输入
        edit_input = DataConverter.collection_to_edit(collection_results, products)
        assert len(edit_input) == 2
        assert len(edit_input[0]["collected_links"]) == 3
        assert len(edit_input[1]["collected_links"]) == 2

        # 步骤4: 验证采集结果
        validation = DataConverter.validate_collection_results(collection_results, expected_count=2)
        assert validation["valid"] is True
        assert validation["summary"]["total_links"] == 5

        # 步骤5: 模拟编辑结果
        edit_results = {"edited_count": 2}

        # 步骤6: 编辑结果 → 认领输入
        claim_input = DataConverter.edit_to_claim(edit_results, claim_times=4)
        assert len(claim_input) == 2
        assert all(item["claim_times"] == 4 for item in claim_input)

    def test_validation_then_merge_flow(self):
        """测试验证后合并流程"""
        from src.data_processor.data_converter import DataConverter

        collection_results = [
            {"product": {"product_name": "产品X"}, "collected_links": ["link1", "link2"]},
        ]
        selection_products = [create_mock_product(product_name="产品X")]

        # 先验证
        validation = DataConverter.validate_collection_results(collection_results, expected_count=1)
        assert validation["valid"] is True

        # 验证通过后合并
        merged = DataConverter.merge_collection_and_selection(
            collection_results, selection_products
        )
        assert len(merged) == 1
        assert merged[0]["collected_count"] == 2
