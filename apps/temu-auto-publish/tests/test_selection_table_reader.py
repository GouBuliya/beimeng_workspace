"""
@PURPOSE: 测试 SelectionTableReader 选品表读取器
@OUTLINE:
  - TestProductSelectionRow: 测试产品选品行数据模型
  - TestSelectionTableReader: 测试选品表读取器主类
  - TestSelectionTableReaderColumnMapping: 测试列名映射
  - TestSelectionTableReaderValidation: 测试数据验证
  - TestSelectionTableReaderEdgeCases: 测试边界情况
@DEPENDENCIES:
  - 外部: pytest, pandas, openpyxl
  - 内部: src.data_processor.selection_table_reader
"""

import json
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from src.data_processor.selection_table_reader import (
    ProductSelectionRow,
    SelectionTableReader,
)


class TestProductSelectionRow:
    """测试产品选品行数据模型"""
    
    def test_create_default(self):
        """测试默认创建"""
        row = ProductSelectionRow()
        
        assert row.owner == "未指定"
        assert row.product_name == ""
        assert row.model_number == "A0000"
        assert row.collect_count == 5
    
    def test_create_with_data(self):
        """测试带数据创建"""
        row = ProductSelectionRow(
            owner="张三",
            product_name="药箱收纳盒",
            model_number="A0001",
            color_spec="白色/大号",
            collect_count=5,
            cost_price=15.0
        )
        
        assert row.owner == "张三"
        assert row.product_name == "药箱收纳盒"
        assert row.model_number == "A0001"
        assert row.cost_price == 15.0
    
    def test_model_number_validation_auto_prefix(self):
        """测试型号编号自动添加A前缀"""
        row = ProductSelectionRow(
            product_name="test",
            model_number="0001"
        )
        
        assert row.model_number == "A0001"
    
    def test_model_number_validation_empty(self):
        """测试空型号编号"""
        row = ProductSelectionRow(
            product_name="test",
            model_number=""
        )
        
        assert row.model_number == "A0000"
    
    def test_spec_options(self):
        """测试规格选项"""
        row = ProductSelectionRow(
            product_name="test",
            spec_options=["小号", "中号", "大号"],
            spec_unit="尺寸"
        )
        
        assert row.spec_options == ["小号", "中号", "大号"]
        assert row.spec_unit == "尺寸"
    
    def test_variant_costs(self):
        """测试多规格进货价"""
        row = ProductSelectionRow(
            product_name="test",
            cost_price=10.0,
            variant_costs=[10.0, 15.0, 20.0]
        )
        
        assert row.cost_price == 10.0
        assert row.variant_costs == [10.0, 15.0, 20.0]
    
    def test_sku_image_urls(self):
        """测试SKU图片URL"""
        row = ProductSelectionRow(
            product_name="test",
            sku_image_urls=[
                "https://example.com/img1.jpg",
                "https://example.com/img2.jpg"
            ]
        )
        
        assert len(row.sku_image_urls) == 2


