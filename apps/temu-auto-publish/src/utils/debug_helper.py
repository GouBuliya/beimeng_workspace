"""
@PURPOSE: 调试工具 - 提供截图、HTML保存、性能分析、断点调试等调试功能
@OUTLINE:
  - class DebugConfig: 调试配置
  - class DebugHelper: 调试助手
    - screenshot(): 截图
    - save_html(): 保存HTML
    - save_state(): 保存完整状态（截图+HTML）
    - start_timer(): 开始计时
    - end_timer(): 结束计时
    - breakpoint(): 断点调试
    - record_video(): 录制视频
    - enable_trace(): 启用Playwright追踪
@GOTCHAS:
  - 截图和HTML会占用磁盘空间
  - 录制视频会显著降低性能
  - 断点模式需要用户交互
@DEPENDENCIES:
  - 外部: playwright, loguru
"""

import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger
from playwright.async_api import Page


@dataclass
class DebugConfig:
    """调试配置."""
    
    # 基础配置
    enabled: bool = True  # 是否启用调试
    debug_dir: Path = field(default_factory=lambda: Path("data/debug"))  # 调试输出目录
    
    # 截图配置
    auto_screenshot: bool = True  # 自动截图
    screenshot_on_error: bool = True  # 错误时截图
    screenshot_format: str = "png"  # 截图格式 (png/jpeg)
    
    # HTML dump配置
    auto_save_html: bool = True  # 自动保存HTML
    save_html_on_error: bool = True  # 错误时保存HTML
    
    # 性能分析
    enable_timing: bool = True  # 启用计时
    log_slow_operations: bool = True  # 记录慢操作
    slow_threshold: float = 5.0  # 慢操作阈值（秒）
    
    # 断点调试
    enable_breakpoint: bool = False  # 启用断点（默认关闭）
    breakpoint_wait_time: int = 30  # 断点等待时间（秒）
    
    # 录制配置
    enable_video: bool = False  # 启用视频录制（默认关闭，影响性能）
    enable_trace: bool = False  # 启用Playwright追踪（默认关闭）
    
    def __post_init__(self):
        """初始化后创建目录."""
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"调试输出目录: {self.debug_dir}")


