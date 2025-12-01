"""
@PURPOSE: 读取并校验选品 Excel/CSV，产出标准化产品行数据供采集与发布流程使用
@OUTLINE:
  - class ProductSelectionRow: 选品表行的 Pydantic 模型与基础校验
  - class SelectionTableReader: 读取文件、列名标准化、数据解析与示例生成
  - Helper: CSV 编码检测、JSON 列表解析、价格/数量/URL 构建工具
@DEPENDENCIES:
  - 外部: pandas, pydantic, loguru
  - 内部: 无
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import pandas as pd
from loguru import logger
from pandas.errors import ParserError
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProductSelectionRow(BaseModel):
    """选品表中的单行产品数据。

    根据采集 SOP 定义的 Excel 结构，包含型号、数量、媒体等字段。

    Attributes:
        owner: 主品负责人。
        product_name: 产品名称或关键字。
        model_number: 型号编号（自动补全 A 前缀）。
        color_spec: 颜色或规格说明。
        collect_count: 需要采集的数量，范围 1-100。
        cost_price: 进货价或成本价。
        spec_unit: 规格单位名称。
        spec_options: 规格选项列表。
        variant_costs: 多规格的进货价列表。
        image_files: 实拍图文件名列表。
        size_chart_image_url: 尺码图 URL。
        product_video_url: 产品视频 URL。
        sku_image_urls: SKU 图 URL 列表（可自动补全前缀）。
    """

    model_config = ConfigDict(str_strip_whitespace=True, populate_by_name=True)

    owner: str = Field(default="未指定", description="主品负责人")
    product_name: str = Field(default="", description="产品名称/关键字")
    model_number: str = Field(default="A0000", description="型号编号，例如 A0001")
    color_spec: str | None = Field(default=None, description="产品颜色或规格")
    collect_count: int = Field(default=5, ge=1, le=100, description="需要采集的数量")
    cost_price: float | None = Field(default=None, ge=0, description="进货价/成本价")
    spec_unit: str | None = Field(default=None, description="规格单位名称")
    spec_options: list[str] | None = Field(default=None, description="规格选项列表")
    variant_costs: list[float] | None = Field(default=None, description="多规格价格列表")
    image_files: list[str] | None = Field(
        default=None, description="本地或相对路径图片文件名"
    )
    size_chart_image_url: str = Field(default="", description="尺码图 URL")
    product_video_url: str | None = Field(default=None, description="产品视频 URL")
    sku_image_urls: list[str] = Field(
        default_factory=list, description="SKU 图片 URL 列表（自动补全前缀）"
    )

    @field_validator("model_number")
    @classmethod
    def validate_model_number(cls, value: str) -> str:
        """确保型号以 A 开头，空值回退到 A0000."""

        if not value:
            return "A0000"
        normalized = value.strip()
        if not normalized:
            return "A0000"
        if not normalized.startswith("A"):
            normalized = f"A{normalized}"
        return normalized


class SelectionTableReader:
    """选品表读取器，支持 Excel/CSV 解析、列名标准化和数据校验。

    Examples:
        >>> reader = SelectionTableReader()
        >>> products = reader.read_excel("data/input/selection.xlsx")
        >>> len(products) > 0
        True
    """

    def __init__(self) -> None:
        self.product_image_base_url = self._resolve_product_image_base_url()
        self.column_mapping = self._build_column_mapping()

    def read_excel(
        self, file_path: str, sheet_name: int | str = 0, skip_rows: int = 0
    ) -> list[ProductSelectionRow]:
        """读取 Excel/CSV 选品表并返回标准化产品列表。

        Args:
            file_path: Excel 或 CSV 文件路径。
            sheet_name: Excel 工作表名称或索引。
            skip_rows: 需要跳过的行数（处理多余标题）。

        Returns:
            ProductSelectionRow 列表。

        Raises:
            FileNotFoundError: 文件不存在。
            ValueError: 文件解析失败。
        """

        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"选品表文件不存在: {path}")

        logger.info("读取选品表: {}", path)

        try:
            suffix = path.suffix.lower()
            if suffix == ".csv":
                df = self._read_csv(path, skip_rows)
            else:
                df = pd.read_excel(
                    path,
                    sheet_name=sheet_name,
                    skiprows=skip_rows,
                    dtype=str,
                )
                logger.info("Excel 读取成功，共 {} 行记录", len(df))
        except Exception as exc:
            raise ValueError(f"读取选品表失败: {exc}") from exc

        df = self._normalize_columns(df)
        products = self.extract_products(df)
        logger.success("成功解析 {} 个产品条目", len(products))
        return products

    def _read_csv(self, path: Path, skip_rows: int) -> pd.DataFrame:
        """读取 CSV 选品表，自动检测编码并处理异常行。

        Args:
            path: CSV 文件路径。
            skip_rows: 需要跳过的行数。

        Returns:
            解析后的 DataFrame。

        Raises:
            ValueError: 无法识别编码或解析失败。
        """

        encoding_candidates = (
            "utf-8-sig",
            "utf-8",
            "utf-16",
            "gbk",
            "gb2312",
            "latin-1",
        )
        last_error: str | None = None

        for encoding in encoding_candidates:
            try:
                df = pd.read_csv(
                    path,
                    skiprows=skip_rows,
                    dtype=str,
                    encoding=encoding,
                )
                logger.info("CSV 读取成功（编码={}），共 {} 行", encoding, len(df))
                return df
            except UnicodeDecodeError as exc:
                last_error = str(exc)
                logger.debug("CSV 编码尝试失败，encoding={}，error={}", encoding, exc)
            except ParserError as exc:
                last_error = str(exc)
                logger.warning(
                    "CSV 解析异常，尝试使用 python engine 跳过坏行: {}", exc
                )
                try:
                    df = pd.read_csv(
                        path,
                        skiprows=skip_rows,
                        dtype=str,
                        encoding=encoding,
                        engine="python",
                        on_bad_lines="skip",
                    )
                    logger.info(
                        "CSV 读取成功（python engine, encoding={}），共 {} 行",
                        encoding,
                        len(df),
                    )
                    return df
                except Exception as fallback_exc:  # noqa: BLE001
                    last_error = str(fallback_exc)
                    logger.debug(
                        "CSV python engine 失败，encoding={}，error={}",
                        encoding,
                        fallback_exc,
                    )
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
                logger.debug("CSV 读取失败，encoding={}，error={}", encoding, exc)

        # 最后容错：宽松解码 + 跳过坏行
        try:
            df = pd.read_csv(
                path,
                skiprows=skip_rows,
                dtype=str,
                encoding="utf-8",
                encoding_errors="replace",
                engine="python",
                on_bad_lines="skip",
            )
            logger.warning(
                "CSV 进入容错模式（utf-8 replace, 跳过异常行），共 {} 行", len(df)
            )
            return df
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            logger.debug("CSV 容错模式失败: {}", exc)

        error_message = (
            "CSV 文件读取失败，无法识别编码"
            if last_error is None
            else f"CSV 文件读取失败，最后错误: {last_error}"
        )
        raise ValueError(error_message)

    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """标准化列名，将中英文列映射到内部字段。

        Args:
            df: 原始 DataFrame。

        Returns:
            列名被映射后的 DataFrame。
        """

        rename_dict: dict[str, str] = {}
        for col in df.columns:
            col_str = str(col).strip()
            if col_str in self.column_mapping:
                rename_dict[col] = self.column_mapping[col_str]

        if rename_dict:
            df = df.rename(columns=rename_dict)
            logger.debug("列名标准化: {}", rename_dict)
        return df

    def extract_products(self, df: pd.DataFrame) -> list[ProductSelectionRow]:
        """从 DataFrame 中提取产品列表并执行轻量校验。

        Args:
            df: 已标准化列名的 DataFrame。

        Returns:
            解析后的 ProductSelectionRow 列表。
        """

        products: list[ProductSelectionRow] = []
        errors: list[str] = []

        for idx, row in df.iterrows():
            try:
                raw_name = row.get("product_name", "")
                if self._is_missing(raw_name):
                    logger.debug("跳过第 {} 行（空产品名）", idx + 1)
                    continue
                product_name = str(raw_name).strip()

                product_data: dict[str, Any] = {
                    "owner": self._parse_scalar(row.get("owner")) or "未指定",
                    "product_name": product_name,
                    "model_number": str(row.get("model_number", "") or ""),
                    "color_spec": self._parse_scalar(row.get("color_spec")),
                    "collect_count": self._parse_collect_count(
                        row.get("collect_count")
                    ),
                    "spec_unit": self._parse_scalar(row.get("spec_unit")),
                    "spec_options": self._parse_json_list(row.get("spec_options")),
                    "image_files": self._parse_json_list(row.get("image_files")),
                    "size_chart_image_url": self._parse_scalar(
                        row.get("size_chart_image_url")
                    )
                    or "",
                    "product_video_url": self._parse_scalar(
                        row.get("product_video_url")
                    ),
                }

                cost_price, variant_costs = self._parse_costs(
                    row.get("cost_price")
                )
                product_data["cost_price"] = cost_price
                product_data["variant_costs"] = variant_costs
                product_data["sku_image_urls"] = self._build_product_image_urls(
                    product_data["image_files"]
                )

                product = ProductSelectionRow(**product_data)
                products.append(product)
                logger.debug(
                    "解析第 {} 行成功: {} ({})", idx + 1, product.product_name, product.model_number
                )
            except Exception as exc:  # noqa: BLE001
                error_msg = f"第 {idx + 1} 行数据错误: {exc}"
                errors.append(error_msg)
                logger.warning("⚠️ {}", error_msg)
                continue

        if errors:
            logger.warning("⚠️ {} 行数据存在问题，已跳过", len(errors))
            for err in errors[:5]:
                logger.warning("  - {}", err)
            if len(errors) > 5:
                logger.warning("  ... 还有 {} 个错误未展示", len(errors) - 5)

        return products

    @staticmethod
    def _is_missing(value: object) -> bool:
        """判断值是否为空或无效。

        Args:
            value: 原始值。

        Returns:
            True 表示应视为缺失。
        """

        if value is None:
            return True
        if isinstance(value, float) and pd.isna(value):
            return True
        if isinstance(value, str):
            text = value.strip()
            return not text or text.lower() == "nan"
        return False

    def validate_row(self, row: dict[str, Any]) -> tuple[bool, str | None]:
        """校验单行数据是否满足最小要求。

        Args:
            row: 行数据字典。

        Returns:
            (是否有效, 错误信息)。
        """

        if not row.get("product_name"):
            return False, "缺少产品名称"
        if not row.get("model_number"):
            return False, "缺少型号编号"

        model = str(row.get("model_number")).strip()
        if not (model.startswith("A") and len(model) == 5 and model[1:].isdigit()):
            return False, f"型号编号格式错误: {model}，应为A0001-A9999"

        return True, None

    def create_sample_excel(self, output_path: str, num_samples: int = 3) -> None:
        """创建示例选品表，便于调试或演示。

        Args:
            output_path: 生成文件的保存路径。
            num_samples: 需要输出的示例行数。

        Examples:
            >>> SelectionTableReader().create_sample_excel("sample.xlsx", num_samples=2)
        """

        logger.info("创建示例选品表: {}", output_path)
        sample_data = [
            {
                "主品负责人": "张三",
                "产品名称": "药箱收纳盒",
                "标题后缀": "A0049",
                "产品颜色/规格": "白色/大号",
                "采集数量": 5,
                "进货价": 18.5,
                "尺码图链接": "https://example.com/images/sample-size-chart-1.jpg",
            },
            {
                "主品负责人": "李四",
                "产品名称": "智能手表运动防水",
                "标题后缀": "A0050",
                "产品颜色/规格": "黑色/标准版",
                "采集数量": 5,
                "进货价": 129.0,
                "尺码图链接": "https://example.com/images/sample-size-chart-2.jpg",
            },
            {
                "主品负责人": "王五",
                "产品名称": "便携洗衣机迷你款",
                "标题后缀": "A0051",
                "产品颜色/规格": "蓝色/家用",
                "采集数量": 5,
                "进货价": 299.0,
                "尺码图链接": "https://example.com/images/sample-size-chart-3.jpg",
            },
        ]

        data = sample_data[:num_samples]
        df = pd.DataFrame(data)
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        df.to_excel(output, index=False, engine="openpyxl")

        logger.success("示例选品表已创建: {}", output)
        logger.info("  包含 {} 个示例产品", len(data))

    def _parse_collect_count(self, value: object) -> int:
        """解析采集数量，落地为 1-100 的整数。

        Args:
            value: 原始数量值。

        Returns:
            处理后的数量，默认回退到 5。
        """
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return 5
        try:
            count = int(float(str(value)))
            return max(1, min(count, 100))
        except (TypeError, ValueError):
            return 5

    @staticmethod
    def _parse_scalar(value: object) -> str | None:
        """解析标量文本，空值返回 None。

        Args:
            value: 原始值。

        Returns:
            去除空白的字符串或 None。
        """
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _parse_json_list(value: object) -> list[str] | None:
        """解析列表字段，支持 JSON 字符串或逗号分隔文本。

        Args:
            value: 原始值。

        Returns:
            清洗后的字符串列表，若无法解析则返回 None。
        """
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
        """解析成本价字段，支持单价或列表。

        Args:
            value: 原始成本值。

        Returns:
            (单一成本价, 多规格成本列表)。
        """
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

    def _build_product_image_urls(
        self, image_files: list[str] | None
    ) -> list[str]:
        """根据实拍图文件名构建 SKU 图 URL 列表。

        Args:
            image_files: 实拍图文件名或 URL 列表。

        Returns:
            补全后的 URL 列表；若入参为空则返回空列表。
        """
        if not image_files:
            return []

        urls: list[str] = []
        for item in image_files:
            text = (item or "").strip()
            if not text:
                continue
            if text.startswith(("http://", "https://")):
                urls.append(text)
            elif self.product_image_base_url:
                url = urljoin(
                    f"{self.product_image_base_url.rstrip('/')}/", text.lstrip("/")
                )
                urls.append(url)
        return urls

    def _resolve_product_image_base_url(self) -> str | None:
        """解析环境变量中的图片前缀 URL。"""
        base_url = os.getenv("PRODUCT_IMAGE_BASE_URL", "")
        text = str(base_url).strip()
        return text or None

    @staticmethod
    def _build_column_mapping() -> dict[str, str]:
        """构建列名映射，覆盖常见的中英文别名。

        Returns:
            列名映射字典。
        """

        return {
            # 负责人
            "主品负责人": "owner",
            "负责人": "owner",
            "owner": "owner",
            # 产品名称
            "产品名称": "product_name",
            "商品名称": "product_name",
            "名称": "product_name",
            "product_name": "product_name",
            # 型号
            "标题后缀": "model_number",
            "型号": "model_number",
            "型号编号": "model_number",
            "款号": "model_number",
            "model_number": "model_number",
            # 规格/颜色
            "产品颜色/规格": "color_spec",
            "颜色规格": "color_spec",
            "规格": "color_spec",
            "color_spec": "color_spec",
            # 数量
            "采集数量": "collect_count",
            "数量": "collect_count",
            "collect_count": "collect_count",
            # 价格
            "进货价": "cost_price",
            "成本价": "cost_price",
            "价格": "cost_price",
            "cost_price": "cost_price",
            # 规格选项
            "规格数组": "spec_options",
            "规格数租": "spec_options",
            "规格数": "spec_options",
            "spec_options": "spec_options",
            # 规格单位
            "规格单位": "spec_unit",
            "spec_unit": "spec_unit",
            # 实拍图/媒体
            "实拍图数组": "image_files",
            "sku实拍图数组": "image_files",
            "SKU实拍图数组": "image_files",
            "image_files": "image_files",
            # 尺码图
            "尺码图": "size_chart_image_url",
            "尺码图链接": "size_chart_image_url",
            "尺码图URL": "size_chart_image_url",
            "尺寸图链接": "size_chart_image_url",
            "尺寸图URL": "size_chart_image_url",
            "size_chart_url": "size_chart_image_url",
            "size_chart_image_url": "size_chart_image_url",
            # 视频
            "视频链接": "product_video_url",
            "视频URL": "product_video_url",
            "video_url": "product_video_url",
            "product_video_url": "product_video_url",
        }
