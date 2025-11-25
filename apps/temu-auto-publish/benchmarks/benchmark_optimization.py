"""
@PURPOSE: 优化组件性能基准测试
@OUTLINE:
  - BenchmarkResult: 基准测试结果数据结构
  - BenchmarkRunner: 基准测试运行器
  - benchmark_enhanced_retry: 重试机制基准测试
  - benchmark_checkpoint_manager: 断点管理基准测试
  - benchmark_smart_wait: 智能等待基准测试
  - benchmark_resilient_selector: 弹性选择器基准测试
@USAGE:
  python -m benchmarks.benchmark_optimization
  python -m benchmarks.benchmark_optimization --iterations 100
  python -m benchmarks.benchmark_optimization --output results.json
@DEPENDENCIES:
  - 外部: asyncio, statistics, json
  - 内部: enhanced_retry, checkpoint_manager, smart_wait_mixin, resilient_selector
"""

from __future__ import annotations

import argparse
import asyncio
import gc
import json
import statistics
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable
from unittest.mock import AsyncMock, MagicMock

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.enhanced_retry import (
    EnhancedRetryHandler,
    RetryPolicy,
    RetryOutcome,
    smart_retry,
)
from src.core.checkpoint_manager import (
    CheckpointManager,
    WorkflowCheckpoint,
    StageCheckpoint,
)
from src.browser.smart_wait_mixin import (
    SmartWaitMixin,
    AdaptiveWaitConfig,
    WaitMetrics,
)
from src.browser.resilient_selector import (
    ResilientLocator,
    SelectorChain,
    SelectorHitMetrics,
)
from src.core.retry_handler import RetryableError


@dataclass
class BenchmarkResult:
    """单个基准测试结果"""
    
    name: str
    iterations: int
    total_time_ms: float
    avg_time_ms: float
    min_time_ms: float
    max_time_ms: float
    std_dev_ms: float
    median_time_ms: float
    percentile_95_ms: float
    percentile_99_ms: float
    throughput_per_sec: float
    memory_delta_kb: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
    
    def __str__(self) -> str:
        return (
            f"{self.name}:\n"
            f"  迭代次数: {self.iterations}\n"
            f"  总耗时: {self.total_time_ms:.2f}ms\n"
            f"  平均耗时: {self.avg_time_ms:.3f}ms\n"
            f"  最小耗时: {self.min_time_ms:.3f}ms\n"
            f"  最大耗时: {self.max_time_ms:.3f}ms\n"
            f"  标准差: {self.std_dev_ms:.3f}ms\n"
            f"  中位数: {self.median_time_ms:.3f}ms\n"
            f"  P95: {self.percentile_95_ms:.3f}ms\n"
            f"  P99: {self.percentile_99_ms:.3f}ms\n"
            f"  吞吐量: {self.throughput_per_sec:.1f}/s"
        )


@dataclass
class BenchmarkSuite:
    """基准测试套件结果"""
    
    timestamp: str
    python_version: str
    platform: str
    results: list[BenchmarkResult]
    summary: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "python_version": self.python_version,
            "platform": self.platform,
            "results": [r.to_dict() for r in self.results],
            "summary": self.summary,
        }
    
    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


