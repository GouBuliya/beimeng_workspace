"""
@PURPOSE: 使用可重试的方式执行首次编辑弹窗填写, 提供JS注入与调试能力
@OUTLINE:
  - class FirstEditPayload: 首次编辑数据模型
  - class FirstEditExecutor: 负责注入数据、保存并输出调试信息
@DEPENDENCIES:
  - 内部: first_edit_controller, debug_tools
  - 外部: pydantic, playwright, tenacity
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

from loguru import logger
from playwright.async_api import Page
from tenacity import RetryError, retry, stop_after_attempt, wait_exponential

from .debug_tools import capture_debug_artifacts, log_payload_preview, maybe_pause_for_inspector
from .first_edit_controller import FirstEditController


@dataclass(slots=True)
class FirstEditPayload:
    """首次编辑数据载体."""

    title: str
    product_number: str
    price: float
    supply_price: float
    source_price: float
    stock: int
    weight_g: int
    length_cm: int
    width_cm: int
    height_cm: int
    supplier_link: str = ""
    specs: list[dict[str, Any]] | None = None
    variants: list[dict[str, Any]] | None = None

    def to_dict(self) -> dict[str, Any]:
        """转换为 dict, 便于序列化与注入."""

        payload = asdict(self)
        payload["specs"] = self.specs or []
        payload["variants"] = self.variants or []
        payload["dimensions_cm"] = {
            "length": self.length_cm,
            "width": self.width_cm,
            "height": self.height_cm,
        }
        return payload


class FirstEditExecutor:
    """负责将 payload 注入首次编辑弹窗并保存."""

    def __init__(
        self,
        controller: FirstEditController,
        *,
        injector_path: Path | None = None,
        debug_dir: Path | None = None,
    ) -> None:
        self._controller = controller
        project_root = Path(__file__).resolve().parents[2]
        self._injector_path = (
            injector_path or project_root / "data" / "assets" / "first_edit_inject.js"
        )
        self._injector_loaded = False
        self._debug_dir = debug_dir or project_root / "data" / "debug"

    async def apply(
        self,
        page: Page,
        payload: FirstEditPayload,
        *,
        post_fill_hook: Callable[[Page], Awaitable[bool]] | None = None,
    ) -> bool:
        """注入 payload 并保存弹窗."""

        await maybe_pause_for_inspector(page)
        log_payload_preview(payload.to_dict(), title="首次编辑字段预览")

        try:
            await self._controller.wait_for_dialog(page)
            injection_result = await self._fill_with_retry(page, payload)
        except RetryError as err:
            logger.error("填写首次编辑弹窗连续失败: {}", err)
            await capture_debug_artifacts(page, step="fill_failed", output_dir=self._debug_dir)
            await self._controller.close_dialog(page)
            return False
        except Exception as err:
            # 捕获其他所有异常（如 RuntimeError），避免异常向上传播导致降级未触发
            logger.error("填写首次编辑弹窗异常: {}", err)
            await capture_debug_artifacts(page, step="fill_exception", output_dir=self._debug_dir)
            await self._controller.close_dialog(page)
            return False

        if not injection_result.get("success", False):
            logger.error("填写返回失败: {}", injection_result)
            await capture_debug_artifacts(
                page, step="payload_injection_failed", output_dir=self._debug_dir
            )
            await self._controller.close_dialog(page)
            return False

        if post_fill_hook is not None:
            try:
                hook_result = await post_fill_hook(page)
                if hook_result:
                    logger.success("SKU 图片同步完成")
                else:
                    logger.warning("SKU 图片同步未成功")
            except Exception as exc:
                logger.error("SKU 图片同步异常: {}", exc)

        saved = await self._controller.save_changes(page, wait_for_close=True)
        if not saved:
            logger.error("保存首次编辑弹窗失败")
            await capture_debug_artifacts(page, step="save_failed", output_dir=self._debug_dir)
            await self._controller.close_dialog(page)
            return False

        await self._controller.close_dialog(page)
        return True

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.8, min=0.8, max=4.0),
        reraise=True,
    )
    async def _fill_with_retry(self, page: Page, payload: FirstEditPayload) -> dict[str, Any]:
        """带重试地读取注入脚本并填写字段."""

        if not self._injector_loaded:
            await self._ensure_injector(page)

        result = await page.evaluate(
            """async (payload) => {
                if (typeof window.__FIRST_EDIT_APPLY__ !== "function") {
                    return { success: false, error: "injector-not-found" };
                }
                return await window.__FIRST_EDIT_APPLY__(payload);
            }""",
            payload.to_dict(),
        )

        # 增强日志输出
        logger.debug("首次编辑注入结果: {}", result)
        if result and "debug" in result:
            logger.info("调试信息: {}", result["debug"])
        if result and "filled" in result:
            logger.success("已填写字段: {}", ", ".join(result.get("filled", [])))
        if result and "missing" in result and result["missing"]:
            logger.warning("缺失字段: {}", ", ".join(result.get("missing", [])))
        
        if not result:
            raise RuntimeError("注入脚本返回空结果")
        if not result.get("success", False):
            missing = ", ".join(result.get("missing", []))
            debug_info = result.get("debug", {})
            raise RuntimeError(f"字段填写失败, 缺失: {missing}, 调试信息: {debug_info}")
        return result

    async def _ensure_injector(self, page: Page) -> None:
        """向页面注入 JS 脚本."""

        if not self._injector_path.exists():
            raise FileNotFoundError(f"注入脚本不存在: {self._injector_path}")

        await page.add_script_tag(path=str(self._injector_path))
        self._injector_loaded = True
        logger.debug("已加载首次编辑注入脚本: {}", self._injector_path)
