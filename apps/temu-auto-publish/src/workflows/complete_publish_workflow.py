"""
@PURPOSE: 基于最新 SOP 的 Temu 发布工作流, 实现首次编辑,认领,批量编辑与发布全流程
@OUTLINE:
  - dataclass StageOutcome: 阶段执行结果
  - dataclass EditedProduct: 首次编辑阶段产物
  - dataclass WorkflowExecutionResult: 整体执行结果
  - class CompletePublishWorkflow: 工作流主体
      - execute(): 同步入口
      - _run(): 异步总控
      - _stage_first_edit(): 阶段 1 首次编辑
      - _stage_claim_products(): 阶段 2 认领
      - _stage_batch_edit(): 阶段 3 批量编辑 18 步
      - _stage_publish(): 阶段 4 选择店铺/供货价/发布
      - 若干辅助方法: 数据准备,标题生成,凭证/店铺解析
@DEPENDENCIES:
  - 内部: browser.*, data_processor.*
  - 外部: playwright (runtime), loguru
"""

from __future__ import annotations

import asyncio
import contextlib
import os
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

from ..core.retry_handler import SessionExpiredError
from ..core.workflow_timeout import (
    TimeoutConfig,
    WorkflowTimeoutError,
    get_timeout_config,
    with_stage_timeout,
)

try:  # pragma: no cover - optional dependency
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None  # type: ignore[assignment]

from config.settings import settings

from ..browser.batch_edit_codegen import run_batch_edit
from ..browser.batch_edit_controller import BatchEditController
from ..browser.first_edit_codegen import open_edit_dialog_codegen
from ..browser.first_edit_controller import FirstEditController
from ..browser.first_edit_dialog_codegen import fill_first_edit_dialog_codegen
from ..browser.image_manager import ImageManager
from ..browser.login_controller import LoginController
from ..browser.miaoshou.batch_edit_api import run_batch_edit_via_api
from ..browser.miaoshou.first_edit_api import run_first_edit_via_api
from ..browser.miaoshou.publish_api import run_publish_via_api
from ..browser.miaoshou_controller import MiaoshouController
from ..browser.publish_controller import PublishController

# 导入稳定性组件
from ..core.browser_watchdog import BrowserWatchdog
from ..core.browser_watchdog import WatchdogConfig as WDConfig

# 导入优化组件
from ..core.checkpoint_manager import CheckpointManager, get_checkpoint_manager
from ..core.continuous_health_monitor import ContinuousHealthMonitor, MonitorConfig
from ..core.performance_reporter import ConsoleReporter
from ..core.performance_tracker import (
    reset_tracker,
)
from ..core.resource_manager import ResourceLimits, ResourceManager
from ..core.session_keeper import SessionKeeper, SessionKeeperConfig
from ..data_processor.price_calculator import PriceCalculator, PriceResult
from ..data_processor.product_data_reader import ProductDataReader
from ..data_processor.selection_table_reader import ProductSelectionRow, SelectionTableReader

FIRST_EDIT_STAGE_TIMEOUT_MS = 5_000

if TYPE_CHECKING:
    from playwright.async_api import Page

    from ..browser.browser_manager import BrowserManager


@dataclass(slots=True)
class StageOutcome:
    """阶段执行结果数据结构."""

    name: str
    success: bool
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EditedProduct:
    """首次编辑后用于后续阶段的数据载体."""

    index: int
    selection: ProductSelectionRow
    title: str
    cost_price: float
    price: PriceResult
    weight_g: int
    dimensions_cm: tuple[int, int, int]

    def to_payload(self) -> dict[str, Any]:
        """转换为可序列化的业务字典."""

        return {
            "index": self.index,
            "product_name": self.selection.product_name,
            "model_number": self.selection.model_number,
            "owner": self.selection.owner,
            "title": self.title,
            "cost_price": self.cost_price,
            "suggested_price": self.price.suggested_price,
            "supply_price": self.price.supply_price,
            "real_supply_price": self.price.real_supply_price,
            "weight_g": self.weight_g,
            "dimensions_cm": {
                "length": self.dimensions_cm[0],
                "width": self.dimensions_cm[1],
                "height": self.dimensions_cm[2],
            },
        }


@dataclass(slots=True)
class WorkflowExecutionResult:
    """整体工作流执行结果."""

    workflow_id: str
    total_success: bool
    stages: list[StageOutcome]
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """转换为易于序列化的字典结构."""

        return {
            "workflow_id": self.workflow_id,
            "total_success": self.total_success,
            "errors": list(self.errors),
            "stages": [
                {
                    "name": stage.name,
                    "success": stage.success,
                    "message": stage.message,
                    "details": stage.details,
                }
                for stage in self.stages
            ],
        }


async def _capture_html_snapshot(page: Page, filename: str) -> None:
    """写出当前页面 HTML 方便排查复杂 UI 结构."""

    try:
        html = await page.content()
    except Exception as exc:  # pragma: no cover - 调试辅助
        logger.warning("获取页面 HTML 失败: {}", exc)
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target_root = Path(__file__).resolve().parents[2] / "data" / "debug" / "html"
    target_root.mkdir(parents=True, exist_ok=True)
    target_file = target_root / f"{timestamp}_{filename}"
    try:
        target_file.write_text(html, encoding="utf-8")
        logger.debug("已写出调试 HTML: {}", target_file)
    except Exception as exc:  # pragma: no cover - IO 失败
        logger.warning("写出调试 HTML 失败: {}", exc)


