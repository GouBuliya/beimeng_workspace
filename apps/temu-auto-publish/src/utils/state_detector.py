"""
@PURPOSE: 页面状态检测器 - 自动检测当前页面状态并提供容错恢复
@OUTLINE:
  - class PageState: 页面状态枚举
  - class StateDetector: 状态检测器
    - detect_current_state(): 检测当前页面状态
    - is_login_page(): 是否在登录页
    - is_collection_box(): 是否在采集箱
    - is_edit_dialog_open(): 编辑弹窗是否打开
    - recover_to_collection_box(): 恢复到采集箱列表页
    - close_any_dialog(): 关闭任何打开的弹窗
@GOTCHAS:
  - 状态检测基于URL和页面元素
  - 容错恢复可能需要多次尝试
@DEPENDENCIES:
  - 外部: playwright, loguru
"""

from enum import Enum

from loguru import logger
from playwright.async_api import Page


class PageState(Enum):
    """页面状态枚举."""

    UNKNOWN = "unknown"  # 未知状态
    LOGIN_PAGE = "login"  # 登录页
    HOME_PAGE = "home"  # 首页
    COLLECTION_BOX = "collection_box"  # 采集箱列表
    EDIT_DIALOG_OPEN = "edit_dialog"  # 编辑弹窗打开
    BATCH_EDIT = "batch_edit"  # 批量编辑页面
    PUBLISH_PAGE = "publish"  # 发布页面


