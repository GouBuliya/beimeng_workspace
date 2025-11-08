"""
@PURPOSE: 读取和处理Excel选品表，提取商品信息用于采集
@OUTLINE:
  - class SelectionTableReader: 选品表读取器
  - def read_excel(): 读取Excel/CSV文件
  - def _read_csv(): CSV读取辅助
  - def validate_row(): 验证行数据完整性
  - def extract_products(): 提取产品列表
  - def _resolve_size_chart_base_url(): 解析尺寸图URL前缀
  - def _build_size_chart_url(): 通过文件名拼接尺寸图URL
@GOTCHAS:
  - Excel格式必须符合SOP规范
  - 型号编号格式为A0001, A0002等
  - 必填字段：产品名称、型号编号、尺寸图URL（可通过图片文件名自动拼接）
@DEPENDENCIES:
  - 外部: pandas, openpyxl
  - 内部: loguru
@RELATED: collection_controller.py, collection_workflow.py
@CHANGELOG:
  - 2025-11-01: 初始创建，实现Excel选品表读取功能
"""

import json
import os
from urllib.parse import urljoin
from pathlib import Path

import pandas as pd
from loguru import logger
from pydantic import BaseModel, Field, field_validator


class ProductSelectionRow(BaseModel):
    """选品表中的单行产品数据.

    根据SOP文档定义的Excel结构：
    - 主品负责人
    - 产品名称 (用作搜索关键词)
    - 标题后缀 (型号编号如A0001)
    - 产品颜色/规格
    - 产品图
    - 尺寸图

    Attributes:
        owner: 主品负责人
        product_name: 产品名称/关键词
        model_number: 型号编号 (如A0001, A026, A045/A046等)
        color_spec: 产品颜色/规格
        collect_count: 需要采集的数量（默认5）
        cost_price: 进货价/成本价

    Examples:
        >>> row = ProductSelectionRow(
        ...     owner="张三",
        ...     product_name="药箱收纳盒",
        ...     model_number="A0049",
        ...     color_spec="白色/大号",
        ...     collect_count=5
        ... )
    """

    owner: str = Field(..., description="主品负责人")
    product_name: str = Field(..., description="产品名称（用作搜索关键词）")
    model_number: str = Field(..., description="型号编号")
    color_spec: str | None = Field(None, description="产品颜色/规格")
    collect_count: int = Field(default=5, ge=1, le=100, description="采集数量")

    cost_price: float | None = Field(None, description="进货价/成本价", ge=0)
    spec_unit: str | None = Field(None, description="规格单位名称")
    spec_options: list[str] | None = Field(None, description="规格选项列表")
    variant_costs: list[float] | None = Field(None, description="多规格对应的进货价列表")
    image_files: list[str] | None = Field(None, description="实拍图数组")
    size_chart_image_url: str = Field(..., description="尺寸图网络图片 URL")

    @field_validator("model_number")
    @classmethod
    def validate_model_number(cls, v: str) -> str:
        """验证型号编号格式（放宽验证，支持 A026, A045/A046 等格式）."""
        if not v or not v.startswith("A"):
            raise ValueError("型号编号必须以A开头")
        return v