class DebugHelper:
    """调试助手 - 提供全方位的调试支持."""
    
    def __init__(self, config: Optional[DebugConfig] = None):
        """初始化调试助手.
        
        Args:
            config: 调试配置，如果为None则使用默认配置
        """
        self.config = config or DebugConfig()
        self.timers: Dict[str, float] = {}  # 计时器
        self.operation_times: List[Dict] = []  # 操作耗时记录
        self.screenshot_count = 0
        self.html_count = 0
        
        if not self.config.enabled:
            logger.info("⚠️  调试模式已禁用")
        else:
            logger.info("🐛 调试模式已启用")
            logger.debug(f"  截图: {'✓' if self.config.auto_screenshot else '✗'}")
            logger.debug(f"  HTML: {'✓' if self.config.auto_save_html else '✗'}")
            logger.debug(f"  计时: {'✓' if self.config.enable_timing else '✗'}")
            logger.debug(f"  断点: {'✓' if self.config.enable_breakpoint else '✗'}")
    
    def _get_timestamp(self) -> str:
        """获取时间戳字符串."""
        return datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    
    def _sanitize_filename(self, name: str) -> str:
        """清理文件名（移除非法字符）."""
        return "".join(c if c.isalnum() or c in "._- " else "_" for c in name)
    
    async def screenshot(
        self, 
        page: Page, 
        name: str = "screenshot",
        full_page: bool = False
    ) -> Optional[Path]:
        """截图.
        
        Args:
            page: Playwright页面对象
            name: 截图名称
            full_page: 是否截取整个页面
            
        Returns:
            截图文件路径，如果失败则返回None
            
        Examples:
            >>> await helper.screenshot(page, "login_page")
            Path('data/debug/20251031_120000_login_page.png')
        """
        if not self.config.enabled:
            return None
        
        try:
            self.screenshot_count += 1
            timestamp = self._get_timestamp()
            safe_name = self._sanitize_filename(name)
            filename = f"{timestamp}_{self.screenshot_count:03d}_{safe_name}.{self.config.screenshot_format}"
            filepath = self.config.debug_dir / filename
            
            await page.screenshot(
                path=str(filepath),
                full_page=full_page,
                type=self.config.screenshot_format
            )
            
            logger.debug(f"📸 截图已保存: {filename}")
            return filepath
            
        except Exception as e:
            logger.error(f"截图失败: {e}")
            return None
    
    async def save_html(
        self, 
        page: Page, 
        name: str = "page"
    ) -> Optional[Path]:
        """保存页面HTML.
        
        Args:
            page: Playwright页面对象
            name: 文件名称
            
        Returns:
            HTML文件路径，如果失败则返回None
        """
        if not self.config.enabled:
            return None
        
        try:
            self.html_count += 1
            timestamp = self._get_timestamp()
            safe_name = self._sanitize_filename(name)
            filename = f"{timestamp}_{self.html_count:03d}_{safe_name}.html"
            filepath = self.config.debug_dir / filename
            
            content = await page.content()
            filepath.write_text(content, encoding='utf-8')
            
            logger.debug(f"📄 HTML已保存: {filename}")
            return filepath
            
        except Exception as e:
            logger.error(f"保存HTML失败: {e}")
            return None
    
    async def save_state(
        self,
        page: Page,
        name: str,
        full_page: bool = False
    ) -> Dict[str, Optional[Path]]:
        """保存完整状态（截图 + HTML + URL）.
        
        Args:
            page: Playwright页面对象
            name: 状态名称
            full_page: 是否截取整个页面
            
        Returns:
            包含截图和HTML路径的字典
        """
        if not self.config.enabled:
            return {}
        
        logger.info(f"💾 保存状态: {name}")
        
        results = {}
        
        # 保存URL
        try:
            url = page.url
            logger.debug(f"  URL: {url}")
            results["url"] = url
        except:
            pass
        
        # 截图
        if self.config.auto_screenshot:
            screenshot_path = await self.screenshot(page, name, full_page)
            results["screenshot"] = screenshot_path
        
        # 保存HTML
        if self.config.auto_save_html:
            html_path = await self.save_html(page, name)
            results["html"] = html_path
        
        return results
    
    async def save_error_state(
        self,
        page: Page,
        error_name: str,
        exception: Optional[Exception] = None
    ):
        """保存错误状态（用于调试失败场景）.
        
        Args:
            page: Playwright页面对象
            error_name: 错误名称
            exception: 异常对象
        """
        if not self.config.enabled:
            return
        
        logger.error(f"❌ 错误状态: {error_name}")
        
        if exception:
            logger.error(f"  异常: {exception}")
        
        # 截图
        if self.config.screenshot_on_error:
            await self.screenshot(page, f"ERROR_{error_name}", full_page=True)
        
        # 保存HTML
        if self.config.save_html_on_error:
            await self.save_html(page, f"ERROR_{error_name}")
    
    def start_timer(self, operation: str):
        """开始计时.
        
        Args:
            operation: 操作名称
        """
        if not self.config.enabled or not self.config.enable_timing:
            return
        
        self.timers[operation] = time.time()
        logger.debug(f"⏱️  开始计时: {operation}")
    
    def end_timer(self, operation: str) -> Optional[float]:
        """结束计时并记录.
        
        Args:
            operation: 操作名称
            
        Returns:
            操作耗时（秒），如果未找到计时器则返回None
        """
        if not self.config.enabled or not self.config.enable_timing:
            return None
        
        if operation not in self.timers:
            logger.warning(f"⚠️  未找到计时器: {operation}")
            return None
        
        start_time = self.timers.pop(operation)
        duration = time.time() - start_time
        
        # 记录
        record = {
            "operation": operation,
            "duration": duration,
            "timestamp": datetime.now().isoformat()
        }
        self.operation_times.append(record)
        
        # 日志
        if duration >= self.config.slow_threshold and self.config.log_slow_operations:
            logger.warning(f"🐌 慢操作: {operation} 耗时 {duration:.2f}秒")
        else:
            logger.debug(f"⏱️  {operation} 耗时 {duration:.2f}秒")
        
        return duration
    
    async def breakpoint(
        self,
        page: Page,
        message: str = "断点",
        auto_continue: bool = False
    ):
        """断点调试（暂停执行，等待用户检查）.
        
        Args:
            page: Playwright页面对象
            message: 断点消息
            auto_continue: 是否自动继续（用于测试）
        """
        if not self.config.enabled or not self.config.enable_breakpoint:
            return
        
        logger.warning("=" * 80)
        logger.warning(f"🔴 断点: {message}")
        logger.warning(f"  当前URL: {page.url}")
        logger.warning("  请在浏览器中手动检查页面状态")
        
        if auto_continue:
            logger.warning(f"  将在 {self.config.breakpoint_wait_time} 秒后自动继续...")
            import asyncio
            await asyncio.sleep(self.config.breakpoint_wait_time)
        else:
            logger.warning("  按 Enter 继续...")
            input()
        
        logger.warning("▶️  继续执行")
        logger.warning("=" * 80)
    
    def get_performance_summary(self) -> Dict:
        """获取性能分析摘要.
        
        Returns:
            性能统计信息
        """
        if not self.operation_times:
            return {}
        
        total_time = sum(record["duration"] for record in self.operation_times)
        avg_time = total_time / len(self.operation_times)
        
        # 找出最慢的操作
        slowest = max(self.operation_times, key=lambda x: x["duration"])
        
        summary = {
            "total_operations": len(self.operation_times),
            "total_time": total_time,
            "average_time": avg_time,
            "slowest_operation": slowest["operation"],
            "slowest_duration": slowest["duration"],
            "screenshots": self.screenshot_count,
            "html_dumps": self.html_count
        }
        
        return summary
    
    def log_performance_summary(self):
        """记录性能分析摘要."""
        if not self.config.enabled or not self.config.enable_timing:
            return
        
        summary = self.get_performance_summary()
        
        if not summary:
            logger.info("📊 性能分析: 暂无数据")
            return
        
        logger.info("=" * 80)
        logger.info("📊 性能分析摘要")
        logger.info("=" * 80)
        logger.info(f"  总操作数: {summary['total_operations']}")
        logger.info(f"  总耗时: {summary['total_time']:.2f}秒")
        logger.info(f"  平均耗时: {summary['average_time']:.2f}秒")
        logger.info(f"  最慢操作: {summary['slowest_operation']} ({summary['slowest_duration']:.2f}秒)")
        logger.info(f"  截图数量: {summary['screenshots']}")
        logger.info(f"  HTML保存: {summary['html_dumps']}")
        logger.info("=" * 80)
    
    async def enable_trace(self, page: Page):
        """启用Playwright追踪（用于详细的性能分析）.
        
        Args:
            page: Playwright页面对象
        """
        if not self.config.enabled or not self.config.enable_trace:
            return
        
        try:
            context = page.context
            trace_path = self.config.debug_dir / f"trace_{self._get_timestamp()}.zip"
            
            await context.tracing.start(screenshots=True, snapshots=True, sources=True)
            logger.info(f"🔍 Playwright追踪已启用，将保存到: {trace_path.name}")
            
            return trace_path
        except Exception as e:
            logger.error(f"启用追踪失败: {e}")
            return None
    
    async def stop_trace(self, page: Page, trace_path: Path):
        """停止Playwright追踪.
        
        Args:
            page: Playwright页面对象
            trace_path: 追踪文件保存路径
        """
        if not self.config.enabled or not self.config.enable_trace:
            return
        
        try:
            context = page.context
            await context.tracing.stop(path=str(trace_path))
            logger.success(f"✓ 追踪已保存: {trace_path.name}")
            logger.info(f"  查看追踪: https://trace.playwright.dev")
        except Exception as e:
            logger.error(f"停止追踪失败: {e}")


# 便捷函数
def create_debug_helper(
    enabled: bool = True,
    screenshot: bool = True,
    html: bool = True,
    timing: bool = True,
    breakpoint: bool = False
) -> DebugHelper:
    """创建调试助手（便捷方法）.
    
    Args:
        enabled: 是否启用调试
        screenshot: 是否自动截图
        html: 是否自动保存HTML
        timing: 是否启用计时
        breakpoint: 是否启用断点
        
    Returns:
        配置好的调试助手
    """
    config = DebugConfig(
        enabled=enabled,
        auto_screenshot=screenshot,
        auto_save_html=html,
        enable_timing=timing,
        enable_breakpoint=breakpoint
    )
    return DebugHelper(config)


# 示例使用
if __name__ == "__main__":
    # 此模块需要配合Page对象使用
    # 测试请在集成测试中进行
    pass