class TestSelectionTableReader:
    """测试选品表读取器主类"""
    
    @pytest.fixture
    def reader(self):
        """创建读取器实例"""
        return SelectionTableReader()
    
    @pytest.fixture
    def sample_excel(self, tmp_path):
        """创建示例Excel文件"""
        filepath = tmp_path / "sample.xlsx"
        df = pd.DataFrame({
            "主品负责人": ["张三", "李四", "王五"],
            "产品名称": ["药箱收纳盒", "厨房收纳架", "桌面整理盒"],
            "标题后缀": ["A0001", "A0002", "A0003"],
            "产品颜色/规格": ["白色", "黑色", "灰色"],
            "采集数量": [5, 3, 5],
            "进货价": [15.0, 25.0, 12.0],
        })
        df.to_excel(filepath, index=False)
        return filepath
    
    @pytest.fixture
    def sample_csv(self, tmp_path):
        """创建示例CSV文件"""
        filepath = tmp_path / "sample.csv"
        df = pd.DataFrame({
            "产品名称": ["药箱收纳盒", "厨房收纳架"],
            "标题后缀": ["A0001", "A0002"],
            "进货价": [15.0, 25.0],
        })
        df.to_csv(filepath, index=False, encoding="utf-8-sig")
        return filepath
    
    def test_init(self, reader):
        """测试初始化"""
        assert reader.column_mapping is not None
        assert "产品名称" in reader.column_mapping
        assert "进货价" in reader.column_mapping
    
    def test_read_excel(self, reader, sample_excel):
        """测试读取Excel"""
        products = reader.read_excel(str(sample_excel))
        
        assert len(products) == 3
        assert products[0].product_name == "药箱收纳盒"
        assert products[0].owner == "张三"
        assert products[0].model_number == "A0001"
    
    def test_read_csv(self, reader, sample_csv):
        """测试读取CSV"""
        products = reader.read_excel(str(sample_csv))
        
        assert len(products) == 2
        assert products[0].product_name == "药箱收纳盒"
    
    def test_read_file_not_found(self, reader):
        """测试文件不存在"""
        with pytest.raises(FileNotFoundError):
            reader.read_excel("nonexistent.xlsx")
    
    def test_skip_empty_rows(self, reader, tmp_path):
        """测试跳过空行"""
        filepath = tmp_path / "with_empty.xlsx"
        df = pd.DataFrame({
            "产品名称": ["产品1", None, "产品2", ""],
            "标题后缀": ["A0001", "A0002", "A0003", "A0004"],
        })
        df.to_excel(filepath, index=False)
        
        products = reader.read_excel(str(filepath))
        
        # 应该只读取到2个有效产品
        assert len(products) == 2
    
    def test_cost_price_parsing(self, reader, tmp_path):
        """测试进货价解析"""
        filepath = tmp_path / "costs.xlsx"
        df = pd.DataFrame({
            "产品名称": ["产品1", "产品2", "产品3"],
            "标题后缀": ["A0001", "A0002", "A0003"],
            "进货价": ["15.0", "[10.0, 15.0, 20.0]", ""],
        })
        df.to_excel(filepath, index=False)
        
        products = reader.read_excel(str(filepath))
        
        assert products[0].cost_price == 15.0
        assert products[1].cost_price == 10.0  # 数组取第一个
        assert products[1].variant_costs == [10.0, 15.0, 20.0]


class TestSelectionTableReaderColumnMapping:
    """测试列名映射"""
    
    @pytest.fixture
    def reader(self):
        return SelectionTableReader()
    
    def test_chinese_column_mapping(self, reader, tmp_path):
        """测试中文列名映射"""
        filepath = tmp_path / "chinese.xlsx"
        df = pd.DataFrame({
            "主品负责人": ["张三"],
            "产品名称": ["测试产品"],
            "型号编号": ["A0001"],
            "成本价": [10.0],
        })
        df.to_excel(filepath, index=False)
        
        products = reader.read_excel(str(filepath))
        
        assert len(products) == 1
        assert products[0].cost_price == 10.0
    
    def test_english_column_mapping(self, reader, tmp_path):
        """测试英文列名映射"""
        filepath = tmp_path / "english.xlsx"
        df = pd.DataFrame({
            "owner": ["John"],
            "product_name": ["Test Product"],
            "model_number": ["A0001"],
            "cost_price": [15.0],
        })
        df.to_excel(filepath, index=False)
        
        products = reader.read_excel(str(filepath))
        
        assert len(products) == 1
        assert products[0].owner == "John"
        assert products[0].cost_price == 15.0
    
    def test_alternative_column_names(self, reader, tmp_path):
        """测试替代列名"""
        filepath = tmp_path / "alternative.xlsx"
        df = pd.DataFrame({
            "负责人": ["张三"],
            "商品名称": ["测试产品"],
            "型号": ["A0001"],
            "价格": [20.0],
        })
        df.to_excel(filepath, index=False)
        
        products = reader.read_excel(str(filepath))
        
        assert products[0].owner == "张三"
        assert products[0].cost_price == 20.0


