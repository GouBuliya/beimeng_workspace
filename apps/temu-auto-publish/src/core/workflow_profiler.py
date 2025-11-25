"""
@PURPOSE: 工作流性能分析器 - 记录整个脚本各阶段的执行时间
@OUTLINE:
  - @dataclass StepTiming: 单个步骤的计时数据
  - @dataclass StageTiming: 阶段计时数据
  - @dataclass WorkflowProfile: 完整工作流性能数据
  - class WorkflowProfiler: 工作流性能分析器
    - step(): 步骤计时上下文管理器
    - stage(): 阶段计时上下文管理器
    - generate_report(): 生成性能报告
    - save_profile(): 保存性能数据
    - compare_profiles(): 对比多次运行
@USAGE:
  profiler = WorkflowProfiler("complete_publish")
  
  with profiler.stage("首次编辑"):
      with profiler.step("打开编辑对话框"):
          # 具体操作
      with profiler.step("填写表单"):
          # 具体操作
  
  profiler.generate_report()
  profiler.save_profile()
@DEPENDENCIES:
  - 外部: loguru
  - 内部: 无
"""

from __future__ import annotations

import json
import statistics
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Generator

from loguru import logger


@dataclass
class StepTiming:
    """单个步骤的计时数据"""
    
    name: str
    stage: str
    start_time: float
    end_time: float = 0.0
    duration_ms: float = 0.0
    success: bool = True
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def complete(self, success: bool = True, error: str | None = None) -> None:
        """完成计时"""
        self.end_time = time.perf_counter()
        self.duration_ms = (self.end_time - self.start_time) * 1000
        self.success = success
        self.error = error


@dataclass
class StageTiming:
    """阶段计时数据"""
    
    name: str
    start_time: float
    end_time: float = 0.0
    duration_ms: float = 0.0
    success: bool = True
    error: str | None = None
    steps: list[StepTiming] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def complete(self, success: bool = True, error: str | None = None) -> None:
        """完成计时"""
        self.end_time = time.perf_counter()
        self.duration_ms = (self.end_time - self.start_time) * 1000
        self.success = success
        self.error = error
    
    @property
    def step_count(self) -> int:
        return len(self.steps)
    
    @property
    def successful_steps(self) -> int:
        return sum(1 for s in self.steps if s.success)
    
    @property
    def failed_steps(self) -> int:
        return sum(1 for s in self.steps if not s.success)
    
    @property
    def avg_step_duration_ms(self) -> float:
        if not self.steps:
            return 0.0
        return statistics.mean(s.duration_ms for s in self.steps)


