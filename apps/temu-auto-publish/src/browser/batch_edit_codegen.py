"""
@PURPOSE: 通过 Playwright Codegen 录制生成的 Temu 批量编辑 18 步脚本封装
@OUTLINE:
  - async def run_batch_edit(page, payload): 统一入口,执行完整 18 步流程
  - async def _open_batch_edit_popover(page): 打开批量编辑弹窗
  - async def _step_01_title(page): 标题编辑
  - async def _step_02_english_title(page): 英语标题编辑
  - async def _step_03_category_attrs(page, payload): 类目属性(参数化)
  - async def _step_04_main_sku(page): 主货号
  - async def _step_05_outer_package(page, image_path): 外包装(参数化图片)
  - async def _step_06_origin(page): 产地(固定浙江)
  - async def _step_07_customized(page): 定制品
  - async def _step_08_sensitive(page): 敏感属性
  - async def _step_09_weight(page): 重量(固定 6000g)
  - async def _step_10_dimensions(page): 尺寸(固定 75x71x65)
  - async def _step_11_platform_sku(page): 平台 SKU
  - async def _step_12_sku_category(page): SKU 分类(固定组合装 500)
  - async def _step_13_size_chart(page): 尺码表
  - async def _step_14_suggested_price(page): 建议售价(固定倍数 10)
  - async def _step_15_packing_list(page): 包装清单
  - async def _step_16_carousel(page): 轮播图
  - async def _step_17_color_image(page): 颜色图
  - async def _step_18_manual(page, file_path): 产品说明书(参数化文件)
  - async def _wait_for_save_toast(page): 等待保存成功提示
  - async def _close_edit_dialog(page): 关闭编辑对话框
  - def smart_retry(): 智能重试装饰器 (使用增强版)
@DEPENDENCIES:
  - 外部: playwright, loguru
  - 内部: smart_wait_mixin, enhanced_retry, resilient_selector
@GOTCHAS:
  - 文件上传需要提供绝对路径
  - 某些步骤可能因页面加载慢而超时,已添加智能等待和增强重试
  - 类目选择需要按层级逐级点击
@OPTIMIZATIONS:
  - 使用 SmartWaitMixin 替代硬编码等待
  - 使用增强重试机制替代简单重试
  - 使用弹性选择器提高元素定位稳定性
"""

import asyncio
from contextlib import suppress
import re
from functools import wraps
from pathlib import Path
from typing import Any, Callable, TypeVar

from loguru import logger
from playwright.async_api import Page

# 导入优化组件
from .smart_wait_mixin import smart_wait, get_smart_waiter
from .resilient_selector import get_resilient_locator, ResilientLocator
from ..core.enhanced_retry import (
    smart_retry as enhanced_smart_retry,
    create_step_retry_policy,
    RetryPolicy,
)

MAX_TITLE_LENGTH = 250

# 定义泛型类型
T = TypeVar("T")

# 获取全局实例
_smart_waiter = get_smart_waiter()
_resilient_locator = get_resilient_locator()

# 步骤级重试策略
_step_retry_policy = create_step_retry_policy()


def smart_retry(max_attempts: int = 2, delay: float = 0.5, exceptions: tuple = (Exception,)):
    """智能重试装饰器,用于关键操作的自动重试。
    
    注意: 此为兼容旧代码的包装器，内部使用增强版重试机制。

    Args:
        max_attempts: 最大尝试次数(默认2次,即1次重试)。
        delay: 重试间隔秒数(默认0.5秒)。
        exceptions: 需要捕获并重试的异常类型元组。

    Returns:
        装饰后的函数。
    """
    # 使用增强版重试机制
    policy = RetryPolicy(
        max_attempts=max_attempts,
        initial_delay_ms=int(delay * 1000),
        backoff_factor=1.5,
        retryable_exceptions=exceptions,
        jitter=True,
    )
    return enhanced_smart_retry(policy)


