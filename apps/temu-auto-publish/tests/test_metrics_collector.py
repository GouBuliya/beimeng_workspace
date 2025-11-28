"""
@PURPOSE: 测试 MetricsCollector 指标收集器
@OUTLINE:
  - TestMetricType: 测试指标类型枚举
  - TestMetric: 测试指标数据类
  - TestWorkflowMetrics: 测试工作流指标
  - TestMetricsCollector: 测试指标收集器主类
  - TestMetricsCollectorTimers: 测试计时器功能
  - TestMetricsCollectorPersistence: 测试持久化功能
@DEPENDENCIES:
  - 外部: pytest, pytest-asyncio
  - 内部: src.core.metrics_collector
"""

import json
import time
from pathlib import Path

import pytest

from src.core.metrics_collector import (
    Metric,
    MetricType,
    MetricsCollector,
    WorkflowMetrics,
    get_metrics,
)


class TestMetricType:
    """测试指标类型枚举"""
    
    def test_metric_types_exist(self):
        """测试所有指标类型存在"""
        assert MetricType.COUNTER == "counter"
        assert MetricType.GAUGE == "gauge"
        assert MetricType.TIMER == "timer"
        assert MetricType.HISTOGRAM == "histogram"
    
    def test_metric_type_is_string_enum(self):
        """测试指标类型是字符串枚举"""
        assert isinstance(MetricType.COUNTER.value, str)
        assert str(MetricType.COUNTER) == "MetricType.COUNTER"


class TestMetric:
    """测试指标数据类"""
    
    def test_create_metric(self):
        """测试创建指标"""
        metric = Metric(
            name="test_metric",
            value=42.0,
            type=MetricType.GAUGE
        )
        
        assert metric.name == "test_metric"
        assert metric.value == 42.0
        assert metric.type == MetricType.GAUGE
        assert metric.timestamp > 0
        assert metric.labels == {}
    
    def test_metric_with_labels(self):
        """测试带标签的指标"""
        metric = Metric(
            name="request_count",
            value=100,
            type=MetricType.COUNTER,
            labels={"endpoint": "/api/test", "method": "GET"}
        )
        
        assert metric.labels["endpoint"] == "/api/test"
        assert metric.labels["method"] == "GET"
    
    def test_metric_to_dict(self):
        """测试指标转换为字典"""
        metric = Metric(
            name="duration",
            value=1.5,
            type=MetricType.TIMER,
            labels={"stage": "first_edit"}
        )
        
        data = metric.to_dict()
        
        assert data["name"] == "duration"
        assert data["value"] == 1.5
        assert data["type"] == "timer"
        assert "timestamp" in data
        assert data["labels"]["stage"] == "first_edit"


class TestWorkflowMetrics:
    """测试工作流指标"""
    
    def test_create_workflow_metrics(self):
        """测试创建工作流指标"""
        wm = WorkflowMetrics(
            workflow_id="WF-001",
            start_time="2024-01-01T00:00:00"
        )
        
        assert wm.workflow_id == "WF-001"
        assert wm.start_time == "2024-01-01T00:00:00"
        assert wm.status == "running"
        assert wm.stages == {}
        assert wm.operations == {}
        assert wm.errors == []
    
    def test_workflow_metrics_to_dict(self):
        """测试工作流指标转换为字典"""
        wm = WorkflowMetrics(
            workflow_id="WF-002",
            start_time="2024-01-01T10:00:00",
            end_time="2024-01-01T10:30:00",
            duration=1800.0,
            status="success"
        )
        wm.stages["first_edit"] = {"duration": 600, "success": True}
        
        data = wm.to_dict()
        
        assert data["workflow_id"] == "WF-002"
        assert data["duration"] == 1800.0
        assert data["status"] == "success"
        assert data["stages"]["first_edit"]["duration"] == 600
    
    def test_workflow_metrics_to_json(self):
        """测试工作流指标转换为JSON"""
        wm = WorkflowMetrics(
            workflow_id="WF-003",
            start_time="2024-01-01T00:00:00"
        )
        
        json_str = wm.to_json()
        data = json.loads(json_str)
        
        assert data["workflow_id"] == "WF-003"


