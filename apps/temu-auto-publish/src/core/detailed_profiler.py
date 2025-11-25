"""
@PURPOSE: 详细性能分析器 - 从头到尾记录每个操作的精确时间
@OUTLINE:
  - @dataclass ActionTiming: 单个操作的计时（click, hover, fill, wait等）
  - @dataclass StepDetail: 步骤详情（包含多个操作）
  - @dataclass PhaseDetail: 阶段详情（包含多个步骤）
  - class DetailedProfiler: 详细性能分析器
    - action(): 记录单个操作
    - step(): 记录步骤
    - phase(): 记录阶段
    - summary(): 实时摘要
    - report(): 完整报告
@USAGE:
  profiler = DetailedProfiler("batch_edit_18")
  
  with profiler.phase("stage3_batch_edit"):
      with profiler.step("step_12_sku_category"):
          profiler.action("click", "SKU分类导航")
          profiler.action("hover", "分类下拉框")
          profiler.action("click", "单品选项")
          profiler.action("click", "保存修改")
  
  profiler.report()
"""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Generator

from loguru import logger


@dataclass
class ActionTiming:
    """单个操作的计时数据"""
    
    action_type: str  # click, hover, fill, wait, upload, etc.
    target: str  # 操作目标描述
    start_time: float
    end_time: float = 0.0
    duration_ms: float = 0.0
    success: bool = True
    error: str | None = None
    
    def complete(self, success: bool = True, error: str | None = None) -> None:
        self.end_time = time.perf_counter()
        self.duration_ms = (self.end_time - self.start_time) * 1000
        self.success = success
        self.error = error


@dataclass
class StepDetail:
    """步骤详情"""
    
    name: str
    step_number: int
    start_time: float
    end_time: float = 0.0
    duration_ms: float = 0.0
    success: bool = True
    error: str | None = None
    actions: list[ActionTiming] = field(default_factory=list)
    
    def complete(self, success: bool = True, error: str | None = None) -> None:
        self.end_time = time.perf_counter()
        self.duration_ms = (self.end_time - self.start_time) * 1000
        self.success = success
        self.error = error
    
    @property
    def action_count(self) -> int:
        return len(self.actions)
    
    @property
    def total_action_time_ms(self) -> float:
        return sum(a.duration_ms for a in self.actions)
    
    @property
    def overhead_ms(self) -> float:
        """步骤总时间 - 操作时间 = 开销时间"""
        return self.duration_ms - self.total_action_time_ms


@dataclass
class PhaseDetail:
    """阶段详情"""
    
    name: str
    start_time: float
    end_time: float = 0.0
    duration_ms: float = 0.0
    success: bool = True
    error: str | None = None
    steps: list[StepDetail] = field(default_factory=list)
    
    def complete(self, success: bool = True, error: str | None = None) -> None:
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


