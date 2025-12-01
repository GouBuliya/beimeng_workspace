"""
@PURPOSE: 提供交互式调试功能，支持逐步执行和断点调试
@OUTLINE:
  - class DebugHelper: 调试辅助类
  - async def wait_for_continue(): 等待用户输入继续
  - def breakpoint(): 设置断点
  - def set_debug_mode(): 设置调试模式
@GOTCHAS:
  - 调试模式下会暂停执行，等待用户输入
  - 只在启用DEBUG_MODE时生效
  - 可以通过环境变量或参数启用
@DEPENDENCIES:
  - 外部: loguru
@RELATED: five_to_twenty_workflow.py, collection_to_edit_workflow.py
"""

import asyncio
import sys
from typing import Optional

from loguru import logger


class DebugHelper:
    """交互式调试辅助工具.

    提供类似调试器的断点功能，支持：
    - 逐步执行（按'n'继续下一步）
    - 查看当前状态
    - 跳过剩余断点

    Attributes:
        enabled: 是否启用调试模式
        step_count: 当前步骤计数
        auto_continue: 是否自动继续（跳过所有断点）

    Examples:
        >>> debug = DebugHelper(enabled=True)
        >>> await debug.breakpoint("开始编辑产品")
        [调试] 断点 #1: 开始编辑产品
        按 'n' 继续，'c' 跳过所有断点，'q' 退出: n

        >>> debug.set_auto_continue()  # 跳过剩余断点
        >>> await debug.breakpoint("这个会被跳过")  # 不会暂停
    """

    def __init__(self, enabled: bool = False):
        """初始化调试辅助工具.

        Args:
            enabled: 是否启用调试模式（默认False）
        """
        self.enabled = enabled
        self.step_count = 0
        self.auto_continue = False

        if self.enabled:
            logger.info("🐛 调试模式已启用（逐步执行）")
            logger.info("   提示：每个断点处按 'n' 继续，'c' 跳过所有断点，'q' 退出")
        else:
            logger.debug("调试模式未启用")

    def set_debug_mode(self, enabled: bool):
        """动态设置调试模式.

        Args:
            enabled: 是否启用调试模式
        """
        self.enabled = enabled
        if enabled:
            logger.info("🐛 调试模式已启用")
        else:
            logger.info("调试模式已禁用")

    def set_auto_continue(self):
        """设置自动继续模式（跳过剩余所有断点）."""
        self.auto_continue = True
        logger.info("⏩ 已启用自动继续模式，将跳过剩余所有断点")

    async def breakpoint(
        self, message: str = "", data: Optional[dict] = None, always_show: bool = False
    ):
        """设置断点，暂停执行等待用户输入.

        在调试模式下会暂停执行，显示提示信息，等待用户输入命令：
        - 'n' 或 Enter: 继续下一步
        - 'c': 跳过所有剩余断点
        - 'q': 退出程序

        Args:
            message: 断点描述信息
            data: 可选的调试数据（字典形式）
            always_show: 是否总是显示（即使调试模式未启用）

        Examples:
            >>> await debug.breakpoint("准备保存商品")
            >>> await debug.breakpoint("处理第1个产品", {"title": "...", "price": 100})
        """
        if not self.enabled and not always_show:
            return

        if self.auto_continue and not always_show:
            return

        self.step_count += 1

        # 显示断点信息
        logger.info("")
        logger.info("=" * 80)
        logger.info(f"🔴 [调试断点 #{self.step_count}] {message}")

        if data:
            logger.info("📊 当前数据:")
            for key, value in data.items():
                # 限制输出长度
                value_str = str(value)
                if len(value_str) > 100:
                    value_str = value_str[:97] + "..."
                logger.info(f"   {key}: {value_str}")

        logger.info("=" * 80)
        logger.info("💡 操作提示:")
        logger.info("   n  + Enter → 继续下一步 (Next)")
        logger.info("   c  + Enter → 跳过所有断点继续运行 (Continue)")
        logger.info("   q  + Enter → 退出程序 (Quit)")
        logger.info("=" * 80)

        # 等待用户输入
        while True:
            try:
                user_input = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: input("👉 请输入命令 (n/c/q): ").strip().lower()
                )

                if user_input == "" or user_input == "n":
                    logger.success("▶️  继续执行...\n")
                    break
                elif user_input == "c":
                    self.set_auto_continue()
                    break
                elif user_input == "q":
                    logger.warning("⛔ 用户选择退出")
                    sys.exit(0)
                else:
                    logger.warning(f"⚠️  无效命令: '{user_input}'，请输入 n/c/q")
            except KeyboardInterrupt:
                logger.warning("\n⛔ 用户中断 (Ctrl+C)")
                sys.exit(0)
            except Exception as e:
                logger.error(f"读取输入失败: {e}")
                break

    async def step(self, message: str = "", **kwargs):
        """简化的断点方法（别名）.

        Args:
            message: 步骤描述
            **kwargs: 其他参数传递给breakpoint
        """
        await self.breakpoint(message, **kwargs)

    def log_step(self, message: str):
        """记录步骤但不暂停（用于非关键步骤）.

        Args:
            message: 步骤描述
        """
        if self.enabled:
            logger.debug(f"[步骤 #{self.step_count + 1}] {message}")


# 全局调试实例（可选）
_global_debug_helper: Optional[DebugHelper] = None


def init_global_debug(enabled: bool = False) -> DebugHelper:
    """初始化全局调试助手.

    Args:
        enabled: 是否启用调试模式

    Returns:
        DebugHelper实例
    """
    global _global_debug_helper
    _global_debug_helper = DebugHelper(enabled=enabled)
    return _global_debug_helper


def get_global_debug() -> DebugHelper:
    """获取全局调试助手实例.

    Returns:
        DebugHelper实例，如果未初始化则创建一个禁用的实例
    """
    global _global_debug_helper
    if _global_debug_helper is None:
        _global_debug_helper = DebugHelper(enabled=False)
    return _global_debug_helper


# 便捷函数
async def debug_breakpoint(message: str = "", data: Optional[dict] = None):
    """全局断点快捷函数.

    Args:
        message: 断点描述
        data: 调试数据
    """
    helper = get_global_debug()
    await helper.breakpoint(message, data)
