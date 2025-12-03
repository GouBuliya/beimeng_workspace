"""
首次编辑 API 模式的单元测试。

测试 _update_product_detail 函数的各项功能：
1. 规格名称填写 (colorPropName)
2. 规格选项替换 (colorMap.name)
3. 标题更新
4. 价格/库存/重量/尺寸更新
5. SKU 图片更新
6. 尺寸图更新
7. 视频更新

使用方法:
uv run pytest tests/test_first_edit_api.py -v
"""

from pathlib import Path

import pytest
from src.browser.miaoshou.first_edit_api import _update_product_detail
from src.data_processor.selection_table_reader import ProductSelectionRow, SelectionTableReader


@pytest.fixture
def sample_selection() -> ProductSelectionRow:
    """创建样例选品数据。"""
    return ProductSelectionRow(
        model_number="A026",
        spec_unit="层",
        spec_options=["3", "4", "5"],
        cost_price=80.0,
        sku_image_urls=[
            "https://miaoshou-tuchuang-beimeng.oss-cn-hangzhou.aliyuncs.com/A026-1.png",
            "https://miaoshou-tuchuang-beimeng.oss-cn-hangzhou.aliyuncs.com/A026-2.png",
            "https://miaoshou-tuchuang-beimeng.oss-cn-hangzhou.aliyuncs.com/A026-3.png",
        ],
        product_video_url="https://miaoshou-tuchuang-beimeng.oss-cn-hangzhou.aliyuncs.com/A026.mp4",
        size_chart_image_url="https://miaoshou-tuchuang-beimeng.oss-cn-hangzhou.aliyuncs.com/A026.png",
    )


@pytest.fixture
def sample_product_detail() -> dict:
    """创建样例产品详情（模拟 API 返回）。"""
    return {
        "commonCollectBoxDetailId": "3037726721",
        "title": "收纳柜 | 白色塑料防潮储物柜 AY026 型号",
        "colorPropName": "颜色",
        "colorMap": {
            "1764691988463": {
                "name": "白色",
                "imgUrls": ["https://old-image.com/old1.png"],
                "imgUrl": "https://old-image.com/old1.png",
            },
            "1764789259262": {
                "name": "黑色",
                "imgUrls": ["https://old-image.com/old2.png"],
                "imgUrl": "https://old-image.com/old2.png",
            },
            "1764789260914": {
                "name": "灰色",
                "imgUrls": ["https://old-image.com/old3.png"],
                "imgUrl": "https://old-image.com/old3.png",
            },
        },
        "skuMap": {
            ";1764691988463;;": {
                "price": "100",
                "stock": "50",
                "weight": "",
                "packageLength": "10",
                "packageWidth": "10",
                "packageHeight": "10",
            },
            ";1764789259262;;": {
                "price": "120",
                "stock": "30",
                "weight": "",
                "packageLength": "10",
                "packageWidth": "10",
                "packageHeight": "10",
            },
            ";1764789260914;;": {
                "price": "130",
                "stock": "20",
                "weight": "",
                "packageLength": "10",
                "packageWidth": "10",
                "packageHeight": "10",
            },
        },
        "sizeChart": "",
        "mainImgVideoUrl": "",
        "weight": "",
        "packageLength": "10",
        "packageWidth": "10",
        "packageHeight": "10",
    }