class TestSelectionTableReaderValidation:
    """测试数据验证"""
    
    @pytest.fixture
    def reader(self):
        return SelectionTableReader()
    
    def test_validate_row_success(self, reader):
        """测试验证成功"""
        row = {
            "product_name": "药箱收纳盒",
            "model_number": "A0001"
        }
        
        valid, error = reader.validate_row(row)
        
        assert valid is True
        assert error is None
    
    def test_validate_row_missing_product_name(self, reader):
        """测试缺少产品名称"""
        row = {
            "model_number": "A0001"
        }
        
        valid, error = reader.validate_row(row)
        
        assert valid is False
        assert "产品名称" in error
    
    def test_validate_row_missing_model_number(self, reader):
        """测试缺少型号编号"""
        row = {
            "product_name": "测试产品"
        }
        
        valid, error = reader.validate_row(row)
        
        assert valid is False
        assert "型号编号" in error
    
    def test_validate_row_invalid_model_format(self, reader):
        """测试型号格式错误"""
        row = {
            "product_name": "测试产品",
            "model_number": "B001"  # 不是A开头
        }
        
        valid, error = reader.validate_row(row)
        
        assert valid is False
        assert "格式错误" in error


class TestSelectionTableReaderJsonParsing:
    """测试JSON解析"""
    
    @pytest.fixture
    def reader(self):
        return SelectionTableReader()
    
    def test_parse_json_list_from_string(self, reader, tmp_path):
        """测试从字符串解析JSON列表"""
        filepath = tmp_path / "json_list.xlsx"
        df = pd.DataFrame({
            "产品名称": ["测试产品"],
            "标题后缀": ["A0001"],
            "规格数组": ['["小号", "中号", "大号"]'],
        })
        df.to_excel(filepath, index=False)
        
        products = reader.read_excel(str(filepath))
        
        assert products[0].spec_options == ["小号", "中号", "大号"]
    
    def test_parse_comma_separated_list(self, reader, tmp_path):
        """测试逗号分隔的列表"""
        filepath = tmp_path / "comma_list.xlsx"
        df = pd.DataFrame({
            "产品名称": ["测试产品"],
            "标题后缀": ["A0001"],
            "规格数组": ["小号, 中号, 大号"],
        })
        df.to_excel(filepath, index=False)
        
        products = reader.read_excel(str(filepath))
        
        assert products[0].spec_options == ["小号", "中号", "大号"]
    
    def test_parse_image_files_array(self, reader, tmp_path):
        """测试实拍图数组解析"""
        filepath = tmp_path / "images.xlsx"
        df = pd.DataFrame({
            "产品名称": ["测试产品"],
            "标题后缀": ["A0001"],
            "实拍图数组": ['["img1.jpg", "img2.jpg"]'],
        })
        df.to_excel(filepath, index=False)
        
        products = reader.read_excel(str(filepath))
        
        assert products[0].image_files == ["img1.jpg", "img2.jpg"]