class TestMetricsCollector:
    """测试指标收集器主类"""
    
    @pytest.fixture
    def collector(self, tmp_path):
        """创建临时存储目录的收集器"""
        return MetricsCollector(storage_dir=tmp_path / "metrics")
    
    def test_init(self, collector):
        """测试初始化"""
        assert collector.workflows == {}
        assert collector.metrics == []
        assert collector.storage_dir.exists()
    
    def test_start_workflow(self, collector):
        """测试开始工作流"""
        workflow_id = collector.start_workflow()
        
        assert workflow_id.startswith("workflow_")
        assert workflow_id in collector.workflows
        assert collector.workflows[workflow_id].status == "running"
    
    def test_start_workflow_with_custom_id(self, collector):
        """测试使用自定义ID开始工作流"""
        workflow_id = collector.start_workflow("custom_wf_001")
        
        assert workflow_id == "custom_wf_001"
        assert "custom_wf_001" in collector.workflows
    
    def test_end_workflow(self, collector):
        """测试结束工作流"""
        workflow_id = collector.start_workflow()
        time.sleep(0.1)  # 确保有时间差
        collector.end_workflow(workflow_id, "success")
        
        workflow = collector.workflows[workflow_id]
        assert workflow.status == "success"
        assert workflow.end_time is not None
        assert workflow.duration > 0
    
    def test_end_workflow_not_found(self, collector):
        """测试结束不存在的工作流"""
        # 不应抛出异常
        collector.end_workflow("nonexistent_workflow")
    
    def test_record_stage(self, collector):
        """测试记录阶段"""
        workflow_id = collector.start_workflow()
        collector.record_stage(
            workflow_id,
            "first_edit",
            duration=120.5,
            success=True,
            products_edited=5
        )
        
        stages = collector.workflows[workflow_id].stages
        assert "first_edit" in stages
        assert stages["first_edit"]["duration"] == 120.5
        assert stages["first_edit"]["success"] is True
        assert stages["first_edit"]["products_edited"] == 5
    
    def test_record_operation(self, collector):
        """测试记录操作"""
        workflow_id = collector.start_workflow()
        
        # 记录多次操作
        collector.record_operation(workflow_id, "click_button", 0.5, True)
        collector.record_operation(workflow_id, "click_button", 0.3, True)
        collector.record_operation(workflow_id, "click_button", 0.4, False)
        
        ops = collector.workflows[workflow_id].operations["click_button"]
        assert ops["count"] == 3
        assert ops["success_count"] == 2
        assert ops["failure_count"] == 1
        assert ops["avg_duration"] == pytest.approx(0.4, rel=0.01)
    
    def test_record_error(self, collector):
        """测试记录错误"""
        workflow_id = collector.start_workflow()
        collector.record_error(
            workflow_id,
            "TimeoutError",
            "Element not found within timeout",
            stage="batch_edit"
        )
        
        errors = collector.workflows[workflow_id].errors
        assert len(errors) == 1
        assert errors[0]["type"] == "TimeoutError"
        assert errors[0]["stage"] == "batch_edit"
    
    def test_record_metric(self, collector):
        """测试记录通用指标"""
        workflow_id = collector.start_workflow()
        collector.record_metric(
            "products_processed",
            20,
            MetricType.COUNTER,
            workflow_id=workflow_id,
            source="batch_edit"
        )
        
        assert len(collector.metrics) == 1
        assert collector.metrics[0].name == "products_processed"
        assert collector.metrics[0].value == 20
        assert collector.metrics[0].labels["source"] == "batch_edit"
    
    def test_increment_counter(self, collector):
        """测试递增计数器"""
        collector.increment("api_calls", 1)
        collector.increment("api_calls", 2)
        collector.increment("api_calls", 1)
        
        assert collector.counters["api_calls"] == 4
    
    def test_gauge_metric(self, collector):
        """测试仪表指标"""
        collector.record_metric("memory_usage", 512.0, MetricType.GAUGE)
        collector.record_metric("memory_usage", 768.0, MetricType.GAUGE)
        
        # GAUGE 应该保留最新值
        assert collector.gauges["memory_usage"] == 768.0
    
    def test_get_workflow(self, collector):
        """测试获取工作流"""
        workflow_id = collector.start_workflow("test_wf")
        
        workflow = collector.get_workflow("test_wf")
        assert workflow is not None
        assert workflow.workflow_id == "test_wf"
        
        # 获取不存在的工作流
        assert collector.get_workflow("nonexistent") is None
    
    def test_get_statistics(self, collector):
        """测试获取统计信息"""
        collector.start_workflow()
        collector.start_workflow()
        collector.increment("test_counter", 5)
        collector.record_metric("test_gauge", 100, MetricType.GAUGE)
        
        stats = collector.get_statistics()
        
        assert stats["total_workflows"] == 2
        assert stats["counters"]["test_counter"] == 5
        assert stats["gauges"]["test_gauge"] == 100