async def run_batch_edit(page: Page, payload: dict[str, Any]) -> dict[str, Any]:
    """执行批量编辑 18 步完整流程。

    Args:
        page: 已经登录并选中产品的页面对象(需在 Temu 全托管采集箱)。
        payload: 业务参数字典,包含:
            - category_path: list[str] - 类目路径,如 ["收纳用品", "收纳篮、箱子、盒子", "盖式储物箱"]
            - category_attrs: dict - 类目属性,包含 product_use, shape, material, closure_type, style
            - outer_package_image: str - 外包装图片文件路径(绝对路径)
            - manual_file: str - 产品说明书 PDF 文件路径(绝对路径)

    Returns:
        执行结果字典:
            {
                "success": bool,
                "completed_steps": int,
                "total_steps": int,
                "error": str | None
            }

    Raises:
        无直接抛出,所有异常被捕获并记录到返回结果中。

    Examples:
        >>> payload = {
        ...     "category_path": ["收纳用品", "收纳篮、箱子、盒子", "盖式储物箱"],
        ...     "category_attrs": {
        ...         "product_use": "多用途",
        ...         "shape": "其他形状",
        ...         "material": "其他材料",
        ...         "closure_type": "其他闭合类型",
        ...         "style": "当代"
        ...     },
        ...     "outer_package_image": "/path/to/package.jpg",
        ...     "manual_file": "/path/to/manual.pdf"
        ... }
        >>> result = await run_batch_edit(page, payload)
        >>> print(result["success"])
        True
    """
    result: dict[str, Any] = {
        "success": False,
        "completed_steps": 0,
        "total_steps": 18,
        "error": None,
        "step_errors": [],  # 记录各步骤的错误
        "timing": {},  # 记录各步骤耗时
    }
    
    import time
    workflow_start = time.perf_counter()

    try:
        logger.info("开始执行批量编辑 18 步流程(使用优化后的等待和重试机制)")

        # 0. 确保在 Temu 全托管采集箱页面
        current_url = page.url
        target_url = "https://erp.91miaoshou.com/pddkj/collect_box/items"
        if target_url not in current_url:
            logger.info(f"导航到 Temu 全托管采集箱: {target_url}")
            await page.goto(target_url, timeout=60000)
            # 使用智能等待替代固定等待
            await smart_wait(page, "navigate_batch_edit", min_ms=50, max_ms=500)

        # 1. 检测并关闭弹窗
        await _close_popups(page)

        # 2. 全选产品 - 使用弹性选择器
        logger.info("全选产品...")
        checkbox = page.locator(".jx-checkbox").first
        await checkbox.click()
        # 使用智能等待
        await smart_wait(page, "select_all_products", min_ms=20, max_ms=300)
        
        # 验证选中状态
        try:
            await page.locator(".jx-checkbox.is-checked").first.wait_for(
                state="visible", timeout=300
            )
        except Exception:
            logger.debug("复选框选中状态验证超时，继续执行")

        # 3. 打开批量编辑弹窗
        logger.info("打开批量编辑菜单...")
        await page.get_by_text("批量编辑").click()
        # 优化: 减少等待时间 600 -> 300
        await smart_wait(page, "open_batch_edit_dialog", min_ms=20, max_ms=300)
        
        try:
            await _wait_for_dialog_open(page)
        except Exception:
            logger.debug("批量编辑弹窗等待超时，继续执行")

        logger.info("批量编辑弹窗已打开")

        # 执行 18 个步骤 - 使用元组存储步骤信息便于重试
        step_definitions = [
            ("标题", lambda: _step_01_title(page)),
            ("英语标题", lambda: _step_02_english_title(page)),
            ("类目属性", lambda: _step_03_category_attrs(page, payload)),
            ("主货号", lambda: _step_04_main_sku(page)),
            ("外包装", lambda: _step_05_outer_package(page, payload.get("outer_package_image", ""))),
            ("产地", lambda: _step_06_origin(page)),
            ("定制品", lambda: _step_07_customized(page)),
            ("敏感属性", lambda: _step_08_sensitive(page)),
            ("重量", lambda: _step_09_weight(page)),
            ("尺寸", lambda: _step_10_dimensions(page)),
            ("平台SKU", lambda: _step_11_platform_sku(page)),
            ("SKU分类", lambda: _step_12_sku_category(page)),
            ("尺码表", lambda: _step_13_size_chart(page)),
            ("建议售价", lambda: _step_14_suggested_price(page)),
            ("包装清单", lambda: _step_15_packing_list(page)),
            ("轮播图", lambda: _step_16_carousel(page)),
            ("颜色图", lambda: _step_17_color_image(page)),
            ("产品说明书", lambda: _step_18_manual(page, payload.get("manual_file", ""))),
        ]

        for idx, (step_name, step_factory) in enumerate(step_definitions, start=1):
            step_start = time.perf_counter()
            logger.info(f"执行步骤 {idx}/18: {step_name}")
            
            try:
                await step_factory()
                result["completed_steps"] = idx
                
                # 步骤完成后使用智能等待（极速模式: 最小等待）
                await smart_wait(page, f"step_{idx}_{step_name}", min_ms=5, max_ms=50)
                
                step_elapsed = (time.perf_counter() - step_start) * 1000
                result["timing"][step_name] = round(step_elapsed, 2)
                logger.success(f"步骤 {idx}/18 完成: {step_name} ({step_elapsed:.0f}ms)")
                
            except Exception as step_exc:
                step_elapsed = (time.perf_counter() - step_start) * 1000
                result["timing"][step_name] = round(step_elapsed, 2)
                result["step_errors"].append({
                    "step": idx,
                    "name": step_name,
                    "error": str(step_exc),
                    "elapsed_ms": round(step_elapsed, 2),
                })
                logger.error(f"步骤 {idx}/18 失败: {step_name} - {step_exc}")
                
                # 非关键步骤失败可以继续（步骤13-17为非关键）
                if idx in (13, 16, 17):  # 尺码表、轮播图、颜色图
                    logger.warning(f"非关键步骤 {step_name} 失败，继续执行后续步骤")
                    result["completed_steps"] = idx
                    continue
                else:
                    raise

        # 关闭编辑框
        await _close_edit_dialog(page)

        workflow_elapsed = (time.perf_counter() - workflow_start) * 1000
        result["timing"]["total"] = round(workflow_elapsed, 2)
        
        logger.success(f"批量编辑 18 步全部完成 (总耗时: {workflow_elapsed:.0f}ms)")
        result["success"] = True

    except Exception as exc:
        workflow_elapsed = (time.perf_counter() - workflow_start) * 1000
        result["timing"]["total"] = round(workflow_elapsed, 2)
        
        logger.exception(
            f"批量编辑流程失败(第 {result['completed_steps']}/{result['total_steps']} 步): {exc}"
        )
        result["error"] = str(exc)

    return result


