"""
@PURPOSE: 提供滚动查找元素的工具函数，用于处理商品列表中元素不在可视区域的情况
@OUTLINE:
  - PRODUCT_ROW_HEIGHT: 商品行高度常量（125px）
  - async def scroll_to_top(): 滚动到容器顶部
  - async def scroll_to_product_position(): 精确滚动到指定商品位置
  - async def scroll_container(): 滚动容器指定距离
  - async def scroll_to_find_element(): 滚动查找指定索引的元素（兼容旧逻辑）
  - async def is_at_scroll_bottom(): 检测是否到达滚动底部
@GOTCHAS:
  - 商品列表可能使用虚拟滚动，滚动时DOM会动态更新
  - 需要在滚动后等待DOM更新
  - 商品行高度固定为 125px，可通过精确计算滚动距离
@DEPENDENCIES:
  - 外部: playwright
"""

from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING, Callable, Awaitable

from loguru import logger

if TYPE_CHECKING:
    from playwright.async_api import Locator, Page


# 商品行高度（像素）- 用于精确滚动计算
PRODUCT_ROW_HEIGHT = 125

# 默认商品列表容器选择器（按优先级排序）
DEFAULT_CONTAINER_SELECTORS = (
    "#appScrollContainer",
    ".pro-virtual-table__body-inner",
    ".jx-table__body-wrapper",
    ".product-list-container",
    ".collect-box-list",
    "table tbody",
    ".el-table__body-wrapper",
)


async def scroll_to_top(
    page: "Page",
    container_selectors: tuple[str, ...] | None = None,
) -> bool:
    """
    滚动到容器顶部。

    Args:
        page: Playwright 页面对象
        container_selectors: 容器选择器列表

    Returns:
        是否成功滚动到顶部
    """
    selectors = container_selectors or DEFAULT_CONTAINER_SELECTORS

    for selector in selectors:
        try:
            container = page.locator(selector).first
            if await container.count() == 0:
                continue

            await container.evaluate("el => el.scrollTop = 0")
            logger.debug(f"已滚动到容器顶部: {selector}")
            return True
        except Exception as exc:
            logger.debug(f"滚动到顶部失败 {selector}: {exc}")
            continue

    # 回退：滚动整个页面到顶部
    try:
        await page.evaluate("window.scrollTo(0, 0)")
        logger.debug("回退滚动页面到顶部")
        return True
    except Exception as exc:
        logger.warning(f"页面滚动到顶部失败: {exc}")
        return False


async def scroll_to_product_position(
    page: "Page",
    target_index: int,
    *,
    row_height: int = PRODUCT_ROW_HEIGHT,
    container_selectors: tuple[str, ...] | None = None,
    wait_after_scroll_ms: int = 300,
) -> bool:
    """
    精确滚动到指定商品位置。

    根据商品索引和行高度，计算精确的滚动距离，直接滚动到目标位置。
    比循环查找更高效。

    Args:
        page: Playwright 页面对象
        target_index: 目标商品索引（0-based）
        row_height: 每行商品高度（像素），默认 125px
        container_selectors: 容器选择器列表
        wait_after_scroll_ms: 滚动后等待时间（毫秒）

    Returns:
        是否成功滚动到目标位置

    Examples:
        >>> # 滚动到第 6 个商品（索引 5）
        >>> await scroll_to_product_position(page, target_index=5)
        >>> # 滚动距离 = 5 × 125 = 625px
    """
    if target_index < 0:
        logger.warning(f"无效的目标索引: {target_index}")
        return False

    scroll_distance = target_index * row_height
    logger.info(
        f"精确滚动到商品 #{target_index + 1}，滚动距离: {scroll_distance}px "
        f"(索引={target_index}, 行高={row_height}px)"
    )

    # 先滚动到顶部，确保从头开始计算
    await scroll_to_top(page, container_selectors)
    await page.wait_for_timeout(100)

    # 滚动到目标位置
    if scroll_distance > 0:
        success = await scroll_container(page, scroll_distance, container_selectors)
        if not success:
            return False

    # 等待渲染
    await page.wait_for_timeout(wait_after_scroll_ms)
    return True


async def scroll_one_product(
    page: "Page",
    *,
    row_height: int = PRODUCT_ROW_HEIGHT,
    container_selectors: tuple[str, ...] | None = None,
    wait_after_scroll_ms: int = 200,
) -> bool:
    """
    向下滚动一个商品的高度。

    用于编辑完一个商品后，滚动到下一个商品。

    Args:
        page: Playwright 页面对象
        row_height: 每行商品高度（像素），默认 125px
        container_selectors: 容器选择器列表
        wait_after_scroll_ms: 滚动后等待时间（毫秒）

    Returns:
        是否成功滚动
    """
    logger.debug(f"滚动到下一个商品，距离: {row_height}px")
    success = await scroll_container(page, row_height, container_selectors)
    if success:
        await page.wait_for_timeout(wait_after_scroll_ms)
    return success


async def scroll_container(
    page: "Page",
    distance: int = 300,
    container_selectors: tuple[str, ...] | None = None,
) -> bool:
    """
    滚动商品列表容器。

    Args:
        page: Playwright 页面对象
        distance: 滚动距离（像素），正数向下滚动
        container_selectors: 容器选择器列表，None 则使用默认值

    Returns:
        是否成功滚动
    """
    selectors = container_selectors or DEFAULT_CONTAINER_SELECTORS

    for selector in selectors:
        try:
            container = page.locator(selector).first
            if await container.count() == 0:
                continue

            # 检查是否可滚动
            is_scrollable = await container.evaluate(
                "el => el.scrollHeight > el.clientHeight"
            )
            if not is_scrollable:
                continue

            # 执行滚动
            await container.evaluate(f"el => el.scrollTop += {distance}")
            logger.debug(f"已滚动容器 {selector}，距离 {distance}px")
            return True
        except Exception as exc:
            logger.debug(f"滚动容器 {selector} 失败: {exc}")
            continue

    # 回退：滚动整个页面
    try:
        await page.mouse.wheel(0, distance)
        logger.debug(f"回退滚动页面，距离 {distance}px")
        return True
    except Exception as exc:
        logger.warning(f"页面滚动失败: {exc}")
        return False