class SelectionTableReader:
    """Excel选品表读取器.

    负责读取和解析Excel选品表，提取商品信息用于采集流程。

    Notes:
        - 如未在表中提供 `size_chart_image_url`，将使用 `SIZE_CHART_BASE_URL`
          环境变量（默认为 OSS 域名 `https://miaoshou-tuchuang-beimeng.oss-cn-hangzhou.aliyuncs.com/10%E6%9C%88%E6%96%B0%E5%93%81%E5%8F%AF%E6%8E%A8/`）
          与 `image_files` 的首个文件名拼接生成尺寸图外链。

    Examples:
        >>> reader = SelectionTableReader()
        >>> products = reader.read_excel("data/input/selection_table.xlsx")
        >>> print(len(products))
        10
        >>> print(products[0].product_name)
        '药箱收纳盒'
    """

    def __init__(self):
        """初始化选品表读取器."""
        logger.info("选品表读取器初始化")
        self.size_chart_base_url = self._resolve_size_chart_base_url()

        # Excel列名映射（支持中英文）
        self.column_mapping = {
            "主品负责人": "owner",
            "owner": "owner",
            "负责人": "owner",
            "产品名称": "product_name",
            "product_name": "product_name",
            "商品名称": "product_name",
            "名称": "product_name",
            "标题后缀": "model_number",
            "model_number": "model_number",
            "型号": "model_number",
            "型号编号": "model_number",
            "产品颜色/规格": "color_spec",
            "color_spec": "color_spec",
            "颜色规格": "color_spec",
            "规格": "color_spec",
            "采集数量": "collect_count",
            "collect_count": "collect_count",
            "规格数组": "spec_options",
            "规格单位": "spec_unit",
            # 新增映射：进货价
            "进货价": "cost_price",
            "    进货价": "cost_price",  # 处理带空格的列名
            "成本价": "cost_price",
            "cost_price": "cost_price",
            "价格": "cost_price",
            # 新增映射：实拍图数组
            "实拍图数组": "image_files",
            "image_files": "image_files",
            "尺寸图链接": "size_chart_image_url",
            "尺寸图URL": "size_chart_image_url",
            "size_chart_url": "size_chart_image_url",
            "size_chart_image_url": "size_chart_image_url",
            "image_url": "size_chart_image_url",
        }

    def read_excel(
        self, file_path: str, sheet_name: str = 0, skip_rows: int = 0
    ) -> list[ProductSelectionRow]:
        """读取Excel/CSV选品表.

        Args:
            file_path: Excel文件路径
            sheet_name: 工作表名称或索引（默认第一个）
            skip_rows: 跳过的行数（如果有标题行）

        Returns:
            产品列表

        Raises:
            FileNotFoundError: 文件不存在
            ValueError: Excel格式错误

        Examples:
            >>> reader = SelectionTableReader()
            >>> products = reader.read_excel("selection.xlsx")
            >>> len(products) > 0
            True
        """
        path = Path(file_path)
        logger.info(f"读取选品表: {path}")

        # 检查文件是否存在
        if not path.exists():
            raise FileNotFoundError(f"选品表文件不存在: {path}")

        try:
            suffix = path.suffix.lower()
            if suffix == ".csv":
                logger.debug("检测到CSV文件，使用pd.read_csv读取")
                df = self._read_csv(path, skip_rows)
            else:
                df = pd.read_excel(
                    path,
                    sheet_name=sheet_name,
                    skiprows=skip_rows,
                    dtype=str,  # 先全部读成字符串，后续转换
                )
                logger.info(f"✓ Excel读取成功，共 {len(df)} 行数据")
            logger.debug(f"  列名: {df.columns.tolist()}")

            # 标准化列名
            df = self._normalize_columns(df)

            # 转换为ProductSelectionRow列表
            products = self.extract_products(df)

            logger.success(f"✓ 成功解析 {len(products)} 个产品")

            return products

        except Exception as e:
            logger.error(f"读取选品表失败: {e}")
            raise

    def _read_csv(self, path: Path, skip_rows: int) -> pd.DataFrame:
        """读取CSV选品表，自动处理常见编码."""
        encoding_candidates = ("utf-8-sig", "utf-8", "gbk", "gb2312")
        last_error: str | None = None

        for encoding in encoding_candidates:
            try:
                df = pd.read_csv(
                    path,
                    skiprows=skip_rows,
                    dtype=str,
                    encoding=encoding,
                )
                logger.info(f"✓ CSV读取成功（编码={encoding}），共 {len(df)} 行数据")
                return df
            except UnicodeDecodeError as exc:
                last_error = str(exc)
                logger.debug(
                    "CSV读取尝试失败，编码=%s，错误=%s。继续尝试下一个编码。",
                    encoding,
                    exc,
                )

        error_message = (
            "CSV文件读取失败，无法识别编码。"
            if last_error is None
            else f"CSV文件读取失败，最后错误: {last_error}"
        )
        raise ValueError(error_message)

    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """标准化列名.

        将中文列名映射为英文字段名。

        Args:
            df: 原始DataFrame

        Returns:
            标准化后的DataFrame
        """
        # 创建列名映射
        rename_dict = {}
        for col in df.columns:
            col_str = str(col).strip()
            if col_str in self.column_mapping:
                rename_dict[col] = self.column_mapping[col_str]

        # 重命名列
        if rename_dict:
            df = df.rename(columns=rename_dict)
            logger.debug(f"列名标准化: {rename_dict}")

        return df

    def extract_products(self, df: pd.DataFrame) -> list[ProductSelectionRow]:
        """从DataFrame提取产品列表.

        Args:
            df: pandas DataFrame

        Returns:
            产品列表

        Raises:
            ValueError: 数据验证失败
        """
        products = []
        errors = []

        for idx, row in df.iterrows():
            try:
                # 跳过空行
                if pd.isna(row.get("product_name")) or str(row.get("product_name")).strip() == "":
                    logger.debug(f"跳过第 {idx + 1} 行（空行）")
                    continue

                # 构建产品数据
                product_data = {
                    "owner": str(row.get("owner", "未指定")).strip(),
                    "product_name": str(row.get("product_name")).strip(),
                    "model_number": str(row.get("model_number")).strip(),
                    "color_spec": str(row.get("color_spec", "")).strip() or None,
                    "collect_count": self._parse_collect_count(row.get("collect_count")),
                }

                cost_price, variant_costs = self._parse_costs(row.get("cost_price"))
                product_data["cost_price"] = cost_price
                product_data["variant_costs"] = variant_costs
                product_data["spec_options"] = self._parse_json_list(row.get("spec_options"))
                product_data["spec_unit"] = self._parse_scalar(row.get("spec_unit"))
                product_data["image_files"] = self._parse_json_list(row.get("image_files"))
                size_chart_url = self._parse_scalar(row.get("size_chart_image_url"))
                if not size_chart_url:
                    size_chart_url = self._build_size_chart_url(product_data["image_files"])
                    if size_chart_url:
                        logger.debug("使用图片文件名生成尺寸图URL: %s", size_chart_url[:100])
                if not size_chart_url:
                    raise ValueError("缺少尺寸图URL(size_chart_image_url)")
                product_data["size_chart_image_url"] = size_chart_url

                # 验证并创建ProductSelectionRow
                product = ProductSelectionRow(**product_data)
                products.append(product)

                logger.debug(f"✓ 第 {idx + 1} 行: {product.product_name} ({product.model_number})")

            except Exception as e:
                error_msg = f"第 {idx + 1} 行数据错误: {e}"
                errors.append(error_msg)
                logger.warning(f"⚠️ {error_msg}")
                continue

        # 如果有错误，汇总报告
        if errors:
            logger.warning(f"⚠️ 共 {len(errors)} 行数据存在问题")
            for err in errors[:5]:  # 只显示前5个错误
                logger.warning(f"  - {err}")
            if len(errors) > 5:
                logger.warning(f"  ... 还有 {len(errors) - 5} 个错误")

        return products

    @staticmethod
    def _parse_collect_count(value: object) -> int:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return 5
        try:
            return int(float(str(value)))
        except (TypeError, ValueError):
            return 5

    @staticmethod
    def _parse_scalar(value: object) -> str | None:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _parse_json_list(value: object) -> list[str] | None:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        text = str(value).strip()
        if not text:
            return None
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except json.JSONDecodeError:
            parts = [item.strip() for item in text.split(",") if item.strip()]
            return parts or None
        return None

    @staticmethod
    def _parse_costs(value: object) -> tuple[float | None, list[float] | None]:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None, None
        text = str(value).strip()
        if not text:
            return None, None

        if text.startswith("["):
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    floats: list[float] = []
                    for item in parsed:
                        try:
                            floats.append(float(item))
                        except (TypeError, ValueError):
                            continue
                    if floats:
                        return floats[0], floats
                    return None, None
            except json.JSONDecodeError:
                return None, None

        try:
            return float(text), None
        except (TypeError, ValueError):
            return None, None

    def validate_row(self, row: dict) -> tuple[bool, str | None]:
        """验证单行数据.

        Args:
            row: 行数据字典

        Returns:
            (是否有效, 错误信息)

        Examples:
            >>> reader = SelectionTableReader()
            >>> valid, error = reader.validate_row({
            ...     "product_name": "药箱",
            ...     "model_number": "A0001"
            ... })
            >>> valid
            True
        """
        # 检查必填字段
        if not row.get("product_name"):
            return False, "缺少产品名称"

        if not row.get("model_number"):
            return False, "缺少型号编号"

        # 验证型号格式
        model = str(row.get("model_number")).strip()
        if not (model.startswith("A") and len(model) == 5 and model[1:].isdigit()):
            return False, f"型号编号格式错误: {model}，应为A0001-A9999"

        size_chart_url = row.get("size_chart_image_url")
        if not size_chart_url or not str(size_chart_url).strip():
            # 如果未提供URL但存在图片文件名且可拼接，也视为有效
            image_files = self._parse_json_list(row.get("image_files"))
            generated_url = self._build_size_chart_url(image_files)
            if generated_url:
                return True, None
            return False, "缺少尺寸图URL(size_chart_image_url)"

        return True, None

    def create_sample_excel(self, output_path: str, num_samples: int = 3) -> None:
        """创建示例Excel选品表.

        用于测试和演示。

        Args:
            output_path: 输出文件路径
            num_samples: 示例数量

        Examples:
            >>> reader = SelectionTableReader()
            >>> reader.create_sample_excel("data/sample.xlsx", num_samples=3)
        """
        logger.info(f"创建示例选品表: {output_path}")

        # 示例数据
        sample_data = [
            {
                "主品负责人": "张三",
                "产品名称": "药箱收纳盒",
                "标题后缀": "A0049",
                "产品颜色/规格": "白色/大号",
                "采集数量": 5,
                "尺寸图链接": "https://example.com/images/sample-size-chart-1.jpg",
            },
            {
                "主品负责人": "李四",
                "产品名称": "智能手表运动防水",
                "标题后缀": "A0050",
                "产品颜色/规格": "黑色/标准版",
                "采集数量": 5,
                "尺寸图链接": "https://example.com/images/sample-size-chart-2.jpg",
            },
            {
                "主品负责人": "王五",
                "产品名称": "便携洗衣机迷你",
                "标题后缀": "A0051",
                "产品颜色/规格": "蓝色/家用款",
                "采集数量": 5,
                "尺寸图链接": "https://example.com/images/sample-size-chart-3.jpg",
            },
        ]

        # 取前N个
        data = sample_data[:num_samples]

        # 创建DataFrame
        df = pd.DataFrame(data)

        # 确保目录存在
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # 保存Excel
        df.to_excel(output_path, index=False, engine="openpyxl")

        logger.success(f"✓ 示例选品表已创建: {output_path}")
        logger.info(f"  包含 {len(data)} 个示例产品")

    def _resolve_size_chart_base_url(self) -> str | None:
        """解析尺寸图外链的基础 URL 前缀."""

        base_url = os.getenv(
            "SIZE_CHART_BASE_URL",
            "https://miaoshou-tuchuang-beimeng.oss-cn-hangzhou.aliyuncs.com/10%E6%9C%88%E6%96%B0%E5%93%81%E5%8F%AF%E6%8E%A8shou/",
        )
        text = str(base_url).strip()
        return text or None

    def _build_size_chart_url(self, image_files: list[str] | None) -> str | None:
        """根据实拍图文件名拼接尺寸图URL."""

        if not self.size_chart_base_url or not image_files:
            return None
        filename = next((item for item in image_files if item), None)
        if not filename:
            return None
        candidate = urljoin(f"{self.size_chart_base_url.rstrip('/')}/", filename.lstrip("/"))
        return candidate or None
