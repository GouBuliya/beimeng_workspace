"""
@PURPOSE: 指标收集器 - 收集和存储工作流执行指标
@OUTLINE:
  - class MetricType: 指标类型枚举
  - class Metric: 单个指标数据
  - class WorkflowMetrics: 工作流指标集合
  - class MetricsCollector: 指标收集器
  - def get_metrics(): 获取全局指标收集器
@GOTCHAS:
  - 指标数据会占用内存，需要定期清理
  - 线程安全问题需要考虑
@TECH_DEBT:
  - TODO: 添加指标持久化到数据库
  - TODO: 添加实时指标推送
@DEPENDENCIES:
  - 外部: loguru, dataclasses, json
"""

import json
import time
import uuid
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger


# ========== 指标类型 ==========

class MetricType(str, Enum):
    """指标类型枚举."""
    
    COUNTER = "counter"  # 计数器
    GAUGE = "gauge"  # 仪表（瞬时值）
    TIMER = "timer"  # 计时器
    HISTOGRAM = "histogram"  # 直方图


# ========== 数据模型 ==========

@dataclass
class Metric:
    """单个指标数据.
    
    Attributes:
        name: 指标名称
        value: 指标值
        type: 指标类型
        timestamp: 时间戳
        labels: 标签（用于分组）
    """
    name: str
    value: float
    type: MetricType
    timestamp: float = field(default_factory=time.time)
    labels: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "name": self.name,
            "value": self.value,
            "type": self.type.value,
            "timestamp": self.timestamp,
            "labels": self.labels,
        }


@dataclass
class WorkflowMetrics:
    """工作流指标集合.
    
    Attributes:
        workflow_id: 工作流ID
        start_time: 开始时间
        end_time: 结束时间
        duration: 总耗时（秒）
        status: 执行状态
        stages: 各阶段指标
        operations: 操作级别指标
        errors: 错误统计
        custom_metrics: 自定义指标
    """
    workflow_id: str
    start_time: str
    end_time: Optional[str] = None
    duration: Optional[float] = None
    status: str = "running"
    stages: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    operations: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    custom_metrics: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return asdict(self)
    
    def to_json(self) -> str:
        """转换为JSON字符串."""
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


# ========== 指标收集器 ==========

