"""
@PURPOSE: 通用重试工具模块，提供带指数退避的重试机制
@OUTLINE:
  - async def retry_with_validation(): 带验证的重试机制
  - def validate_sku_fields(): 验证 SKU 字段（重量、分类等）是否正确设置
@DEPENDENCIES:
  - 外部: asyncio
@RELATED: first_edit_api.py, batch_edit_api.py
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from loguru import logger


async def retry_with_backoff[T](
    func: Callable[[], Awaitable[T]],
    *,
    max_retries: int = 3,
    initial_delay: float = 2.0,
    backoff_factor: float = 1.5,
    operation_name: str = "操作",
    on_retry: Callable[[int, Exception | None, str | None], None] | None = None,
) -> T:
    """带指数退避的重试机制.

    Args:
        func: 要执行的异步函数
        max_retries: 最大重试次数
        initial_delay: 初始重试延迟（秒）
        backoff_factor: 退避因子
        operation_name: 操作名称（用于日志）
        on_retry: 重试时的回调函数 (attempt, exception, message)

    Returns:
        函数执行结果

    Raises:
        最后一次执行的异常

    Examples:
        >>> async def save_product():
        ...     return await api.save(product)
        >>> result = await retry_with_backoff(
        ...     save_product,
        ...     max_retries=3,
        ...     operation_name="保存产品"
        ... )
    """
    last_exception: Exception | None = None
    delay = initial_delay

    for attempt in range(1, max_retries + 1):
        try:
            result = await func()
            if attempt > 1:
                logger.success(f"{operation_name}在第 {attempt} 次尝试时成功")
            return result
        except Exception as e:
            last_exception = e
            if attempt < max_retries:
                logger.warning(f"{operation_name}失败 (尝试 {attempt}/{max_retries}): {e}")
                if on_retry:
                    on_retry(attempt, e, str(e))
                logger.info(f"等待 {delay:.1f} 秒后重试...")
                await asyncio.sleep(delay)
                delay *= backoff_factor
            else:
                logger.error(f"{operation_name}最终失败，已重试 {max_retries} 次: {e}")

    if last_exception:
        raise last_exception
    raise RuntimeError(f"{operation_name}失败，但没有捕获到异常")


def validate_sku_fields(sku_data: dict[str, Any]) -> tuple[bool, list[str]]:
    """验证 SKU 字段是否正确设置.

    检查重量、SKU 分类、尺寸等必要字段。

    Args:
        sku_data: SKU 数据字典

    Returns:
        (是否有效, 错误信息列表)

    Examples:
        >>> valid, errors = validate_sku_fields(sku)
        >>> if not valid:
        ...     logger.warning(f"SKU 字段验证失败: {errors}")
    """
    errors: list[str] = []

    # 检查重量
    weight = sku_data.get("weight")
    if not weight:
        errors.append("重量(weight)未设置")
    else:
        try:
            weight_val = float(weight)
            if weight_val <= 0:
                errors.append(f"重量(weight)必须大于0: {weight}")
        except (ValueError, TypeError):
            errors.append(f"重量(weight)格式无效: {weight}")

    # 检查 SKU 分类
    sku_classification = sku_data.get("skuClassification")
    if sku_classification is None:
        errors.append("SKU分类(skuClassification)未设置")

    # 检查件数
    number_of_pieces = sku_data.get("numberOfPieces")
    if not number_of_pieces:
        errors.append("件数(numberOfPieces)未设置")

    # 检查件单位
    piece_unit_code = sku_data.get("pieceUnitCode")
    if piece_unit_code is None:
        errors.append("件单位(pieceUnitCode)未设置")

    # 检查尺寸
    length = sku_data.get("packageLength")
    width = sku_data.get("packageWidth")
    height = sku_data.get("packageHeight")

    if not all([length, width, height]):
        missing = []
        if not length:
            missing.append("长(packageLength)")
        if not width:
            missing.append("宽(packageWidth)")
        if not height:
            missing.append("高(packageHeight)")
        errors.append(f"尺寸未设置: {', '.join(missing)}")

    return len(errors) == 0, errors


def ensure_sku_fields(sku_data: dict[str, Any], *, weight_g: int = 9527) -> dict[str, Any]:
    """确保 SKU 字段正确设置，缺失字段使用默认值.

    这是一个幂等操作，可以多次调用。

    Args:
        sku_data: SKU 数据字典（会被修改）
        weight_g: 默认重量（克）

    Returns:
        修改后的 SKU 数据字典

    Examples:
        >>> sku = ensure_sku_fields(sku, weight_g=9527)
    """
    import random

    # 确保重量设置
    if not sku_data.get("weight"):
        sku_data["weight"] = str(weight_g)
        logger.debug(f"设置默认重量: {weight_g}g")

    # 确保 SKU 分类设置（单品 1 件）
    if sku_data.get("skuClassification") is None:
        sku_data["skuClassification"] = 1  # 单品
        logger.debug("设置默认 SKU 分类: 单品")

    if not sku_data.get("numberOfPieces"):
        sku_data["numberOfPieces"] = "1"
        logger.debug("设置默认件数: 1")

    if sku_data.get("pieceUnitCode") is None:
        sku_data["pieceUnitCode"] = 1  # 件
        logger.debug("设置默认件单位: 件")

    # 确保尺寸设置（50-99cm，长>宽>高）
    if not all(
        [
            sku_data.get("packageLength"),
            sku_data.get("packageWidth"),
            sku_data.get("packageHeight"),
        ]
    ):
        dimensions = [random.randint(50, 99) for _ in range(3)]
        dimensions.sort(reverse=True)
        sku_data["packageLength"] = str(dimensions[0])
        sku_data["packageWidth"] = str(dimensions[1])
        sku_data["packageHeight"] = str(dimensions[2])
        logger.debug(f"设置默认尺寸: {dimensions[0]}x{dimensions[1]}x{dimensions[2]}cm")

    return sku_data


def validate_product_detail(detail: dict[str, Any]) -> tuple[bool, list[str]]:
    """验证产品详情中的关键字段.

    Args:
        detail: 产品详情字典

    Returns:
        (是否有效, 错误信息列表)
    """
    errors: list[str] = []

    # 检查顶层重量
    weight = detail.get("weight")
    if not weight:
        errors.append("顶层重量(weight)未设置")

    # 检查 skuMap 中的每个 SKU
    sku_map = detail.get("skuMap", {})
    if isinstance(sku_map, dict):
        for sku_key, sku_data in sku_map.items():
            if isinstance(sku_data, dict):
                valid, sku_errors = validate_sku_fields(sku_data)
                if not valid:
                    errors.extend([f"SKU[{sku_key[:20]}...]: {e}" for e in sku_errors])

    return len(errors) == 0, errors


def ensure_product_detail_fields(
    detail: dict[str, Any],
    *,
    weight_g: int = 9527,
) -> dict[str, Any]:
    """确保产品详情中的关键字段正确设置.

    Args:
        detail: 产品详情字典（会被修改）
        weight_g: 默认重量（克）

    Returns:
        修改后的产品详情字典
    """
    import random

    # 确保顶层重量
    if not detail.get("weight"):
        detail["weight"] = str(weight_g)

    # 确保顶层尺寸
    if not all(
        [
            detail.get("packageLength"),
            detail.get("packageWidth"),
            detail.get("packageHeight"),
        ]
    ):
        dimensions = [random.randint(50, 99) for _ in range(3)]
        dimensions.sort(reverse=True)
        detail["packageLength"] = str(dimensions[0])
        detail["packageWidth"] = str(dimensions[1])
        detail["packageHeight"] = str(dimensions[2])

    # 确保每个 SKU 的字段
    sku_map = detail.get("skuMap", {})
    if isinstance(sku_map, dict):
        for sku_data in sku_map.values():
            if isinstance(sku_data, dict):
                ensure_sku_fields(sku_data, weight_g=weight_g)

    return detail