class TestMetricsCollectorTimers:
    """测试计时器功能"""
    
    @pytest.fixture
    def collector(self, tmp_path):
        return MetricsCollector(storage_dir=tmp_path / "metrics")
    
    def test_start_and_stop_timer(self, collector):
        """测试开始和停止计时器"""
        timer_key = collector.start_timer("operation_duration")
        time.sleep(0.1)
        duration = collector.stop_timer(timer_key)
        
        assert duration >= 0.1
        assert timer_key not in collector.timers  # 计时器已清理
        assert len(collector.metrics) == 1
        assert collector.metrics[0].name == "operation_duration"
    
    def test_stop_nonexistent_timer(self, collector):
        """测试停止不存在的计时器"""
        duration = collector.stop_timer("nonexistent_timer")
        
        assert duration == 0.0
    
    def test_multiple_timers(self, collector):
        """测试多个计时器并行"""
        timer1 = collector.start_timer("timer1")
        timer2 = collector.start_timer("timer2")
        
        time.sleep(0.05)
        duration1 = collector.stop_timer(timer1)
        
        time.sleep(0.05)
        duration2 = collector.stop_timer(timer2)
        
        assert duration1 < duration2  # timer2 运行更久


class TestMetricsCollectorPersistence:
    """测试持久化功能"""
    
    @pytest.fixture
    def collector(self, tmp_path):
        return MetricsCollector(storage_dir=tmp_path / "metrics")
    
    def test_save_workflow(self, collector):
        """测试保存工作流到文件"""
        workflow_id = collector.start_workflow("test_save")
        collector.record_stage(workflow_id, "stage1", 10.0, True)
        collector.end_workflow(workflow_id, "success")
        
        # 检查文件是否创建
        filepath = collector.storage_dir / f"{workflow_id}.json"
        assert filepath.exists()
        
        # 验证文件内容
        data = json.loads(filepath.read_text(encoding="utf-8"))
        assert data["workflow_id"] == "test_save"
        assert data["status"] == "success"
    
    def test_export_to_json(self, collector, tmp_path):
        """测试导出所有指标到JSON"""
        workflow_id = collector.start_workflow()
        collector.record_metric("test_metric", 42)
        collector.increment("test_counter", 10)
        
        output_file = tmp_path / "export.json"
        collector.export_to_json(output_file)
        
        assert output_file.exists()
        data = json.loads(output_file.read_text(encoding="utf-8"))
        assert "workflows" in data
        assert "metrics" in data
        assert "statistics" in data
    
    def test_export_to_csv(self, collector, tmp_path):
        """测试导出指标到CSV"""
        collector.record_metric("metric1", 100)
        collector.record_metric("metric2", 200)
        
        output_file = tmp_path / "export.csv"
        collector.export_to_csv(output_file)
        
        assert output_file.exists()
        content = output_file.read_text(encoding="utf-8")
        assert "name,value,type,timestamp,labels" in content


class TestGetMetrics:
    """测试全局指标收集器"""
    
    def test_get_metrics_singleton(self):
        """测试获取全局指标收集器"""
        collector1 = get_metrics()
        collector2 = get_metrics()
        
        assert collector1 is collector2
    
    def test_get_metrics_returns_collector(self):
        """测试返回MetricsCollector实例"""
        collector = get_metrics()
        
        assert isinstance(collector, MetricsCollector)





