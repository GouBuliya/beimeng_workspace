"""
@PURPOSE: 选择器命中记录器，用于记录运行时成功匹配的选择器及代码位置，便于后续优化选择器顺序.
@OUTLINE:
  - class SelectorHitRecorder: 单例记录器，收集命中信息
  - record_selector_hit(): 全局便捷函数，记录选择器命中
  - export_selector_report(): 全局便捷函数，导出报告
@GOTCHAS:
  - 使用 inspect 模块获取调用位置，需要根据调用深度调整 frame 层级
  - 报告文件名包含时间戳，避免覆盖历史记录
@DEPENDENCIES:
  - 内部: loguru
  - 外部: inspect, json, pathlib
"""

from __future__ import annotations

import inspect
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger


class SelectorHitRecorder:
    """选择器命中记录器单例类.

    用于在运行时记录哪个选择器最终成功匹配，以及对应的代码位置，
    便于后续分析和优化选择器顺序。
    """

    _instance: SelectorHitRecorder | None = None
    _hits: dict[str, dict[str, Any]]

    def __new__(cls) -> SelectorHitRecorder:
        """确保单例模式."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._hits = {}
            cls._instance._enabled = os.environ.get("SELECTOR_RECORDER_ENABLED", "1") != "0"
        return cls._instance

    @classmethod
    def get_instance(cls) -> SelectorHitRecorder:
        """获取单例实例.

        Returns:
            SelectorHitRecorder 单例实例.
        """
        return cls()

    @property
    def enabled(self) -> bool:
        """是否启用记录功能."""
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        """设置是否启用记录功能."""
        self._enabled = value

    def record_hit(
        self,
        selector: str | dict[str, Any],
        selector_list: list[str | dict[str, Any]],
        selector_index: int,
        context_name: str = "",
        stack_depth: int = 2,
    ) -> None:
        """记录一次选择器命中.

        Args:
            selector: 成功匹配的选择器（字符串或配置字典）.
            selector_list: 完整的选择器候选列表.
            selector_index: 成功选择器在列表中的索引.
            context_name: 业务上下文名称，如"类目选择器"、"重量输入框".
            stack_depth: 调用栈深度，用于获取正确的调用位置（默认2层）.
        """
        if not self._enabled:
            return

        try:
            # 获取调用栈信息
            frame = inspect.currentframe()
            for _ in range(stack_depth):
                if frame is not None:
                    frame = frame.f_back

            if frame is None:
                logger.warning("无法获取调用栈信息")
                return

            file_path = frame.f_code.co_filename
            line_number = frame.f_lineno
            function_name = frame.f_code.co_name

            # 简化文件路径（只保留相对路径部分）
            try:
                file_path_obj = Path(file_path)
                # 尝试获取相对于 src 目录的路径
                parts = file_path_obj.parts
                if "src" in parts:
                    src_index = parts.index("src")
                    relative_path = "/".join(parts[src_index:])
                else:
                    relative_path = file_path_obj.name
            except Exception:
                relative_path = file_path

            # 生成唯一的位置标识
            location_key = f"{relative_path}:{function_name}:{context_name}"

            # 序列化选择器（处理字典类型）
            def serialize_selector(sel: str | dict[str, Any]) -> str:
                if isinstance(sel, dict):
                    return json.dumps(sel, ensure_ascii=False)
                return sel

            serialized_selector = serialize_selector(selector)
            serialized_list = [serialize_selector(s) for s in selector_list]

            hit_info = {
                "file": str(file_path),
                "relative_path": relative_path,
                "line": line_number,
                "function": function_name,
                "context": context_name,
                "successful_selector": serialized_selector,
                "successful_index": selector_index,
                "selector_list": serialized_list,
                "timestamp": datetime.now().isoformat(),
            }

            self._hits[location_key] = hit_info

            # 如果不是第一个选择器成功，记录优化建议
            if selector_index > 0:
                logger.debug(
                    "[选择器记录] {} 可优化: 索引 {} 命中 (非首位)",
                    context_name or function_name,
                    selector_index,
                )
            else:
                logger.trace(
                    "[选择器记录] {} 首位命中",
                    context_name or function_name,
                )

        except Exception as exc:
            logger.warning(f"记录选择器命中失败: {exc}")

    def get_hits(self) -> dict[str, dict[str, Any]]:
        """获取所有命中记录.

        Returns:
            命中记录字典.
        """
        return self._hits.copy()

    def get_optimizable_items(self) -> dict[str, dict[str, Any]]:
        """获取可优化的项目（成功索引 > 0 的记录）.

        Returns:
            需要优化的命中记录字典.
        """
        return {k: v for k, v in self._hits.items() if v.get("successful_index", 0) > 0}

    def clear(self) -> None:
        """清空所有记录."""
        self._hits.clear()

    def export_report(
        self,
        output_dir: str | Path = "D:/codespace/beimeng_workspace/data/temp",
    ) -> Path:
        """导出命中报告到 JSON 文件.

        Args:
            output_dir: 输出目录路径.

        Returns:
            生成的报告文件路径.
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = output_path / f"selector_hits_{timestamp}.json"

        optimizable = self.get_optimizable_items()

        report = {
            "generated_at": datetime.now().isoformat(),
            "total_locations": len(self._hits),
            "optimizable_count": len(optimizable),
            "summary": {
                "message": f"共 {len(self._hits)} 个位置记录, {len(optimizable)} 个可优化",
                "optimizable_locations": list(optimizable.keys()),
            },
            "hits": self._hits,
        }

        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        logger.info(f"选择器命中报告已导出: {report_file}")
        if optimizable:
            logger.info(f"发现 {len(optimizable)} 个可优化位置:")
            for key in optimizable:
                info = optimizable[key]
                logger.info(f"  - {key} (索引 {info['successful_index']})")

        return report_file


# ========== 全局便捷函数 ==========


def record_selector_hit(
    selector: str | dict[str, Any],
    selector_list: list[str | dict[str, Any]],
    index: int,
    context: str = "",
) -> None:
    """全局便捷函数：记录选择器命中.

    Args:
        selector: 成功匹配的选择器.
        selector_list: 完整的选择器候选列表.
        index: 成功选择器在列表中的索引.
        context: 业务上下文名称.

    Examples:
        >>> selectors = ["selector1", "selector2", "selector3"]
        >>> for i, sel in enumerate(selectors):
        ...     if try_selector(sel):
        ...         record_selector_hit(sel, selectors, i, "示例选择器")
        ...         break
    """
    SelectorHitRecorder.get_instance().record_hit(
        selector=selector,
        selector_list=selector_list,
        selector_index=index,
        context_name=context,
        stack_depth=2,
    )


def export_selector_report(
    output_dir: str | Path = "D:/codespace/beimeng_workspace/data/temp",
) -> Path:
    """全局便捷函数：导出选择器命中报告.

    Args:
        output_dir: 输出目录路径.

    Returns:
        生成的报告文件路径.

    Examples:
        >>> # 在程序结束时调用
        >>> report_path = export_selector_report()
        >>> print(f"报告已保存到: {report_path}")
    """
    return SelectorHitRecorder.get_instance().export_report(output_dir)


def get_selector_recorder() -> SelectorHitRecorder:
    """获取选择器记录器实例.

    Returns:
        SelectorHitRecorder 单例实例.
    """
    return SelectorHitRecorder.get_instance()