class DetailedProfiler:
    """详细性能分析器"""
    
    def __init__(self, name: str, workflow_id: str | None = None):
        self.name = name
        self.workflow_id = workflow_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.start_time = time.perf_counter()
        self.end_time: float = 0.0
        self.phases: list[PhaseDetail] = []
        self._current_phase: PhaseDetail | None = None
        self._current_step: StepDetail | None = None
        self._step_counter = 0
        
        logger.info(f"[DetailedProfiler] 开始记录: {name} ({self.workflow_id})")
    
    @contextmanager
    def phase(self, name: str) -> Generator[PhaseDetail, None, None]:
        """阶段计时上下文"""
        phase = PhaseDetail(name=name, start_time=time.perf_counter())
        self._current_phase = phase
        self.phases.append(phase)
        
        logger.info(f"[Profiler] >>> 阶段开始: {name}")
        
        try:
            yield phase
            phase.complete(success=True)
        except Exception as e:
            phase.complete(success=False, error=str(e))
            raise
        finally:
            self._current_phase = None
            duration = self._format_duration(phase.duration_ms)
            status = "OK" if phase.success else "FAIL"
            logger.info(f"[Profiler] <<< 阶段完成: {name} ({duration}) [{status}]")
    
    @contextmanager
    def step(self, name: str) -> Generator[StepDetail, None, None]:
        """步骤计时上下文"""
        self._step_counter += 1
        step = StepDetail(
            name=name,
            step_number=self._step_counter,
            start_time=time.perf_counter()
        )
        self._current_step = step
        
        if self._current_phase:
            self._current_phase.steps.append(step)
        
        logger.debug(f"[Profiler]   步骤 {self._step_counter}: {name}")
        
        try:
            yield step
            step.complete(success=True)
        except Exception as e:
            step.complete(success=False, error=str(e))
            raise
        finally:
            self._current_step = None
            duration = self._format_duration(step.duration_ms)
            status = "OK" if step.success else "FAIL"
            logger.debug(f"[Profiler]   步骤完成: {name} ({duration}) [{status}]")
    
    def action(
        self,
        action_type: str,
        target: str,
        duration_ms: float | None = None,
        success: bool = True,
        error: str | None = None
    ) -> None:
        """记录单个操作"""
        action = ActionTiming(
            action_type=action_type,
            target=target,
            start_time=time.perf_counter(),
        )
        
        if duration_ms is not None:
            action.duration_ms = duration_ms
            action.end_time = action.start_time + (duration_ms / 1000)
        else:
            action.complete(success=success, error=error)
        
        action.success = success
        action.error = error
        
        if self._current_step:
            self._current_step.actions.append(action)
        
        if not success:
            logger.warning(f"[Profiler]     {action_type}({target}): FAIL - {error}")
    
    def action_start(self, action_type: str, target: str) -> ActionTiming:
        """开始记录一个操作（用于需要手动结束的场景）"""
        action = ActionTiming(
            action_type=action_type,
            target=target,
            start_time=time.perf_counter(),
        )
        if self._current_step:
            self._current_step.actions.append(action)
        return action
    
    def finish(self) -> None:
        """完成记录"""
        self.end_time = time.perf_counter()
        total_ms = (self.end_time - self.start_time) * 1000
        logger.info(f"[DetailedProfiler] 记录完成: {self.name} (总耗时: {self._format_duration(total_ms)})")
    
    def summary(self) -> str:
        """生成实时摘要"""
        elapsed_ms = (time.perf_counter() - self.start_time) * 1000
        lines = [
            f"=== 实时摘要 ({self._format_duration(elapsed_ms)}) ===",
            f"阶段数: {len(self.phases)}",
            f"步骤数: {self._step_counter}",
        ]
        
        if self._current_phase:
            lines.append(f"当前阶段: {self._current_phase.name}")
        if self._current_step:
            lines.append(f"当前步骤: {self._current_step.name}")
        
        return "\n".join(lines)
    
    def report(self) -> str:
        """生成完整报告"""
        if self.end_time == 0:
            self.finish()
        
        total_ms = (self.end_time - self.start_time) * 1000
        
        lines = [
            "",
            "=" * 80,
            f"[DETAILED PROFILE] {self.name}",
            "=" * 80,
            f"工作流ID: {self.workflow_id}",
            f"总耗时: {self._format_duration(total_ms)}",
            f"阶段数: {len(self.phases)}",
            f"步骤数: {self._step_counter}",
            "",
        ]
        
        # 阶段概览
        lines.append("-" * 80)
        lines.append("阶段概览:")
        lines.append("-" * 80)
        
        for phase in self.phases:
            status = "OK" if phase.success else "FAIL"
            pct = (phase.duration_ms / total_ms * 100) if total_ms > 0 else 0
            lines.append(
                f"  {phase.name:30} {self._format_duration(phase.duration_ms):>10} "
                f"({pct:5.1f}%) [{status}] ({phase.step_count} 步骤)"
            )
        
        # 详细步骤
        lines.append("")
        lines.append("-" * 80)
        lines.append("详细步骤:")
        lines.append("-" * 80)
        
        for phase in self.phases:
            lines.append(f"\n[{phase.name}]")
            
            for step in phase.steps:
                status = "OK" if step.success else "FAIL"
                lines.append(
                    f"  {step.step_number:2}. {step.name:40} "
                    f"{self._format_duration(step.duration_ms):>10} [{status}]"
                )
                
                # 显示操作详情
                if step.actions:
                    for action in step.actions:
                        a_status = "OK" if action.success else "FAIL"
                        lines.append(
                            f"      - {action.action_type:10} {action.target:30} "
                            f"{action.duration_ms:>8.1f}ms [{a_status}]"
                        )
                    
                    # 显示开销
                    if step.overhead_ms > 10:
                        lines.append(
                            f"      * 开销: {step.overhead_ms:.1f}ms "
                            f"(操作: {step.total_action_time_ms:.1f}ms)"
                        )
        
        # 性能统计
        lines.append("")
        lines.append("-" * 80)
        lines.append("性能统计:")
        lines.append("-" * 80)
        
        # 找出最慢的步骤
        all_steps = [s for p in self.phases for s in p.steps]
        if all_steps:
            slowest = max(all_steps, key=lambda s: s.duration_ms)
            fastest = min(all_steps, key=lambda s: s.duration_ms)
            avg_ms = sum(s.duration_ms for s in all_steps) / len(all_steps)
            
            lines.append(f"  最慢步骤: {slowest.name} ({self._format_duration(slowest.duration_ms)})")
            lines.append(f"  最快步骤: {fastest.name} ({self._format_duration(fastest.duration_ms)})")
            lines.append(f"  平均耗时: {self._format_duration(avg_ms)}")
        
        # 操作统计
        all_actions = [a for p in self.phases for s in p.steps for a in s.actions]
        if all_actions:
            lines.append("")
            lines.append("  操作类型统计:")
            action_types: dict[str, list[float]] = {}
            for action in all_actions:
                if action.action_type not in action_types:
                    action_types[action.action_type] = []
                action_types[action.action_type].append(action.duration_ms)
            
            for atype, durations in sorted(action_types.items(), key=lambda x: sum(x[1]), reverse=True):
                total = sum(durations)
                avg = total / len(durations)
                lines.append(
                    f"    {atype:15} 次数: {len(durations):3}  "
                    f"总计: {self._format_duration(total):>10}  "
                    f"平均: {avg:>8.1f}ms"
                )
        
        lines.append("")
        lines.append("=" * 80)
        
        return "\n".join(lines)
    
    def save(self, directory: str = "data/profiles") -> str:
        """保存性能数据到 JSON 文件"""
        if self.end_time == 0:
            self.finish()
        
        dir_path = Path(directory)
        dir_path.mkdir(parents=True, exist_ok=True)
        
        filename = f"detailed_{self.name}_{self.workflow_id}.json"
        filepath = dir_path / filename
        
        data = {
            "name": self.name,
            "workflow_id": self.workflow_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "total_duration_ms": (self.end_time - self.start_time) * 1000,
            "phases": [self._phase_to_dict(p) for p in self.phases],
            "generated_at": datetime.now().isoformat(),
        }
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"[DetailedProfiler] 数据已保存: {filepath}")
        return str(filepath)
    
    def _phase_to_dict(self, phase: PhaseDetail) -> dict:
        return {
            "name": phase.name,
            "duration_ms": phase.duration_ms,
            "success": phase.success,
            "error": phase.error,
            "step_count": phase.step_count,
            "steps": [self._step_to_dict(s) for s in phase.steps],
        }
    
    def _step_to_dict(self, step: StepDetail) -> dict:
        return {
            "name": step.name,
            "step_number": step.step_number,
            "duration_ms": step.duration_ms,
            "success": step.success,
            "error": step.error,
            "action_count": step.action_count,
            "total_action_time_ms": step.total_action_time_ms,
            "overhead_ms": step.overhead_ms,
            "actions": [self._action_to_dict(a) for a in step.actions],
        }
    
    def _action_to_dict(self, action: ActionTiming) -> dict:
        return {
            "type": action.action_type,
            "target": action.target,
            "duration_ms": action.duration_ms,
            "success": action.success,
            "error": action.error,
        }
    
    @staticmethod
    def _format_duration(ms: float) -> str:
        """格式化时间显示"""
        if ms < 1000:
            return f"{ms:.0f}ms"
        elif ms < 60000:
            return f"{ms/1000:.1f}s"
        else:
            minutes = int(ms // 60000)
            seconds = (ms % 60000) / 1000
            return f"{minutes}m {seconds:.1f}s"


# 全局实例
_detailed_profiler: DetailedProfiler | None = None


def get_detailed_profiler(name: str = "batch_edit", workflow_id: str | None = None) -> DetailedProfiler:
    """获取或创建详细分析器实例"""
    global _detailed_profiler
    if _detailed_profiler is None:
        _detailed_profiler = DetailedProfiler(name, workflow_id)
    return _detailed_profiler


def reset_detailed_profiler() -> None:
    """重置详细分析器"""
    global _detailed_profiler
    _detailed_profiler = None