class StateDetector:
    """页面状态检测器 - 提供智能状态检测和容错恢复."""

    def __init__(self):
        """初始化状态检测器."""
        logger.debug("状态检测器已初始化")

    async def detect_current_state(self, page: Page) -> PageState:
        """检测当前页面状态.

        Args:
            page: Playwright页面对象

        Returns:
            当前页面状态

        Examples:
            >>> detector = StateDetector()
            >>> state = await detector.detect_current_state(page)
            >>> print(state)
            PageState.COLLECTION_BOX
        """
        try:
            url = page.url
            logger.debug(f"检测页面状态,当前URL: {url}")

            # 1. 检查是否在登录页
            if await self.is_login_page(page):
                logger.info("📍 当前状态: 登录页")
                return PageState.LOGIN_PAGE

            # 2. 检查是否有编辑弹窗打开
            if await self.is_edit_dialog_open(page):
                logger.info("📍 当前状态: 编辑弹窗打开")
                return PageState.EDIT_DIALOG_OPEN

            # 3. 检查是否在采集箱页面
            if await self.is_collection_box(page):
                logger.info("📍 当前状态: 采集箱列表页")
                return PageState.COLLECTION_BOX

            # 4. 检查是否在首页
            if await self.is_home_page(page):
                logger.info("📍 当前状态: 首页")
                return PageState.HOME_PAGE

            # 5. 检查是否在批量编辑页面
            if await self.is_batch_edit_page(page):
                logger.info("📍 当前状态: 批量编辑页")
                return PageState.BATCH_EDIT

            # 6. 检查是否在发布页面
            if await self.is_publish_page(page):
                logger.info("📍 当前状态: 发布页")
                return PageState.PUBLISH_PAGE

            logger.warning("⚠️  当前状态: 未知")
            return PageState.UNKNOWN

        except Exception as e:
            logger.error(f"检测页面状态失败: {e}")
            return PageState.UNKNOWN

    async def is_login_page(self, page: Page) -> bool:
        """检查是否在登录页.

        Args:
            page: Playwright页面对象

        Returns:
            是否在登录页
        """
        try:
            url = page.url
            if "login" in url or "sub_account/users" in url:
                return True

            # 检查是否有登录表单
            login_btn_count = await page.locator(
                "button:has-text('登录'), button:has-text('立即登录')"
            ).count()
            return login_btn_count > 0
        except Exception:

            return False

    async def is_home_page(self, page: Page) -> bool:
        """检查是否在首页.

        Args:
            page: Playwright页面对象

        Returns:
            是否在首页
        """
        try:
            url = page.url
            return "welcome" in url or url.endswith("91miaoshou.com/")
        except Exception:

            return False

    async def is_collection_box(self, page: Page) -> bool:
        """检查是否在采集箱页面.

        Args:
            page: Playwright页面对象

        Returns:
            是否在采集箱页面
        """
        try:
            url = page.url
            if "common_collect_box/items" not in url:
                return False

            # 确认页面加载完成(检查tab是否存在)
            tab_count = await page.locator(".jx-radio-button:has-text('全部'), text='全部'").count()
            return tab_count > 0
        except Exception:

            return False

    async def is_edit_dialog_open(self, page: Page) -> bool:
        """检查编辑弹窗是否打开.

        Args:
            page: Playwright页面对象

        Returns:
            编辑弹窗是否打开
        """
        try:
            dialog_count = await page.locator(".jx-dialog, .el-dialog, [role='dialog']").count()
            if dialog_count == 0:
                return False

            # 检查是否是编辑弹窗(而不是其他弹窗)
            edit_indicators = [
                "text='基本信息'",
                "text='销售属性'",
                "text='产品图片'",
                "input[placeholder*='标题']",
                "button:has-text('保存')",
            ]

            for indicator in edit_indicators:
                count = await page.locator(indicator).count()
                if count > 0:
                    return True

            return False
        except Exception:

            return False

    async def is_batch_edit_page(self, page: Page) -> bool:
        """检查是否在批量编辑页面.

        Args:
            page: Playwright页面对象

        Returns:
            是否在批量编辑页面
        """
        try:
            url = page.url
            return "batch_edit" in url or "认领到" in await page.content()
        except Exception:

            return False

    async def is_publish_page(self, page: Page) -> bool:
        """检查是否在发布页面.

        Args:
            page: Playwright页面对象

        Returns:
            是否在发布页面
        """
        try:
            url = page.url
            return "publish" in url or "发布" in url
        except Exception:

            return False

    async def close_any_dialog(self, page: Page) -> bool:
        """关闭任何打开的弹窗(容错恢复).

        Args:
            page: Playwright页面对象

        Returns:
            是否成功关闭
        """
        logger.info("🔄 尝试关闭所有打开的弹窗...")

        try:
            # 关闭按钮选择器列表
            close_selectors = [
                "button[aria-label='关闭']",
                "button[aria-label='Close']",
                ".jx-dialog__headerbtn",
                ".jx-dialog__close",
                ".el-dialog__headerbtn",
                ".el-dialog__close",
                "button:has-text('取消')",
                "button:has-text('关闭')",
                "[class*='close']",
            ]

            closed_count = 0
            for selector in close_selectors:
                try:
                    count = await page.locator(selector).count()
                    if count > 0:
                        logger.debug(f"找到{count}个关闭按钮: {selector}")
                        # 点击所有匹配的关闭按钮
                        for i in range(min(count, 3)):  # 最多点击3个
                            await page.locator(selector).nth(i).click(timeout=2000)
                            closed_count += 1
                            await page.wait_for_timeout(500)
                except Exception:

                    continue

            # 按ESC键作为最后的尝试
            try:
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(500)
            except Exception:

                pass

            # 验证是否关闭
            await page.wait_for_timeout(1000)
            dialog_count = await page.locator(".jx-dialog, .el-dialog, [role='dialog']").count()

            if dialog_count == 0:
                logger.success(f"✓ 已关闭{closed_count}个弹窗")
                return True
            else:
                logger.warning(f"⚠️ 关闭了{closed_count}个按钮,但仍有{dialog_count}个弹窗")
                return False

        except Exception as e:
            logger.error(f"关闭弹窗失败: {e}")
            return False

    async def recover_to_collection_box(self, page: Page) -> bool:
        """恢复到采集箱列表页(容错恢复).

        Args:
            page: Playwright页面对象

        Returns:
            是否成功恢复
        """
        logger.info("🔄 尝试恢复到采集箱列表页...")

        try:
            # 1. 先关闭所有弹窗
            await self.close_any_dialog(page)

            # 2. 检查当前状态
            current_state = await self.detect_current_state(page)

            if current_state == PageState.COLLECTION_BOX:
                logger.success("✓ 已在采集箱列表页")
                return True

            # 3. 导航到采集箱
            logger.info("导航到采集箱...")
            await page.goto("https://erp.91miaoshou.com/common_collect_box/items")
            await page.wait_for_load_state("domcontentloaded")
            await page.wait_for_timeout(2000)

            # 4. 验证是否成功
            if await self.is_collection_box(page):
                logger.success("✓ 成功恢复到采集箱列表页")
                return True
            else:
                logger.error("✗ 恢复失败")
                return False

        except Exception as e:
            logger.error(f"恢复到采集箱失败: {e}")
            return False

    async def ensure_state(
        self, page: Page, expected_state: PageState, auto_recover: bool = True
    ) -> bool:
        """确保当前处于期望的状态,如果不是则尝试恢复.

        Args:
            page: Playwright页面对象
            expected_state: 期望的状态
            auto_recover: 是否自动恢复(默认True)

        Returns:
            是否处于期望状态

        Examples:
            >>> await detector.ensure_state(page, PageState.COLLECTION_BOX)
            True
        """
        logger.info(f"🔍 检查状态是否为: {expected_state.value}")

        current_state = await self.detect_current_state(page)

        if current_state == expected_state:
            logger.success(f"✓ 已处于期望状态: {expected_state.value}")
            return True

        if not auto_recover:
            logger.warning(
                f"⚠️ 当前状态({current_state.value}) != 期望状态({expected_state.value}),且未启用自动恢复"
            )
            return False

        # 尝试恢复
        logger.warning(
            f"⚠️ 当前状态({current_state.value}) != 期望状态({expected_state.value}),尝试恢复..."
        )

        if expected_state == PageState.COLLECTION_BOX:
            return await self.recover_to_collection_box(page)
        elif expected_state == PageState.HOME_PAGE:
            await page.goto("https://erp.91miaoshou.com/welcome")
            return await self.is_home_page(page)
        else:
            logger.error(f"✗ 不支持自动恢复到状态: {expected_state.value}")
            return False


# 示例使用
if __name__ == "__main__":
    # 此模块需要配合Page对象使用
    # 测试请在集成测试中进行
    pass