class CompletePublishWorkflow:
    """Temu 商品发布完整工作流 (SOP 步骤 1-11)."""

    def __init__(
        self,
        *,
        headless: bool | None = None,
        selection_table: Path | str | None = None,
        selection_rows_override: Sequence[ProductSelectionRow] | None = None,
        use_ai_titles: bool = False,
        use_codegen_batch_edit: bool = False,
        use_api_batch_edit: bool = True,
        use_api_first_edit: bool = False,
        skip_first_edit: bool = False,
        only_claim: bool = False,
        only_stage4_publish: bool = False,
        outer_package_image: Path | str | None = None,
        manual_file: Path | str | None = None,
        collection_owner: str | None = None,
        # 新增: 断点恢复参数
        resume_from_checkpoint: bool = False,
        checkpoint_id: str | None = None,
        # 新增: 执行轮次与浏览器复用
        execution_round: int = 1,
        login_ctrl: LoginController | None = None,
        reuse_existing_login: bool = False,
        # 新增: 超时配置
        timeout_config: dict[str, int] | TimeoutConfig | None = None,
    ) -> None:
        """初始化工作流控制器.

        Args:
            headless: 浏览器是否使用无头模式; None 时读取配置文件.
            selection_table: 选品表路径,必须由外部提供(Web 上传或 CLI 参数).
            use_ai_titles: 是否启用 AI 生成标题 (失败时自动回退).
            use_codegen_batch_edit: 是否使用 codegen 录制的批量编辑模块 (默认 False).
            use_api_batch_edit: 是否使用 API 方式执行批量编辑 (默认 True, 最快速, 支持文件上传).
            use_api_first_edit: 是否使用 API 方式执行首次编辑 (默认 False, 实验性功能).
            skip_first_edit: 是否直接跳过首次编辑阶段.
            resume_from_checkpoint: 是否从检查点恢复.
            checkpoint_id: 指定要恢复的检查点ID,为空则使用最新检查点.
            execution_round: 连续执行的轮位(从 1 开始),用于计算首次编辑起始索引.
            login_ctrl: 可选复用的登录控制器,传入后会复用同一浏览器实例.
        """

        if load_dotenv:  # pragma: no cover - 环境可选
            load_dotenv()

        self.settings = settings
        self.use_ai_titles = use_ai_titles
        self.use_codegen_batch_edit = use_codegen_batch_edit
        self.use_api_batch_edit = use_api_batch_edit
        self.use_api_first_edit = use_api_first_edit
        self.skip_first_edit = skip_first_edit
        self.only_claim = only_claim
        self.only_stage4_publish = only_stage4_publish
        if self.only_stage4_publish and self.only_claim:
            raise ValueError("only_stage4_publish 与 only_claim 不能同时为 True")
        self.collection_owner_override = (collection_owner or "").strip()
        self._selection_rows_override = (
            list(selection_rows_override) if selection_rows_override else None
        )
        # 移除上限限制，一次性处理所有选品
        self.collect_count = max(1, self.settings.business.collect_count)
        self.claim_times = max(1, self.settings.business.claim_count)
        self.headless = headless if headless is not None else self.settings.browser.headless

        # 断点恢复配置
        self.resume_from_checkpoint = resume_from_checkpoint
        self.checkpoint_id = checkpoint_id
        self.execution_round = max(1, execution_round)
        self.login_ctrl = login_ctrl
        self.reuse_existing_login = reuse_existing_login

        # 超时配置
        if isinstance(timeout_config, TimeoutConfig):
            self.timeout_config = timeout_config
        else:
            self.timeout_config = get_timeout_config(timeout_config)

        # 归一化相对路径(以应用根目录为基准,适配 Windows)
        self._app_root = Path(__file__).resolve().parents[2]
        # 图片基础目录(从环境变量或配置读取, 默认为 data/input/10月新品可推)
        self.image_base_dir = self._resolve_image_base_dir()

        self.manual_file_override = self._resolve_optional_path(manual_file, "说明书文件")
        self.outer_package_image_override = self._resolve_optional_path(
            outer_package_image, "外包装图片"
        )

        self.selection_table_path = Path(selection_table) if selection_table else None

        self.selection_reader = SelectionTableReader()
        self.product_reader = ProductDataReader()
        self.price_calculator = PriceCalculator(
            suggested_multiplier=self.settings.business.price_multiplier,
            supply_multiplier=self.settings.business.supply_price_multiplier,
        )
        self.image_manager = ImageManager()

        # 初始化性能追踪器
        self._perf_tracker = reset_tracker("temu_publish")
        self._perf_reporter = ConsoleReporter(self._perf_tracker)

        # 稳定性组件(延迟初始化,在 _run 中创建)
        self._watchdog: BrowserWatchdog | None = None
        self._health_monitor: ContinuousHealthMonitor | None = None
        self._resource_manager: ResourceManager | None = None
        self._checkpoint_cleanup_task: asyncio.Task | None = None
        self._session_keeper: SessionKeeper | None = None

        # 24 小时稳定运行配置
        self._auto_recovery_enabled = True
        self._max_stage_retries = 3
        # 复用登录控制器时不关闭浏览器,以便后续批次继续使用
        self._close_browser_on_complete = not (login_ctrl is not None and reuse_existing_login)

    def execute(self) -> WorkflowExecutionResult:
        """????, ?? asyncio ??."""

        logger.info("?? Temu ??????? (SOTA ??)")
        return asyncio.run(self.execute_async())

    async def execute_async(self) -> WorkflowExecutionResult:
        """异步执行工作流入口,带总超时保护."""

        logger.info("启动 Temu 发布工作流 (SOTA 异步模式)")

        workflow_timeout = self.timeout_config.get("workflow_total", 3600)
        logger.info(
            f"[TIMEOUT] 工作流总超时: {workflow_timeout}s ({workflow_timeout / 60:.1f}分钟)"
        )

        try:
            async with with_stage_timeout(
                "workflow_total",
                workflow_timeout,
                on_timeout=lambda: logger.warning("[TIMEOUT] 工作流超时,将触发紧急清理"),
            ):
                return await self._run()

        except WorkflowTimeoutError as exc:
            logger.error(f"[TIMEOUT] 工作流超时异常: {exc}")
            await self._emergency_cleanup("timeout")
            # 返回失败结果而非抛出异常,确保上游能正常处理
            return WorkflowExecutionResult(
                workflow_id=f"timeout_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                total_success=False,
                stages=[],
                errors=[f"工作流超时 ({workflow_timeout}s): {exc}"],
            )

        except asyncio.CancelledError:
            logger.warning("[CANCELLED] 工作流被外部取消")
            await self._emergency_cleanup("cancelled")
            raise  # 取消异常需要继续传播

    async def _emergency_cleanup(self, reason: str = "timeout") -> None:
        """紧急清理: 超时或取消时调用.

        Args:
            reason: 触发清理的原因 ("timeout" | "cancelled" | "error")
        """
        logger.warning(f"[EMERGENCY] 触发紧急清理: {reason}")

        # 1. 尝试关闭浏览器资源
        if self.login_ctrl and self.login_ctrl.browser_manager:
            try:
                bm = self.login_ctrl.browser_manager
                # 调用改进后的 close 方法
                await bm.close(save_state=False)
                logger.info("[EMERGENCY] 浏览器资源已清理")
            except Exception as exc:
                logger.error(f"[EMERGENCY] 浏览器清理失败: {exc}")

        # 2. 结束性能追踪
        try:
            self._perf_tracker.end_workflow(success=False, error=f"Emergency cleanup: {reason}")
            self._perf_reporter.print_summary()
        except Exception as exc:
            logger.debug(f"[EMERGENCY] 性能追踪结束失败: {exc}")

        # 3. 停止稳定性组件
        await self._cleanup_stability_components()

    async def _safe_cleanup(
        self,
        workflow_id: str,
        stages: list[StageOutcome],
        errors: list[str],
    ) -> None:
        """安全清理资源，确保浏览器正确关闭.

        此方法在 finally 块中调用，确保即使出现异常也能正确清理资源。

        Args:
            workflow_id: 工作流 ID
            stages: 已执行的阶段列表
            errors: 错误列表
        """
        cleanup_errors: list[str] = []
        workflow_failed = errors or any(not stage.success for stage in stages)

        # 1. 停止稳定性组件(复用登录时跳过,由最后一个批次清理)
        if self._close_browser_on_complete:
            try:
                await self._cleanup_stability_components()
            except Exception as e:
                cleanup_errors.append(f"稳定性组件清理: {e}")
                logger.warning(f"[SafeCleanup] 稳定性组件清理失败: {e}")
        else:
            logger.debug("[SafeCleanup] 跳过稳定性组件清理(浏览器保持打开)")

        # 2. 保存最终状态（性能追踪）
        try:
            if workflow_failed:
                error_msg = "; ".join(errors) if errors else "阶段失败"
                self._perf_tracker.end_workflow(success=False, error=error_msg)
            else:
                self._perf_tracker.end_workflow(success=True)
            self._perf_reporter.print_summary()
            self._perf_tracker.save_to_file()
        except Exception as e:
            cleanup_errors.append(f"性能追踪保存: {e}")
            logger.warning(f"[SafeCleanup] 性能追踪保存失败: {e}")

        # 3. 关闭浏览器（关键步骤）
        if self._close_browser_on_complete and self.login_ctrl and self.login_ctrl.browser_manager:
            browser_manager = self.login_ctrl.browser_manager
            try:
                # 带超时的浏览器关闭（最多 30 秒）
                async with asyncio.timeout(30):
                    await browser_manager.close(save_state=True)
                logger.info("[SafeCleanup] 浏览器已关闭")
            except TimeoutError:
                cleanup_errors.append("浏览器关闭超时")
                logger.error("[SafeCleanup] 浏览器关闭超时（30秒）")
                # 尝试强制关闭
                try:
                    if browser_manager.browser:
                        await browser_manager.browser.close()
                except Exception:
                    pass
            except Exception as e:
                cleanup_errors.append(f"浏览器关闭: {e}")
                logger.error(f"[SafeCleanup] 浏览器关闭失败: {e}")
        elif workflow_failed:
            # 失败时输出恢复命令
            logger.warning("检测到阶段失败,保留浏览器以便继续排查.")
            logger.info(f"可使用 --resume --checkpoint-id={workflow_id} 从断点恢复")

        # 4. 输出清理报告
        if cleanup_errors:
            logger.warning(
                f"[SafeCleanup] 清理期间发生 {len(cleanup_errors)} 个错误: {cleanup_errors}"
            )
        else:
            logger.debug("[SafeCleanup] 资源清理完成")

    async def _retry_stage_with_recovery(
        self,
        stage_name: str,
        stage_func: Callable[[], Awaitable[StageOutcome | tuple[StageOutcome, Any]]],
        checkpoint_mgr: CheckpointManager,
        max_retries: int | None = None,
    ) -> StageOutcome | tuple[StageOutcome, Any]:
        """带自动恢复的阶段执行包装器.

        当阶段失败时，自动重试指定次数。每次重试前会刷新页面状态。

        Args:
            stage_name: 阶段名称
            stage_func: 阶段执行函数
            checkpoint_mgr: 检查点管理器
            max_retries: 最大重试次数（默认使用 self._max_stage_retries）

        Returns:
            阶段执行结果
        """
        retries = max_retries if max_retries is not None else self._max_stage_retries

        for attempt in range(retries + 1):
            try:
                result = await stage_func()

                # 判断结果类型
                outcome = result[0] if isinstance(result, tuple) else result

                if outcome.success:
                    if attempt > 0:
                        logger.success(
                            f"[AutoRecovery] 阶段 {stage_name} 在第 {attempt + 1} 次尝试后成功"
                        )
                    return result

                # 阶段失败，检查是否需要重试
                if attempt < retries and self._auto_recovery_enabled:
                    logger.warning(
                        f"[AutoRecovery] 阶段 {stage_name} 失败 (尝试 {attempt + 1}/{retries + 1}): "
                        f"{outcome.message}"
                    )

                    # 增加检查点重试计数
                    await checkpoint_mgr.increment_retry(stage_name)

                    # 等待后重试（递增延迟）
                    delay = min(5 * (attempt + 1), 30)  # 5s, 10s, 15s... 最多 30s
                    logger.info(f"[AutoRecovery] 等待 {delay} 秒后重试...")
                    await asyncio.sleep(delay)

                    # 尝试刷新页面状态
                    if self.login_ctrl and self.login_ctrl.browser_manager.page:
                        try:
                            await self.login_ctrl.browser_manager.page.reload(
                                wait_until="domcontentloaded"
                            )
                            logger.debug("[AutoRecovery] 页面已刷新")
                        except Exception as e:
                            logger.warning(f"[AutoRecovery] 页面刷新失败: {e}")

                    continue

                # 最后一次尝试也失败
                logger.error(f"[AutoRecovery] 阶段 {stage_name} 在 {retries + 1} 次尝试后仍然失败")
                return result

            except Exception as exc:
                if attempt < retries and self._auto_recovery_enabled:
                    logger.warning(
                        f"[AutoRecovery] 阶段 {stage_name} 异常 (尝试 {attempt + 1}/{retries + 1}): {exc}"
                    )
                    await asyncio.sleep(5 * (attempt + 1))
                    continue
                raise

        # 不应该到达这里
        return result

    async def _init_stability_components(
        self,
        browser_manager: BrowserManager | None = None,
        login_controller: LoginController | None = None,
    ) -> None:
        """初始化稳定性组件.

        Args:
            browser_manager: 浏览器管理器实例
            login_controller: 登录控制器实例
        """
        # 复用登录时跳过稳定性组件初始化(避免重复创建后台任务)
        if not self._close_browser_on_complete:
            logger.debug("[Stability] 跳过稳定性组件初始化(复用登录模式)")
            return

        # 1. 初始化资源管理器
        resource_cfg = self.settings.resource
        self._resource_manager = ResourceManager(
            limits=ResourceLimits(
                max_memory_mb=resource_cfg.max_memory_mb,
                min_disk_free_gb=resource_cfg.min_disk_free_gb,
                max_page_count=resource_cfg.max_page_count,
                max_temp_file_age_hours=resource_cfg.max_temp_file_age_hours,
                gc_trigger_memory_mb=resource_cfg.gc_trigger_memory_mb,
                enable_auto_gc=resource_cfg.enable_auto_gc,
            )
        )
        logger.info(
            "[Stability] 资源管理器已初始化 (内存限制: %dMB)",
            resource_cfg.max_memory_mb,
        )

        # 2. 初始化浏览器看门狗
        watchdog_cfg = self.settings.watchdog
        if watchdog_cfg.enabled and browser_manager:
            self._watchdog = BrowserWatchdog(
                browser_manager=browser_manager,
                login_controller=login_controller,
                config=WDConfig(
                    heartbeat_interval_sec=watchdog_cfg.heartbeat_interval_sec,
                    health_check_timeout_sec=watchdog_cfg.health_check_timeout_sec,
                    max_recovery_attempts=watchdog_cfg.max_recovery_attempts,
                    recovery_cooldown_sec=watchdog_cfg.recovery_cooldown_sec,
                    enable_auto_relogin=watchdog_cfg.enable_auto_relogin,
                    page_response_timeout_sec=watchdog_cfg.page_response_timeout_sec,
                    max_consecutive_failures=watchdog_cfg.max_consecutive_failures,
                ),
            )
            await self._watchdog.start()
            logger.info(
                "[Stability] 浏览器看门狗已启动 (心跳间隔: %ds)",
                watchdog_cfg.heartbeat_interval_sec,
            )

        # 3. 初始化持续健康监控
        monitor_cfg = self.settings.health_monitor
        if monitor_cfg.enabled:
            self._health_monitor = ContinuousHealthMonitor(
                browser_manager=browser_manager,
                login_controller=login_controller,
                config=MonitorConfig(
                    enabled=True,
                    check_interval_sec=monitor_cfg.check_interval_sec,
                    alert_threshold=monitor_cfg.alert_threshold,
                    include_browser_check=monitor_cfg.include_browser_check,
                    include_network_check=monitor_cfg.include_network_check,
                    include_disk_check=monitor_cfg.include_disk_check,
                    include_memory_check=monitor_cfg.include_memory_check,
                    alert_cooldown_sec=monitor_cfg.alert_cooldown_sec,
                ),
            )
            await self._health_monitor.start()
            logger.info(
                "[Stability] 持续健康监控已启动 (检查间隔: %ds, 告警阈值: %d次)",
                monitor_cfg.check_interval_sec,
                monitor_cfg.alert_threshold,
            )

        # 4. 启动检查点自动清理任务
        checkpoint_cfg = self.settings.checkpoint
        if checkpoint_cfg.auto_cleanup_enabled:
            self._checkpoint_cleanup_task = await CheckpointManager.start_auto_cleanup_task(
                interval_hours=checkpoint_cfg.auto_cleanup_interval_hours,
                retention_hours=checkpoint_cfg.retention_hours,
            )
            logger.info(
                "[Stability] 检查点自动清理已启动 (间隔: %dh, 保留: %dh)",
                checkpoint_cfg.auto_cleanup_interval_hours,
                checkpoint_cfg.retention_hours,
            )

        # 5. 启动会话保活（24 小时运行关键组件）
        session_cfg = getattr(self.settings, "session_keeper", None)
        if browser_manager and login_controller:
            refresh_interval = 30  # 默认 30 分钟
            if session_cfg and hasattr(session_cfg, "refresh_interval_minutes"):
                refresh_interval = session_cfg.refresh_interval_minutes

            self._session_keeper = SessionKeeper(
                browser_manager=browser_manager,
                login_controller=login_controller,
                config=SessionKeeperConfig(
                    enabled=True,
                    refresh_interval_minutes=refresh_interval,
                    max_refresh_failures=3,
                    relogin_on_failure=True,
                ),
            )
            await self._session_keeper.start()
            logger.info(
                "[Stability] 会话保活已启动 (刷新间隔: %d分钟)",
                refresh_interval,
            )

    async def _cleanup_stability_components(self) -> None:
        """清理稳定性组件."""
        # 1. 停止会话保活（优先停止，避免刷新干扰关闭流程）
        if self._session_keeper:
            try:
                await self._session_keeper.stop()
                logger.info("[Stability] 会话保活已停止")
            except Exception as exc:
                logger.warning(f"[Stability] 停止会话保活失败: {exc}")
            self._session_keeper = None

        # 2. 停止看门狗
        if self._watchdog:
            try:
                await self._watchdog.stop()
                logger.info("[Stability] 浏览器看门狗已停止")
            except Exception as exc:
                logger.warning(f"[Stability] 停止看门狗失败: {exc}")
            self._watchdog = None

        # 3. 停止健康监控
        if self._health_monitor:
            try:
                await self._health_monitor.stop()
                logger.info("[Stability] 持续健康监控已停止")
            except Exception as exc:
                logger.warning(f"[Stability] 停止健康监控失败: {exc}")
            self._health_monitor = None

        # 4. 停止检查点清理任务
        if self._checkpoint_cleanup_task:
            try:
                self._checkpoint_cleanup_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._checkpoint_cleanup_task
                logger.info("[Stability] 检查点清理任务已停止")
            except Exception as exc:
                logger.warning(f"[Stability] 停止清理任务失败: {exc}")
            self._checkpoint_cleanup_task = None

        # 5. 执行资源清理
        if self._resource_manager:
            try:
                status = await self._resource_manager.enforce_limits()
                if status.gc_triggered:
                    logger.info("[Stability] 最终 GC 已执行")
                if status.temp_files_cleaned > 0:
                    logger.info(f"[Stability] 清理临时文件: {status.temp_files_cleaned} 个")
            except Exception as exc:
                logger.warning(f"[Stability] 资源清理失败: {exc}")
            self._resource_manager = None

    async def _run(self) -> WorkflowExecutionResult:
        workflow_id = (
            self.checkpoint_id or f"temu_publish_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        stages: list[StageOutcome] = []
        errors: list[str] = []

        # 初始化断点管理器
        checkpoint_mgr = get_checkpoint_manager(workflow_id, "complete_publish")

        # 开始性能追踪
        self._perf_tracker.start_workflow(workflow_id)
        self._perf_reporter.print_workflow_start()

        # 尝试从检查点恢复
        restored_products: list[EditedProduct] = []
        if self.resume_from_checkpoint:
            checkpoint = await checkpoint_mgr.load_checkpoint()
            if checkpoint and checkpoint.is_resumable:
                logger.info(f"从检查点恢复: {checkpoint.current_stage}")
                logger.info(f"已完成阶段: {checkpoint.completed_stages}")

                # 恢复已完成阶段的数据
                stage1_data = checkpoint_mgr.get_stage_data("stage1_first_edit")
                if stage1_data and "products" in stage1_data:
                    # 重建 EditedProduct 对象(简化处理)
                    logger.info(f"恢复了 {len(stage1_data['products'])} 个商品数据")

        login_ctrl = self.login_ctrl or LoginController()
        self.login_ctrl = login_ctrl

        try:
            selection_rows: list[ProductSelectionRow] = []
            staff_name = ""
            page = None
            miaoshou_ctrl: MiaoshouController | None = None
            first_edit_ctrl: FirstEditController | None = None
            batch_edit_ctrl: BatchEditController | None = None
            publish_ctrl: PublishController | None = None
            edited_products: list[EditedProduct] = []

            # ===== 阶段 0: 预处理(登录+初始化) =====
            logger.info("阶段0: 预处理开始")

            # 解析凭证
            username, password = self._resolve_credentials()
            if not username or not password:
                raise RuntimeError("缺少登录凭证 (MIAOSHOU_USERNAME/MIAOSHOU_PASSWORD)")

            # 登录ERP
            already_logged_in = False
            try:
                if (
                    self.reuse_existing_login
                    and login_ctrl.browser_manager.page
                    and await login_ctrl._check_login_status()
                ):
                    already_logged_in = True
                    logger.info("检测到已登录状态,跳过登录流程")
            except Exception as exc:
                logger.debug("检查登录状态失败: {}", exc)

            login_success = True
            if not already_logged_in:
                login_success = await login_ctrl.login(
                    username=username,
                    password=password,
                    headless=self.headless,
                    keep_browser_open=True,
                )

            if not login_success:
                raise RuntimeError("登录ERP失败, 请检查账户或 Cookie")

            # 关闭登录后弹窗(已登录时跳过,避免阻塞)
            if not already_logged_in:
                logger.debug("关闭登录弹窗...")
                await login_ctrl.dismiss_login_overlays()
                logger.debug("登录弹窗已关闭")

            # 初始化页面
            logger.debug("获取页面对象...")
            page = login_ctrl.browser_manager.page
            if page is None:
                raise RuntimeError("Playwright page 未初始化")
            logger.debug("页面对象已获取")

            # 初始化稳定性组件(登录成功后)
            # 复用登录时仍然需要初始化(因为每个工作流实例是独立的)
            logger.debug("初始化稳定性组件...")
            await self._init_stability_components(
                browser_manager=login_ctrl.browser_manager,
                login_controller=login_ctrl,
            )
            logger.debug("稳定性组件初始化完成")

            logger.debug("检查 only_stage4_publish 模式...")
            if self.only_stage4_publish:
                # 跳转 Temu 采集箱页面(仅发布)
                collect_box_url = login_ctrl.selectors.get("temu_collect_box", {}).get(
                    "url", "https://erp.91miaoshou.com/pddkj/collect_box/items"
                )
                await login_ctrl.ensure_collect_box_ready(collect_box_url)

            # 准备选品数据
            logger.debug("准备选品数据...")
            selection_rows = self._prepare_selection_rows()
            staff_name = ""
            if selection_rows:
                staff_name = self._resolve_collection_owner(selection_rows[0].owner)
            logger.debug("选品数据准备完成: {} 条", len(selection_rows))

            # 初始化控制器
            logger.debug("初始化控制器...")
            miaoshou_ctrl = MiaoshouController()
            first_edit_ctrl = FirstEditController()
            legacy_manual = self.manual_file_override
            try:
                batch_edit_ctrl = BatchEditController(
                    page,
                    outer_package_image=str(self.outer_package_image_override)
                    if self.outer_package_image_override
                    else None,
                    manual_file_path=str(legacy_manual) if legacy_manual else None,
                    collection_owner=staff_name,
                    miaoshou_controller=miaoshou_ctrl,
                    perf_tracker=self._perf_tracker,
                )
            except TypeError:
                logger.warning("旧版 BatchEditController 不支持扩展参数,使用兼容参数重新初始化")
                batch_edit_ctrl = BatchEditController(perf_tracker=self._perf_tracker)
            publish_ctrl = PublishController()

            if (
                page is None
                or miaoshou_ctrl is None
                or first_edit_ctrl is None
                or batch_edit_ctrl is None
                or publish_ctrl is None
            ):
                raise RuntimeError("工作流初始化失败,关键控制器未创建")
            logger.debug("控制器初始化完成")
            logger.info("阶段0: 预处理完成,开始执行阶段1")

            # ===== 阶段 1: 首次编辑 =====
            async with self._perf_tracker.stage("stage1_first_edit", "首次编辑", order=1):
                if checkpoint_mgr.should_skip_stage("stage1_first_edit"):
                    logger.info("从检查点恢复: 跳过阶段1首次编辑")
                    stage1_data = checkpoint_mgr.get_stage_data("stage1_first_edit")
                    if stage1_data:
                        logger.debug("恢复阶段1数据: {}", stage1_data.keys())
                    edited_products = restored_products or self._build_placeholder_edits(
                        selection_rows
                    )
                    stage1 = StageOutcome(
                        name="stage1_first_edit",
                        success=True,
                        message="检查点恢复: 首次编辑已跳过",
                        details={
                            "skipped": True,
                            "restored": True,
                            "execution_round": self.execution_round,
                        },
                    )
                    stages.append(stage1)
                elif self.only_claim or self.only_stage4_publish:
                    mode_label = "仅认领模式" if self.only_claim else "仅发布模式"
                    mode_key = "only_claim" if self.only_claim else "only_stage4_publish"
                    logger.info("{}: 跳过首次编辑阶段", mode_label)
                    edited_products = self._build_placeholder_edits(selection_rows)
                    stage1 = StageOutcome(
                        name="stage1_first_edit",
                        success=True,
                        message=f"{mode_label}: 首次编辑已跳过",
                        details={
                            "skipped": True,
                            "mode": mode_key,
                            "edited_products": [prod.to_payload() for prod in edited_products],
                        },
                    )
                    stages.append(stage1)
                else:
                    try:
                        stage1, edited_products = await self._stage_first_edit(
                            page,
                            miaoshou_ctrl,
                            first_edit_ctrl,
                            selection_rows,
                        )
                    except SessionExpiredError as e:
                        # Session expired, attempt re-login
                        logger.warning("Session expired detected, attempting re-login: {}", e)
                        login_success = await login_ctrl.login(
                            username=username,
                            password=password,
                            force=True,  # Force re-login
                            headless=self.headless,
                            keep_browser_open=True,
                        )
                        if not login_success:
                            stage1 = StageOutcome(
                                name="stage1_first_edit",
                                success=False,
                                message="Re-login failed after session expired",
                                details={"session_expired": True},
                            )
                            stages.append(stage1)
                            errors.append(stage1.message)
                            self._perf_tracker.end_workflow(success=False, error=stage1.message)
                            return WorkflowExecutionResult(workflow_id, False, stages, errors)

                        # Re-login successful, dismiss popups
                        await login_ctrl.dismiss_login_overlays()

                        # Retry first edit stage
                        logger.info("Re-login successful, retrying first edit stage")
                        stage1, edited_products = await self._stage_first_edit(
                            page,
                            miaoshou_ctrl,
                            first_edit_ctrl,
                            selection_rows,
                        )

                    stages.append(stage1)
                    stage1_errors = (
                        stage1.details.get("errors") if isinstance(stage1.details, dict) else None
                    )
                    logger.info(
                        "阶段1完成: success={success}, edited_products={count}, errors={errors}",
                        success=stage1.success,
                        count=len(edited_products),
                        errors=stage1_errors,
                    )
                    if stage1.success:
                        await checkpoint_mgr.mark_stage_complete(
                            "stage1_first_edit",
                            {"products": [p.to_payload() for p in edited_products]},
                        )
                    else:
                        await checkpoint_mgr.mark_stage_failed("stage1_first_edit", stage1.message)
                        errors.append(stage1.message)
                        self._perf_tracker.end_workflow(success=False, error=stage1.message)
                        return WorkflowExecutionResult(workflow_id, False, stages, errors)

            # ===== 阶段 2: 认领 =====
            if self.only_stage4_publish:
                stage2 = StageOutcome(
                    name="stage2_claim",
                    success=True,
                    message="仅发布模式: 认领阶段已跳过",
                    details={"skipped": True, "mode": "only_stage4_publish"},
                )
                stages.append(stage2)
            else:
                async with self._perf_tracker.stage("stage2_claim", "认领", order=2):
                    if checkpoint_mgr.should_skip_stage("stage2_claim"):
                        logger.info("从检查点恢复: 跳过阶段2认领")
                        stage2 = StageOutcome(
                            name="stage2_claim",
                            success=True,
                            message="从检查点恢复: 认领已跳过",
                            details={"skipped": True, "restored": True},
                        )
                        stages.append(stage2)
                    else:
                        stage2 = await self._stage_claim_products(
                            page,
                            miaoshou_ctrl,
                            edited_products,
                        )
                        stages.append(stage2)
                        if stage2.success:
                            await checkpoint_mgr.mark_stage_complete("stage2_claim", stage2.details)
                        else:
                            await checkpoint_mgr.mark_stage_failed("stage2_claim", stage2.message)
                            errors.append(stage2.message)
                            self._perf_tracker.end_workflow(success=False, error=stage2.message)
                            return WorkflowExecutionResult(workflow_id, False, stages, errors)

            if self.only_claim and not self.only_stage4_publish:
                logger.info("仅认领模式: 停止后续批量编辑与发布阶段")
                stages.append(
                    StageOutcome(
                        name="stage3_batch_edit",
                        success=True,
                        message="仅认领模式: 批量编辑已跳过",
                        details={"skipped": True},
                    )
                )
                stages.append(
                    StageOutcome(
                        name="stage4_publish",
                        success=True,
                        message="仅认领模式: 发布阶段已跳过",
                        details={"skipped": True},
                    )
                )
                total_success = all(stage.success for stage in stages)
                self._perf_tracker.end_workflow(success=total_success)
                self._perf_reporter.print_summary()
                self._perf_tracker.save_to_file()
                if total_success:
                    await checkpoint_mgr.clear_checkpoint()
                return WorkflowExecutionResult(workflow_id, total_success, stages, errors)

            # ===== 阶段 3: 批量编辑 =====
            if self.only_stage4_publish:
                stage3 = StageOutcome(
                    name="stage3_batch_edit",
                    success=True,
                    message="仅发布模式: 批量编辑阶段已跳过",
                    details={"skipped": True, "mode": "only_stage4_publish"},
                )
                stages.append(stage3)
            else:
                async with self._perf_tracker.stage("stage3_batch_edit", "批量编辑", order=3):
                    if checkpoint_mgr.should_skip_stage("stage3_batch_edit"):
                        logger.info("从检查点恢复: 跳过阶段3批量编辑")
                        stage3 = StageOutcome(
                            name="stage3_batch_edit",
                            success=True,
                            message="从检查点恢复: 批量编辑已跳过",
                            details={"skipped": True, "restored": True},
                        )
                        stages.append(stage3)
                    else:
                        stage3 = await self._stage_batch_edit(
                            page,
                            batch_edit_ctrl,
                            edited_products,
                        )
                        stages.append(stage3)
                        if stage3.success:
                            await checkpoint_mgr.mark_stage_complete(
                                "stage3_batch_edit", stage3.details
                            )
                        else:
                            await checkpoint_mgr.mark_stage_failed(
                                "stage3_batch_edit", stage3.message
                            )
                            errors.append(stage3.message)
                            self._perf_tracker.end_workflow(success=False, error=stage3.message)
                            return WorkflowExecutionResult(workflow_id, False, stages, errors)

            # ===== 阶段 4: 发布 =====
            async with self._perf_tracker.stage("stage4_publish", "发布", order=4):
                stage4 = await self._stage_publish(
                    page,
                    publish_ctrl,
                    edited_products,
                )
                stages.append(stage4)
                if stage4.success:
                    await checkpoint_mgr.mark_stage_complete("stage4_publish", stage4.details)
                else:
                    await checkpoint_mgr.mark_stage_failed("stage4_publish", stage4.message)
                    errors.append(stage4.message)

            total_success = all(stage.success for stage in stages)

            if total_success:
                await checkpoint_mgr.clear_checkpoint()
                logger.success("工作流执行成功，检查点已清除")

            return WorkflowExecutionResult(workflow_id, total_success, stages, errors)

        except Exception as exc:
            # 全局异常捕获：处理所有未预期的异常
            logger.error(f"[CRITICAL] 工作流发生未预期异常: {exc}", exc_info=True)
            errors.append(f"未预期异常: {exc}")

            # 紧急清理
            await self._emergency_cleanup("unexpected_error")

            return WorkflowExecutionResult(
                workflow_id=workflow_id,
                total_success=False,
                stages=stages,
                errors=errors,
            )

        finally:
            # 使用安全清理方法，确保资源正确释放
            await self._safe_cleanup(workflow_id, stages, errors)

    async def _stage_first_edit(
        self,
        page,
        miaoshou_ctrl: MiaoshouController,
        first_edit_ctrl: FirstEditController,
        selections: Sequence[ProductSelectionRow],
    ) -> tuple[StageOutcome, list[EditedProduct]]:
        """阶段 1: 妙手公用采集箱首次编辑流程."""

        if not selections:
            return (
                StageOutcome(
                    name="stage1_first_edit",
                    success=False,
                    message="未找到可用的选品数据",
                    details={},
                ),
                [],
            )

        # 一次性处理所有选品，不分轮次
        working_selections = list(selections)
        logger.info(f"首次编辑: 准备一次性处理 {len(working_selections)} 个产品")

        if not working_selections:
            message = f"执行轮位 {self.execution_round} 超出可编辑范围,跳过首次编辑"
            logger.warning(message)
            return (
                StageOutcome(
                    name="stage1_first_edit",
                    success=True,
                    message=message,
                    details={
                        "owner": "",
                        "edited_products": [],
                        "errors": [],
                        "skipped": True,
                        "execution_round": self.execution_round,
                    },
                ),
                [],
            )

        staff_name = working_selections[0].owner
        staff_name = self._resolve_collection_owner(staff_name)

        if self.skip_first_edit:
            logger.info("首次编辑阶段被配置为跳过")
            placeholders = self._build_placeholder_edits(selections)
            details = {
                "owner": staff_name,
                "edited_products": [prod.to_payload() for prod in placeholders],
                "errors": [],
                "skipped": True,
            }
            return StageOutcome("stage1_first_edit", True, "首次编辑已跳过", details), placeholders

        # API 模式首次编辑（带重试机制）
        if self.use_api_first_edit:
            max_api_retries = 3
            api_result = None

            for attempt in range(max_api_retries):
                logger.info(f"使用 API 模式执行首次编辑... (尝试 {attempt + 1}/{max_api_retries})")
                api_result = await run_first_edit_via_api(
                    page,
                    list(working_selections),
                    filter_owner=staff_name,
                    # 一次性处理所有选品，不传 max_count 则使用选品数量
                )

                # 判断是否有成功的产品（部分成功也算成功，不回退 DOM）
                if api_result.success_count > 0:
                    # 构建占位符编辑结果
                    placeholders = self._build_placeholder_edits(selections)
                    details = {
                        "owner": staff_name,
                        "edited_products": [prod.to_payload() for prod in placeholders],
                        "errors": api_result.error_details,
                        "api_mode": True,
                        "api_success_count": api_result.success_count,
                        "api_failed_count": api_result.failed_count,
                        "api_attempts": attempt + 1,
                    }
                    # 根据是否有失败，生成不同的消息
                    if api_result.failed_count > 0:
                        msg = (
                            f"API 模式首次编辑部分成功: "
                            f"{api_result.success_count} 成功, {api_result.failed_count} 失败"
                        )
                        logger.warning(msg)
                    else:
                        msg = f"API 模式首次编辑完成: 成功 {api_result.success_count}"
                    return (
                        StageOutcome(
                            "stage1_first_edit",
                            True,
                            msg,
                            details,
                        ),
                        placeholders,
                    )
                else:
                    # 全部失败才重试或回退
                    if attempt < max_api_retries - 1:
                        logger.warning(
                            f"API 模式首次编辑全部失败 (尝试 {attempt + 1}/{max_api_retries})，"
                            f"等待 2 秒后重试..."
                        )
                        await asyncio.sleep(2)
                    else:
                        logger.warning(
                            f"API 模式首次编辑在 {max_api_retries} 次尝试后仍然全部失败，回退到 DOM 模式"
                        )
                        # 继续执行原有的 DOM 模式

        # DOM 模式回退所需的变量
        page_size = 20
        use_override_rows = self._selection_rows_override is not None
        start_offset = 0  # 一次性处理，从头开始

        # 导航到采集箱并筛选（带登录兜底机制）
        navigation_success = await miaoshou_ctrl.navigate_and_filter_collection_box(
            page,
            filter_by_user=staff_name,
            switch_to_tab="all",
        )

        # 检查是否被重定向到登录页（Cookie 失效）
        if not navigation_success or await self._is_redirected_to_login(page):
            logger.warning("导航失败或 Cookie 已失效，尝试重新登录...")
            # 获取凭据并重新登录
            username, password = self._resolve_credentials()
            if username and password and self.login_ctrl:
                relogin_success = await self.login_ctrl.login(
                    username=username,
                    password=password,
                    force=True,
                    headless=self.headless,
                    keep_browser_open=True,
                )
                if relogin_success:
                    logger.info("重新登录成功，再次尝试导航...")
                    # 更新 page 引用（登录后可能创建新页面）
                    page = self.login_ctrl.browser_manager.page
                    navigation_success = await miaoshou_ctrl.navigate_and_filter_collection_box(
                        page,
                        filter_by_user=staff_name,
                        switch_to_tab="all",
                    )

        if not navigation_success:
            return (
                StageOutcome(
                    name="stage1_first_edit",
                    success=False,
                    message="导航或筛选妙手公用采集箱失败（重试后仍失败）",
                    details={},
                ),
                [],
            )

        if use_override_rows:
            logger.info(
                "Execution round %s (override rows): editing batch size %s",
                self.execution_round,
                len(working_selections),
            )
        else:
            logger.info(
                "Execution round %s: editing from product #%s (round size %s)",
                self.execution_round,
                start_offset + 1,
                self.collect_count,
            )
        current_page = 1

        async def _jump_to_page(target_page: int) -> int:
            nonlocal current_page
            if target_page <= 1 and current_page == 1:
                return current_page

            selectors = [
                'input#jx-id-6212-797.jx-input__inner[type="number"]',
                'input.jx-input__inner[type="number"][aria-label]',
                'input[type="number"][aria-label]',
                '.jx-pagination__goto input[type="number"]',
            ]
            for selector in selectors:
                locator = page.locator(selector).first
                try:
                    if await locator.count() == 0:
                        continue
                    await locator.click()
                    await locator.fill(str(target_page))
                    with contextlib.suppress(Exception):
                        await locator.press("Enter")
                    await page.wait_for_timeout(800)
                    with contextlib.suppress(Exception):
                        await miaoshou_ctrl._wait_for_table_refresh(page)  # type: ignore[attr-defined]
                    current_page = target_page
                    logger.info("????? {} ???????", target_page)
                    return current_page
                except Exception as exc:
                    logger.debug("???? selector={} ??: {}", selector, exc)

            logger.warning("???????? {} ????????? {}", target_page, current_page)
            return current_page

        original_timeout_ms = getattr(
            page, "_bemg_default_timeout_ms", self.settings.browser.timeout
        )
        reduced_timeout_ms = min(original_timeout_ms, FIRST_EDIT_STAGE_TIMEOUT_MS)
        timeout_overridden = False
        if reduced_timeout_ms < original_timeout_ms:
            logger.debug(
                "临时调低 Page 默认超时: %sms -> %sms",
                original_timeout_ms,
                reduced_timeout_ms,
            )
            page.set_default_timeout(reduced_timeout_ms)
            page._bemg_default_timeout_ms = reduced_timeout_ms
            timeout_overridden = True

        try:

            async def open_edit_dialog(absolute_idx: int) -> bool:
                """打开编辑弹窗.

                使用基于行的定位策略:
                1. click_edit_product_by_index 会定位第 N 个商品行
                2. 如果行不可见,会自动滚动到目标位置
                3. 在目标行内点击编辑按钮

                Args:
                    absolute_idx: 商品的绝对索引(从0开始)
                """
                opened = await miaoshou_ctrl.click_edit_product_by_index(
                    page, absolute_idx, enable_scroll=True
                )
                if opened:
                    return True
                logger.debug("默认点击失败,尝试 Codegen 录制逻辑打开第 {} 个商品", absolute_idx + 1)
                return await open_edit_dialog_codegen(page, absolute_idx)

            errors: list[str] = []
            opened_any = False
            processed_products: list[EditedProduct] = []
            per_item_max_retry = 3

            # 计算起始页码并翻页(每页20条)
            initial_page = start_offset // page_size + 1
            if initial_page > 1:
                logger.info(f"起始偏移 {start_offset} 超过单页容量,跳转到第 {initial_page} 页")
                await _jump_to_page(initial_page)

            # 注：虚拟列表滚动已在 _click_edit_button_by_js 内部处理（基于 DOM 顺序定位算法）

            for index, selection in enumerate(working_selections):
                absolute_index = start_offset + index
                # 计算目标页码和页内相对索引
                target_page = absolute_index // page_size + 1
                page_relative_index = absolute_index % page_size

                # 如果需要翻页(商品跨页)
                if target_page != current_page:
                    logger.info(
                        f"商品 {absolute_index + 1} 在第 {target_page} 页,"
                        f"当前在第 {current_page} 页,执行翻页"
                    )
                    await _jump_to_page(target_page)

                # 为每个商品的编辑添加 Operation 级别追踪
                op_name = f"edit_product_{absolute_index + 1}"
                async with self._perf_tracker.operation(op_name, product_index=absolute_index + 1):
                    # [首次编辑诊断] 记录准备编辑的商品信息
                    logger.info(
                        "[首次编辑诊断] 准备编辑商品: 绝对索引={}, 页内索引={}, 产品名={}, 型号={}",
                        absolute_index,
                        page_relative_index,
                        selection.product_name[:20] if selection.product_name else "?",
                        selection.model_number,
                    )
                    logger.info(
                        f"编辑商品 {absolute_index + 1} "
                        f"(批次内第 {index + 1}/{len(working_selections)} 个,"
                        f"页内索引 {page_relative_index})"
                    )
                    attempt_success = False
                    for attempt in range(1, per_item_max_retry + 1):
                        opened = False
                        try:
                            # 使用页内相对索引定位商品
                            opened = await open_edit_dialog(page_relative_index)
                            if not opened:
                                raise RuntimeError("编辑弹窗打开失败")

                            await first_edit_ctrl.wait_for_dialog(page)
                            opened_any = True

                            original_title = await first_edit_ctrl.get_original_title(page)
                            base_title = original_title or selection.product_name

                            # [诊断日志] 记录对话框标题（仅用于调试，不做验证）
                            logger.debug(
                                "[首次编辑诊断] 对话框已打开, 实际标题='{}'",
                                original_title[:50] if original_title else "(空)",
                            )

                            payload_dict = self._build_first_edit_payload(selection, base_title)
                            sku_image_urls = list(payload_dict.get("sku_image_urls", []) or [])
                            size_chart_url = (
                                payload_dict.get("size_chart_image_url") or ""
                            ).strip()
                            product_video_url = (
                                payload_dict.get("product_video_url") or ""
                            ).strip()

                            # [诊断日志] 记录 SKU 图片数据状态
                            if sku_image_urls:
                                logger.info(
                                    "[SKU诊断] 产品 {} 有 {} 张 SKU 图片待上传",
                                    selection.model_number,
                                    len(sku_image_urls),
                                )
                            else:
                                logger.warning(
                                    "[SKU诊断] 产品 {} 无 SKU 图片数据 "
                                    "(image_files={}, sku_image_urls={})",
                                    selection.model_number,
                                    getattr(selection, "image_files", None),
                                    getattr(selection, "sku_image_urls", None),
                                )

                            # [诊断日志] 记录尺寸图数据状态
                            if size_chart_url:
                                logger.info(
                                    "[尺寸图诊断] 产品 {} 有尺寸图待上传: {}",
                                    selection.model_number,
                                    size_chart_url[:80] + "..."
                                    if len(size_chart_url) > 80
                                    else size_chart_url,
                                )
                            else:
                                logger.warning(
                                    "[尺寸图诊断] 产品 {} 无尺寸图数据 (原始值='{}')",
                                    selection.model_number,
                                    getattr(selection, "size_chart_image_url", None),
                                )

                            hook_fn = self._build_first_edit_hook(
                                first_edit_ctrl=first_edit_ctrl,
                                sku_image_urls=sku_image_urls,
                                size_chart_url=size_chart_url,
                                product_video_url=product_video_url,
                            )

                            logger.info("使用 Codegen 方式填写首次编辑弹窗(已禁用JS注入)")
                            success = await fill_first_edit_dialog_codegen(page, payload_dict)

                            if not success:
                                raise RuntimeError("Codegen 填写失败")

                            if hook_fn is not None:
                                hook_modified = False
                                try:
                                    hook_result = await hook_fn(page)
                                    hook_modified = True
                                    if hook_result:
                                        logger.success("SKU 图片同步完成")
                                    else:
                                        logger.warning("SKU 图片同步未成功")
                                except Exception as exc:  # pragma: no cover
                                    hook_modified = True
                                    logger.error("SKU 图片同步异常: {}", exc)
                                finally:
                                    if hook_modified:
                                        saved_after_hook = await first_edit_ctrl.save_changes(
                                            page, wait_for_close=False
                                        )
                                        if not saved_after_hook:
                                            logger.warning(
                                                "SKU/媒体操作后保存失败,可能触发离开提示"
                                            )

                            processed_products.append(
                                self._create_edited_product(
                                    selection, absolute_index, payload_dict["title"]
                                )
                            )
                            attempt_success = True
                            break
                        except Exception as exc:
                            errors.append(
                                f"第{absolute_index + 1}个商品处理失败"
                                f"(第{attempt}/{per_item_max_retry}次): {exc}"
                            )
                            logger.warning(
                                "商品 {} 第 {} 次尝试失败,准备重试", absolute_index + 1, attempt
                            )
                            await page.wait_for_timeout(500)
                        finally:
                            if opened:
                                with contextlib.suppress(Exception):
                                    await first_edit_ctrl.close_dialog(page)

                    if not attempt_success:
                        logger.error(
                            "商品 {} 在 {} 次尝试后仍未成功", absolute_index + 1, per_item_max_retry
                        )

            if not opened_any:
                message = "采集箱无可编辑商品,首次编辑阶段跳过"
                logger.warning(message)
                details = {
                    "owner": staff_name,
                    "edited_products": [],
                    "errors": errors or ["未能打开任何首次编辑弹窗"],
                    "skipped": True,
                    "execution_round": self.execution_round,
                }
                return StageOutcome("stage1_first_edit", True, message, details), []

            success = bool(processed_products)
            message = "完成首次编辑处理" if not errors else "首次编辑存在部分失败"
            details = {
                "owner": staff_name,
                "edited_products": [product.to_payload() for product in processed_products],
                "errors": errors,
                "execution_round": self.execution_round,
            }

            return StageOutcome("stage1_first_edit", success, message, details), processed_products
        finally:
            if timeout_overridden:
                logger.debug(
                    "恢复 Page 默认超时: %sms",
                    original_timeout_ms,
                )
                page.set_default_timeout(original_timeout_ms)
                page._bemg_default_timeout_ms = original_timeout_ms

    def _build_first_edit_hook(
        self,
        *,
        first_edit_ctrl: FirstEditController,
        sku_image_urls: list[str],
        size_chart_url: str | None,
        product_video_url: str | None,
    ) -> Callable[[Page], Awaitable[bool]] | None:
        """构造首次编辑混合策略的附加操作 hook."""

        hooks: list[Callable[[Page], Awaitable[bool]]] = []

        if sku_image_urls:
            urls_for_hook = [url.strip() for url in sku_image_urls if url and url.strip()]

            if urls_for_hook:

                async def _sync_sku_images(target_page) -> bool:
                    try:
                        return await self.image_manager.replace_sku_images_with_urls(
                            target_page, urls_for_hook
                        )
                    except Exception as exc:
                        logger.error("SKU 图片同步异常: {}", exc)
                        return False

                hooks.append(_sync_sku_images)

        # 尺寸图/视频已在 fill_first_edit_dialog_codegen 内完成,这里不再重复执行
        # 仅保留 SKU 图同步 hook,避免重复等待

        if not hooks:
            return None

        async def _run_hooks(target_page) -> bool:
            overall = True
            for hook in hooks:
                try:
                    result = await hook(target_page)
                    overall = overall and (result is not False)
                except Exception as exc:
                    logger.error("首次编辑附加步骤执行异常: {}", exc)
                    overall = False
            return overall

        return _run_hooks

    def _build_first_edit_payload(
        self,
        selection: ProductSelectionRow,
        base_title: str,
    ) -> dict[str, Any]:
        """根据选品和成本信息构造首次编辑 payload."""

        model_number = selection.model_number or ""
        new_title = self._append_title_suffix(base_title, model_number)

        cost_price = self._resolve_cost_price(selection)
        price_result = self.price_calculator.calculate_batch([cost_price])[0]
        weight_g = self._resolve_weight(selection)
        dimensions = self._resolve_dimensions(selection)
        stock = max(selection.collect_count * 20, 50)
        spec_unit_name = selection.spec_unit or "规格"

        specs: list[dict[str, Any]] = []
        variants_payload: list[dict[str, Any]] = []

        if selection.spec_options:
            options = [option.strip() for option in selection.spec_options if option.strip()]
            if options:
                specs.append(
                    {
                        "name": spec_unit_name,
                        "options": options,
                    }
                )

                for idx, option in enumerate(options):
                    variant_cost = cost_price
                    if selection.variant_costs and idx < len(selection.variant_costs):
                        variant_cost = float(selection.variant_costs[idx])

                    price_variant = self.price_calculator.calculate_batch([variant_cost])[0]
                    variants_payload.append(
                        {
                            "option": option,
                            "price": round(price_variant.suggested_price, 2),
                            "supply_price": round(price_variant.supply_price, 2),
                            "source_price": round(price_variant.real_supply_price, 2),
                            "stock": stock,
                        }
                    )

        # 提取规格选项数组用于 SKU 规格替换
        spec_array: list[str] = []
        if selection.spec_options:
            spec_array = [option.strip() for option in selection.spec_options if option.strip()]
            if spec_array:
                logger.debug("SKU 规格数组: {}", spec_array)

        payload: dict[str, Any] = {
            "title": new_title,
            "product_number": model_number,
            "price": round(price_result.suggested_price, 2),
            "supply_price": round(price_result.supply_price, 2),
            "source_price": round(price_result.real_supply_price, 2),
            "stock": stock,
            "weight_g": weight_g,
            "length_cm": dimensions[0],
            "width_cm": dimensions[1],
            "height_cm": dimensions[2],
            "supplier_link": "",
            "specs": specs,
            "variants": variants_payload,
            "spec_array": spec_array,  # SKU 规格替换数组
            "spec_unit": spec_unit_name,
        }

        if selection.size_chart_image_url:
            payload["size_chart_image_url"] = selection.size_chart_image_url
            logger.debug("添加尺寸图URL: {}", payload["size_chart_image_url"][:100])

        if getattr(selection, "sku_image_urls", None):
            payload["sku_image_urls"] = selection.sku_image_urls
            logger.debug("添加 SKU 图片: {}", len(selection.sku_image_urls))

        if getattr(selection, "product_video_url", None):
            payload["product_video_url"] = selection.product_video_url
            logger.debug("添加产品视频URL: {}", payload["product_video_url"][:100])

        return payload

    def _build_placeholder_edits(
        self, selections: Sequence[ProductSelectionRow]
    ) -> list[EditedProduct]:
        """根据选品表构造占位首次编辑结果."""

        placeholders: list[EditedProduct] = []
        for index, selection in enumerate(selections):
            cost_price = self._resolve_cost_price(selection)
            price_result = self.price_calculator.calculate_batch([cost_price])[0]
            weight_g = self._resolve_weight(selection)
            dimensions = self._resolve_dimensions(selection)
            title = self._append_title_suffix(selection.product_name, selection.model_number or "")

            placeholders.append(
                EditedProduct(
                    index=index,
                    selection=selection,
                    title=title,
                    cost_price=cost_price,
                    price=price_result,
                    weight_g=weight_g,
                    dimensions_cm=dimensions,
                )
            )

        return placeholders

    def _create_edited_product(
        self,
        selection: ProductSelectionRow,
        index: int,
        title: str,
    ) -> EditedProduct:
        """构造用于后续阶段的 EditedProduct."""

        cost_price = self._resolve_cost_price(selection)
        price_result = self.price_calculator.calculate_batch([cost_price])[0]
        weight_g = self._resolve_weight(selection)
        dimensions = self._resolve_dimensions(selection)

        return EditedProduct(
            index=index,
            selection=selection,
            title=title,
            cost_price=cost_price,
            price=price_result,
            weight_g=weight_g,
            dimensions_cm=dimensions,
        )

    async def _stage_claim_products(
        self,
        page,
        miaoshou_ctrl: MiaoshouController,
        edited_products: Sequence[EditedProduct],
    ) -> StageOutcome:
        """阶段 2: 认领产品到 Temu 全托管.

        默认使用 API 直接认领（更快速、更稳定），如果 API 失败则回退到 DOM 操作。
        """

        if self.skip_first_edit:
            message = "首次编辑被跳过, 认领阶段随之跳过"
            logger.warning(message)
            return StageOutcome(
                name="stage2_claim",
                success=True,
                message=message,
                details={"skipped": True, "expected_total": 0},
            )

        if not edited_products:
            message = "首次编辑未产生可认领商品,认领阶段跳过"
            logger.warning(message)
            return StageOutcome(
                name="stage2_claim",
                success=True,
                message=message,
                details={"skipped": True, "expected_total": 0},
            )

        # edited_products 是当前批次要处理的商品数据
        working_products = list(edited_products)
        selection_count = len(working_products)  # 认领所有产品，分批在后面处理

        # 如果当前批次没有可用商品，直接跳过认领阶段
        if len(working_products) == 0:
            logger.info(f"执行轮次 {self.execution_round} 无可用商品，跳过认领阶段")
            return StageOutcome(
                name="stage2_claim",
                success=True,
                message="NO_PRODUCTS_FOR_ROUND",
                details={
                    "execution_round": self.execution_round,
                    "skipped": True,
                },
            )

        # 优先使用 web 前端提供的 collection_owner，否则从 edited_products 获取
        filter_owner: str | None = None
        owner_candidate = self.collection_owner_override or (
            getattr(edited_products[0].selection, "owner", "") if edited_products else ""
        )
        if owner_candidate:
            try:
                filter_owner = self._resolve_collection_owner(owner_candidate)
                logger.info(f"认领阶段使用创建人员筛选: '{filter_owner}'")
            except RuntimeError as exc:
                logger.warning("Unable to resolve collection owner for claim stage: {}", exc)
                filter_owner = None

        # ==================== 使用 API 认领 ====================
        logger.info(
            "认领阶段 (API 模式): 目标 %s 个商品, 每商品认领 %s 次",
            selection_count,
            self.claim_times,
        )

        total_claimed = 0
        api_success = True
        api_failures: list[str] = []

        # 一次性认领所有产品（不分轮次）
        detail_ids: list[str] = []

        # 使用 API 获取产品列表（通过 page.evaluate + fetch）
        # API: POST /api/move/common_collect_box/searchDetailList
        logger.info("使用 API 获取产品 ID 列表")

        # 获取 owner_account_id（如果有筛选）
        owner_account_id = ""
        if filter_owner:
            logger.info(f"需要筛选创建人员: {filter_owner}")
            # 从产品列表中查找匹配创建人员的 subAppAccountId
            # 需要多页搜索因为目标创建人员的产品可能不在前面
            # 匹配策略：模糊匹配用户名部分（括号前的名字或括号内的账号名）
            sample_result = await page.evaluate(
                r"""
                async (filterName) => {
                    try {
                        // 搜索多页以找到目标创建人员
                        const allOwners = new Map();  // ownerName -> accountId
                        const filterLower = filterName.toLowerCase();

                        for (let pageNo = 1; pageNo <= 10; pageNo++) {
                            const formData = new URLSearchParams();
                            formData.append('pageNo', String(pageNo));
                            formData.append('pageSize', '100');
                            formData.append('filter[tabPaneName]', 'all');

                            const resp = await fetch(
                                '/api/move/common_collect_box/searchDetailList',
                                {
                                    method: 'POST',
                                    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                                    body: formData.toString()
                                }
                            );
                            const data = await resp.json();
                            if (data.result !== 'success' || !data.detailList) break;

                            for (const item of data.detailList) {
                                const ownerName = item.ownerSubAccountAliasName || '';
                                const accountId = item.subAppAccountId;
                                if (ownerName && accountId && !allOwners.has(ownerName)) {
                                    allOwners.set(ownerName, accountId);
                                }
                                // 多种匹配方式
                                if (ownerName) {
                                    const ownerLower = ownerName.toLowerCase();
                                    // 1. 完全包含
                                    // 2. 用户名部分匹配（括号前的名字）
                                    // 3. 账号部分匹配（括号内）
                                    const nameMatch = ownerLower.includes(filterLower);
                                    const bracketMatch = ownerName.match(/\(([^)]+)\)/);
                                    const accountMatch = bracketMatch &&
                                        bracketMatch[1].toLowerCase().includes(filterLower);
                                    const prefixMatch = ownerName.split('(')[0]
                                        .toLowerCase().includes(filterLower);

                                    if (nameMatch || accountMatch || prefixMatch) {
                                        return {
                                            success: true,
                                            accountId: accountId,
                                            ownerName: ownerName
                                        };
                                    }
                                }
                            }
                            // 如果没有更多数据，停止
                            if (data.detailList.length < 100) break;
                        }
                        // 返回所有可用的创建人员名称和 ID
                        const ownerList = [];
                        for (const [name, id] of allOwners.entries()) {
                            ownerList.push({name, id});
                        }
                        return {
                            success: false,
                            availableOwners: ownerList.slice(0, 30)
                        };
                    } catch (e) {
                        return {error: e.message};
                    }
                }
                """,
                filter_owner,
            )
            if sample_result and sample_result.get("success"):
                owner_account_id = str(sample_result.get("accountId", ""))
                owner_name = sample_result.get("ownerName", "")
                logger.info(f"找到创建人员: {owner_name} -> accountId={owner_account_id}")
            elif sample_result and "availableOwners" in sample_result:
                owners = sample_result.get("availableOwners", [])
                names_with_ids = [f"{o['name']}({o['id']})" for o in owners[:15]]
                logger.warning(f"未找到匹配 '{filter_owner}' 的账号，可用: {names_with_ids}")
            elif sample_result and sample_result.get("error"):
                logger.error(f"查找创建人员失败: {sample_result.get('error')}")

        # 调用 searchDetailList API 获取产品列表
        api_result = await page.evaluate(
            """
            async (params) => {
                try {
                    const formData = new URLSearchParams();
                    formData.append('pageNo', params.pageNo);
                    formData.append('pageSize', params.pageSize);
                    formData.append('filter[tabPaneName]', params.tabPaneName);
                    if (params.ownerAccountId) {
                        formData.append('filter[ownerAccountIds][0]', params.ownerAccountId);
                    }

                    const resp = await fetch(
                        '/api/move/common_collect_box/searchDetailList',
                        {
                            method: 'POST',
                            headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                            body: formData.toString()
                        }
                    );
                    return await resp.json();
                } catch (e) {
                    return {error: e.message};
                }
            }
            """,
            {
                "pageNo": "1",
                "pageSize": str(selection_count + 10),  # 多获取一些
                "tabPaneName": "all",
                "ownerAccountId": owner_account_id,
            },
        )

        if api_result and api_result.get("result") == "success":
            detail_list = api_result.get("detailList", [])
            total_available = api_result.get("total", 0)
            logger.info(f"API 获取产品列表成功: {len(detail_list)} 条 / 共 {total_available} 条")

            # 提取产品 ID - 使用 commonCollectBoxDetailId 字段
            all_ids = []
            for item in detail_list:
                product_id = item.get("commonCollectBoxDetailId")
                if product_id:
                    all_ids.append(str(product_id))
            logger.info(f"提取到 {len(all_ids)} 个产品 ID: {all_ids[:5]}...")

            # 取前 selection_count 个产品
            detail_ids = all_ids[:selection_count]
        else:
            error_msg = api_result.get("error") or api_result.get("message", "未知错误")
            logger.warning(f"API 获取产品列表失败: {error_msg}")

        if not detail_ids:
            logger.warning("无法获取产品 ID，认领阶段失败")
            api_success = False
        else:
            logger.info(f"提取到 {len(detail_ids)} 个产品 ID: {detail_ids[:5]}...")

            # Step 3: 分批次使用 API 认领（每批 5 个产品，每批认领 claim_times 次）
            batch_size = 5
            total_batches = (len(detail_ids) + batch_size - 1) // batch_size

            for batch_idx in range(total_batches):
                batch_start = batch_idx * batch_size
                batch_end = min(batch_start + batch_size, len(detail_ids))
                batch_ids = detail_ids[batch_start:batch_end]

                logger.info(
                    f"批次 {batch_idx + 1}/{total_batches}: "
                    f"认领 {len(batch_ids)} 个产品，每个 {self.claim_times} 次"
                )

                # 每批产品认领 claim_times 次
                for claim_round in range(1, self.claim_times + 1):
                    try:
                        result = await miaoshou_ctrl.claim_specific_products_via_api(
                            page,
                            detail_ids=batch_ids,
                            platform="pddkj",
                        )
                        if result.get("success"):
                            claimed_count = result.get("claimed_count", 0)
                            total_claimed += claimed_count
                            logger.success(
                                f"  批次{batch_idx + 1} 第{claim_round}次: "
                                f"成功认领 {claimed_count} 个"
                            )
                        else:
                            msg = f"批次{batch_idx + 1} 第{claim_round}次失败: {result.get('message')}"
                            api_failures.append(msg)
                            logger.warning(f"  {msg}")
                    except Exception as exc:
                        msg = f"批次{batch_idx + 1} 第{claim_round}次异常: {exc}"
                        api_failures.append(msg)
                        logger.error(f"  {msg}")

        # 判断 API 认领结果
        expected_total = selection_count * self.claim_times
        api_success = total_claimed > 0

        if api_success:
            message = f"API 认领成功: 共认领 {total_claimed} 次 (期望 {expected_total} 次)"
            if api_failures:
                message += f", 存在 {len(api_failures)} 个失败"
            logger.success(message)
        else:
            message = f"API 认领失败: 期望 {expected_total} 次, 实际 0 次"
            if api_failures:
                message += f", 失败详情: {api_failures}"
            logger.error(message)

        return StageOutcome(
            name="stage2_claim",
            success=api_success,
            message=message,
            details={
                "method": "api",
                "selected_count": selection_count,
                "total_claimed": total_claimed,
                "expected_total": expected_total,
                "claim_rounds": self.claim_times,
                "api_failures": api_failures,
                "detail_ids": detail_ids if detail_ids else [],
            },
        )

    async def _stage_batch_edit(
        self,
        page,
        batch_edit_ctrl: BatchEditController,
        edited_products: Sequence[EditedProduct],
    ) -> StageOutcome:
        """阶段 3: Temu 全托管批量编辑 18 步,增加重试保障.

        支持三种模式:
        1. use_api_batch_edit=True: API 模式，仅编辑纯数据字段（最快速）
        2. use_codegen_batch_edit=True: Codegen DOM 模式（推荐，完整 18 步）
        3. 默认: Legacy BatchEditController 模式
        """

        if not edited_products:
            message = "无待批量编辑商品,批量编辑阶段跳过"
            logger.warning(message)
            return StageOutcome(
                name="stage3_batch_edit",
                success=True,
                message=message,
                details={"skipped": True},
            )

        reference = edited_products[0]
        max_attempts = 3

        # 获取 owner 信息用于筛选(与首次编辑和认领阶段保持一致)
        filter_owner: str | None = None
        if edited_products:
            owner_candidate = getattr(edited_products[0].selection, "owner", "") or ""
            try:
                filter_owner = self._resolve_collection_owner(owner_candidate)
                logger.info("二次编辑阶段将按人员筛选: {}", filter_owner)
            except RuntimeError as exc:
                logger.warning("无法解析二次编辑阶段的创建人员: {}", exc)
                filter_owner = None

        # ===== API 批量编辑模式 =====
        if self.use_api_batch_edit:
            # 二次编辑处理数量 = 选品数量 * claim_times（认领次数）
            selection_count = len(edited_products)
            batch_edit_count = selection_count * self.claim_times
            logger.info(
                f"使用 API 方式执行批量编辑: {batch_edit_count} 个产品 "
                f"(选品 {selection_count} * 认领 {self.claim_times} 次)"
            )
            payload = self._build_api_batch_edit_payload()

            api_result = await run_batch_edit_via_api(
                page,
                payload,
                filter_owner=filter_owner,
                max_products=batch_edit_count,
            )

            success = api_result.get("success", False)
            edited_count = api_result.get("edited_count", 0)
            total_count = api_result.get("total_count", 0)

            message = (
                f"API 批量编辑完成: {edited_count}/{total_count} 个产品"
                if success
                else f"API 批量编辑失败: {api_result.get('error', '未知错误')}"
            )

            return StageOutcome(
                name="stage3_batch_edit",
                success=success,
                message=message,
                details={
                    "mode": "api",
                    "edited_count": edited_count,
                    "total_count": total_count,
                    "error": api_result.get("error"),
                },
            )

        # ===== DOM 批量编辑模式 =====
        def _build_codegen_payload() -> dict[str, object]:
            manual_source = self.manual_file_override
            manual_path_str = ""
            if manual_source:
                if manual_source.exists():
                    manual_path_str = str(manual_source)
                else:
                    logger.warning("说明书文件不存在, 将跳过上传: {}", manual_source)

            return {
                "category_path": ["收纳用品", "收纳篮,箱子,盒子", "盖式储物箱"],
                "category_attrs": {
                    "product_use": "多用途",
                    "shape": "其他形状",
                    "material": "其他材料",
                    "closure_type": "其他闭合类型",
                    "style": "当代",
                },
                "outer_package_image": str(self.outer_package_image_override)
                if self.outer_package_image_override
                else "",
                "manual_file": manual_path_str,
            }

        async def _run_codegen_stage(tag: str) -> StageOutcome:
            payload = _build_codegen_payload()
            batch_result = await run_batch_edit(page, payload, filter_owner=filter_owner)

            total = batch_result.get("total_steps", 18)
            success_steps = batch_result.get("completed_steps", 0)
            threshold = int(total * 0.9)
            overall_success = batch_result.get("success", False)

            message = (
                f"批量编辑成功 {success_steps}/{total} 步 ({tag})"
                if overall_success
                else f"批量编辑仅成功 {success_steps}/{total} 步 ({tag}), 低于阈值 {threshold}"
            )

            return StageOutcome(
                name="stage3_batch_edit",
                success=overall_success,
                message=message,
                details=batch_result,
            )

        if self.use_codegen_batch_edit:
            # 使用 codegen 录制的批量编辑模块(自带导航)
            logger.info("使用 Codegen 录制模块执行批量编辑 18 步")
            last_outcome: StageOutcome | None = None
            for attempt in range(1, max_attempts + 1):
                outcome = await _run_codegen_stage("Codegen")
                outcome.details["attempts"] = attempt  # type: ignore[index]
                if outcome.success:
                    return outcome
                last_outcome = outcome
                logger.warning("Codegen 批量编辑第 {}/{} 次失败,准备重试", attempt, max_attempts)
                await page.wait_for_timeout(800)
            if last_outcome:
                last_outcome.message = f"{last_outcome.message}(已重试 {max_attempts} 次)"
                return last_outcome
            return await _run_codegen_stage("Codegen")

        # 使用原有的批量编辑控制器(需要先导航)
        logger.info("使用原有批量编辑控制器执行 18 步")

        target_count = max(edited_products.__len__() * self.claim_times, 20)
        if hasattr(batch_edit_ctrl, "navigate_to_batch_edit"):
            payload = {
                "product_name": reference.selection.product_name if reference else "",
                "cost_price": reference.cost_price if reference else 0.0,
                "weight": reference.weight_g if reference else 6000,
                "length": reference.dimensions_cm[0] if reference else 85,
                "width": reference.dimensions_cm[1] if reference else 60,
                "height": reference.dimensions_cm[2] if reference else 50,
            }

            last_stage: StageOutcome | None = None
            for attempt in range(1, max_attempts + 1):
                navigation_ok = await batch_edit_ctrl.navigate_to_batch_edit(
                    select_count=target_count
                )
                if not navigation_ok:
                    last_stage = StageOutcome(
                        name="stage3_batch_edit",
                        success=False,
                        message="无法进入Temu全托管批量编辑页面",
                        details={"attempts": attempt},
                    )
                    await page.wait_for_timeout(500)
                    continue

                batch_result = await batch_edit_ctrl.execute_all_steps(payload)

                total = batch_result.get("total", 18)
                success_steps = batch_result.get("success", 0)
                threshold = int(total * 0.9)
                overall_success = success_steps >= threshold
                message = (
                    f"批量编辑成功 {success_steps}/{total} 步"
                    if overall_success
                    else f"批量编辑仅成功 {success_steps}/{total} 步, 低于阈值 {threshold}"
                )

                stage = StageOutcome(
                    name="stage3_batch_edit",
                    success=overall_success,
                    message=message,
                    details={**batch_result, "attempts": attempt},
                )
                last_stage = stage

                if overall_success:
                    return stage

                logger.warning("批量编辑第 {}/{} 次未达标,准备重试", attempt, max_attempts)
                await page.wait_for_timeout(800)

            if last_stage:
                last_stage.message = f"{last_stage.message}(已重试 {max_attempts} 次)"
                return last_stage

        logger.info("检测到 Legacy BatchEditController,回退到 Codegen 流程")
        return await _run_codegen_stage("Legacy")

    async def _stage_publish(
        self,
        page,
        publish_ctrl: PublishController,
        edited_products: Sequence[EditedProduct],
    ) -> StageOutcome:
        """阶段 4: 选择店铺,设置供货价,批量发布."""

        if not edited_products:
            message = "无待发布商品,发布阶段跳过"
            logger.warning(message)
            return StageOutcome(
                name="stage4_publish",
                success=True,
                message=message,
                details={"skipped": True},
            )

        shop_name = self._resolve_shop_name(edited_products)

        # 使用 API 方式发布
        # 发布数量 = 选品数量 * claim_times（认领次数）
        selection_count = len(edited_products)
        publish_count = selection_count * self.claim_times
        logger.info(
            f"使用 API 方式执行发布: {publish_count} 个产品 "
            f"(选品 {selection_count} * 认领 {self.claim_times} 次)"
        )

        # 获取筛选人员
        owner_candidate = self.collection_owner_override or (
            edited_products[0].selection.owner if edited_products else ""
        )
        filter_owner = self._resolve_collection_owner(owner_candidate) if owner_candidate else None

        api_result = await run_publish_via_api(
            page,
            filter_owner=filter_owner,
            shop_id="9134811",  # 默认店铺 ID
            max_products=publish_count,
        )

        success = api_result.get("success", False)
        published_count = api_result.get("published_count", 0)
        error_msg = api_result.get("error")

        if success:
            message = f"API 发布完成: 成功发布 {published_count} 个产品"
        else:
            message = f"API 发布失败: {error_msg}"

        details = {
            "shop_name": shop_name,
            "publish_success": success,
            "published_count": published_count,
            "detail_ids": api_result.get("detail_ids", []),
            "error": error_msg,
        }

        return StageOutcome("stage4_publish", success, message, details)

    def _prepare_selection_rows(self) -> list[ProductSelectionRow]:
        """读取/生成选品数据."""

        if self._selection_rows_override is not None:
            if not self._selection_rows_override:
                raise RuntimeError("外部注入的选品数据为空, 无法继续执行")
            logger.info(
                "使用外部注入的选品数据 (共 %s 条)",
                len(self._selection_rows_override),
            )
            return self._finalize_selection_rows(self._selection_rows_override)

        if not self.selection_table_path:
            raise RuntimeError("未指定选品表, 请通过 --input=路径 提供 Excel 文件")

        if not self.selection_table_path.exists():
            raise FileNotFoundError(
                f"选品表不存在: {self.selection_table_path}. 请确认路径是否正确"
            )

        try:
            rows: list[ProductSelectionRow] = self.selection_reader.read_excel(
                str(self.selection_table_path)
            )
            logger.info(
                "选品表已加载: {} (总计 {} 条)",
                self.selection_table_path,
                len(rows),
            )
        except Exception as exc:
            raise RuntimeError(f"读取选品表失败: {exc}") from exc

        if not rows:
            raise RuntimeError(f"选品表 {self.selection_table_path} 未包含有效数据, 无法继续执行")

        return self._finalize_selection_rows(rows)

    def _finalize_selection_rows(
        self, rows: Sequence[ProductSelectionRow]
    ) -> list[ProductSelectionRow]:
        """一次性处理所有选品数据并输出日志."""

        # 一次性处理所有选品，不再按轮次截断
        limited_rows = list(rows)

        for idx, row in enumerate(limited_rows, start=1):
            cost_value = float(row.cost_price) if row.cost_price else 0.0
            logger.info(
                "选品[{}]: 负责人={}, 商品={}, 型号={}, 采集数={}, 成本={:.2f}",
                idx,
                row.owner,
                row.product_name,
                row.model_number,
                row.collect_count,
                cost_value,
            )

        return limited_rows

    def _resolve_credentials(self) -> tuple[str, str]:
        """解析登录凭证."""

        username = (
            os.getenv("MIAOSHOU_USERNAME")
            or os.getenv("TEMU_USERNAME")
            or self.settings.temu_username
        )
        password = (
            os.getenv("MIAOSHOU_PASSWORD")
            or os.getenv("TEMU_PASSWORD")
            or self.settings.temu_password
        )
        return username or "", password or ""

    def _resolve_optional_path(self, raw: Path | str | None, description: str) -> Path | None:
        """解析可选的本地文件路径."""

        if not raw:
            return None

        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            candidate = (self._app_root / candidate).resolve()
        if candidate.exists():
            logger.info("使用自定义{}: {}", description, candidate)
            return candidate

        logger.warning("{} 不存在: {},将忽略该配置", description, candidate)
        return None

    def _resolve_cost_price(self, selection: ProductSelectionRow) -> float:
        """根据选品或Excel推断成本价."""

        if selection.cost_price:
            return float(selection.cost_price)

        cost = self.product_reader.get_cost_price(selection.product_name)
        if cost:
            return float(cost)

        logger.warning("无法获取成本价, 使用默认 20.0 元")
        return 20.0

    def _resolve_weight(self, selection: ProductSelectionRow) -> int:
        """解析或生成重量 (克)."""

        weight = self.product_reader.get_weight(selection.product_name)
        if weight:
            return int(weight)
        return ProductDataReader.generate_random_weight()

    def _resolve_dimensions(self, selection: ProductSelectionRow) -> tuple[int, int, int]:
        """解析或生成尺寸 (长宽高, 厘米)."""

        dims = self.product_reader.get_dimensions(selection.product_name)
        if dims:
            return (
                int(dims["length"]),
                int(dims["width"]),
                int(dims["height"]),
            )
        random_dims = ProductDataReader.generate_random_dimensions()
        return (
            int(random_dims["length"]),
            int(random_dims["width"]),
            int(random_dims["height"]),
        )

    @staticmethod
    def _append_title_suffix(title: str, suffix: str) -> str:
        """确保标题末尾附加商品编号."""

        base = title.strip()
        normalized_suffix = suffix.strip()
        if not normalized_suffix:
            return base
        if normalized_suffix in base:
            return base
        return f"{base} {normalized_suffix}".strip()

    async def _update_title_only(self, page: Page, title: str) -> bool:
        """仅更新编辑弹窗中的标题字段."""

        selectors = [
            ".collect-box-editor-dialog-V2 input.jx-input__inner[type='text']",
            "input[placeholder*='标题']",
            "input[placeholder*='Title']",
        ]

        for selector in selectors:
            try:
                locator = page.locator(selector).first
                if await locator.count() == 0:
                    continue

                await locator.wait_for(state="visible", timeout=2_000)
                await locator.click()
                await locator.fill("")
                await locator.press("ControlOrMeta+a")
                await locator.fill(title)
                logger.success("✓ 已更新标题: {}", title)
                # await page.wait_for_timeout(300)
                return True
            except Exception:
                continue

        logger.error("✗ 未能找到标题输入框, 无法更新标题")
        return False

    async def _is_redirected_to_login(self, page) -> bool:
        """检查页面是否被重定向到登录页.

        用于检测 Cookie 失效的情况。

        Args:
            page: Playwright Page 对象

        Returns:
            True 如果被重定向到登录页
        """
        if not page:
            return True

        try:
            url = page.url.lower()

            # 检测重定向到登录页的 URL 模式
            if (
                "redirect=" in url
                or "redirect%3d" in url
                or "sub_account/users" in url
                or "login" in url
            ):
                logger.debug(f"检测到重定向到登录页: {url}")
                return True

            # 检测登录表单
            login_form_count = await page.locator(
                "input[name='mobile'], input[name='username'], "
                "input[placeholder*='手机'], input[placeholder*='账号']"
            ).count()
            login_btn_count = await page.locator(
                "button:has-text('登录'), button:has-text('立即登录')"
            ).count()

            if login_form_count > 0 and login_btn_count > 0:
                logger.debug("检测到登录表单")
                return True

            return False

        except Exception as e:
            logger.debug(f"检查登录重定向时出错: {e}")
            return False

    def _resolve_collection_owner(self, owner_value: str) -> str:
        """解析妙手采集箱筛选所需的创建人员显示名."""

        configured_owner = self.settings.business.collection_owner.strip()
        selection_owner = owner_value.strip()
        username = self.settings.miaoshou_username.strip()
        override = getattr(self, "collection_owner_override", "").strip()

        if override:
            owner = override
        elif configured_owner:
            owner = configured_owner
        elif selection_owner:
            owner = selection_owner
        else:
            owner = ""

        if not owner and username:
            owner = username

        if not owner:
            raise RuntimeError("无法解析妙手采集箱创建人员, 请检查配置或选品表")

        if "(" in owner and ")" in owner:
            return owner

        if username:
            return f"{owner}({username})"
        return owner

    def _build_api_batch_edit_payload(self) -> dict[str, object]:
        """构建 API 批量编辑的 payload.

        Returns:
            包含类目属性等编辑数据的字典
        """
        return {
            "category_path": ["收纳用品", "收纳篮,箱子,盒子", "盖式储物箱"],
            "category_attrs": {
                "product_use": "多用途",
                "shape": "其他形状",
                "material": "其他材料",
                "closure_type": "其他闭合类型",
                "style": "当代",
            },
        }

    def _resolve_image_base_dir(self) -> Path:
        """解析图片基础目录路径.

        优先级:
        1. 环境变量 IMAGE_BASE_DIR
        2. 配置文件中的路径
        3. 默认路径: data/input/10月新品可推

        Returns:
            图片基础目录的 Path 对象.
        """
        # 从环境变量读取
        env_dir = os.getenv("IMAGE_BASE_DIR")
        if env_dir:
            path = Path(env_dir)
            if not path.is_absolute():
                # 如果是相对路径, 相对于项目根目录
                path = self._get_project_root() / path
            return path

        # 使用默认路径
        default_dir = (
            self._get_project_root()
            / "apps"
            / "temu-auto-publish"
            / "data"
            / "input"
            / "10月新品可推"
        )
        return default_dir

    def _get_project_root(self) -> Path:
        """获取项目根目录."""
        # 从当前文件向上查找, 找到包含 pyproject.toml 的目录
        current = Path(__file__).resolve()
        for parent in current.parents:
            if (parent / "pyproject.toml").exists():
                return parent
        # 如果找不到, 返回当前文件所在的上上上级目录(apps/temu-auto-publish/src -> apps/temu-auto-publish -> apps -> workspace)
        return Path(__file__).resolve().parents[3]

    def _resolve_shop_name(self, edited_products: Sequence[EditedProduct]) -> str:
        """解析发布店铺名称."""

        env_shop = os.getenv("MIAOSHOU_SHOP_NAME") or os.getenv("TEMU_SHOP_NAME")
        if env_shop:
            return env_shop

        workflow_shop = getattr(self.settings.workflow, "default_shop", None)
        if workflow_shop:
            return str(workflow_shop)

        if edited_products:
            return edited_products[0].selection.owner or "自动化店铺"

        return "自动化店铺"


__all__ = [
    "CompletePublishWorkflow",
    "EditedProduct",
    "StageOutcome",
    "WorkflowExecutionResult",
]