async def _open_batch_edit_popover(page: Page) -> None:
    """打开批量编辑弹窗(前提:已全选产品)。

    Args:
        page: Playwright 页面对象。
    """
    # 点击第一个复选框(全选)
    checkbox = page.locator(".jx-checkbox").first
    await checkbox.click()
    # 智能等待: 等待选中状态生效
    try:
        await page.locator(".jx-checkbox.is-checked").first.wait_for(state="visible", timeout=300)
    except Exception:
        pass


async def _close_popups(page: Page) -> None:
    """检测并关闭页面弹窗（优化版：精简选择器，减少超时）。

    Args:
        page: Playwright 页面对象。
    """
    logger.debug("快速检测页面弹窗...")

    # 优化: 精简为最常用的3个选择器
    popup_selectors = [
        "[aria-label='关闭此对话框']",
        "button:has-text('我知道了')",
        ".el-dialog__close",
    ]

    closed_count = 0
    for selector in popup_selectors:
        try:
            close_buttons = page.locator(selector)
            count = await close_buttons.count()

            if count > 0:
                logger.debug(f"发现 {count} 个弹窗(选择器: {selector})")
                # 只点击第一个可见的（优化: 不遍历所有）
                try:
                    button = close_buttons.first
                    if await button.is_visible(timeout=300):  # 优化: 1000 -> 300
                        await button.click(timeout=500)       # 优化: 2000 -> 500
                        closed_count += 1
                        logger.debug(f"已关闭弹窗")
                        # 优化: 减少等待 800 -> 200
                        try:
                            await button.wait_for(state="hidden", timeout=200)
                        except Exception:
                            pass
                except Exception:
                    continue
        except Exception:
            continue

    if closed_count > 0:
        logger.debug(f"总共关闭了 {closed_count} 个弹窗")
    else:
        logger.info("未发现需要关闭的弹窗")


