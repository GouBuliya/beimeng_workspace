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
@DEPENDENCIES:
  - 外部: playwright, loguru
  - 内部: 无
@GOTCHAS:
  - 文件上传需要提供绝对路径
  - 某些步骤可能因页面加载慢而超时,已添加适当等待
  - 类目选择需要按层级逐级点击
"""

import contextlib
import re
from pathlib import Path
from typing import Any

from loguru import logger
from playwright.async_api import Page

MAX_TITLE_LENGTH = 250


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
    }

    try:
        logger.info("开始执行批量编辑 18 步流程(基于 Codegen 录制)")

        # 0. 确保在 Temu 全托管采集箱页面
        current_url = page.url
        target_url = "https://erp.91miaoshou.com/pddkj/collect_box/items"
        if target_url not in current_url:
            logger.info(f"导航到 Temu 全托管采集箱: {target_url}")
            await page.goto(target_url, timeout=60000)
            # 智能等待: 等待网络空闲而非固定延迟
            await page.wait_for_load_state("networkidle", timeout=30000)

        # 1. 检测并关闭弹窗
        await _close_popups(page)

        # 2. 全选产品
        logger.info("全选产品...")
        checkbox = page.locator(".jx-checkbox").first
        await checkbox.click()
        # 智能等待: 等待选中状态生效
        try:
            await page.locator(".jx-checkbox.is-checked").first.wait_for(state="visible", timeout=3000)
        except Exception:
            pass  # 即使超时也继续,可能已经选中

        # 3. 打开批量编辑弹窗
        logger.info("打开批量编辑菜单...")
        await page.get_by_text("批量编辑").click()
        # 智能等待: 等待批量编辑对话框或弹窗打开
        try:
            # 先尝试等待role=dialog的标准对话框
            await _wait_for_dialog_open(page)
        except Exception:
            # 如果标准对话框超时,尝试等待其他可能的批量编辑容器
            try:
                await page.locator(".batch-edit-popover, .el-popover, .batch-edit-container").first.wait_for(state="visible", timeout=3000)
            except Exception:
                logger.warning("批量编辑弹窗未通过标准选择器检测到,继续执行")

        logger.info("批量编辑弹窗已打开")

        # 执行 18 个步骤
        steps = [
            ("标题", _step_01_title(page)),
            ("英语标题", _step_02_english_title(page)),
            ("类目属性", _step_03_category_attrs(page, payload)),
            ("主货号", _step_04_main_sku(page)),
            ("外包装", _step_05_outer_package(page, payload.get("outer_package_image", ""))),
            ("产地", _step_06_origin(page)),
            ("定制品", _step_07_customized(page)),
            ("敏感属性", _step_08_sensitive(page)),
            ("重量", _step_09_weight(page)),
            ("尺寸", _step_10_dimensions(page)),
            ("平台SKU", _step_11_platform_sku(page)),
            ("SKU分类", _step_12_sku_category(page)),
            ("尺码表", _step_13_size_chart(page)),
            ("建议售价", _step_14_suggested_price(page)),
            ("包装清单", _step_15_packing_list(page)),
            ("轮播图", _step_16_carousel(page)),
            ("颜色图", _step_17_color_image(page)),
            ("产品说明书", _step_18_manual(page, payload.get("manual_file", ""))),
        ]

        for idx, (step_name, step_coro) in enumerate(steps, start=1):
            logger.info(f"执行步骤 {idx}/18: {step_name}")
            await step_coro
            result["completed_steps"] = idx
            logger.success(f"步骤 {idx}/18 完成: {step_name}")

        # 关闭编辑框
        await _close_edit_dialog(page)
        logger.success("批量编辑 18 步全部完成")

        result["success"] = True

    except Exception as exc:
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
        await page.locator(".jx-checkbox.is-checked").first.wait_for(state="visible", timeout=2000)
    except Exception:
        pass


async def _close_popups(page: Page) -> None:
    """检测并关闭页面弹窗。

    Args:
        page: Playwright 页面对象。
    """
    logger.info("检测页面弹窗...")

    # 常见弹窗关闭按钮的选择器列表
    popup_selectors = [
        "button:has-text('关闭')",
        "button:has-text('我知道了')",
        "button:has-text('取消')",
        ".el-dialog__close",
        ".el-icon-close",
        "[aria-label='关闭此对话框']",
        "text='关闭'",
    ]

    closed_count = 0
    for selector in popup_selectors:
        try:
            # 查找所有匹配的关闭按钮
            close_buttons = page.locator(selector)
            count = await close_buttons.count()

            if count > 0:
                logger.debug(f"发现 {count} 个弹窗(选择器: {selector})")
                # 点击所有可见的关闭按钮
                for i in range(count):
                    try:
                        button = close_buttons.nth(i)
                        if await button.is_visible(timeout=1000):
                            await button.click(timeout=2000)
                            closed_count += 1
                            logger.success(f"✓ 已关闭弹窗 {closed_count}")
                            # 智能等待: 等待弹窗消失
                            try:
                                await button.wait_for(state="hidden", timeout=2000)
                            except Exception:
                                pass
                    except Exception:
                        continue
        except Exception:
            continue

    if closed_count > 0:
        logger.success(f"✓ 总共关闭了 {closed_count} 个弹窗")
    else:
        logger.info("未发现需要关闭的弹窗")


async def _step_01_title(page: Page) -> None:
    """步骤 1: 标题 - 保持原样点击预览保存。

    Args:
        page: Playwright 页面对象。
    """
    await page.locator("div").filter(has_text=re.compile(r"^标题$")).click()
    # 智能等待: 等待标题编辑对话框打开
    await _wait_for_dialog_open(page)
    await _ensure_title_length(page)
    await page.get_by_role("button", name="预览").click()
    await page.get_by_role("button", name="保存修改").click()
    await _wait_for_save_toast(page)
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
                await locator.evaluate("el => el.dispatchEvent(new Event('input', { bubbles: true }))")
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
    await _wait_for_save_toast(page)
    await _close_edit_dialog(page)


async def _step_03_category_attrs(page: Page, payload: dict[str, Any]) -> None:
    """步骤 3: 类目属性 - 参数化类目路径和属性值。

    Args:
        page: Playwright 页面对象。
        payload: 包含 category_path 和 category_attrs 的字典。
    """
    await page.get_by_text("类目属性").click()

    await page.get_by_role("button", name="预览").click()
    await page.get_by_role("button", name="保存修改").click()
    await _wait_for_save_toast(page)
    await _close_edit_dialog(page)


async def _step_04_main_sku(page: Page) -> None:
    """步骤 4: 主货号 - 保持原样。

    Args:
        page: Playwright 页面对象。
    """
    await page.get_by_role("dialog").get_by_text("主货号").click()
    await page.get_by_role("button", name="预览").click()
    await page.get_by_role("button", name="保存修改").click()
    await _wait_for_save_toast(page)
    await _close_edit_dialog(page)


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
        await page.get_by_role("radio").filter(has_text="addImages").click()
        
        # 点击展开上传选项的下拉按钮
        option_trigger = (
            page.get_by_role("dialog")
            .locator("span")
            .filter(has_text="本地上传 选择空间图片 使用网络图片")
            .locator("i")
            .first
        )
        await option_trigger.click()
        await page.wait_for_timeout(300)  # 等待下拉菜单展开
        
        # 点击"本地上传"选项
        popover = page.locator("[id^='el-popover']").filter(has_text="本地上传")
        await popover.get_by_text("本地上传").first.click()
        await page.wait_for_timeout(300)  # 等待文件选择器准备
        
        # 查找文件输入框并上传
        file_input = page.locator("input[type='file']").last
        await file_input.wait_for(state="attached", timeout=5000)
        await file_input.set_input_files(chosen_path)
        logger.success("✓ 外包装图片已上传: {}", chosen_path)
        
        # 等待上传完成
        await page.wait_for_timeout(1500)  # 给服务器时间处理上传
        
        # 点击确定/保存按钮关闭上传弹窗
        confirm_btn = page.get_by_role("button", name=re.compile("^(确定|保存)$", re.I))
        if await confirm_btn.count() > 0:
            await confirm_btn.first.click()
            await page.wait_for_timeout(500)
            
    except Exception as exc:
        logger.warning("外包装图片上传失败, 保留已有图片: {}", exc)

    await page.get_by_role("button", name="预览").click()
    await page.get_by_role("button", name="保存修改").click()
    await _wait_for_save_toast(page)
    await _close_edit_dialog(page)


async def _step_06_origin(page: Page) -> None:
    """步骤 6: 产地 - 固定为浙江。

    Args:
        page: Playwright 页面对象。
    """
    await page.get_by_text("产地").click()
    await page.get_by_role("dialog", name="dialog").get_by_placeholder("请选择或输入搜索").click()
    await (
        page.get_by_role("dialog", name="dialog")
        .get_by_placeholder("请选择或输入搜索")
        .fill("浙江")
    )
    await page.get_by_text("中国大陆 / 浙江省").click()
    await page.get_by_role("button", name="保存修改").click()
    await _wait_for_save_toast(page)
    await _close_edit_dialog(page)


async def _step_07_customized(page: Page) -> None:
    """步骤 7: 定制品 - 保持原样。

    Args:
        page: Playwright 页面对象。
    """
    # 录制中这一步只是点击预览保存,没有修改
    await page.get_by_role("button", name="预览").click()
    await page.get_by_role("button", name="保存修改").click()
    await _wait_for_save_toast(page)
    await _close_edit_dialog(page)


async def _step_08_sensitive(page: Page) -> None:
    """步骤 8: 敏感属性 - 保持原样。

    Args:
        page: Playwright 页面对象。
    """
    await page.get_by_text("敏感属性").click()
    await page.get_by_role("button", name="预览").click()
    await page.get_by_role("button", name="保存修改").click()
    await _wait_for_save_toast(page)
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
    await _wait_for_save_toast(page)
    await _close_edit_dialog(page)


async def _step_10_dimensions(page: Page) -> None:
    """步骤 10: 尺寸 - 固定 75x71x65 cm。

    Args:
        page: Playwright 页面对象。
    """
    await page.get_by_text("尺寸").click()

    # 长
    await (
        page.locator("div")
        .filter(has_text=re.compile(r"^长:CM$"))
        .get_by_role("spinbutton")
        .click()
    )
    await (
        page.locator("div")
        .filter(has_text=re.compile(r"^长:CM$"))
        .get_by_role("spinbutton")
        .fill("75")
    )

    # 宽
    await (
        page.locator("div")
        .filter(has_text=re.compile(r"^宽:CM$"))
        .get_by_role("spinbutton")
        .click()
    )
    await (
        page.locator("div")
        .filter(has_text=re.compile(r"^宽:CM$"))
        .get_by_role("spinbutton")
        .fill("71")
    )

    # 高
    await (
        page.locator("div")
        .filter(has_text=re.compile(r"^高:CM$"))
        .get_by_role("spinbutton")
        .click()
    )
    await (
        page.locator("div")
        .filter(has_text=re.compile(r"^高:CM$"))
        .get_by_role("spinbutton")
        .fill("65")
    )

    await page.get_by_role("button", name="预览").click()
    await page.get_by_role("button", name="保存修改").click()
    await _wait_for_save_toast(page)
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
    await _wait_for_save_toast(page)
    await _close_edit_dialog(page)


async def _step_12_sku_category(page: Page) -> None:
    """步骤 12: SKU 分类 - 选择组合装 500 件。

    Args:
        page: Playwright 页面对象。
    """
    # 点击打开SKU分类编辑对话框
    await page.get_by_text("SKU分类").click()
    await _wait_for_dialog_open(page)
    
    # 点击下拉框触发器展开选项列表
    trigger = (
        page.get_by_role("dialog")
        .locator("form")
        .locator(".el-select")
        .locator("input")
        .first
    )
    await trigger.click()
    await page.wait_for_timeout(500)  # 等待下拉选项列表展开
    
    # 选择"组合装 500 件"
    dropdown_item = page.locator(".el-select-dropdown__item").filter(has_text="组合装 500 件").first
    await dropdown_item.wait_for(state="visible", timeout=3000)
    await dropdown_item.click()

    await page.get_by_role("button", name="预览").click()
    await page.get_by_role("button", name="保存修改").click()
    await _wait_for_save_toast(page)
    await _close_edit_dialog(page)


async def _step_13_size_chart(page: Page) -> None:
    """步骤 13: 尺码表 - 跳过(录制中只是点击)。

    Args:
        page: Playwright 页面对象。
    """
    await page.get_by_text("尺码表").click()
    # 录制中没有实际操作,等待对话框打开后直接继续
    await _wait_for_dialog_open(page)


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
    await _wait_for_save_toast(page)
    await _close_edit_dialog(page)


async def _step_15_packing_list(page: Page) -> None:
    """步骤 15: 包装清单 - 保持原样。

    Args:
        page: Playwright 页面对象。
    """
    await page.get_by_text("包装清单").click()
    await page.get_by_role("button", name="预览").click()
    await page.get_by_role("button", name="保存修改").click()
    await _wait_for_save_toast(page)
    await _close_edit_dialog(page)


async def _step_16_carousel(page: Page) -> None:
    """步骤 16: 轮播图 - 保持原样。

    Args:
        page: Playwright 页面对象。
    """
    await page.get_by_text("轮播图").click()
    # 录制中没有实际操作,等待对话框打开后直接继续
    await _wait_for_dialog_open(page)


async def _step_17_color_image(page: Page) -> None:
    """步骤 17: 颜色图 - 保持原样。

    Args:
        page: Playwright 页面对象。
    """
    await page.get_by_text("颜色图").click()
    # 录制中没有实际操作,等待对话框打开后直接继续
    await _wait_for_dialog_open(page)


async def _step_18_manual(page: Page, file_path: str) -> None:
    """步骤 18: 产品说明书 - 参数化文件路径。

    Args:
        page: Playwright 页面对象。
        file_path: 产品说明书 PDF 文件路径(绝对路径)。
    """
    await page.get_by_text("产品说明书").click()

    if file_path:
        # 上传文件
        await page.get_by_role("button", name="上传文件").click()
        await page.get_by_role("tooltip", name="本地上传").locator("div").first.click()

        # 使用 set_input_files 上传文件
        file_input = page.locator("#el-popover-5067").get_by_text("本地上传")
        await file_input.set_input_files(file_path)
        # 智能等待: 等待文件上传完成(等待上传进度条消失或成功提示)
        try:
            # 等待上传成功的文件名出现或上传区域状态变化
            await page.locator(".el-upload-list__item.is-success").wait_for(state="visible", timeout=5000)
        except Exception:
            # 如果没有明确的成功标识,等待一个较短的时间
            try:
                await page.wait_for_load_state("networkidle", timeout=3000)
            except Exception:
                pass

    await page.get_by_role("button", name="预览").click()
    await page.get_by_role("button", name="保存修改").click()
    await _wait_for_save_toast(page)
    await _close_edit_dialog(page)


async def _wait_for_save_toast(page: Page, timeout: int = 5000) -> None:
    """等待保存成功提示并等待其消失(智能等待)。

    Args:
        page: Playwright 页面对象。
        timeout: 超时时间(毫秒),默认 5000。
    """
    try:
        # 尝试等待成功提示
        toast = page.locator("text=保存成功")
        await toast.wait_for(state="visible", timeout=timeout)
        # 智能等待: 等待 toast 消失而非固定延迟
        await toast.wait_for(state="hidden", timeout=3000)
    except Exception:
        # 如果没有找到提示,继续执行
        logger.warning("未检测到保存成功提示,继续执行")


async def _wait_for_dropdown_options(page: Page, timeout: int = 3000) -> None:
    """等待下拉选项列表出现(智能等待)。

    Args:
        page: Playwright 页面对象。
        timeout: 超时时间(毫秒),默认 3000。
    """
    try:
        await page.locator(".el-select-dropdown").wait_for(state="visible", timeout=timeout)
    except Exception:
        logger.debug("下拉选项列表未在预期时间内出现")


async def _wait_for_dialog_open(page: Page, timeout: int = 5000) -> None:
    """等待编辑对话框完全打开(智能等待)。

    Args:
        page: Playwright 页面对象。
        timeout: 超时时间(毫秒),默认 5000。
    """
    dialog = page.get_by_role("dialog")
    await dialog.wait_for(state="visible", timeout=timeout)
    # 确保对话框内容加载完成
    try:
        await dialog.locator(".el-form").wait_for(state="visible", timeout=2000)
    except Exception:
        # 有些对话框可能没有 el-form,跳过
        pass


async def _close_edit_dialog(page: Page) -> None:
    """关闭编辑对话框并等待其真正关闭(智能等待)。

    Args:
        page: Playwright 页面对象。
    """
    try:
        close_btn = page.get_by_role("button", name="关闭", exact=True)
        await close_btn.click()
        # 智能等待: 等待对话框真正关闭(detached)
        try:
            await page.locator(".el-dialog__wrapper").wait_for(state="hidden", timeout=3000)
        except Exception:
            # 如果对话框选择器不匹配,至少等待按钮消失
            await close_btn.wait_for(state="hidden", timeout=2000)
    except Exception:
        # 如果没有关闭按钮,尝试其他方式
        try:
            close_icon = page.locator(".edit-box-header-side > .el-icon-close")
            await close_icon.click()
            await page.locator(".el-dialog__wrapper").wait_for(state="hidden", timeout=3000)
        except Exception:
            logger.warning("未找到关闭按钮,跳过")