async def is_at_scroll_bottom(
    page: "Page",
    container_selectors: tuple[str, ...] | None = None,
    threshold: int = 20,
) -> bool:
    """
    检测是否已滚动到容器底部。

    Args:
        page: Playwright 页面对象
        container_selectors: 容器选择器列表
        threshold: 判断到底部的阈值（像素）

    Returns:
        是否到达底部
    """
    selectors = container_selectors or DEFAULT_CONTAINER_SELECTORS

    for selector in selectors:
        try:
            container = page.locator(selector).first
            if await container.count() == 0:
                continue

            at_bottom = await container.evaluate(
                f"el => el.scrollTop + el.clientHeight >= el.scrollHeight - {threshold}"
            )
            if at_bottom:
                return True
            return False
        except Exception:
            continue

    # 回退：检查页面滚动
    try:
        at_bottom = await page.evaluate(
            f"() => window.innerHeight + window.scrollY >= document.body.scrollHeight - {threshold}"
        )
        return at_bottom
    except Exception:
        return False


async def scroll_to_find_element(
    page: "Page",
    locator_factory: Callable[[], "Locator"],
    target_index: int,
    *,
    max_scroll_attempts: int = 15,
    scroll_distance: int = 300,
    wait_after_scroll_ms: int = 500,
    container_selectors: tuple[str, ...] | None = None,
) -> "Locator | None":
    """
    滚动查找指定索引的元素。

    当目标元素不在当前可视区域时，通过滚动容器来加载更多元素，
    直到找到目标索引的元素或到达底部。

    Args:
        page: Playwright 页面对象
        locator_factory: 返回元素定位器的工厂函数（无参数）
        target_index: 目标元素的索引（0-based）
        max_scroll_attempts: 最大滚动尝试次数
        scroll_distance: 每次滚动距离（像素）
        wait_after_scroll_ms: 滚动后等待时间（毫秒）
        container_selectors: 容器选择器列表

    Returns:
        找到的元素定位器，未找到返回 None

    Examples:
        >>> locator = await scroll_to_find_element(
        ...     page,
        ...     lambda: page.locator(".product-row"),
        ...     target_index=15,
        ... )
        >>> if locator:
        ...     await locator.click()
    """
    logger.debug(f"开始滚动查找元素，目标索引: {target_index}")

    for attempt in range(max_scroll_attempts):
        # 1. 获取当前可见的元素
        locator = locator_factory()
        try:
            count = await locator.count()
        except Exception as exc:
            logger.debug(f"获取元素数量失败: {exc}")
            count = 0

        logger.debug(f"第 {attempt + 1} 次尝试，当前元素数量: {count}，目标索引: {target_index}")

        # 2. 检查是否已经有足够的元素
        if count > target_index:
            target_element = locator.nth(target_index)

            # 检查元素是否可见
            try:
                is_visible = await target_element.is_visible()
                if is_visible:
                    # 滚动到元素位置确保可交互
                    with suppress(Exception):
                        await target_element.scroll_into_view_if_needed()
                    logger.success(f"✓ 找到目标元素，索引: {target_index}")
                    return target_element
            except Exception:
                pass

            # 元素存在但不可见，尝试滚动到它
            try:
                await target_element.scroll_into_view_if_needed()
                await page.wait_for_timeout(200)
                if await target_element.is_visible():
                    logger.success(f"✓ 滚动后找到目标元素，索引: {target_index}")
                    return target_element
            except Exception as exc:
                logger.debug(f"滚动到元素失败: {exc}")

        # 3. 检查是否已到达底部
        if await is_at_scroll_bottom(page, container_selectors):
            logger.warning(f"已滚动到底部，未找到索引 {target_index} 的元素（当前数量: {count}）")
            return None

        # 4. 向下滚动
        scrolled = await scroll_container(page, scroll_distance, container_selectors)
        if not scrolled:
            logger.warning("无法继续滚动")
            break

        # 5. 等待新内容加载
        await page.wait_for_timeout(wait_after_scroll_ms)

    logger.warning(f"达到最大滚动次数 {max_scroll_attempts}，未找到索引 {target_index} 的元素")
    return None


async def scroll_to_find_and_click(
    page: "Page",
    locator_factory: Callable[[], "Locator"],
    target_index: int,
    *,
    click_timeout_ms: int = 3000,
    **scroll_kwargs,
) -> bool:
    """
    滚动查找并点击指定索引的元素。

    Args:
        page: Playwright 页面对象
        locator_factory: 返回元素定位器的工厂函数
        target_index: 目标元素的索引（0-based）
        click_timeout_ms: 点击超时时间（毫秒）
        **scroll_kwargs: 传递给 scroll_to_find_element 的其他参数

    Returns:
        是否成功点击
    """
    element = await scroll_to_find_element(
        page, locator_factory, target_index, **scroll_kwargs
    )

    if element is None:
        return False

    try:
        await element.click(timeout=click_timeout_ms)
        logger.success(f"✓ 成功点击索引 {target_index} 的元素")
        return True
    except Exception as exc:
        logger.error(f"点击元素失败: {exc}")
        return False