class BenchmarkRunner:
    """基准测试运行器"""
    
    def __init__(self, iterations: int = 100, warmup_iterations: int = 10):
        self.iterations = iterations
        self.warmup_iterations = warmup_iterations
        self.results: list[BenchmarkResult] = []
    
    async def run_async_benchmark(
        self,
        name: str,
        func: Callable[[], Awaitable[Any]],
        setup: Callable[[], Awaitable[None]] | None = None,
        teardown: Callable[[], Awaitable[None]] | None = None,
    ) -> BenchmarkResult:
        """运行异步基准测试"""
        
        print(f"\n[TIME] 运行基准测试: {name}")
        print(f"   预热 {self.warmup_iterations} 次, 测试 {self.iterations} 次")
        
        # 预热
        for _ in range(self.warmup_iterations):
            if setup:
                await setup()
            await func()
            if teardown:
                await teardown()
        
        # 强制垃圾回收
        gc.collect()
        
        # 正式测试
        times_ms: list[float] = []
        
        for i in range(self.iterations):
            if setup:
                await setup()
            
            start = time.perf_counter()
            await func()
            elapsed_ms = (time.perf_counter() - start) * 1000
            times_ms.append(elapsed_ms)
            
            if teardown:
                await teardown()
            
            # 进度显示
            if (i + 1) % max(1, self.iterations // 10) == 0:
                print(f"   进度: {i + 1}/{self.iterations}")
        
        # 计算统计数据
        sorted_times = sorted(times_ms)
        total_time = sum(times_ms)
        
        result = BenchmarkResult(
            name=name,
            iterations=self.iterations,
            total_time_ms=total_time,
            avg_time_ms=statistics.mean(times_ms),
            min_time_ms=min(times_ms),
            max_time_ms=max(times_ms),
            std_dev_ms=statistics.stdev(times_ms) if len(times_ms) > 1 else 0,
            median_time_ms=statistics.median(times_ms),
            percentile_95_ms=sorted_times[int(len(sorted_times) * 0.95)],
            percentile_99_ms=sorted_times[int(len(sorted_times) * 0.99)],
            throughput_per_sec=1000 / statistics.mean(times_ms) if statistics.mean(times_ms) > 0 else 0,
        )
        
        self.results.append(result)
        print(f"   [OK] 完成: 平均 {result.avg_time_ms:.3f}ms")
        
        return result
    
    def run_sync_benchmark(
        self,
        name: str,
        func: Callable[[], Any],
        setup: Callable[[], None] | None = None,
        teardown: Callable[[], None] | None = None,
    ) -> BenchmarkResult:
        """运行同步基准测试"""
        
        print(f"\n[TIME] 运行基准测试: {name}")
        
        # 预热
        for _ in range(self.warmup_iterations):
            if setup:
                setup()
            func()
            if teardown:
                teardown()
        
        gc.collect()
        
        # 正式测试
        times_ms: list[float] = []
        
        for i in range(self.iterations):
            if setup:
                setup()
            
            start = time.perf_counter()
            func()
            elapsed_ms = (time.perf_counter() - start) * 1000
            times_ms.append(elapsed_ms)
            
            if teardown:
                teardown()
        
        sorted_times = sorted(times_ms)
        total_time = sum(times_ms)
        
        result = BenchmarkResult(
            name=name,
            iterations=self.iterations,
            total_time_ms=total_time,
            avg_time_ms=statistics.mean(times_ms),
            min_time_ms=min(times_ms),
            max_time_ms=max(times_ms),
            std_dev_ms=statistics.stdev(times_ms) if len(times_ms) > 1 else 0,
            median_time_ms=statistics.median(times_ms),
            percentile_95_ms=sorted_times[int(len(sorted_times) * 0.95)],
            percentile_99_ms=sorted_times[int(len(sorted_times) * 0.99)],
            throughput_per_sec=1000 / statistics.mean(times_ms) if statistics.mean(times_ms) > 0 else 0,
        )
        
        self.results.append(result)
        print(f"   [OK] 完成: 平均 {result.avg_time_ms:.3f}ms")
        
        return result
    
    def generate_report(self) -> BenchmarkSuite:
        """生成测试报告"""
        import platform
        
        suite = BenchmarkSuite(
            timestamp=datetime.now().isoformat(),
            python_version=sys.version,
            platform=platform.platform(),
            results=self.results,
            summary={
                "total_benchmarks": len(self.results),
                "total_iterations": sum(r.iterations for r in self.results),
                "total_time_ms": sum(r.total_time_ms for r in self.results),
                "fastest_benchmark": min(self.results, key=lambda r: r.avg_time_ms).name if self.results else None,
                "slowest_benchmark": max(self.results, key=lambda r: r.avg_time_ms).name if self.results else None,
            },
        )
        
        return suite


# ============= 基准测试函数 =============


async def benchmark_enhanced_retry(runner: BenchmarkRunner) -> None:
    """增强重试机制基准测试"""
    
    # 测试1: 成功执行（无重试）
    async def success_func():
        return "success"
    
    handler = EnhancedRetryHandler(RetryPolicy(max_attempts=3))
    
    await runner.run_async_benchmark(
        name="EnhancedRetry - 成功执行(无重试)",
        func=lambda: handler.execute(success_func),
    )
    
    # 测试2: 重试后成功
    call_count = 0
    
    async def retry_then_succeed():
        nonlocal call_count
        call_count += 1
        if call_count % 3 != 0:  # 每3次成功一次
            raise RetryableError("模拟失败")
        return "success"
    
    handler2 = EnhancedRetryHandler(
        RetryPolicy(max_attempts=5, initial_delay_ms=1, jitter=False)
    )
    
    await runner.run_async_benchmark(
        name="EnhancedRetry - 重试后成功(2次重试)",
        func=lambda: handler2.execute(retry_then_succeed),
    )
    
    # 测试3: 延迟计算性能
    policy = RetryPolicy(
        initial_delay_ms=100,
        backoff_factor=2.0,
        jitter=True,
    )
    
    runner.run_sync_benchmark(
        name="RetryPolicy - 延迟计算(带抖动)",
        func=lambda: [policy.get_delay(i) for i in range(1, 6)],
    )
    
    # 测试4: 重试条件判断
    runner.run_sync_benchmark(
        name="RetryPolicy - 可重试判断",
        func=lambda: policy.is_retryable(RetryableError("test"), 1),
    )
    
    # 测试5: smart_retry 装饰器
    @smart_retry(max_attempts=2, initial_delay_ms=1)
    async def decorated_success():
        return 42
    
    await runner.run_async_benchmark(
        name="smart_retry 装饰器 - 成功执行",
        func=decorated_success,
    )


async def benchmark_checkpoint_manager(runner: BenchmarkRunner) -> None:
    """断点管理基准测试"""
    
    with tempfile.TemporaryDirectory() as tmpdir:
        checkpoint_dir = Path(tmpdir)
        
        # 测试1: 保存检查点
        manager = CheckpointManager("bench_workflow", checkpoint_dir=checkpoint_dir)
        
        await runner.run_async_benchmark(
            name="CheckpointManager - 保存检查点",
            func=lambda: manager.save_checkpoint(
                "stage1",
                {"data": list(range(100))},
                global_data={"key": "value"},
            ),
        )
        
        # 测试2: 加载检查点
        await runner.run_async_benchmark(
            name="CheckpointManager - 加载检查点",
            func=lambda: manager.load_checkpoint(),
        )
        
        # 测试3: 标记阶段完成
        await runner.run_async_benchmark(
            name="CheckpointManager - 标记阶段完成",
            func=lambda: manager.mark_stage_complete("stage_test", {"result": "ok"}),
        )
        
        # 测试4: 检查是否跳过阶段
        runner.run_sync_benchmark(
            name="CheckpointManager - 跳过阶段判断",
            func=lambda: manager.should_skip_stage("stage1"),
        )
        
        # 测试5: 获取恢复信息
        runner.run_sync_benchmark(
            name="CheckpointManager - 获取恢复信息",
            func=lambda: manager.get_resume_info(),
        )
        
        # 测试6: WorkflowCheckpoint 序列化
        checkpoint = WorkflowCheckpoint(
            workflow_id="test",
            stages={
                f"stage{i}": StageCheckpoint(
                    name=f"stage{i}",
                    status="completed",
                    data={"items": list(range(50))},
                )
                for i in range(5)
            },
        )
        
        runner.run_sync_benchmark(
            name="WorkflowCheckpoint - to_dict 序列化",
            func=lambda: checkpoint.to_dict(),
        )
        
        # 测试7: WorkflowCheckpoint 反序列化
        data = checkpoint.to_dict()
        runner.run_sync_benchmark(
            name="WorkflowCheckpoint - from_dict 反序列化",
            func=lambda: WorkflowCheckpoint.from_dict(data.copy()),
        )


async def benchmark_smart_wait(runner: BenchmarkRunner) -> None:
    """智能等待基准测试"""
    
    # 创建模拟 Page 对象
    def create_mock_page():
        page = MagicMock()
        page.wait_for_load_state = AsyncMock(return_value=None)
        page.evaluate = AsyncMock(return_value=(1000, 50))
        return page
    
    mock_page = create_mock_page()
    mixin = SmartWaitMixin()
    
    # 测试1: 自适应等待（无网络/DOM检测）
    await runner.run_async_benchmark(
        name="SmartWait - 自适应等待(最小等待)",
        func=lambda: mixin.adaptive_wait(
            mock_page,
            "bench_op",
            min_ms=1,
            max_ms=10,
            wait_for_network=False,
            wait_for_dom=False,
        ),
    )
    
    # 测试2: 网络空闲等待
    await runner.run_async_benchmark(
        name="SmartWait - 网络空闲等待",
        func=lambda: mixin._wait_for_network_quiet(mock_page, timeout_ms=100),
    )
    
    # 测试3: DOM 稳定检测
    await runner.run_async_benchmark(
        name="SmartWait - DOM稳定检测",
        func=lambda: mixin._wait_for_dom_stable(
            mock_page,
            timeout_ms=50,
            checks=2,
            interval_ms=5,
        ),
    )
    
    # 测试4: 统计数据更新
    runner.run_sync_benchmark(
        name="SmartWait - 统计更新",
        func=lambda: mixin._update_wait_metrics("bench_op", 50.0, True),
    )
    
    # 测试5: 获取统计数据
    runner.run_sync_benchmark(
        name="SmartWait - 获取统计",
        func=lambda: mixin.get_wait_statistics(),
    )
    
    # 测试6: 边界框比较
    box1 = {"x": 100, "y": 200, "width": 50, "height": 30}
    box2 = {"x": 100.5, "y": 200.5, "width": 50.5, "height": 30.5}
    
    runner.run_sync_benchmark(
        name="SmartWait - 边界框比较",
        func=lambda: mixin._boxes_equal(box1, box2),
    )
    
    # 测试7: WaitMetrics 记录
    metrics = WaitMetrics(operation="bench")
    runner.run_sync_benchmark(
        name="WaitMetrics - 记录操作",
        func=lambda: metrics.record(50.0, True),
    )


async def benchmark_resilient_selector(runner: BenchmarkRunner) -> None:
    """弹性选择器基准测试"""
    
    # 创建模拟 Page 对象
    def create_mock_page():
        page = MagicMock()
        mock_locator = MagicMock()
        mock_locator.wait_for = AsyncMock()
        mock_locator.click = AsyncMock()
        mock_locator.fill = AsyncMock()
        mock_locator.clear = AsyncMock()
        page.locator = MagicMock(return_value=mock_locator)
        return page
    
    mock_page = create_mock_page()
    locator = ResilientLocator()
    
    # 测试1: 元素定位（主选择器成功）
    await runner.run_async_benchmark(
        name="ResilientLocator - 定位元素(主选择器)",
        func=lambda: locator.locate(mock_page, "claim_button", timeout=1000),
    )
    
    # 测试2: 元素定位（降级场景）
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError
    
    call_count = 0
    
    def create_fallback_locator(selector):
        nonlocal call_count
        mock_loc = MagicMock()
        if call_count % 3 == 0:
            mock_loc.wait_for = AsyncMock(side_effect=PlaywrightTimeoutError("timeout"))
        else:
            mock_loc.wait_for = AsyncMock()
        call_count += 1
        return mock_loc
    
    mock_page_fallback = MagicMock()
    mock_page_fallback.locator = MagicMock(side_effect=create_fallback_locator)
    
    locator2 = ResilientLocator()
    await runner.run_async_benchmark(
        name="ResilientLocator - 定位元素(降级场景)",
        func=lambda: locator2.locate(mock_page_fallback, "claim_button", timeout=500),
    )
    
    # 测试3: 点击操作
    await runner.run_async_benchmark(
        name="ResilientLocator - 点击元素",
        func=lambda: locator.click(mock_page, "claim_button"),
    )
    
    # 测试4: 填写操作
    await runner.run_async_benchmark(
        name="ResilientLocator - 填写元素",
        func=lambda: locator.fill(mock_page, "title_input", "测试内容"),
    )
    
    # 测试5: 注册选择器链
    custom_chain = SelectorChain(
        key=f"bench_chain",
        primary="#primary",
        fallbacks=["#fallback1", "#fallback2"],
    )
    
    runner.run_sync_benchmark(
        name="ResilientLocator - 注册选择器链",
        func=lambda: locator.register_chain(custom_chain),
    )
    
    # 测试6: 获取统计数据
    # 先生成一些统计数据
    for _ in range(10):
        locator._metrics["claim_button"] = SelectorHitMetrics(chain_key="claim_button")
        locator._metrics["claim_button"].record_hit(0, 50.0)
    
    runner.run_sync_benchmark(
        name="ResilientLocator - 获取统计",
        func=lambda: locator.get_metrics(),
    )
    
    # 测试7: 优化建议
    metrics = SelectorHitMetrics(chain_key="bench")
    for _ in range(15):
        metrics.record_hit(1, 100.0)  # 模拟降级命中
    locator._metrics["bench_suggest"] = metrics
    
    runner.run_sync_benchmark(
        name="ResilientLocator - 生成优化建议",
        func=lambda: locator.suggest_optimizations(),
    )
    
    # 测试8: SelectorHitMetrics 转换
    runner.run_sync_benchmark(
        name="SelectorHitMetrics - to_dict",
        func=lambda: metrics.to_dict(),
    )


async def benchmark_comparison(runner: BenchmarkRunner) -> None:
    """对比测试：优化组件 vs 传统方法"""
    
    # 对比1: 智能等待 vs 固定等待
    print("\n[COMPARE] 对比测试: 智能等待 vs 固定等待")
    
    # 固定等待
    async def fixed_wait():
        await asyncio.sleep(0.01)  # 10ms
    
    await runner.run_async_benchmark(
        name="对比 - 固定等待 10ms",
        func=fixed_wait,
    )
    
    # 智能等待（最小等待）
    mock_page = MagicMock()
    mock_page.wait_for_load_state = AsyncMock()
    mock_page.evaluate = AsyncMock(return_value=(100, 10))
    mixin = SmartWaitMixin()
    
    await runner.run_async_benchmark(
        name="对比 - 智能等待(自适应)",
        func=lambda: mixin.adaptive_wait(
            mock_page, "compare", min_ms=1, max_ms=20,
            wait_for_network=False, wait_for_dom=False,
        ),
    )
    
    # 对比2: 增强重试 vs 简单重试
    print("\n[COMPARE] 对比测试: 增强重试 vs 简单重试")
    
    # 简单重试
    async def simple_retry(func, max_attempts=3):
        for i in range(max_attempts):
            try:
                return await func()
            except Exception:
                if i == max_attempts - 1:
                    raise
                await asyncio.sleep(0.001)
    
    async def success():
        return "ok"
    
    await runner.run_async_benchmark(
        name="对比 - 简单重试(成功)",
        func=lambda: simple_retry(success),
    )
    
    handler = EnhancedRetryHandler(
        RetryPolicy(max_attempts=3, initial_delay_ms=1, jitter=False)
    )
    
    await runner.run_async_benchmark(
        name="对比 - 增强重试(成功)",
        func=lambda: handler.execute(success),
    )


def print_summary(suite: BenchmarkSuite) -> None:
    """打印测试摘要"""
    
    print("\n" + "=" * 70)
    print("[REPORT] 基准测试报告")
    print("=" * 70)
    print(f"时间: {suite.timestamp}")
    print(f"Python: {suite.python_version.split()[0]}")
    print(f"平台: {suite.platform}")
    print(f"测试数量: {suite.summary['total_benchmarks']}")
    print(f"总迭代: {suite.summary['total_iterations']}")
    print(f"总耗时: {suite.summary['total_time_ms']:.2f}ms")
    
    print("\n" + "-" * 70)
    print("详细结果:")
    print("-" * 70)
    
    # 按模块分组显示
    groups: dict[str, list[BenchmarkResult]] = {}
    for r in suite.results:
        if "EnhancedRetry" in r.name or "RetryPolicy" in r.name or "smart_retry" in r.name:
            group = "增强重试 (EnhancedRetry)"
        elif "Checkpoint" in r.name or "Workflow" in r.name:
            group = "断点管理 (CheckpointManager)"
        elif "SmartWait" in r.name or "WaitMetrics" in r.name:
            group = "智能等待 (SmartWaitMixin)"
        elif "ResilientLocator" in r.name or "Selector" in r.name:
            group = "弹性选择器 (ResilientLocator)"
        elif "对比" in r.name:
            group = "对比测试"
        else:
            group = "其他"
        
        if group not in groups:
            groups[group] = []
        groups[group].append(r)
    
    for group_name, results in groups.items():
        print(f"\n【{group_name}】")
        for r in results:
            print(f"  {r.name}")
            print(f"    平均: {r.avg_time_ms:.3f}ms | "
                  f"中位数: {r.median_time_ms:.3f}ms | "
                  f"P95: {r.percentile_95_ms:.3f}ms | "
                  f"吞吐: {r.throughput_per_sec:.0f}/s")
    
    # 性能排名
    print("\n" + "-" * 70)
    print("[RANK] 性能排名 (按平均耗时):")
    print("-" * 70)
    
    sorted_results = sorted(suite.results, key=lambda r: r.avg_time_ms)
    for i, r in enumerate(sorted_results[:10], 1):
        print(f"  {i}. {r.name}: {r.avg_time_ms:.3f}ms")
    
    print("\n" + "=" * 70)


async def main():
    """主函数"""
    
    # 设置控制台编码（Windows）
    import io
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    
    parser = argparse.ArgumentParser(description="优化组件性能基准测试")
    parser.add_argument("-i", "--iterations", type=int, default=100,
                        help="每个测试的迭代次数 (默认: 100)")
    parser.add_argument("-w", "--warmup", type=int, default=10,
                        help="预热迭代次数 (默认: 10)")
    parser.add_argument("-o", "--output", type=str, default=None,
                        help="输出 JSON 文件路径")
    parser.add_argument("--module", type=str, default="all",
                        choices=["all", "retry", "checkpoint", "wait", "selector", "compare"],
                        help="要测试的模块")
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("[BENCHMARK] 优化组件性能基准测试")
    print("=" * 70)
    print(f"迭代次数: {args.iterations}")
    print(f"预热次数: {args.warmup}")
    print(f"测试模块: {args.module}")
    
    runner = BenchmarkRunner(
        iterations=args.iterations,
        warmup_iterations=args.warmup,
    )
    
    # 运行指定模块的基准测试
    if args.module in ("all", "retry"):
        await benchmark_enhanced_retry(runner)
    
    if args.module in ("all", "checkpoint"):
        await benchmark_checkpoint_manager(runner)
    
    if args.module in ("all", "wait"):
        await benchmark_smart_wait(runner)
    
    if args.module in ("all", "selector"):
        await benchmark_resilient_selector(runner)
    
    if args.module in ("all", "compare"):
        await benchmark_comparison(runner)
    
    # 生成报告
    suite = runner.generate_report()
    print_summary(suite)
    
    # 输出 JSON
    if args.output:
        output_path = Path(args.output)
        output_path.write_text(suite.to_json(), encoding="utf-8")
        print(f"\n[FILE] 结果已保存至: {output_path}")
    
    return suite


if __name__ == "__main__":
    asyncio.run(main())

