"""
@PURPOSE: 浏览器管理器, 使用 Playwright 管理浏览器实例, 支持反检测、Cookie 管理与版本一致性校验
@OUTLINE:
  - class BrowserManager: 浏览器管理器主类
  - async def start(): 启动浏览器, 应用统一配置并校验版本
  - async def close(): 关闭浏览器
  - async def save_cookies(): 保存 Cookie
  - async def load_cookies(): 加载 Cookie
  - async def screenshot(): 截图
  - async def _launch_chromium(): 优先使用具备编解码器的 Chromium 渠道
  - def _assert_version_consistency(): 校验 Playwright 与浏览器版本
  - def _build_wait_strategy(): 构建统一等待策略
  - def _patch_page_wait(): 注入智能等待逻辑
  - def prepare_page(): 对外暴露的页面初始化
@GOTCHAS:
  - 必须使用 async/await 异步操作
  - 关闭浏览器前应保存 Cookie
  - 反检测配置在 browser_config.json 中
@DEPENDENCIES:
  - 外部: playwright
@RELATED: login_controller.py, cookie_manager.py
"""



import importlib.metadata as importlib_metadata
import json
import os
import random
import time
from pathlib import Path
from typing import Any

from loguru import logger
from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)

from .browser_settings import BrowserSettings
from ..utils.page_waiter import PageWaiter, WaitStrategy