class TestUpdateProductDetail:
    """测试 _update_product_detail 函数。"""

    def test_update_color_prop_name(
        self, sample_selection: ProductSelectionRow, sample_product_detail: dict
    ):
        """测试规格名称更新。"""
        updated = _update_product_detail(
            detail=sample_product_detail,
            selection=sample_selection,
        )

        # 验证规格名称已更新
        assert updated["colorPropName"] == "层"

    def test_update_spec_options(
        self, sample_selection: ProductSelectionRow, sample_product_detail: dict
    ):
        """测试规格选项更新。"""
        updated = _update_product_detail(
            detail=sample_product_detail,
            selection=sample_selection,
        )

        # 验证规格选项已更新
        color_map = updated["colorMap"]
        names = [data["name"] for data in color_map.values()]
        assert names == ["3", "4", "5"]

    def test_update_sku_images(
        self, sample_selection: ProductSelectionRow, sample_product_detail: dict
    ):
        """测试 SKU 图片更新。"""
        updated = _update_product_detail(
            detail=sample_product_detail,
            selection=sample_selection,
        )

        # 验证 SKU 图片已更新
        color_map = updated["colorMap"]
        for idx, (_, data) in enumerate(color_map.items()):
            expected_url = sample_selection.sku_image_urls[idx]
            assert data["imgUrl"] == expected_url
            assert data["imgUrls"] == [expected_url]

    def test_update_size_chart(
        self, sample_selection: ProductSelectionRow, sample_product_detail: dict
    ):
        """测试尺寸图更新。"""
        updated = _update_product_detail(
            detail=sample_product_detail,
            selection=sample_selection,
        )

        # 验证尺寸图已更新
        assert updated["sizeChart"] == sample_selection.size_chart_image_url

    def test_update_video(self, sample_selection: ProductSelectionRow, sample_product_detail: dict):
        """测试视频更新。"""
        updated = _update_product_detail(
            detail=sample_product_detail,
            selection=sample_selection,
        )

        # 验证视频已更新
        assert updated["mainImgVideoUrl"] == sample_selection.product_video_url

    def test_update_sku_stock(
        self, sample_selection: ProductSelectionRow, sample_product_detail: dict
    ):
        """测试库存更新为 999。"""
        updated = _update_product_detail(
            detail=sample_product_detail,
            selection=sample_selection,
        )

        # 验证所有 SKU 库存都更新为 999
        for sku_data in updated["skuMap"].values():
            assert sku_data["stock"] == "999"

    def test_update_weight_and_dimensions(
        self, sample_selection: ProductSelectionRow, sample_product_detail: dict
    ):
        """测试重量和尺寸更新。"""
        updated = _update_product_detail(
            detail=sample_product_detail,
            selection=sample_selection,
        )

        # 验证所有 SKU 都有重量和尺寸
        for sku_data in updated["skuMap"].values():
            assert sku_data["weight"] != ""
            assert int(sku_data["weight"]) >= 5000  # 随机生成的重量范围
            assert int(sku_data["packageLength"]) >= 50
            assert int(sku_data["packageWidth"]) >= 50
            assert int(sku_data["packageHeight"]) >= 50

    def test_update_title_with_model(
        self, sample_selection: ProductSelectionRow, sample_product_detail: dict
    ):
        """测试标题添加型号。"""
        updated = _update_product_detail(
            detail=sample_product_detail,
            selection=sample_selection,
        )

        # 验证标题包含型号（追加在原标题后面）
        assert "A026" in updated["title"]
        # 验证不会重复添加型号
        assert updated["title"].count("A026") == 1

    def test_no_selection_keeps_original(self, sample_product_detail: dict):
        """测试没有选品数据时保持原值但更新基础字段。"""
        original_title = sample_product_detail["title"]
        original_color_prop = sample_product_detail["colorPropName"]

        updated = _update_product_detail(
            detail=sample_product_detail,
            selection=None,
        )

        # 验证标题和规格名称保持不变
        assert updated["title"] == original_title
        assert updated["colorPropName"] == original_color_prop

        # 但基础字段（库存、重量、尺寸）仍会更新
        for sku_data in updated["skuMap"].values():
            assert sku_data["stock"] == "999"
            assert int(sku_data["weight"]) >= 5000

    def test_expand_spec_options_when_more_needed(self, sample_product_detail: dict):
        """测试当选品表规格数量大于现有规格时，自动扩展。"""
        # 创建一个有 5 个规格的选品数据（现有只有 3 个）
        selection = ProductSelectionRow(
            model_number="A100",
            spec_unit="颜色",
            spec_options=["蓝", "粉", "灰", "黑", "白"],
            cost_price=100.0,
            sku_image_urls=[
                "https://example.com/blue.png",
                "https://example.com/pink.png",
                "https://example.com/gray.png",
                "https://example.com/black.png",
                "https://example.com/white.png",
            ],
        )

        updated = _update_product_detail(
            detail=sample_product_detail,
            selection=selection,
        )

        # 验证 colorMap 现在有 5 个规格
        color_map = updated["colorMap"]
        assert len(color_map) == 5

        # 验证所有规格名称正确
        names = [data["name"] for data in color_map.values()]
        assert names == ["蓝", "粉", "灰", "黑", "白"]

        # 验证所有规格图片正确
        for idx, color_data in enumerate(color_map.values()):
            expected_url = selection.sku_image_urls[idx]
            assert color_data["imgUrl"] == expected_url
            assert color_data["imgUrls"] == [expected_url]

        # 验证 skuMap 也有 5 个 SKU
        sku_map = updated["skuMap"]
        assert len(sku_map) == 5

    def test_shrink_spec_options_when_fewer_needed(self, sample_product_detail: dict):
        """测试当选品表规格数量小于现有规格时，自动精简。"""
        # 创建一个只有 2 个规格的选品数据（现有有 3 个）
        selection = ProductSelectionRow(
            model_number="A200",
            spec_unit="尺寸",
            spec_options=["小号", "大号"],
            cost_price=50.0,
            sku_image_urls=[
                "https://example.com/small.png",
                "https://example.com/large.png",
            ],
        )

        updated = _update_product_detail(
            detail=sample_product_detail,
            selection=selection,
        )

        # 验证 colorMap 现在只有 2 个规格
        color_map = updated["colorMap"]
        assert len(color_map) == 2

        # 验证所有规格名称正确
        names = [data["name"] for data in color_map.values()]
        assert names == ["小号", "大号"]

        # 验证 skuMap 也只有 2 个 SKU
        sku_map = updated["skuMap"]
        assert len(sku_map) == 2


class TestSelectionTableReader:
    """测试使用真实 CSV 文件读取选品数据。"""

    def test_read_sample_csv(self):
        """测试读取样例 CSV 文件。"""
        csv_path = Path("/Users/candy/beimeng_workspace/data/10月新品可上架(3).csv")
        if not csv_path.exists():
            pytest.skip("样例 CSV 文件不存在")

        reader = SelectionTableReader()
        selections = reader.read_excel(str(csv_path))

        assert len(selections) > 0

        # 验证第一条数据
        first = selections[0]
        assert first.model_number == "A026"
        assert first.spec_unit == "层"
        assert first.spec_options == ["3", "4", "5"]
        assert first.size_chart_image_url.endswith("A026.png")
        assert first.product_video_url.endswith("A026.mp4")
        assert len(first.sku_image_urls) == 3