@dataclass
class WorkflowProfile:
    """完整工作流性能数据"""
    
    workflow_id: str
    workflow_type: str
    start_time: str
    end_time: str = ""
    total_duration_ms: float = 0.0
    success: bool = True
    stages: list[StageTiming] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    @property
    def stage_count(self) -> int:
        return len(self.stages)
    
    @property
    def total_steps(self) -> int:
        return sum(s.step_count for s in self.stages)
    
    @property
    def successful_stages(self) -> int:
        return sum(1 for s in self.stages if s.success)
    
    @property
    def failed_stages(self) -> int:
        return sum(1 for s in self.stages if not s.success)
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "workflow_id": self.workflow_id,
            "workflow_type": self.workflow_type,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "total_duration_ms": round(self.total_duration_ms, 2),
            "total_duration_readable": self._format_duration(self.total_duration_ms),
            "success": self.success,
            "stage_count": self.stage_count,
            "total_steps": self.total_steps,
            "successful_stages": self.successful_stages,
            "failed_stages": self.failed_stages,
            "stages": [self._stage_to_dict(s) for s in self.stages],
            "metadata": self.metadata,
        }
    
    def _stage_to_dict(self, stage: StageTiming) -> dict[str, Any]:
        """阶段转字典"""
        return {
            "name": stage.name,
            "duration_ms": round(stage.duration_ms, 2),
            "duration_readable": self._format_duration(stage.duration_ms),
            "success": stage.success,
            "error": stage.error,
            "step_count": stage.step_count,
            "successful_steps": stage.successful_steps,
            "failed_steps": stage.failed_steps,
            "avg_step_duration_ms": round(stage.avg_step_duration_ms, 2),
            "steps": [self._step_to_dict(s) for s in stage.steps],
            "metadata": stage.metadata,
        }
    
    def _step_to_dict(self, step: StepTiming) -> dict[str, Any]:
        """步骤转字典"""
        return {
            "name": step.name,
            "duration_ms": round(step.duration_ms, 2),
            "duration_readable": self._format_duration(step.duration_ms),
            "success": step.success,
            "error": step.error,
            "metadata": step.metadata,
        }
    
    @staticmethod
    def _format_duration(ms: float) -> str:
        """格式化时长为可读字符串"""
        if ms < 1000:
            return f"{ms:.0f}ms"
        elif ms < 60000:
            return f"{ms/1000:.1f}s"
        else:
            minutes = int(ms // 60000)
            seconds = (ms % 60000) / 1000
            return f"{minutes}m {seconds:.0f}s"
    
    def to_json(self, indent: int = 2) -> str:
        """转换为 JSON"""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


class WorkflowProfiler:
    """工作流性能分析器
    
    用于记录整个脚本各阶段和步骤的执行时间。
    
    Examples:
        >>> profiler = WorkflowProfiler("complete_publish")
        >>> 
        >>> with profiler.stage("stage1_first_edit"):
        ...     with profiler.step("open_dialog"):
        ...         await open_edit_dialog()
        ...     with profiler.step("fill_form"):
        ...         await fill_form()
        >>> 
        >>> with profiler.stage("stage2_claim"):
        ...     with profiler.step("select_products"):
        ...         await select_products()
        >>> 
        >>> profiler.finish()
        >>> print(profiler.generate_report())
        >>> profiler.save_profile()
    """
    
    PROFILE_DIR = Path("data/profiles")
    
    def __init__(
        self,
        workflow_type: str,
        workflow_id: str | None = None,
        profile_dir: Path | str | None = None,
    ):
        """初始化性能分析器
        
        Args:
            workflow_type: 工作流类型（如 "complete_publish"）
            workflow_id: 工作流ID（默认自动生成）
            profile_dir: 性能数据存储目录
        """
        self.workflow_type = workflow_type
        self.workflow_id = workflow_id or f"{workflow_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        if profile_dir:
            self.profile_dir = Path(profile_dir)
        else:
            self.profile_dir = self.PROFILE_DIR
        
        self._start_time = time.perf_counter()
        self._current_stage: StageTiming | None = None
        self._stages: list[StageTiming] = []
        self._finished = False
        
        logger.info(f"[Profiler] 开始记录工作流: {self.workflow_id}")
    
    @contextmanager
    def stage(
        self,
        name: str,
        **metadata,
    ) -> Generator[StageTiming, None, None]:
        """阶段计时上下文管理器
        
        Args:
            name: 阶段名称
            **metadata: 额外的元数据
            
        Yields:
            StageTiming 对象
        """
        stage = StageTiming(
            name=name,
            start_time=time.perf_counter(),
            metadata=metadata,
        )
        self._current_stage = stage
        self._stages.append(stage)
        
        logger.info(f"[Profiler] >>> 阶段开始: {name}")
        
        try:
            yield stage
            stage.complete(success=True)
            logger.info(
                f"[Profiler] <<< 阶段完成: {name} "
                f"(耗时: {stage.duration_ms:.0f}ms, "
                f"步骤: {stage.step_count})"
            )
        except Exception as e:
            stage.complete(success=False, error=str(e))
            logger.error(f"[Profiler] <<< 阶段失败: {name} - {e}")
            raise
        finally:
            self._current_stage = None
    
    @contextmanager
    def step(
        self,
        name: str,
        **metadata,
    ) -> Generator[StepTiming, None, None]:
        """步骤计时上下文管理器
        
        Args:
            name: 步骤名称
            **metadata: 额外的元数据
            
        Yields:
            StepTiming 对象
        """
        stage_name = self._current_stage.name if self._current_stage else "unknown"
        
        step = StepTiming(
            name=name,
            stage=stage_name,
            start_time=time.perf_counter(),
            metadata=metadata,
        )
        
        if self._current_stage:
            self._current_stage.steps.append(step)
        
        logger.debug(f"[Profiler]   - 步骤开始: {name}")
        
        try:
            yield step
            step.complete(success=True)
            logger.debug(f"[Profiler]   - 步骤完成: {name} ({step.duration_ms:.0f}ms)")
        except Exception as e:
            step.complete(success=False, error=str(e))
            logger.warning(f"[Profiler]   - 步骤失败: {name} - {e}")
            raise
    
    def record_step(
        self,
        name: str,
        duration_ms: float,
        success: bool = True,
        error: str | None = None,
        **metadata,
    ) -> None:
        """手动记录步骤（用于无法使用上下文管理器的场景）
        
        Args:
            name: 步骤名称
            duration_ms: 耗时（毫秒）
            success: 是否成功
            error: 错误信息
            **metadata: 额外的元数据
        """
        stage_name = self._current_stage.name if self._current_stage else "unknown"
        
        step = StepTiming(
            name=name,
            stage=stage_name,
            start_time=0,
            end_time=0,
            duration_ms=duration_ms,
            success=success,
            error=error,
            metadata=metadata,
        )
        
        if self._current_stage:
            self._current_stage.steps.append(step)
        
        status = "OK" if success else "FAIL"
        logger.debug(f"[Profiler]   - 步骤记录: {name} ({duration_ms:.0f}ms) [{status}]")
    
    def finish(self, success: bool | None = None) -> WorkflowProfile:
        """完成性能分析
        
        Args:
            success: 工作流是否成功（默认根据阶段状态判断）
            
        Returns:
            WorkflowProfile 完整的性能数据
        """
        if self._finished:
            return self._get_profile()
        
        self._finished = True
        end_time = time.perf_counter()
        total_duration_ms = (end_time - self._start_time) * 1000
        
        # 自动判断成功状态
        if success is None:
            success = all(s.success for s in self._stages)
        
        profile = WorkflowProfile(
            workflow_id=self.workflow_id,
            workflow_type=self.workflow_type,
            start_time=datetime.now().isoformat(),
            end_time=datetime.now().isoformat(),
            total_duration_ms=total_duration_ms,
            success=success,
            stages=self._stages,
        )
        
        logger.info(
            f"[Profiler] 工作流完成: {self.workflow_id}\n"
            f"           总耗时: {profile._format_duration(total_duration_ms)}\n"
            f"           阶段数: {profile.stage_count}\n"
            f"           步骤数: {profile.total_steps}\n"
            f"           状态: {'成功' if success else '失败'}"
        )
        
        return profile
    
    def _get_profile(self) -> WorkflowProfile:
        """获取当前性能数据"""
        end_time = time.perf_counter()
        total_duration_ms = (end_time - self._start_time) * 1000
        
        return WorkflowProfile(
            workflow_id=self.workflow_id,
            workflow_type=self.workflow_type,
            start_time=datetime.now().isoformat(),
            end_time=datetime.now().isoformat() if self._finished else "",
            total_duration_ms=total_duration_ms,
            success=all(s.success for s in self._stages),
            stages=self._stages,
        )
    
    def generate_report(self, detailed: bool = True) -> str:
        """生成性能报告
        
        Args:
            detailed: 是否包含详细步骤信息
            
        Returns:
            格式化的报告字符串
        """
        profile = self._get_profile()
        
        lines = [
            "",
            "=" * 70,
            f"[PROFILE] 工作流性能报告",
            "=" * 70,
            f"工作流ID: {profile.workflow_id}",
            f"类型: {profile.workflow_type}",
            f"状态: {'成功' if profile.success else '失败'}",
            f"总耗时: {profile._format_duration(profile.total_duration_ms)}",
            f"阶段数: {profile.stage_count} (成功: {profile.successful_stages}, 失败: {profile.failed_stages})",
            f"步骤数: {profile.total_steps}",
            "",
            "-" * 70,
            "阶段耗时分布:",
            "-" * 70,
        ]
        
        # 阶段耗时条形图
        if profile.stages:
            max_duration = max(s.duration_ms for s in profile.stages)
            bar_width = 40
            
            for stage in profile.stages:
                if max_duration > 0:
                    bar_len = int((stage.duration_ms / max_duration) * bar_width)
                else:
                    bar_len = 0
                bar = "█" * bar_len + "░" * (bar_width - bar_len)
                status = "OK" if stage.success else "FAIL"
                duration_str = profile._format_duration(stage.duration_ms)
                lines.append(
                    f"  {stage.name[:20]:<20} [{bar}] {duration_str:>8} [{status}]"
                )
        
        # 详细步骤信息
        if detailed:
            lines.extend([
                "",
                "-" * 70,
                "详细步骤:",
                "-" * 70,
            ])
            
            for stage in profile.stages:
                status = "OK" if stage.success else "FAIL"
                lines.append(
                    f"\n[{stage.name}] "
                    f"({profile._format_duration(stage.duration_ms)}, "
                    f"{stage.step_count} 步骤) [{status}]"
                )
                
                if stage.error:
                    lines.append(f"  错误: {stage.error}")
                
                for step in stage.steps:
                    step_status = "OK" if step.success else "FAIL"
                    lines.append(
                        f"  - {step.name}: "
                        f"{profile._format_duration(step.duration_ms)} [{step_status}]"
                    )
                    if step.error:
                        lines.append(f"    错误: {step.error}")
        
        # 性能统计
        lines.extend([
            "",
            "-" * 70,
            "性能统计:",
            "-" * 70,
        ])
        
        if profile.stages:
            stage_durations = [s.duration_ms for s in profile.stages]
            all_steps = [step for stage in profile.stages for step in stage.steps]
            
            lines.extend([
                f"  阶段统计:",
                f"    最快阶段: {min(profile.stages, key=lambda s: s.duration_ms).name} "
                f"({profile._format_duration(min(stage_durations))})",
                f"    最慢阶段: {max(profile.stages, key=lambda s: s.duration_ms).name} "
                f"({profile._format_duration(max(stage_durations))})",
                f"    平均耗时: {profile._format_duration(statistics.mean(stage_durations))}",
            ])
            
            if all_steps:
                step_durations = [s.duration_ms for s in all_steps]
                lines.extend([
                    f"  步骤统计:",
                    f"    最快步骤: {min(all_steps, key=lambda s: s.duration_ms).name} "
                    f"({profile._format_duration(min(step_durations))})",
                    f"    最慢步骤: {max(all_steps, key=lambda s: s.duration_ms).name} "
                    f"({profile._format_duration(max(step_durations))})",
                    f"    平均耗时: {profile._format_duration(statistics.mean(step_durations))}",
                ])
        
        lines.extend([
            "",
            "=" * 70,
        ])
        
        return "\n".join(lines)
    
    def save_profile(self, filename: str | None = None) -> Path:
        """保存性能数据到文件
        
        Args:
            filename: 文件名（默认使用 workflow_id）
            
        Returns:
            保存的文件路径
        """
        profile = self._get_profile()
        
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        
        if filename is None:
            filename = f"{self.workflow_id}.json"
        
        filepath = self.profile_dir / filename
        filepath.write_text(profile.to_json(), encoding="utf-8")
        
        logger.info(f"[Profiler] 性能数据已保存: {filepath}")
        return filepath
    
    @classmethod
    def load_profile(cls, filepath: Path | str) -> WorkflowProfile:
        """加载性能数据
        
        Args:
            filepath: 文件路径
            
        Returns:
            WorkflowProfile 对象
        """
        data = json.loads(Path(filepath).read_text(encoding="utf-8"))
        
        # 重建对象
        stages = []
        for stage_data in data.get("stages", []):
            steps = []
            for step_data in stage_data.get("steps", []):
                steps.append(StepTiming(
                    name=step_data["name"],
                    stage=stage_data["name"],
                    start_time=0,
                    duration_ms=step_data["duration_ms"],
                    success=step_data["success"],
                    error=step_data.get("error"),
                    metadata=step_data.get("metadata", {}),
                ))
            
            stage = StageTiming(
                name=stage_data["name"],
                start_time=0,
                duration_ms=stage_data["duration_ms"],
                success=stage_data["success"],
                error=stage_data.get("error"),
                steps=steps,
                metadata=stage_data.get("metadata", {}),
            )
            stages.append(stage)
        
        return WorkflowProfile(
            workflow_id=data["workflow_id"],
            workflow_type=data["workflow_type"],
            start_time=data["start_time"],
            end_time=data.get("end_time", ""),
            total_duration_ms=data["total_duration_ms"],
            success=data["success"],
            stages=stages,
            metadata=data.get("metadata", {}),
        )
    
    @classmethod
    def compare_profiles(
        cls,
        profiles: list[WorkflowProfile],
        output_format: str = "text",
    ) -> str:
        """对比多次运行的性能数据
        
        Args:
            profiles: 性能数据列表
            output_format: 输出格式 ("text" 或 "json")
            
        Returns:
            对比报告
        """
        if not profiles:
            return "无可对比的数据"
        
        if output_format == "json":
            return json.dumps({
                "profiles": [p.to_dict() for p in profiles],
                "comparison": cls._calculate_comparison(profiles),
            }, indent=2, ensure_ascii=False)
        
        # 文本格式
        lines = [
            "",
            "=" * 70,
            "[COMPARE] 性能对比报告",
            "=" * 70,
            f"对比数量: {len(profiles)}",
            "",
            "-" * 70,
            "总耗时对比:",
            "-" * 70,
        ]
        
        durations = [p.total_duration_ms for p in profiles]
        for p in profiles:
            lines.append(
                f"  {p.workflow_id}: "
                f"{WorkflowProfile._format_duration(p.total_duration_ms)}"
            )
        
        if len(durations) > 1:
            lines.extend([
                "",
                f"  平均: {WorkflowProfile._format_duration(statistics.mean(durations))}",
                f"  最快: {WorkflowProfile._format_duration(min(durations))}",
                f"  最慢: {WorkflowProfile._format_duration(max(durations))}",
                f"  标准差: {WorkflowProfile._format_duration(statistics.stdev(durations))}",
            ])
        
        # 阶段对比
        all_stages = set()
        for p in profiles:
            for s in p.stages:
                all_stages.add(s.name)
        
        if all_stages:
            lines.extend([
                "",
                "-" * 70,
                "阶段耗时对比:",
                "-" * 70,
            ])
            
            for stage_name in sorted(all_stages):
                stage_durations = []
                for p in profiles:
                    for s in p.stages:
                        if s.name == stage_name:
                            stage_durations.append(s.duration_ms)
                            break
                
                if stage_durations:
                    avg = statistics.mean(stage_durations)
                    lines.append(
                        f"  {stage_name}: "
                        f"平均 {WorkflowProfile._format_duration(avg)} "
                        f"(样本 {len(stage_durations)})"
                    )
        
        lines.extend([
            "",
            "=" * 70,
        ])
        
        return "\n".join(lines)
    
    @classmethod
    def _calculate_comparison(cls, profiles: list[WorkflowProfile]) -> dict:
        """计算对比统计数据"""
        durations = [p.total_duration_ms for p in profiles]
        
        return {
            "count": len(profiles),
            "total_duration": {
                "mean_ms": statistics.mean(durations) if durations else 0,
                "min_ms": min(durations) if durations else 0,
                "max_ms": max(durations) if durations else 0,
                "stdev_ms": statistics.stdev(durations) if len(durations) > 1 else 0,
            },
        }
    
    @classmethod
    def list_profiles(
        cls,
        profile_dir: Path | str | None = None,
        workflow_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """列出所有保存的性能数据
        
        Args:
            profile_dir: 性能数据目录
            workflow_type: 过滤特定工作流类型
            
        Returns:
            性能数据摘要列表
        """
        target_dir = Path(profile_dir) if profile_dir else cls.PROFILE_DIR
        
        if not target_dir.exists():
            return []
        
        profiles = []
        for filepath in target_dir.glob("*.json"):
            try:
                data = json.loads(filepath.read_text(encoding="utf-8"))
                
                if workflow_type and data.get("workflow_type") != workflow_type:
                    continue
                
                profiles.append({
                    "file": filepath.name,
                    "workflow_id": data.get("workflow_id"),
                    "workflow_type": data.get("workflow_type"),
                    "total_duration_ms": data.get("total_duration_ms"),
                    "success": data.get("success"),
                    "stage_count": data.get("stage_count"),
                    "start_time": data.get("start_time"),
                })
            except Exception as e:
                logger.warning(f"读取性能文件失败 {filepath}: {e}")
        
        return sorted(profiles, key=lambda x: x.get("start_time", ""), reverse=True)


# 全局实例
_global_profiler: WorkflowProfiler | None = None


def get_profiler(
    workflow_type: str = "default",
    workflow_id: str | None = None,
) -> WorkflowProfiler:
    """获取或创建全局性能分析器
    
    Args:
        workflow_type: 工作流类型
        workflow_id: 工作流ID
        
    Returns:
        WorkflowProfiler 实例
    """
    global _global_profiler
    if _global_profiler is None:
        _global_profiler = WorkflowProfiler(workflow_type, workflow_id)
    return _global_profiler


def reset_profiler() -> None:
    """重置全局性能分析器"""
    global _global_profiler
    _global_profiler = None


# 导出
__all__ = [
    "StepTiming",
    "StageTiming",
    "WorkflowProfile",
    "WorkflowProfiler",
    "get_profiler",
    "reset_profiler",
]