class MetricsCollector:
    """指标收集器 - 收集和管理执行指标.
    
    Examples:
        >>> collector = MetricsCollector()
        >>> workflow_id = collector.start_workflow()
        >>> collector.record_metric("products_processed", 20, workflow_id=workflow_id)
        >>> collector.end_workflow(workflow_id, "success")
    """
    
    def __init__(self, storage_dir: Optional[Path] = None):
        """初始化指标收集器.
        
        Args:
            storage_dir: 指标存储目录，默认为 data/metrics
        """
        self.storage_dir = storage_dir or Path("data/metrics")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # 内存中的指标数据
        self.workflows: Dict[str, WorkflowMetrics] = {}
        self.metrics: List[Metric] = []
        self.timers: Dict[str, float] = {}  # 活动计时器
        
        # 统计数据
        self.counters: Dict[str, float] = defaultdict(float)
        self.gauges: Dict[str, float] = {}
        
        logger.debug(f"指标收集器已初始化，存储目录: {self.storage_dir}")
    
    # ========== 工作流级别 ==========
    
    def start_workflow(self, workflow_id: Optional[str] = None) -> str:
        """开始记录工作流.
        
        Args:
            workflow_id: 工作流ID，如果为None则自动生成
            
        Returns:
            工作流ID
        """
        if workflow_id is None:
            workflow_id = f"workflow_{uuid.uuid4().hex[:8]}"
        
        self.workflows[workflow_id] = WorkflowMetrics(
            workflow_id=workflow_id,
            start_time=datetime.now().isoformat(),
        )
        
        logger.debug(f"开始记录工作流: {workflow_id}")
        return workflow_id
    
    def end_workflow(self, workflow_id: str, status: str = "success"):
        """结束记录工作流.
        
        Args:
            workflow_id: 工作流ID
            status: 执行状态（success/failure）
        """
        if workflow_id not in self.workflows:
            logger.warning(f"工作流不存在: {workflow_id}")
            return
        
        workflow = self.workflows[workflow_id]
        workflow.end_time = datetime.now().isoformat()
        workflow.status = status
        
        # 计算总耗时
        start = datetime.fromisoformat(workflow.start_time)
        end = datetime.fromisoformat(workflow.end_time)
        workflow.duration = (end - start).total_seconds()
        
        # 保存到文件
        self._save_workflow(workflow_id)
        
        logger.info(f"工作流完成: {workflow_id}, 状态: {status}, 耗时: {workflow.duration:.2f}秒")
    
    def record_stage(
        self,
        workflow_id: str,
        stage_name: str,
        duration: float,
        success: bool = True,
        **kwargs
    ):
        """记录阶段指标.
        
        Args:
            workflow_id: 工作流ID
            stage_name: 阶段名称
            duration: 耗时（秒）
            success: 是否成功
            **kwargs: 其他自定义指标
        """
        if workflow_id not in self.workflows:
            logger.warning(f"工作流不存在: {workflow_id}")
            return
        
        self.workflows[workflow_id].stages[stage_name] = {
            "duration": duration,
            "success": success,
            **kwargs
        }
        
        logger.debug(f"记录阶段: {stage_name}, 耗时: {duration:.2f}秒")
    
    def record_operation(
        self,
        workflow_id: str,
        operation_name: str,
        duration: float,
        success: bool = True,
        **kwargs
    ):
        """记录操作指标.
        
        Args:
            workflow_id: 工作流ID
            operation_name: 操作名称
            duration: 耗时（秒）
            success: 是否成功
            **kwargs: 其他自定义指标
        """
        if workflow_id not in self.workflows:
            logger.warning(f"工作流不存在: {workflow_id}")
            return
        
        if operation_name not in self.workflows[workflow_id].operations:
            self.workflows[workflow_id].operations[operation_name] = {
                "count": 0,
                "total_duration": 0.0,
                "success_count": 0,
                "failure_count": 0,
            }
        
        op = self.workflows[workflow_id].operations[operation_name]
        op["count"] += 1
        op["total_duration"] += duration
        
        if success:
            op["success_count"] += 1
        else:
            op["failure_count"] += 1
        
        # 计算平均耗时
        op["avg_duration"] = op["total_duration"] / op["count"]
        
        # 添加自定义指标
        for key, value in kwargs.items():
            op[key] = value
    
    def record_error(
        self,
        workflow_id: str,
        error_type: str,
        error_message: str,
        stage: Optional[str] = None
    ):
        """记录错误.
        
        Args:
            workflow_id: 工作流ID
            error_type: 错误类型
            error_message: 错误消息
            stage: 发生错误的阶段
        """
        if workflow_id not in self.workflows:
            logger.warning(f"工作流不存在: {workflow_id}")
            return
        
        self.workflows[workflow_id].errors.append({
            "type": error_type,
            "message": error_message,
            "stage": stage,
            "timestamp": datetime.now().isoformat(),
        })
    
    # ========== 通用指标 ==========
    
    def record_metric(
        self,
        name: str,
        value: float,
        metric_type: MetricType = MetricType.GAUGE,
        workflow_id: Optional[str] = None,
        **labels
    ):
        """记录指标.
        
        Args:
            name: 指标名称
            value: 指标值
            metric_type: 指标类型
            workflow_id: 关联的工作流ID
            **labels: 标签
        """
        metric = Metric(
            name=name,
            value=value,
            type=metric_type,
            labels=labels
        )
        
        if workflow_id:
            metric.labels["workflow_id"] = workflow_id
        
        self.metrics.append(metric)
        
        # 更新统计
        if metric_type == MetricType.COUNTER:
            self.counters[name] += value
        elif metric_type == MetricType.GAUGE:
            self.gauges[name] = value
    
    def increment(self, name: str, value: float = 1.0, **labels):
        """递增计数器.
        
        Args:
            name: 计数器名称
            value: 递增值
            **labels: 标签
        """
        self.record_metric(name, value, MetricType.COUNTER, **labels)
    
    # ========== 计时器 ==========
    
    def start_timer(self, name: str) -> str:
        """开始计时.
        
        Args:
            name: 计时器名称
            
        Returns:
            计时器键（用于停止计时）
        """
        timer_key = f"{name}_{time.time()}"
        self.timers[timer_key] = time.time()
        return timer_key
    
    def stop_timer(self, timer_key: str, workflow_id: Optional[str] = None) -> float:
        """停止计时并记录.
        
        Args:
            timer_key: 计时器键
            workflow_id: 关联的工作流ID
            
        Returns:
            耗时（秒）
        """
        if timer_key not in self.timers:
            logger.warning(f"计时器不存在: {timer_key}")
            return 0.0
        
        start_time = self.timers.pop(timer_key)
        duration = time.time() - start_time
        
        # 提取名称
        name = timer_key.rsplit("_", 1)[0]
        
        # 记录指标
        self.record_metric(name, duration, MetricType.TIMER, workflow_id=workflow_id)
        
        return duration
    
    # ========== 数据查询 ==========
    
    def get_workflow(self, workflow_id: str) -> Optional[WorkflowMetrics]:
        """获取工作流指标.
        
        Args:
            workflow_id: 工作流ID
            
        Returns:
            工作流指标，如果不存在则返回None
        """
        return self.workflows.get(workflow_id)
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息.
        
        Returns:
            统计数据字典
        """
        return {
            "total_workflows": len(self.workflows),
            "total_metrics": len(self.metrics),
            "counters": dict(self.counters),
            "gauges": dict(self.gauges),
            "active_timers": len(self.timers),
        }
    
    # ========== 数据持久化 ==========
    
    def _save_workflow(self, workflow_id: str):
        """保存工作流指标到文件.
        
        Args:
            workflow_id: 工作流ID
        """
        if workflow_id not in self.workflows:
            return
        
        workflow = self.workflows[workflow_id]
        filename = f"{workflow_id}.json"
        filepath = self.storage_dir / filename
        
        try:
            filepath.write_text(workflow.to_json(), encoding="utf-8")
            logger.debug(f"指标已保存: {filename}")
        except Exception as e:
            logger.error(f"保存指标失败: {e}")
    
    def export_to_json(self, output_file: Path):
        """导出所有指标到JSON文件.
        
        Args:
            output_file: 输出文件路径
        """
        data = {
            "workflows": {wid: w.to_dict() for wid, w in self.workflows.items()},
            "metrics": [m.to_dict() for m in self.metrics],
            "statistics": self.get_statistics(),
        }
        
        try:
            output_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            logger.success(f"✓ 指标已导出: {output_file}")
        except Exception as e:
            logger.error(f"导出指标失败: {e}")
    
    def export_to_csv(self, output_file: Path):
        """导出指标到CSV文件.
        
        Args:
            output_file: 输出文件路径
        """
        import csv
        
        try:
            with output_file.open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["name", "value", "type", "timestamp", "labels"])
                
                for metric in self.metrics:
                    writer.writerow([
                        metric.name,
                        metric.value,
                        metric.type.value,
                        metric.timestamp,
                        json.dumps(metric.labels),
                    ])
            
            logger.success(f"✓ 指标已导出: {output_file}")
        except Exception as e:
            logger.error(f"导出指标失败: {e}")


# ========== 全局实例 ==========

_global_metrics_collector: Optional[MetricsCollector] = None


def get_metrics() -> MetricsCollector:
    """获取全局指标收集器实例.
    
    Returns:
        全局指标收集器
    """
    global _global_metrics_collector
    if _global_metrics_collector is None:
        _global_metrics_collector = MetricsCollector()
    return _global_metrics_collector