class BrowserManager:
    """浏览器管理器.

    管理 Playwright 浏览器实例的创建、配置和销毁。

    Attributes:
        config: 浏览器配置
        playwright: Playwright 实例
        browser: 浏览器实例
        context: 浏览器上下文
        page: 当前页面

    Examples:
        >>> async with BrowserManager() as manager:
        ...     page = manager.page
        ...     await page.goto("https://example.com")
    """

    def __init__(self, config_path: str = "config/browser_config.json"):
        """初始化管理器.

        Args:
            config_path: 配置文件路径
        """
        self.settings = BrowserSettings()
        self._raw_config_path = Path(config_path)
        self.config_path = self._resolve_config_path(self._raw_config_path)
        self.load_config()
        self._override_settings_from_config()

        self.playwright: Playwright | None = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None
        self.timing_config: dict[str, Any] = self.config.get("timing", {})
        self.network_idle_trigger_ms = getattr(
            self,
            "network_idle_trigger_ms",
            int(self.timing_config.get("network_idle_trigger_ms", 1200)),
        )
        self.wait_strategy = getattr(
            self,
            "wait_strategy",
            self._build_wait_strategy(self.timing_config),
        )

    def _resolve_config_path(self, config_path: Path) -> Path:
        """根据当前文件位置解析配置文件的实际路径."""
        if config_path.is_absolute():
            return config_path

        resolved_via_settings = self.settings.resolve_path(config_path)
        if resolved_via_settings.exists():
            return resolved_via_settings

        current_file = Path(__file__).resolve()
        for parent in current_file.parents:
            candidate = parent / config_path
            if candidate.exists():
                return candidate

        # Fallback: 退回到项目根目录的推断路径，便于日志定位
        return resolved_via_settings

    def load_config(self) -> None:
        """加载配置."""
        if not self.config_path.exists():
            logger.warning(
                f"配置文件不存在: {self.config_path} "
                f"(原始路径: {self._raw_config_path}), 使用默认配置"
            )
            self.config = {
                "browser": {"type": "chromium", "headless": False},
                "timeouts": {"default": 30000},
                "timing": {
                    "slow_mo_ms": 0,
                    "wait_after_action_ms": 30,
                    "wait_for_stability_timeout_ms": 375,
                    "wait_for_network_idle_timeout_ms": 750,
                    "retry_initial_delay_ms": 30,
                    "retry_backoff_factor": 1.6,
                    "retry_max_delay_ms": 375,
                    "validation_timeout_ms": 500,
                    "dom_stable_checks": 3,
                    "dom_stable_interval_ms": 30,
                    "network_idle_trigger_ms": 300,
                },
            }
            self.timing_config = self.config["timing"]
            self.network_idle_trigger_ms = int(
                self.timing_config.get("network_idle_trigger_ms", 1200)
            )
            self.wait_strategy = self._build_wait_strategy(self.timing_config)
            return

        with open(self.config_path, encoding="utf-8") as f:
            self.config = json.load(f)
        logger.info("浏览器配置已加载")
        self.timing_config = self.config.get("timing", {})
        self.network_idle_trigger_ms = int(self.timing_config.get("network_idle_trigger_ms", 1200))
        self.wait_strategy = self._build_wait_strategy(self.timing_config)

    def _override_settings_from_config(self) -> None:
        """基于配置文件覆盖浏览器设置, 确保打包后也能使用固定参数."""

        overrides = self.config.get("browser_settings", {})
        if overrides:
            self.settings = BrowserSettings(**overrides)

    async def start(self, headless: bool | None = None) -> None:
        """启动浏览器.

        Args:
            headless: 是否无头模式, None 则使用配置文件设置.
        """
        settings = self.settings
        settings.apply_environment()
        settings.ensure_directories()

        logger.info("启动 Playwright 浏览器, 校验环境一致性..")

        self.playwright = await async_playwright().start()

        browser_config = self.config.get("browser", {})
        browser_type = browser_config.get("type", settings.browser_name)

        if headless is None:
            headless = (
                settings.headless
                if settings.headless is not None
                else browser_config.get("headless", False)
            )

        timing_config = self.timing_config or self.config.get("timing", {})
        slow_mo_ms = timing_config.get("slow_mo_ms")
        if slow_mo_ms is None:
            slow_mo_ms = 0 if headless else 300

        window_width = int(browser_config.get("window_width", 2564))
        window_height = int(browser_config.get("window_height", 1600))
        device_scale_factor = float(browser_config.get("device_scale_factor", 1.0))
        os.environ["TEMU_PIXEL_REFERENCE_DPR"] = f"{device_scale_factor:.16g}"

        launch_options = {
            "headless": headless,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
            ],
            "slow_mo": max(int(slow_mo_ms), 0),
        }

        stealth_config = self.config.get("stealth", {})
        extra_args = stealth_config.get(
            "extra_args",
            [
                "--disable-blink-features",
                "--disable-features=TranslateUI",
                "--disable-extensions",
                "--disable-infobars",
                "--disable-popup-blocking",
                "--no-first-run",
                "--no-default-browser-check",
                "--password-store=basic",
                "--use-gl=desktop",
                "--mute-audio",
            ],
        )
        locale = browser_config.get("locale", settings.locale)
        locale_arg = f"--lang={locale}"
        extra_args.append(locale_arg)
        launch_options["args"] = self._merge_launch_args(launch_options["args"], extra_args)
        window_size_arg = f"--window-size={window_width},{window_height}"
        launch_options["args"] = self._merge_launch_args(
            launch_options["args"],
            [window_size_arg],
        )

        if browser_type == "chromium":
            scale_args: list[str] = [
                f"--force-device-scale-factor={device_scale_factor}",
            ]
            if device_scale_factor == 1.0:
                scale_args.append("--high-dpi-support=1")

            launch_options["args"] = self._merge_launch_args(
                launch_options["args"],
                scale_args,
            )

        launch_options["args"] = self._merge_launch_args(
            launch_options["args"],
            settings.launch_args,
        )

        if browser_type == "chromium":
            self.browser = await self._launch_chromium(launch_options, browser_config)
        elif browser_type == "firefox":
            self.browser = await self.playwright.firefox.launch(**launch_options)
        elif browser_type == "webkit":
            self.browser = await self.playwright.webkit.launch(**launch_options)
        else:
            raise ValueError(f"不支持的浏览器类型: {browser_type}")

        timezone_id = browser_config.get("timezone", settings.timezone_id)
        context_options = {
            "viewport": {
                "width": window_width,
                "height": window_height,
            },
            "screen": {
                "width": window_width,
                "height": window_height,
            },
            "device_scale_factor": device_scale_factor,
            "locale": locale,
            "timezone_id": timezone_id,
            "accept_downloads": True,
        }

        picked_user_agent = self._pick_user_agent(browser_config)
        if picked_user_agent:
            context_options["user_agent"] = picked_user_agent

        storage_state_path = settings.resolve_path(
            browser_config.get("storage_state_path", settings.storage_state_path)
        )
        if storage_state_path.exists():
            context_options["storage_state"] = str(storage_state_path)
        else:
            logger.debug("Storage state 文件不存在, 跳过预加载")

        self.context = await self.browser.new_context(**context_options)

        if stealth_config.get("enabled", True):
            await self._apply_stealth()
            await self._apply_additional_stealth(locale)

        await self.context.add_init_script(
            """
            // 禁用CSS动画和过渡效果, 加速页面交互
            const style = document.createElement('style');
            style.innerHTML = `
                *, ::before, ::after {
                    transition: none !important;
                    animation: none !important;
                    animation-duration: 0s !important;
                    animation-delay: 0s !important;
                }
            `;
            document.head.appendChild(style);
            """
        )

        self.page = await self.context.new_page()
        self._patch_page_wait(self.page)

        default_timeout = self.config.get("timeouts", {}).get("default", 30000)
        self.page.set_default_timeout(default_timeout)
        setattr(self.page, "_bemg_default_timeout_ms", default_timeout)

        self._assert_version_consistency(settings)
        logger.success(f"浏览器已启动 (headless={headless})")

    async def _apply_stealth(self) -> None:
        """应用反检测补丁."""
        try:
            from playwright_stealth import stealth_async

            await stealth_async(self.context)
            logger.debug("✓ 已应用反检测补丁")
        except ImportError:
            logger.warning("playwright-stealth 未安装, 跳过反检测")
        except Exception as e:
            logger.warning(f"应用反检测补丁失败: {e}")

    async def _apply_additional_stealth(self, locale: str) -> None:
        """额外注入反检测脚本."""

        if not self.context:
            return

        try:
            await self.context.add_init_script(
                """
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                window.chrome = window.chrome || { runtime: {} };
                Object.defineProperty(navigator, 'platform', { get: () => 'MacIntel' });
                Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
                Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
                Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en-US'] });
                """
            )
            await self.context.add_init_script(
                f"""
                Object.defineProperty(navigator, 'language', {{ get: () => '{locale}' }});
                """
            )
        except Exception as exc:
            logger.warning(f"注入额外反检测脚本失败: {exc}")

    async def goto(self, url: str, wait_until: str = "networkidle") -> None:
        """导航到URL.

        Args:
            url: 目标URL
            wait_until: 等待条件 (load|domcontentloaded|networkidle|commit)
        """
        if not self.page:
            raise RuntimeError("浏览器未启动")

        logger.info(f"导航到: {url}")
        await self.page.goto(url, wait_until=wait_until)

    def _build_wait_strategy(self, config: dict[str, Any] | None = None) -> WaitStrategy:
        """根据配置构建等待策略."""

        cfg = config or self.timing_config or {}
        return WaitStrategy(
            wait_after_action_ms=int(cfg.get("wait_after_action_ms", 120)),
            wait_for_stability_timeout_ms=int(cfg.get("wait_for_stability_timeout_ms", 1500)),
            wait_for_network_idle_timeout_ms=int(cfg.get("wait_for_network_idle_timeout_ms", 3000)),
            retry_initial_delay_ms=int(cfg.get("retry_initial_delay_ms", 120)),
            retry_backoff_factor=float(cfg.get("retry_backoff_factor", 1.6)),
            retry_max_delay_ms=int(cfg.get("retry_max_delay_ms", 1500)),
            validation_timeout_ms=int(cfg.get("validation_timeout_ms", 2000)),
            dom_stable_checks=int(cfg.get("dom_stable_checks", 3)),
            dom_stable_interval_ms=int(cfg.get("dom_stable_interval_ms", 120)),
        )

    def _patch_page_wait(self, page: Page) -> None:
        """为页面注入智能等待逻辑, 减少硬编码延迟."""

        if getattr(page, "_bemg_smart_wait_patched", False):
            return

        waiter = PageWaiter(page, self.wait_strategy)
        original_wait_for_timeout = page.wait_for_timeout
        minimal_wait_ms = max(self.wait_strategy.wait_after_action_ms, 60)

        async def smart_wait_for_timeout(timeout: float) -> None:
            if timeout <= 0:
                return

            if timeout <= minimal_wait_ms:
                await original_wait_for_timeout(timeout)
                return

            wait_for_network = timeout >= self.network_idle_trigger_ms
            start = time.perf_counter()

            try:
                await waiter.post_action_wait(
                    wait_for_network_idle=wait_for_network,
                    wait_for_dom_stable=True,
                )
            except Exception as exc:
                logger.debug(f"智能等待失败, 回退原始等待 ({timeout}ms): {exc}")
                await original_wait_for_timeout(timeout)
                return

            elapsed_ms = (time.perf_counter() - start) * 1000
            if elapsed_ms < minimal_wait_ms:
                remaining = max(minimal_wait_ms - elapsed_ms, 0)
                await original_wait_for_timeout(remaining)

        page.wait_for_timeout = smart_wait_for_timeout  # type: ignore[assignment]
        page._bemg_smart_wait_patched = True  # type: ignore[attr-defined]
        page._bemg_original_wait_for_timeout = original_wait_for_timeout  # type: ignore[attr-defined]

    def get_timing_config(self) -> dict[str, Any]:
        """获取时序配置."""

        return self.timing_config or {}

    def prepare_page(self, page: Page) -> Page:
        """对外暴露的页面初始化入口, 注入智能等待."""

        self._patch_page_wait(page)
        return page

    async def _launch_chromium(
        self,
        launch_options: dict[str, Any],
        browser_config: dict[str, Any],
    ) -> Browser:
        """启动Chromium浏览器并优先尝试具备专有编解码器的渠道.

        Args:
            launch_options: Playwright launch 参数
            browser_config: 浏览器配置

        Returns:
            Browser 实例
        """
        if not self.playwright:
            raise RuntimeError("Playwright 未初始化")

        if not browser_config.get("enable_codec_workaround", True):
            logger.debug("已禁用 Chromium 编解码器渠道兼容方案, 使用默认浏览器.")
            return await self.playwright.chromium.launch(**launch_options)

        channel_candidates = self._collect_channel_candidates(browser_config)
        last_error: Exception | None = None

        for candidate in channel_candidates:
            candidate_name = candidate.strip()
            if not candidate_name:
                continue

            try:
                logger.info(f"尝试使用 Chromium 渠道: {candidate_name}")
                browser = await self.playwright.chromium.launch(
                    **(launch_options | {"channel": candidate_name})
                )
                logger.success(f"✓ 已启用 Chromium 渠道: {candidate_name}")
                return browser
            except Exception as exc:
                logger.warning(f"使用渠道 {candidate_name} 启动 Chromium 失败: {exc}")
                last_error = exc

        if last_error:
            logger.warning(
                "所有指定的 Chromium 渠道均启动失败, 回退到默认 Chromium."
                " 这可能导致视频上传校验继续失败, 请确认已安装带专有编解码器的 Chrome/Edge."
            )

        return await self.playwright.chromium.launch(**launch_options)

    def _assert_version_consistency(self, settings: BrowserSettings) -> None:
        """校验 Playwright 包与浏览器版本一致性.

        Args:
            settings: 浏览器设置实例.

        Raises:
            RuntimeError: 当 Playwright 包或浏览器版本不符合预期时抛出.
        """

        try:
            package_version = importlib_metadata.version("playwright")
        except importlib_metadata.PackageNotFoundError as exc:
            raise RuntimeError(
                "未找到 Playwright 包元数据, 请确认环境已正确安装依赖或在 PyInstaller 打包"
                " 时添加 --copy-metadata=playwright/--collect-all=playwright."
            ) from exc
        if settings.expected_playwright_version and (
            package_version != settings.expected_playwright_version
        ):
            raise RuntimeError(
                "Playwright 包版本不一致, 请执行 `uv sync --frozen` 重新安装依赖并运行 "
                "`uv run playwright install chromium` 确认浏览器版本同步."
                f" 当前={package_version}, 期望={settings.expected_playwright_version}"
            )

        browser_version: str | None = None
        executable_path: str | None = None
        if self.browser:
            try:
                browser_version = self.browser.version
            except Exception as exc:  # pragma: no cover - 仅在 Playwright 低版本异常时触发
                logger.debug(f"获取浏览器版本失败: {exc}")
        if self.playwright:
            try:
                executable_path = self.playwright.chromium.executable_path()
            except Exception as exc:  # pragma: no cover - 兼容 API 变动
                logger.debug(f"获取浏览器可执行路径失败: {exc}")

        if settings.expected_browser_version and browser_version:
            if settings.expected_browser_version not in browser_version:
                raise RuntimeError(
                    "浏览器版本不一致, 请重新执行 `uv run playwright install chromium` "
                    f"或清理 {settings.resolve_path(settings.browsers_path)} 重新安装."
                    f" 当前={browser_version}, 期望包含={settings.expected_browser_version}"
                )

        logger.info(
            f"Playwright 包版本: {package_version}, 浏览器版本: {browser_version or '未知'}, "
            f"可执行路径: {executable_path or '未知'}"
        )

    @staticmethod
    def _merge_launch_args(base: list[str], extra: list[str]) -> list[str]:
        """合并启动参数并去重."""

        seen = set(base)
        merged = base.copy()
        for arg in extra:
            if arg and arg not in seen:
                merged.append(arg)
                seen.add(arg)
        return merged

    @staticmethod
    def _collect_channel_candidates(browser_config: dict[str, Any]) -> list[str]:
        """收集可用的Chromium渠道候选列表."""

        candidates: list[str] = []
        configured_channel = browser_config.get("channel")
        if configured_channel:
            candidates.append(configured_channel)

        raw_fallbacks: Any = browser_config.get("channel_fallbacks", [])
        if isinstance(raw_fallbacks, str):
            raw_fallbacks = [raw_fallbacks]
        if isinstance(raw_fallbacks, list):
            for fallback in raw_fallbacks:
                if fallback and fallback not in candidates:
                    candidates.append(fallback)

        for default_candidate in ("msedge", "chrome"):
            if default_candidate not in candidates:
                candidates.append(default_candidate)

        return candidates

    @staticmethod
    def _pick_user_agent(browser_config: dict) -> str | None:
        """选择 User-Agent, 支持配置列表随机挑选."""

        explicit = browser_config.get("user_agent")
        candidates = browser_config.get("user_agents", [])
        if candidates:
            return random.choice(candidates)
        return explicit

    async def save_cookies(self, file_path: str) -> None:
        """保存 Cookie.

        Args:
            file_path: Cookie 文件路径
        """
        if not self.context:
            raise RuntimeError("浏览器未启动")

        cookies = await self.context.cookies()

        cookie_file = Path(file_path)
        cookie_file.parent.mkdir(parents=True, exist_ok=True)

        with open(cookie_file, "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)

        logger.info(f"Cookie 已保存到: {cookie_file}")

    async def load_cookies(self, file_path: str) -> bool:
        """加载 Cookie.

        Args:
            file_path: Cookie 文件路径

        Returns:
            是否成功加载
        """
        if not self.context:
            raise RuntimeError("浏览器未启动")

        cookie_file = Path(file_path)
        if not cookie_file.exists():
            logger.debug("Cookie 文件不存在")
            return False

        try:
            with open(cookie_file, encoding="utf-8") as f:
                cookies = json.load(f)

            await self.context.add_cookies(cookies)
            logger.success("✓ Cookie 已加载")
            return True
        except Exception as e:
            logger.error(f"加载 Cookie 失败: {e}")
            return False

    async def screenshot(self, path: str, full_page: bool = False) -> None:
        """截图.

        Args:
            path: 截图保存路径
            full_page: 是否截取整个页面
        """
        if not self.page:
            raise RuntimeError("浏览器未启动")

        screenshot_path = Path(path)
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)

        await self.page.screenshot(path=str(screenshot_path), full_page=full_page)
        logger.debug(f"截图已保存: {screenshot_path}")

    async def close(self) -> None:
        """关闭浏览器."""
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

        logger.info("浏览器已关闭")

    async def __aenter__(self):
        """异步上下文管理器入口."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口."""
        await self.close()


# 测试代码
if __name__ == "__main__":
    import asyncio

    async def test():
        async with BrowserManager() as manager:
            await manager.goto("https://www.baidu.com")
            await manager.screenshot("data/temp/test.png")
            logger.success("✓ 测试完成")

    asyncio.run(test())