class TestSelectionTableReaderEdgeCases:
    """测试边界情况"""
    
    @pytest.fixture
    def reader(self):
        return SelectionTableReader()
    
    def test_empty_file(self, reader, tmp_path):
        """测试空文件"""
        filepath = tmp_path / "empty.xlsx"
        df = pd.DataFrame(columns=["产品名称", "标题后缀"])
        df.to_excel(filepath, index=False)
        
        products = reader.read_excel(str(filepath))
        
        assert len(products) == 0
    
    def test_special_characters_in_data(self, reader, tmp_path):
        """测试特殊字符"""
        filepath = tmp_path / "special.xlsx"
        df = pd.DataFrame({
            "产品名称": ["产品「特殊」名称"],
            "标题后缀": ["A0001"],
        })
        df.to_excel(filepath, index=False)
        
        products = reader.read_excel(str(filepath))
        
        assert "特殊" in products[0].product_name
    
    def test_large_collect_count(self, reader, tmp_path):
        """测试大采集数量"""
        filepath = tmp_path / "large_count.xlsx"
        df = pd.DataFrame({
            "产品名称": ["测试产品"],
            "标题后缀": ["A0001"],
            "采集数量": [100],
        })
        df.to_excel(filepath, index=False)
        
        products = reader.read_excel(str(filepath))
        
        assert products[0].collect_count == 100
    
    def test_default_collect_count(self, reader, tmp_path):
        """测试默认采集数量"""
        filepath = tmp_path / "no_count.xlsx"
        df = pd.DataFrame({
            "产品名称": ["测试产品"],
            "标题后缀": ["A0001"],
        })
        df.to_excel(filepath, index=False)
        
        products = reader.read_excel(str(filepath))
        
        assert products[0].collect_count == 5  # 默认值
    
    def test_csv_encoding_detection(self, reader, tmp_path):
        """测试CSV编码检测"""
        # GBK 编码
        filepath = tmp_path / "gbk.csv"
        df = pd.DataFrame({
            "产品名称": ["中文产品"],
            "标题后缀": ["A0001"],
        })
        df.to_csv(filepath, index=False, encoding="gbk")
        
        products = reader.read_excel(str(filepath))
        
        assert len(products) == 1
        assert products[0].product_name == "中文产品"


class TestSelectionTableReaderSampleCreation:
    """测试示例文件创建"""
    
    def test_create_sample_excel(self, tmp_path):
        """测试创建示例Excel"""
        reader = SelectionTableReader()
        output_path = tmp_path / "sample_output.xlsx"
        
        reader.create_sample_excel(str(output_path), num_samples=3)
        
        assert output_path.exists()
        
        # 验证内容
        products = reader.read_excel(str(output_path))
        assert len(products) == 3
    
    def test_create_sample_excel_custom_count(self, tmp_path):
        """测试自定义数量创建示例"""
        reader = SelectionTableReader()
        output_path = tmp_path / "sample_2.xlsx"
        
        reader.create_sample_excel(str(output_path), num_samples=2)
        
        products = reader.read_excel(str(output_path))
        assert len(products) == 2


class TestSelectionTableReaderURLBuilding:
    """测试URL构建功能"""
    
    @pytest.fixture
    def reader(self):
        return SelectionTableReader()
    
    def test_build_sku_image_urls_from_files(self, reader, tmp_path, monkeypatch):
        """测试从文件名构建SKU图片URL"""
        monkeypatch.setenv("PRODUCT_IMAGE_BASE_URL", "https://example.com/images/")
        
        reader_new = SelectionTableReader()
        
        filepath = tmp_path / "sku_images.xlsx"
        df = pd.DataFrame({
            "产品名称": ["测试产品"],
            "标题后缀": ["A0001"],
            "实拍图数组": ['["product1.jpg", "product2.jpg"]'],
        })
        df.to_excel(filepath, index=False)
        
        products = reader_new.read_excel(str(filepath))
        
        # 应该构建完整URL
        assert len(products[0].sku_image_urls) == 2
    
    def test_full_url_preserved(self, reader, tmp_path):
        """测试完整URL保留"""
        filepath = tmp_path / "full_urls.xlsx"
        df = pd.DataFrame({
            "产品名称": ["测试产品"],
            "标题后缀": ["A0001"],
            "实拍图数组": ['["https://full.url/img.jpg"]'],
        })
        df.to_excel(filepath, index=False)
        
        products = reader.read_excel(str(filepath))
        
        assert products[0].sku_image_urls[0] == "https://full.url/img.jpg"








