"""
@PURPOSE: 批量编辑步骤混入，封装 18 个具体步骤与重试逻辑
@OUTLINE:
  - class BatchEditStepsMixin: 提供 step_01 ~ step_18 方法
@DEPENDENCIES:
  - 内部: ..utils.batch_edit_helpers.retry_on_failure
  - 外部: loguru.logger, random, pathlib.Path
"""

from __future__ import annotations

import random
from contextlib import suppress
from pathlib import Path
from typing import Optional

from loguru import logger

from ...utils.batch_edit_helpers import retry_on_failure


class BatchEditStepsMixin:
    """提供批量编辑 18 个步骤的混入类."""

    async def step_01_title(self) -> bool:
        """步骤7.1：标题（不改动）."""
        if not await self.click_step("标题", "7.1"):
            return False

        logger.info("  ℹ️ 标题不改动，直接预览+保存")
        return await self.click_preview_and_save("标题")

    async def step_02_english_title(self) -> bool:
        """步骤7.2：英语标题（按空格）."""
        if not await self.click_step("英语标题", "7.2"):
            return False

        try:
            logger.info("  填写英语标题（输入空格）...")

            # 等待页面加载
            await self.page.wait_for_timeout(500)

            # 精准定位：排除disabled/readonly，优先匹配placeholder包含"英"的输入框
            precise_selectors = [
                "input[placeholder*='英']:not([disabled]):not([readonly])",
                "textarea[placeholder*='英']:not([disabled]):not([readonly])",
                "input[placeholder*='English']:not([disabled]):not([readonly])",
            ]

            filled = False
            for selector in precise_selectors:
                try:
                    inputs = await self.page.locator(selector).all()
                    logger.debug(f"  精准选择器找到 {len(inputs)} 个候选")

                    for input_elem in inputs:
                        if not await input_elem.is_visible():
                            continue

                        try:
                            # 快速点击测试（500ms超时）
                            await input_elem.click(timeout=500)
                            await input_elem.clear()
                            await input_elem.fill(" ")
                            logger.success("  ✓ 已输入空格（精准定位）")
                            filled = True
                            break
                        except:  # noqa: E722
                            continue

                    if filled:
                        break
                except Exception:  # noqa: BLE001
                    continue

            if not filled:
                logger.warning("  ⚠️ 未找到英语标题输入框")

            return await self.click_preview_and_save("英语标题")
        except Exception as exc:  # noqa: BLE001
            logger.error(f"  ✗ 操作失败: {exc}")
            return False

    async def step_03_category_attrs(self) -> bool:
        """步骤7.3：类目属性（参考采集链接填写）."""
        if not await self.click_step("类目属性", "7.3"):
            return False

        logger.info("  ℹ️ 类目属性需要参考原商品链接")
        logger.info("  ℹ️ 当前跳过，实际使用时需要填写")

        return await self.click_preview_and_save("类目属性")

    async def step_04_main_sku(self) -> bool:
        """步骤7.4：主货号（填写或保持默认）."""
        if not await self.click_step("主货号", "7.4"):
            return False

        try:
            logger.info("  检查主货号是否需要填写...")
            await self.page.wait_for_timeout(500)

            # 精准定位：排除disabled/readonly
            precise_selectors = [
                "input[placeholder*='货号']:not([disabled]):not([readonly])",
                "input[placeholder*='SKU']:not([disabled]):not([readonly])",
            ]

            input_found = False
            for selector in precise_selectors:
                try:
                    inputs = await self.page.locator(selector).all()

                    for input_elem in inputs:
                        if await input_elem.is_visible():
                            current_value = await input_elem.input_value()
                            if current_value:
                                logger.info(f"  ℹ️ 主货号已有值：{current_value}，保持不变")
                            else:
                                logger.info("  ℹ️ 主货号为空，保持默认")
                            input_found = True
                            break

                    if input_found:
                        break
                except Exception:  # noqa: BLE001
                    continue

            return await self.click_preview_and_save("主货号")

        except Exception as exc:  # noqa: BLE001
            logger.error(f"  ✗ 操作失败: {exc}")
            return False

    async def step_05_packaging(self, image_url: Optional[str] = None) -> bool:
        """步骤7.5：外包装（长方体+硬包装）.

        Args:
            image_url: 外包装图片来源（可为 URL 或本地文件路径）
        """
        if not await self.click_step("外包装", "7.5"):
            return False

        try:
            logger.info("  填写外包装信息...")

            # 等待页面加载完成
            await self.page.wait_for_timeout(1000)

            # 1. 选择外包装形状：长方体（使用下拉选择框）
            logger.info("    - 外包装形状：长方体")
            shape_selected = False

            try:
                # 查找"外包装形状"标签，然后找到对应的下拉框
                shape_label = self.page.locator("text='外包装形状'").first
                if await shape_label.count() > 0:
                    # 找到同一行的el-select下拉框
                    parent = shape_label.locator("..").locator("..")
                    select_input = parent.locator(".el-input__inner, input.el-input__inner").first

                    if await select_input.count() > 0 and await select_input.is_visible():
                        # 点击下拉框打开选项
                        await select_input.click()
                        logger.debug("      已点击外包装形状下拉框")
                        await self.page.wait_for_timeout(500)

                        # 选择"长方体"选项
                        option_selectors = [
                            ".el-select-dropdown__item:has-text('长方体')",
                            "li.el-select-dropdown__item:has-text('长方体')",
                            ".jx-pro-option:has-text('长方体')",
                        ]

                        for selector in option_selectors:
                            try:
                                option = self.page.locator(selector).first
                                if await option.count() > 0:
                                    # 等待选项可见
                                    await option.wait_for(state="visible", timeout=3000)
                                    await option.click()
                                    logger.info("      ✓ 已选择长方体")
                                    shape_selected = True
                                    break
                            except Exception as err:  # noqa: BLE001
                                logger.debug(f"      选项选择器 {selector} 失败: {err}")
                                continue
                    else:
                        logger.warning("      ⚠️ 未找到外包装形状下拉框")
                else:
                    logger.warning("      ⚠️ 未找到'外包装形状'标签")
            except Exception as err:  # noqa: BLE001
                logger.warning(f"      ⚠️ 选择外包装形状失败: {err}")

            if not shape_selected:
                logger.warning("      ⚠️ 未能选择长方体")
                try:
                    await self.page.screenshot(path="debug_packaging_shape.png")
                    logger.info("      📸 已保存截图: debug_packaging_shape.png")
                except Exception:  # noqa: BLE001
                    pass

            await self.page.wait_for_timeout(500)

            # 2. 选择外包装类型：硬包装（使用下拉选择框）
            logger.info("    - 外包装类型：硬包装")
            type_selected = False

            try:
                # 查找"外包装类型"标签，然后找到对应的下拉框
                type_label = self.page.locator("text='外包装类型'").first
                if await type_label.count() > 0:
                    parent = type_label.locator("..").locator("..")
                    select_input = parent.locator(".el-input__inner, input.el-input__inner").first

                    if await select_input.count() > 0 and await select_input.is_visible():
                        await select_input.click()
                        logger.debug("      已点击外包装类型下拉框")
                        await self.page.wait_for_timeout(500)

                        option_selectors = [
                            ".el-select-dropdown__item:has-text('硬包装')",
                            "li.el-select-dropdown__item:has-text('硬包装')",
                            ".jx-pro-option:has-text('硬包装')",
                        ]

                        for selector in option_selectors:
                            try:
                                option = self.page.locator(selector).first
                                if await option.count() > 0:
                                    await option.wait_for(state="visible", timeout=3000)
                                    await option.click()
                                    logger.info("      ✓ 已选择硬包装")
                                    type_selected = True
                                    break
                            except Exception as err:  # noqa: BLE001
                                logger.debug(f"      选项选择器 {selector} 失败: {err}")
                                continue
                    else:
                        logger.warning("      ⚠️ 未找到外包装类型下拉框")
                else:
                    logger.warning("      ⚠️ 未找到'外包装类型'标签")
            except Exception as err:  # noqa: BLE001
                logger.warning(f"      ⚠️ 选择外包装类型失败: {err}")

            if not type_selected:
                logger.warning("      ⚠️ 未能选择硬包装")
                try:
                    await self.page.screenshot(path="debug_packaging_type.png")
                    logger.info("      📸 已保存截图: debug_packaging_type.png")
                except Exception:  # noqa: BLE001
                    pass

            await self.page.wait_for_timeout(500)

            def _is_url(value: str) -> bool:
                return value.lower().startswith(("http://", "https://"))

            upload_source = image_url or getattr(self, "outer_package_image_source", None)
            if upload_source:
                if _is_url(upload_source):
                    logger.info(f"    - 上传外包装图片(URL): {upload_source}")
                    try:
                        network_img_btn = self.page.locator("button:has-text('使用网络图片')").first
                        if await network_img_btn.count() > 0 and await network_img_btn.is_visible():
                            await network_img_btn.click()
                            await self.page.wait_for_timeout(1000)

                            url_input = self.page.locator("input[placeholder*='图片'], textarea").first
                            if await url_input.count() > 0:
                                await url_input.fill(upload_source)
                                await self.page.wait_for_timeout(500)

                                confirm_btn = self.page.locator(
                                    "button:has-text('确定'), button:has-text('确认')",
                                ).first
                                if await confirm_btn.count() > 0:
                                    await confirm_btn.click()
                                    logger.info("      ✓ 图片URL已上传")
                                else:
                                    logger.warning("      ⚠️ 未找到确定按钮")
                            else:
                                logger.warning("      ⚠️ 未找到图片URL输入框")
                        else:
                            logger.debug("      未找到网络图片按钮")
                    except Exception as err:  # noqa: BLE001
                        logger.warning(f"      ⚠️ 图片上传失败: {err}")
                else:
                    file_path = Path(upload_source)
                    if file_path.exists():
                        logger.info(f"    - 上传外包装本地图片: {file_path}")
                        try:
                            file_inputs = self.page.locator("input[type='file']")
                            if await file_inputs.count() > 0:
                                await file_inputs.last.set_input_files(str(file_path))
                                logger.success("      ✓ 本地图片已上传")
                                await self.page.wait_for_timeout(500)
                            else:
                                logger.warning("      ⚠️ 未找到图片文件选择框")
                        except Exception as err:  # noqa: BLE001
                            logger.warning(f"      ⚠️ 上传本地图片失败: {err}")
                    else:
                        logger.warning(f"      ⚠️ 图片文件不存在: {file_path}")
            else:
                logger.info("    - 跳过图片上传（未提供图片）")

            await self.page.wait_for_timeout(500)
            return await self.click_preview_and_save("外包装")

        except Exception as exc:  # noqa: BLE001
            logger.error(f"  ✗ 操作失败: {exc}")
            return False

    async def step_06_origin(self) -> bool:
        """步骤7.6：产地（先输入\"浙江\"，然后选择\"中国大陆 / 浙江省\"）."""
        if not await self.click_step("产地", "7.6"):
            return False

        try:
            logger.info("  填写产地：浙江 -> 中国大陆 / 浙江省...")

            await self.page.wait_for_timeout(1000)

            precise_selectors = [
                "input[placeholder='请选择或输入搜索']:not([readonly]):not([disabled]):not([type='number'])",
                ".jx-cascader__search-input:visible",
            ]

            input_found = False

            for selector in precise_selectors:
                try:
                    all_inputs = await self.page.locator(selector).all()
                    logger.debug(f"  精准选择器 '{selector[:50]}...' 找到 {len(all_inputs)} 个候选")

                    for idx, input_elem in enumerate(all_inputs):
                        try:
                            if not await input_elem.is_visible():
                                continue

                            try:
                                await input_elem.click(timeout=1000)
                                await self.page.wait_for_timeout(200)
                                await input_elem.clear()
                                await input_elem.fill("浙江")
                                logger.success(
                                    f"  ✓ 已输入搜索关键词：浙江（精准定位第 {idx + 1} 个）",
                                )
                                input_found = True

                                await self.page.wait_for_timeout(1500)

                                option_selectors = [
                                    "text='中国大陆 / 浙江省'",
                                    "text='中国大陆/浙江省'",
                                    ".el-select-dropdown__item:has-text('中国大陆')",
                                    ".el-select-dropdown__item:has-text('浙江省')",
                                ]

                                selected = False
                                for opt_selector in option_selectors:
                                    try:
                                        options = await self.page.locator(opt_selector).all()

                                        for option in options:
                                            try:
                                                await option.wait_for(state="visible", timeout=1000)
                                                option_text = (await option.inner_text()).strip()

                                                if (
                                                    "中国大陆" in option_text
                                                    and "浙江" in option_text
                                                ):
                                                    await option.click(timeout=2000)
                                                    logger.success(f"  ✓ 已选择：{option_text}")
                                                    selected = True
                                                    break
                                            except Exception:  # noqa: BLE001
                                                continue

                                        if selected:
                                            break
                                    except Exception:  # noqa: BLE001
                                        continue

                                if not selected:
                                    try:
                                        await input_elem.press("ArrowDown")
                                        await self.page.wait_for_timeout(300)
                                        await input_elem.press("Enter")
                                        logger.info("  ✓ 已按ArrowDown+Enter确认")
                                    except Exception:  # noqa: BLE001
                                        logger.warning("  ⚠️ 未找到下拉选项，但已输入文本")

                                break

                            except Exception:  # noqa: BLE001
                                continue

                        except Exception:  # noqa: BLE001
                            continue

                    if input_found:
                        break

                except Exception as err:  # noqa: BLE001
                    logger.debug(f"  选择器失败: {str(err)[:60]}")
                    continue

            if not input_found:
                logger.warning("  ⚠️ 未找到可用的产地输入框")
                try:
                    await self.page.screenshot(path="debug_origin.png")
                    logger.info("  📸 已保存截图: debug_origin.png")
                except Exception:  # noqa: BLE001
                    pass

            await self.page.wait_for_timeout(500)
            return await self.click_preview_and_save("产地")

        except Exception as exc:  # noqa: BLE001
            logger.error(f"  ✗ 操作失败: {exc}")
            return False

    async def step_07_customization(self) -> bool:
        """步骤7.7：定制品（不改动）."""
        if not await self.click_step("定制品", "7.7"):
            return False

        logger.info("  ℹ️ 定制品不改动，直接预览+保存")
        return await self.click_preview_and_save("定制品")

    async def step_08_sensitive_attrs(self) -> bool:
        """步骤7.8：敏感属性（不改动）."""
        if not await self.click_step("敏感属性", "7.8"):
            return False

        logger.info("  ℹ️ 敏感属性不改动，直接预览+保存")
        return await self.click_preview_and_save("敏感属性")

    async def step_09_weight(
        self,
        weight: Optional[int] = None,
        product_name: Optional[str] = None,
    ) -> bool:
        """步骤7.9：重量（5000-9999G）.

        Args:
            weight: 重量（克），如果不提供则尝试从Excel读取或随机生成
            product_name: 产品名称，用于从Excel读取数据
        """
        if not await self.click_step("重量", "7.9"):
            return False

        try:
            if weight is None and product_name:
                try:
                    from src.data_processor.product_data_reader import ProductDataReader

                    reader = ProductDataReader()
                    weight = reader.get_weight(product_name)
                    if weight:
                        logger.info(f"  从Excel读取到重量: {weight}G")
                except Exception as err:  # noqa: BLE001
                    logger.debug(f"  从Excel读取重量失败: {err}")

            if weight is None:
                from src.data_processor.product_data_reader import ProductDataReader

                weight = ProductDataReader.generate_random_weight()
                logger.info(f"  使用随机重量: {weight}G")

            logger.info(f"  填写重量：{weight}G...")

            precise_selectors = [
                "input[placeholder*='重量']:not([disabled]):not([readonly])",
                "input[placeholder*='克']:not([disabled]):not([readonly])",
            ]

            for selector in precise_selectors:
                try:
                    weight_input = self.page.locator(selector).first
                    if await weight_input.count() > 0 and await weight_input.is_visible():
                        await weight_input.fill(str(weight))
                        logger.info(f"  ✓ 已输入：{weight}G")
                        break
                except Exception:  # noqa: BLE001
                    continue

            return await self.click_preview_and_save("重量")

        except Exception as exc:  # noqa: BLE001
            logger.error(f"  ✗ 操作失败: {exc}")
            return False

    async def step_10_dimensions(
        self,
        length: Optional[int] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        product_name: Optional[str] = None,
    ) -> bool:
        """步骤7.10：尺寸（50-99cm，长>宽>高）."""
        if not await self.click_step("尺寸", "7.10"):
            return False

        try:
            if length is None and width is None and height is None and product_name:
                try:
                    from src.data_processor.product_data_reader import ProductDataReader

                    reader = ProductDataReader()
                    dimensions = reader.get_dimensions(product_name)
                    if dimensions:
                        length = dimensions["length"]
                        width = dimensions["width"]
                        height = dimensions["height"]
                        logger.info(f"  从Excel读取到尺寸: {length} × {width} × {height} cm")
                except Exception as err:  # noqa: BLE001
                    logger.debug(f"  从Excel读取尺寸失败: {err}")

            if length is None:
                from src.data_processor.product_data_reader import ProductDataReader

                dims = ProductDataReader.generate_random_dimensions()
                length = dims["length"]
                width = dims["width"]
                height = dims["height"]
                logger.info(f"  使用随机尺寸: {length} × {width} × {height} cm")

            from src.data_processor.product_data_reader import ProductDataReader

            length, width, height = ProductDataReader.validate_and_fix_dimensions(
                length,
                width,
                height,
            )

            logger.info(f"  填写尺寸：{length} × {width} × {height} cm...")

            length_selectors = ["input[placeholder*='长']:not([disabled]):not([readonly])"]
            width_selectors = ["input[placeholder*='宽']:not([disabled]):not([readonly])"]
            height_selectors = ["input[placeholder*='高']:not([disabled]):not([readonly])"]

            for selector in length_selectors:
                try:
                    length_input = self.page.locator(selector).first
                    if await length_input.count() > 0 and await length_input.is_visible():
                        await length_input.fill(str(length))
                        logger.debug(f"  ✓ 长度: {length}cm")
                        break
                except Exception:  # noqa: BLE001
                    continue

            for selector in width_selectors:
                try:
                    width_input = self.page.locator(selector).first
                    if await width_input.count() > 0 and await width_input.is_visible():
                        await width_input.fill(str(width))
                        logger.debug(f"  ✓ 宽度: {width}cm")
                        break
                except Exception:  # noqa: BLE001
                    continue

            for selector in height_selectors:
                try:
                    height_input = self.page.locator(selector).first
                    if await height_input.count() > 0 and await height_input.is_visible():
                        await height_input.fill(str(height))
                        logger.debug(f"  ✓ 高度: {height}cm")
                        break
                except Exception:  # noqa: BLE001
                    continue

            logger.info(f"  ✓ 已输入尺寸（验证：{length} > {width} > {height}）")

            return await self.click_preview_and_save("尺寸")

        except Exception as exc:  # noqa: BLE001
            logger.error(f"  ✗ 操作失败: {exc}")
            return False

    async def step_11_platform_sku(self) -> bool:
        """步骤7.11：平台SKU（自定义SKU编码）."""
        if not await self.click_step("平台SKU", "7.11"):
            return False

        try:
            logger.info("  点击自定义SKU编码...")

            custom_sku_selectors = [
                "button:has-text('自定义SKU编码')",
                "text='自定义SKU编码'",
                "label:has-text('自定义SKU编码')",
                ".el-button:has-text('自定义SKU编码')",
                "span:has-text('自定义SKU编码')",
            ]

            clicked = False
            for selector in custom_sku_selectors:
                try:
                    all_elems = await self.page.locator(selector).all()
                    for elem in all_elems:
                        if await elem.is_visible():
                            await elem.click()
                            logger.info("  ✓ 已点击自定义SKU编码")
                            clicked = True
                            break
                    if clicked:
                        break
                except Exception as err:  # noqa: BLE001
                    logger.debug(f"  选择器 {selector} 失败: {err}")
                    continue

            if not clicked:
                logger.warning("  ⚠️ 未找到自定义SKU编码按钮，尝试强制点击")
                try:
                    await self.page.locator("button:has-text('自定义SKU编码')").first.click(
                        force=True,
                    )
                    logger.info("  ✓ 强制点击成功")
                except Exception:  # noqa: BLE001
                    logger.warning("  ⚠️ 未找到自定义SKU编码按钮")

            return await self.click_preview_and_save("平台SKU")

        except Exception as exc:  # noqa: BLE001
            logger.error(f"  ✗ 操作失败: {exc}")
            return False

    async def step_12_sku_category(self) -> bool:
        """步骤7.12：SKU分类（默认选择单品）."""
        if not await self.click_step("SKU分类", "7.12"):
            return False

        try:
            logger.info("  选择SKU分类：单品...")

            # 1. 点击分类下拉框
            select_selectors = [
                ".el-select",
                "input.el-input__inner",
                ".el-select__input",
            ]

            clicked = False
            for selector in select_selectors:
                try:
                    select_box = self.page.locator(selector).first
                    if await select_box.count() > 0 and await select_box.is_visible():
                        await select_box.click()
                        logger.debug("  ✓ 已点击分类下拉框")
                        clicked = True
                    break
                except Exception:  # noqa: BLE001
                    continue

            if not clicked:
                logger.warning("  ⚠️ 未找到分类下拉框")

            # 2. 点击"单品"选项
            option_selectors = [
                ".el-select-dropdown__item:has-text('单品')",
                "li:has-text('单品')",
                "text='单品'",
            ]

            selected = False
            for selector in option_selectors:
            try:
                    option = self.page.locator(selector).first
                    if await option.count() > 0 and await option.is_visible():
                        await option.click()
                        logger.success("  ✓ 已选择：单品")
                    selected = True
                    break
                except Exception:  # noqa: BLE001
                continue

        if not selected:
                logger.warning("  ⚠️ 未找到'单品'选项")

            await self.page.wait_for_timeout(300)
            return await self.click_preview_and_save("SKU分类")

        except Exception as exc:  # noqa: BLE001
            logger.error(f"  ✗ 操作失败: {exc}")
            return False

    @retry_on_failure(max_retries=3, delay=0.3, backoff=1.8)
    async def step_13_size_chart(self) -> bool:
        """步骤7.13：尺码表（不用修改）."""
        if not await self.click_step("尺码表", "7.13"):
            raise RuntimeError("未能定位到『尺码表』步骤")

        logger.info("  ℹ️ 尺码表不用修改")
        if await self.click_preview_and_save("尺码表"):
            return True
        raise RuntimeError("尺码表预览/保存失败")

    async def step_14_suggested_price(
        self,
        cost_price: Optional[float] = None,
        product_name: Optional[str] = None,
    ) -> bool:
        """步骤7.14：建议售价（成本价×10）."""
        if not await self.click_step("建议售价", "7.14"):
            return False

        try:
            if cost_price is None and product_name:
                try:
                    from src.data_processor.product_data_reader import ProductDataReader

                    reader = ProductDataReader()
                    cost_price = reader.get_cost_price(product_name)
                    if cost_price:
                        logger.info(f"  从Excel读取到成本价: ¥{cost_price}")
                except Exception as err:  # noqa: BLE001
                    logger.debug(f"  从Excel读取成本价失败: {err}")

            if cost_price:
                suggested_price = cost_price * 10
                logger.info(f"  填写建议售价：¥{suggested_price} (成本价 ¥{cost_price} × 10)...")

                precise_selectors = [
                    "input[placeholder*='价格']:not([disabled]):not([readonly])[type='number']",
                    "input[placeholder*='售价']:not([disabled]):not([readonly])[type='number']",
                    "input[placeholder*='建议']:not([disabled]):not([readonly])[type='number']",
                ]

                for selector in precise_selectors:
                    try:
                        price_input = self.page.locator(selector).first
                        if await price_input.count() > 0 and await price_input.is_visible():
                            await price_input.fill(str(suggested_price))
                            logger.info(f"  ✓ 已输入：¥{suggested_price}")
                            break
                    except Exception:  # noqa: BLE001
                        continue
            else:
                logger.info("  ℹ️ 无成本价数据，跳过填写（SOP要求：不做要求随便填）")

            return await self.click_preview_and_save("建议售价")

        except Exception as exc:  # noqa: BLE001
            logger.error(f"  ✗ 操作失败: {exc}")
            return False

    async def step_15_package_list(self) -> bool:
        """步骤7.15：包装清单（不改动）."""
        if not await self.click_step("包装清单", "7.15"):
            return False

        logger.info("  ℹ️ 包装清单不改动，直接预览+保存")
        return await self.click_preview_and_save("包装清单")

    async def step_16_carousel_images(self) -> bool:
        """步骤7.16：轮播图（暂时不需要）."""
        if not await self.click_step("轮播图", "7.16"):
            return False

        logger.info("  ℹ️ 轮播图暂时不修改")
        return await self.click_preview_and_save("轮播图")

    async def step_17_color_images(self) -> bool:
        """步骤7.17：颜色图（不需要）."""
        if not await self.click_step("颜色图", "7.17"):
            return False

        logger.info("  ℹ️ 颜色图不需要修改")
        return await self.click_preview_and_save("颜色图")

    async def step_18_manual(self, manual_file_path: Optional[str] = None) -> bool:
        """步骤7.18：产品说明书（上传PDF文件）."""
        if not await self.click_step("产品说明书", "7.18"):
            return False
        #等待1s
        await self.page.wait_for_timeout(1000)
        try:
            if manual_file_path:
                file_path = Path(manual_file_path)
                if not file_path.exists():
                    logger.warning(f"  ⚠️ 文件不存在: {manual_file_path}")
                else:
                    success_upload = False
                    last_error: Exception | None = None

                    for attempt in range(1, 4):
                        logger.info(f"  ↻ 产品说明书上传尝试 {attempt}/3")
                        uploaded = False
                        file_chooser = None
                        try:
                    logger.info(f"  上传产品说明书: {file_path.name}...")

                    upload_btn_selectors = [
                        "button:has-text('上传文件')",
                        "text='上传文件'",
                        ".el-button:has-text('上传文件')",
                        "span:has-text('上传文件')",
                        "xpath=/html/body/div[12]/div/div[2]/div[1]/div[2]/form/div/div[1]/div/div/button",
                    ]
                    section_candidates = [
                        "text='批量编辑方式'",
                        "text='使用网络的说明书'",
                        "text='使用网络说明书'",
                        "text='使用网络说明书 '",
                    ]
                    upload_section = None
                    for section in section_candidates:
                        try:
                            label = self.page.locator(section).first
                            if await label.count() > 0 and await label.is_visible():
                                upload_section = label.locator("..").locator("..")
                                break
                        except Exception:
                            continue
                    upload_btn_scope = upload_section or self.page

                            hovered = False
                            for selector in upload_btn_selectors:
                                try:
                            upload_btn = upload_btn_scope.locator(selector).first
                                    if await upload_btn.count() > 0 and await upload_btn.is_visible():
                                        await upload_btn.hover()
                                        logger.debug("  ✓ 已悬停在'上传文件'按钮")
                                        await self.page.wait_for_timeout(100)
                                        with suppress(Exception):
                                            await upload_btn.click()
                                        with suppress(Exception):
                                            await upload_btn.click(button="right")
                                        await self.page.wait_for_timeout(150)
                                        hovered = True
                                        break
                                except Exception as err:  # noqa: BLE001
                                    logger.debug(f"  悬停选择器 {selector} 失败: {err}")
                                    continue

                            if not hovered:
                                logger.warning("  ⚠️ 未找到'上传文件'按钮")
                                continue

                            local_upload_selectors = [
                                "text='本地上传'",
                                "li:has-text('本地上传')",
                                ".el-dropdown-menu__item:has-text('本地上传')",
                                "div:has-text('本地上传')",
                            ]

                            clicked = False
                            for selector in local_upload_selectors:
                                try:
                                    local_upload_option = self.page.locator(selector).first
                                    if await local_upload_option.count() > 0 and await local_upload_option.is_visible():
                                        dropdown_wrapper = self.page.locator(
                                            ".el-dropdown-menu:visible, .el-popover:visible"
                                        )
                                        with suppress(Exception):
                                            await dropdown_wrapper.first.wait_for(state="visible", timeout=1500)
                                        try:
                                            with self.page.expect_file_chooser(timeout=2000) as fc_info:
                                                await local_upload_option.click()
                                            file_chooser = await fc_info.value
                                            logger.debug("  ✓ 已点击'本地上传'并捕获文件选择器")
                                            clicked = True
                                            break
                                        except TimeoutError:
                                            logger.debug("  ⚠️ '本地上传' 未触发文件选择器, 尝试下一候选")
                                            continue
                                except Exception as err:  # noqa: BLE001
                                    logger.debug(f"  点击选择器 {selector} 失败: {err}")
                                    continue

                            if not clicked or file_chooser is None:
                                logger.warning("  ⚠️ 未找到'本地上传'选项")
                                continue

                            try:
                                await file_chooser.set_files(str(file_path))
                                await self.page.wait_for_timeout(1500)
                                logger.success(f"  ✅ 已上传产品说明书: {file_path.name}")
                                await self.page.wait_for_timeout(500)
                                uploaded = True
                            except Exception as err:  # noqa: BLE001
                                logger.error(f"  ❌ 文件选择器上传失败: {err}")

                            if not uploaded:
                                fallback_inputs = [
                                    ":text('批量编辑方式') >> .. >> .. >> input[type='file'][accept*='pdf']",
                                    ":text('使用网络的说明书') >> .. >> .. >> input[type='file'][accept*='pdf']",
                                    ":text('使用网络说明书') >> .. >> .. >> input[type='file'][accept*='pdf']",
                                    ":text('上传文件') >> .. >> input[type='file'][accept*='pdf']",
                                    "xpath=//div[contains(normalize-space(),'批量编辑方式')]/ancestor::div[1]//input[@type='file']",
                                    "xpath=//div[contains(normalize-space(),'使用网络的说明书')]/ancestor::div[1]//input[@type='file']",
                                    "input[type='file'][accept*='pdf']",
                                    "input[accept*='.pdf']",
                                    ":text('产品说明书') >> .. >> input[type='file']",
                                    "input[type='file']",
                                ]
                                seen = set()
                                for selector in fallback_inputs:
                                    if selector in seen:
                                        continue
                                    seen.add(selector)
                        try:
                                        file_input = self.page.locator(selector).last
                                        if await file_input.count() == 0:
                                            continue
                                        accept_attr = ""
                                        with suppress(Exception):
                                            accept_attr = await file_input.get_attribute("accept") or ""
                                        if accept_attr and "pdf" not in accept_attr.lower():
                                            logger.debug(
                                                "  ⚠️ 选择器 %s 的 accept=%s, 跳过非 PDF 输入框",
                                                selector,
                                                accept_attr,
                                            )
                                            continue
                                await file_input.set_input_files(str(file_path))
                                        await self.page.wait_for_timeout(1500)
                                        logger.success(f"  ✅ 已上传产品说明书: {file_path.name}")
                                        await self.page.wait_for_timeout(500)
                                uploaded = True
                                break
                        except Exception as err:  # noqa: BLE001
                            logger.debug(f"  上传选择器 {selector} 失败: {err}")
                            continue

                            if uploaded:
                                success_upload = True
                                break
                            else:
                                logger.warning("  ⚠️ 第 %s 次尝试仍未上传成功，重试中...", attempt)
                                await self.page.wait_for_timeout(400)
                        except Exception as err:  # noqa: BLE001
                            last_error = err
                            logger.warning("  ⚠️ 上传尝试 %s 失败: %s", attempt, err)
                            await self.page.wait_for_timeout(400)

                    if not success_upload:
                        if last_error:
                            raise last_error
                        raise RuntimeError("说明书上传重试仍未成功")
            else:
                logger.info("  ℹ️ 未提供说明书文件，跳过上传")

            return await self.click_preview_and_save("产品说明书")

        except Exception as e:
            logger.error(f"  ❌ 产品说明书上传失败: {e}")
            return await self.click_preview_and_save("产品说明书")