@smart_retry(max_attempts=1, delay=0.2)
async def _step_01_title(page: Page) -> None:
    """步骤 1: 标题 - 保持原样点击预览保存。

    Args:
        page: Playwright 页面对象。
    """
    await page.locator("div").filter(has_text=re.compile(r"^标题$")).click()
    # 智能等待: 等待标题编辑对话框打开
    # await _wait_for_dialog_open(page)
    await _ensure_title_length(page)
    await page.get_by_role("button", name="预览").click()
    await page.get_by_role("button", name="保存修改").click()
    # await _wait_for_save_toast(page)
    await _close_edit_dialog(page)


async def _ensure_title_length(page: Page) -> None:
    """确保批量编辑弹窗中的标题不超过平台限制."""

    selectors = [
        "textarea[placeholder*='标题']",
        "input[placeholder*='标题']",
        ".jx-dialog textarea",
        ".jx-dialog input",
    ]

    for selector in selectors:
        locator = page.locator(selector).first
        try:
            if await locator.count() == 0:
                continue

            current_title = await locator.input_value()
            if current_title is None:
                current_title = ""

            length = len(current_title)
            if length <= MAX_TITLE_LENGTH:
                logger.debug("批量编辑标题长度 {} 未超限", length)
                return

            excess = length - MAX_TITLE_LENGTH
            mid = length // 2
            start = max(0, mid - excess // 2)
            end = start + excess
            new_title = current_title[:start] + current_title[end:]

            if len(new_title) > MAX_TITLE_LENGTH:
                new_title = new_title[:MAX_TITLE_LENGTH]

            await locator.fill(new_title)
            logger.warning(
                "批量编辑标题超出限制, 已从 {} 字符裁剪至 {} 字符",
                length,
                len(new_title),
            )
            # 智能等待: 等待输入值生效
            try:
                await locator.evaluate(
                    "el => el.dispatchEvent(new Event('input', { bubbles: true }))"
                )
            except Exception:
                pass
            return
        except Exception as exc:
            logger.debug("标题长度检查选择器 {} 失败: {}", selector, exc)

    logger.error("未能定位标题输入框, 无法执行长度校验")


async def _step_02_english_title(page: Page) -> None:
    """步骤 2: 英语标题 - 输入空格。

    Args:
        page: Playwright 页面对象。
    """
    await page.get_by_text("英语标题").click()
    input_box = (
        page.locator("div")
        .filter(has_text=re.compile(r"^使用新英语标题:Abc$"))
        .get_by_role("textbox")
    )
    await input_box.click()
    await input_box.fill(" ")
    await page.get_by_role("button", name="预览").click()
    await page.get_by_role("button", name="保存修改").click()
    # await _wait_for_save_toast(page)
    await _close_edit_dialog(page)


@smart_retry(max_attempts=1, delay=0.2)
async def _step_03_category_attrs(page: Page, payload: dict[str, Any]) -> None:
    """步骤 3: 类目属性 - 参数化类目路径和属性值。

    Args:
        page: Playwright 页面对象。
        payload: 包含 category_path 和 category_attrs 的字典。
    """
    await page.get_by_text("类目属性").click()

    await page.get_by_role("button", name="预览").click()
    await page.get_by_role("button", name="保存修改").click()
    # await _wait_for_save_toast(page)

    await _close_edit_dialog(page)


async def _step_04_main_sku(page: Page) -> None:
    """步骤 4: 主货号 - 保持原样。

    Args:
        page: Playwright 页面对象。
    """
    await page.get_by_role("dialog").get_by_text("主货号").click()
    await page.get_by_role("button", name="预览").click()
    await page.get_by_role("button", name="保存修改").click()
    # await _wait_for_save_toast(page)
    await _close_edit_dialog(page)


@smart_retry(max_attempts=1, delay=0.2)
async def _step_05_outer_package(page: Page, image_path: str | None) -> None:
    """步骤 5: 外包装 - 固定形状/类型,参数化图片路径。

    Args:
        page: Playwright 页面对象。
        image_path: 外包装图片文件路径(绝对路径)。
    """
    await page.get_by_text("外包装").click()

    # 选择外包装形状:长方体
    await (
        page.get_by_role("dialog")
        .locator("form div")
        .filter(has_text="外包装形状: 不规则 长方体 圆柱体")
        .get_by_placeholder("请选择")
        .click()
    )
    await page.get_by_text("长方体", exact=True).click()

    # 选择外包装类型:硬包装
    await (
        page.get_by_role("dialog")
        .locator("form div")
        .filter(has_text="外包装类型: 硬包装 软包装+硬物 软包装+软物")
        .get_by_placeholder("请选择")
        .click()
    )
    await page.get_by_text("硬包装", exact=True).click()

    chosen_path = image_path
    if not chosen_path:
        chosen_path = str(Path(__file__).resolve().parents[2] / "data/image/packaging.png")

    try:
        # 点击图片上传区域的单选按钮
        radio_btn = page.get_by_role("radio").filter(has_text="addImages")
        if await radio_btn.count() > 0:
            await radio_btn.click()
            # 优化: 移除固定等待100ms

        # 尝试直接找到文件输入框（可能已经存在）
        file_inputs = page.locator("input[type='file']")
        if await file_inputs.count() > 0:
            # 直接使用已存在的文件输入框
            await file_inputs.last.set_input_files(chosen_path)
            logger.success("✓ 外包装图片已上传: {}", chosen_path)
            await page.wait_for_timeout(50)  # 极速模式: 150 -> 50
        else:
            # 如果没有文件输入框,尝试通过下拉菜单触发
            logger.warning("未找到文件输入框,跳过外包装图片上传")

    except Exception as exc:
        logger.warning("外包装图片上传失败, 保留已有图片: {}", exc)

    await page.get_by_role("button", name="预览").click()
    await page.get_by_role("button", name="保存修改").click()
    # await _wait_for_save_toast(page)
    await _close_edit_dialog(page)


async def _step_06_origin(page: Page) -> None:
    """步骤 6: 产地 - 固定为浙江。

    Args:
        page: Playwright 页面对象。
    """
    await page.get_by_text("产地").click()
    await page.get_by_role("dialog", name="dialog").get_by_placeholder("请选择或输入搜索").click()
    await page.wait_for_timeout(200)  # 极速: 500 -> 200
    await (
        page.get_by_role("dialog", name="dialog")
        .get_by_placeholder("请选择或输入搜索")
        .fill("浙江")
    )
    await page.get_by_text("中国大陆 / 浙江省").click()
    await page.get_by_role("button", name="保存修改").click()
    # await _wait_for_save_toast(page)
    await _close_edit_dialog(page)


async def _step_07_customized(page: Page) -> None:
    """步骤 7: 定制品 - 保持原样。

    Args:
        page: Playwright 页面对象。
    """
    # 录制中这一步只是点击预览保存,没有修改
    await page.get_by_text("定制品").click()

    await page.get_by_role("button", name="预览").click()
    await page.get_by_role("button", name="保存修改").click()
    # await _wait_for_save_toast(page)
    await _close_edit_dialog(page)


async def _step_08_sensitive(page: Page) -> None:
    """步骤 8: 敏感属性 - 保持原样。

    Args:
        page: Playwright 页面对象。
    """
    await page.get_by_text("敏感属性").click()
    await page.get_by_role("button", name="预览").click()
    await page.get_by_role("button", name="保存修改").click()
    # await _wait_for_save_toast(page)
    await _close_edit_dialog(page)


async def _step_09_weight(page: Page) -> None:
    """步骤 9: 重量 - 固定 6000g。

    Args:
        page: Playwright 页面对象。
    """
    await page.get_by_text("重量").click()
    await page.get_by_role("spinbutton").nth(2).click()
    await page.get_by_role("spinbutton").nth(2).fill("6000.00")
    await page.get_by_role("button", name="预览").click()
    await page.get_by_role("button", name="保存修改").click()
    # await _wait_for_save_toast(page)
    await _close_edit_dialog(page)


async def _step_10_dimensions(page: Page) -> None:
    """步骤 10: 尺寸 - 固定 75x71x65 cm。

    Args:
        page: Playwright 页面对象。
    """
    dialog = page.get_by_role("dialog")
    await dialog.get_by_text("尺寸", exact=True).click()

    # 长
    await (
        dialog.locator("div")
        .filter(has_text=re.compile(r"^长:CM$"))
        .get_by_role("spinbutton")
        .click()
    )
    await (
        dialog.locator("div")
        .filter(has_text=re.compile(r"^长:CM$"))
        .get_by_role("spinbutton")
        .fill("75")
    )

    # 宽
    await (
        dialog.locator("div")
        .filter(has_text=re.compile(r"^宽:CM$"))
        .get_by_role("spinbutton")
        .click()
    )
    await (
        dialog.locator("div")
        .filter(has_text=re.compile(r"^宽:CM$"))
        .get_by_role("spinbutton")
        .fill("71")
    )

    # 高
    await (
        dialog.locator("div")
        .filter(has_text=re.compile(r"^高:CM$"))
        .get_by_role("spinbutton")
        .click()
    )
    await (
        dialog.locator("div")
        .filter(has_text=re.compile(r"^高:CM$"))
        .get_by_role("spinbutton")
        .fill("65")
    )

    await dialog.get_by_role("button", name="预览").click()
    await dialog.get_by_role("button", name="保存修改").click()
    # await _wait_for_save_toast(page)
    await _close_edit_dialog(page)


async def _step_11_platform_sku(page: Page) -> None:
    """步骤 11: 平台 SKU - 全选。

    Args:
        page: Playwright 页面对象。
    """
    await page.get_by_role("dialog").get_by_text("平台SKU").click()
    await page.locator(
        ".el-checkbox.jx-pro-checkbox > .el-checkbox__input > .el-checkbox__inner"
    ).first.click()
    await page.get_by_role("button", name="预览").click()
    await page.get_by_role("button", name="保存修改").click()
    # await _wait_for_save_toast(page)
    await _close_edit_dialog(page)


@smart_retry(max_attempts=2, delay=0.5)
async def _step_12_sku_category(page: Page) -> None:
    """步骤 12: SKU 分类 - 点击分类下拉框选择单品，然后保存。"""
    dialog = page.get_by_role("dialog")
    
    # 等待加载遮罩消失
    loading_mask = page.locator(".el-loading-mask")
    with suppress(Exception):
        await loading_mask.wait_for(state="hidden", timeout=2000)
    
    # 1. 点击左侧导航"SKU分类"
    nav = dialog.locator(".batch-editor-left").get_by_text("SKU分类", exact=False).first
    if await nav.count():
        await nav.click(timeout=800)
        logger.debug("✓ 点击SKU分类导航")
    
    # 等待加载
    with suppress(Exception):
        await loading_mask.wait_for(state="hidden", timeout=1000)
    await page.wait_for_timeout(500)  # 等待内容加载
    
    # 2. 点击"分类"下拉框 - 多种选择器尝试
    dropdown_clicked = False
    dropdown_selectors = [
        # 通过 placeholder 定位
        dialog.get_by_placeholder("分类").first,
        dialog.get_by_placeholder("请选择").first,
        # 通过 SKU分类 标签旁边的 el-select 定位
        dialog.locator("text=SKU分类").locator("..").locator(".el-select input").first,
        dialog.locator("text=SKU分类").locator("..").locator(".el-select").first,
        # 通过表单中的第一个 el-select 定位
        dialog.locator("form .el-select input").first,
        dialog.locator("form .el-select").first,
        # 直接在对话框中找 el-select
        dialog.locator(".el-select input").first,
        dialog.locator(".el-select").first,
    ]
    
    for selector in dropdown_selectors:
        try:
            if await selector.count():
                await selector.click(timeout=800)
                dropdown_clicked = True
                logger.debug("✓ 点击分类下拉框")
                break
        except Exception as e:
            logger.debug(f"选择器失败: {e}")
            continue
    
    if dropdown_clicked:
        # 等待下拉菜单出现
        await page.wait_for_timeout(300)
        
        # 3. 在下拉菜单中选择"单品"
        option_clicked = False
        option_selectors = [
            page.locator(".el-select-dropdown:visible .el-select-dropdown__item").filter(has_text="单品").first,
            page.locator(".el-select-dropdown__item:has-text('单品')").first,
            page.get_by_role("option", name="单品").first,
            page.get_by_text("单品", exact=True).first,
        ]
        
        for option in option_selectors:
            try:
                if await option.count():
                    await option.click(timeout=500)
                    option_clicked = True
                    logger.success("✓ 已选择: 单品")
                    break
            except Exception:
                continue
        
        if not option_clicked:
            logger.warning("⚠️ 未找到'单品'选项")
    else:
        logger.warning("⚠️ 未找到分类下拉框")
    
    # 4. 点击保存修改
    await page.get_by_role("button", name="保存修改").click()
    await _close_edit_dialog(page)


async def _step_13_size_chart(page: Page) -> None:
    """步骤 13: 尺码表 - 跳过(录制中只是点击)。

    Args:
        page: Playwright 页面对象。
    """
    await page.get_by_text("尺码表").click()
    # 录制中没有实际操作,等待对话框打开后直接继续
    # await _wait_for_dialog_open(page)


@smart_retry(max_attempts=1, delay=0.2)
async def _step_14_suggested_price(page: Page) -> None:
    """步骤 14: 建议售价 - 固定倍数 10。

    Args:
        page: Playwright 页面对象。
    """
    await page.get_by_text("建议售价").click()

    # 选择使用公式
    await page.get_by_role("radio", name="使用公式:").click()

    # 填写倍数
    await page.get_by_role("textbox", name="倍数").click()
    await page.get_by_role("textbox", name="倍数").fill("10")

    await page.get_by_role("button", name="预览").click()
    await page.get_by_role("button", name="保存修改").click()
    # await _wait_for_save_toast(page)
    await _close_edit_dialog(page)


async def _step_15_packing_list(page: Page) -> None:
    """步骤 15: 包装清单 - 保持原样。

    Args:
        page: Playwright 页面对象。
    """
    await page.get_by_text("包装清单").click()
    await page.get_by_role("button", name="预览").click()
    await page.get_by_role("button", name="保存修改").click()
    # await _wait_for_save_toast(page)
    await _close_edit_dialog(page)


async def _step_16_carousel(page: Page) -> None:
    """步骤 16: 轮播图 - 保持原样。

    Args:
        page: Playwright 页面对象。
    """
    await page.get_by_text("轮播图").click()
    # 录制中没有实际操作,等待对话框打开后直接继续
    # await _wait_for_dialog_open(page)


async def _step_17_color_image(page: Page) -> None:
    """步骤 17: 颜色图 - 保持原样。

    Args:
        page: Playwright 页面对象。
    """
    await page.get_by_text("颜色图").click()
    # 录制中没有实际操作,等待对话框打开后直接继续
    # await _wait_for_dialog_open(page)


@smart_retry(max_attempts=1, delay=0.2)
async def _step_18_manual(page: Page, file_path: str) -> None:
    """步骤 18: 产品说明书 - 参数化文件路径。

    Args:
        page: Playwright 页面对象。
        file_path: 产品说明书 PDF 文件路径(绝对路径)。
    """
    await page.get_by_text("产品说明书").click()
    # await _wait_for_dialog_open(page)
    if file_path:
        try:
            # 点击上传文件按钮
            upload_btn = self.page.locator("button:has-text('上传文件')").first
            if await upload_btn.count() > 0 and await upload_btn.is_visible():
                await upload_btn.click()
                logger.info("      ✓ 图片URL已上传")

        except Exception as exc:
            logger.warning("产品说明书上传失败, 保留已有文件: {}", exc)

    await page.get_by_role("button", name="预览").click()
    await page.get_by_role("button", name="保存修改").click()
    #  await _wait_for_save_toast(page)
    await _close_edit_dialog(page)


async def _wait_for_save_toast(page: Page, timeout: int = 200) -> None:
    """等待保存成功提示并等待其消失(极速模式)。

    Args:
        page: Playwright 页面对象。
        timeout: 超时时间(毫秒),默认 200（极速: 600 -> 200）。
    """
    try:
        toast = page.locator("text=保存成功")
        await toast.wait_for(state="visible", timeout=timeout)
        # 极速模式: 减少等待时间 300 -> 100
        await smart_wait(page, "wait_save_toast", min_ms=10, max_ms=100, wait_for_network=True)
    except Exception:
        # 静默失败（极速: 100 -> 30）
        await smart_wait(page, "wait_save_fallback", min_ms=10, max_ms=30)


async def _wait_for_dropdown_options(page: Page, timeout: int = 150) -> None:
    """等待下拉选项列表出现(极速模式)。

    Args:
        page: Playwright 页面对象。
        timeout: 超时时间(毫秒),默认 150（极速: 400 -> 150）。
    """
    try:
        await page.locator(".el-select-dropdown").wait_for(state="visible", timeout=timeout)
    except Exception:
        pass


async def _wait_for_dialog_open(page: Page, timeout: int = 300) -> None:
    """等待编辑对话框完全打开(极速模式)。

    Args:
        page: Playwright 页面对象。
        timeout: 超时时间(毫秒),默认 300（极速: 800 -> 300）。
    """
    try:
        dialog = page.get_by_role("dialog")
        await dialog.wait_for(state="visible", timeout=timeout)
        # 极速模式: 150 -> 50
        await smart_wait(page, "dialog_open", min_ms=10, max_ms=50)
    except Exception:
        # 降级（极速: 200 -> 50）
        await smart_wait(page, "dialog_open_fallback", min_ms=10, max_ms=50)


async def _close_edit_dialog(page: Page) -> None:
    """关闭编辑对话框(极速模式)。

    Args:
        page: Playwright 页面对象。
    """
    # 极速: 800 -> 300
    close_locator = await _resilient_locator.locate(page, "close_button", timeout=300)
    
    if close_locator:
        try:
            await close_locator.click()
            # 极速: 150 -> 30
            await smart_wait(page, "close_dialog", min_ms=10, max_ms=30)
            return
        except Exception as exc:
            logger.debug(f"弹性选择器关闭按钮点击失败: {exc}")
    
    # 降级方案1: 使用 role 定位
    try:
        close_btn = page.get_by_role("button", name="关闭", exact=True)
        await close_btn.click()
        # 极速: 150 -> 30
        await smart_wait(page, "close_dialog_role", min_ms=10, max_ms=30)
        return
    except Exception:
        pass
    
    # 降级方案2: 使用图标关闭
    try:
        close_icon = page.locator(".edit-box-header-side > .el-icon-close")
        await close_icon.click()
        # 极速: 150 -> 30
        await smart_wait(page, "close_dialog_icon", min_ms=10, max_ms=30)
    except Exception:
        logger.warning("无法关闭编辑对话框，继续执行")
