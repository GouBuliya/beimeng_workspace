"""
@PURPOSE: 测试增强的重试机制
@OUTLINE:
  - test_retry_policy_delay_calculation: 测试延迟计算
  - test_retry_policy_is_retryable: 测试可重试判断
  - test_enhanced_retry_handler_success: 测试成功执行
  - test_enhanced_retry_handler_retry_then_success: 测试重试后成功
  - test_enhanced_retry_handler_exhausted: 测试重试耗尽
  - test_enhanced_retry_handler_non_retryable: 测试不可重试异常
  - test_smart_retry_decorator: 测试智能重试装饰器
@DEPENDENCIES:
  - 外部: pytest, pytest-asyncio
"""


import contextlib

import pytest
from src.core.enhanced_retry import (
    EnhancedRetryHandler,
    RetryOutcome,
    RetryPolicy,
    RetryResult,
    create_stage_retry_policy,
    create_step_retry_policy,
    smart_retry,
)
from src.core.retry_handler import (
    NetworkError,
    NonRetryableError,
    RetryableError,
    ValidationError,
)


class TestRetryPolicy:
    """测试 RetryPolicy 配置类"""

    def test_default_values(self):
        """测试默认值"""
        policy = RetryPolicy()

        assert policy.max_attempts == 3
        assert policy.initial_delay_ms == 500
        assert policy.backoff_factor == 2.0
        assert policy.max_delay_ms == 10_000
        assert policy.jitter is True

    def test_get_delay_calculation(self):
        """测试延迟计算(无抖动)"""
        policy = RetryPolicy(
            initial_delay_ms=1000,
            backoff_factor=2.0,
            jitter=False,
        )

        # 第1次重试: 1000ms = 1s
        assert policy.get_delay(1) == 1.0
        # 第2次重试: 1000 * 2 = 2000ms = 2s
        assert policy.get_delay(2) == 2.0
        # 第3次重试: 1000 * 4 = 4000ms = 4s
        assert policy.get_delay(3) == 4.0

    def test_get_delay_respects_max(self):
        """测试延迟不超过最大值"""
        policy = RetryPolicy(
            initial_delay_ms=5000,
            backoff_factor=3.0,
            max_delay_ms=10000,
            jitter=False,
        )

        # 第3次: 5000 * 9 = 45000 > 10000, 应该被限制
        assert policy.get_delay(3) == 10.0

    def test_get_delay_with_jitter(self):
        """测试抖动范围"""
        policy = RetryPolicy(
            initial_delay_ms=1000,
            jitter=True,
            jitter_factor=0.1,
        )

        # 多次调用应该在范围内变化
        delays = [policy.get_delay(1) for _ in range(10)]
        # 应该在 0.9s - 1.1s 范围内
        for delay in delays:
            assert 0.85 <= delay <= 1.15

        # 应该有一定的变化(不全相同)
        assert len(set(delays)) > 1

    def test_is_retryable_for_retryable_error(self):
        """测试可重试错误判断"""
        policy = RetryPolicy(max_attempts=3)

        # 可重试错误
        assert policy.is_retryable(RetryableError("test"), 1) is True
        assert policy.is_retryable(NetworkError("test"), 1) is True
        assert policy.is_retryable(ConnectionError("test"), 1) is True

    def test_is_retryable_for_non_retryable_error(self):
        """测试不可重试错误判断"""
        policy = RetryPolicy(max_attempts=3)

        # 不可重试错误
        assert policy.is_retryable(NonRetryableError("test"), 1) is False
        assert policy.is_retryable(ValidationError("test"), 1) is False
        assert policy.is_retryable(KeyboardInterrupt(), 1) is False

    def test_is_retryable_respects_max_attempts(self):
        """测试达到最大次数后不再重试"""
        policy = RetryPolicy(max_attempts=3)

        # 第3次尝试后不再重试
        assert policy.is_retryable(RetryableError("test"), 2) is True
        assert policy.is_retryable(RetryableError("test"), 3) is False

    def test_custom_should_retry(self):
        """测试自定义重试条件"""

        def custom_condition(exc: Exception, attempt: int) -> bool:
            # 只在错误消息包含 "retry" 时重试
            return "retry" in str(exc)

        policy = RetryPolicy(
            max_attempts=5,
            should_retry=custom_condition,
        )

        assert policy.is_retryable(RetryableError("please retry"), 1) is True
        assert policy.is_retryable(RetryableError("no way"), 1) is False


class TestRetryResult:
    """测试 RetryResult 结果类"""

    def test_success_property(self):
        """测试成功属性"""
        success_result = RetryResult(outcome=RetryOutcome.SUCCESS, value=42)
        assert success_result.success is True

        failed_result = RetryResult(outcome=RetryOutcome.EXHAUSTED)
        assert failed_result.success is False

    def test_to_dict(self):
        """测试转换为字典"""
        result = RetryResult(
            outcome=RetryOutcome.SUCCESS,
            value="test",
            total_attempts=2,
            total_delay_ms=1500.5,
        )

        data = result.to_dict()

        assert data["outcome"] == "success"
        assert data["success"] is True
        assert data["total_attempts"] == 2
        assert data["total_delay_ms"] == 1500.5


@pytest.mark.asyncio
class TestEnhancedRetryHandler:
    """测试 EnhancedRetryHandler"""

    async def test_success_on_first_attempt(self):
        """测试首次执行成功"""

        async def success_func():
            return "success"

        handler = EnhancedRetryHandler()
        result = await handler.execute(success_func)

        assert result.success is True
        assert result.value == "success"
        assert result.total_attempts == 1
        assert len(result.errors) == 0

    async def test_retry_then_success(self):
        """测试重试后成功"""
        call_count = 0

        async def eventually_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RetryableError(f"失败 {call_count}")
            return "success"

        policy = RetryPolicy(
            max_attempts=5,
            initial_delay_ms=10,  # 快速测试
            jitter=False,
        )
        handler = EnhancedRetryHandler(policy)
        result = await handler.execute(eventually_succeed)

        assert result.success is True
        assert result.value == "success"
        assert result.total_attempts == 3
        assert len(result.errors) == 2

    async def test_exhausted_after_max_attempts(self):
        """测试重试耗尽"""

        async def always_fail():
            raise RetryableError("总是失败")

        policy = RetryPolicy(
            max_attempts=3,
            initial_delay_ms=10,
            jitter=False,
        )
        handler = EnhancedRetryHandler(policy)

        with pytest.raises(RetryableError):
            await handler.execute(always_fail)

        metrics = handler.get_metrics()
        assert metrics["total_failures"] == 1
        assert metrics["total_retries"] == 2  # 3次尝试 = 2次重试

    async def test_non_retryable_error_raises_immediately(self):
        """测试不可重试错误立即抛出"""
        call_count = 0

        async def raise_non_retryable():
            nonlocal call_count
            call_count += 1
            raise ValidationError("验证失败")

        handler = EnhancedRetryHandler()

        with pytest.raises(ValidationError):
            await handler.execute(raise_non_retryable)

        # 应该只调用一次,不重试
        assert call_count == 1

    async def test_pre_retry_action_called(self):
        """测试重试前恢复动作被调用"""
        recovery_calls = []

        async def recovery_action():
            recovery_calls.append(1)

        call_count = 0

        async def eventually_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RetryableError("失败")
            return "success"

        policy = RetryPolicy(
            max_attempts=3,
            initial_delay_ms=10,
            pre_retry_action=recovery_action,
            jitter=False,
        )
        handler = EnhancedRetryHandler(policy)
        result = await handler.execute(eventually_succeed)

        assert result.success is True
        # 恢复动作在第一次失败后,第二次尝试前被调用
        assert len(recovery_calls) == 1

    async def test_metrics_tracking(self):
        """测试指标追踪"""
        handler = EnhancedRetryHandler(RetryPolicy(initial_delay_ms=10, jitter=False))

        async def success():
            return 1

        await handler.execute(success)
        await handler.execute(success)

        metrics = handler.get_metrics()
        assert metrics["total_executions"] == 2
        assert metrics["successful_executions"] == 2

        handler.reset_metrics()
        metrics = handler.get_metrics()
        assert metrics["total_executions"] == 0


@pytest.mark.asyncio
class TestSmartRetryDecorator:
    """测试 smart_retry 装饰器"""

    async def test_decorator_basic_usage(self):
        """测试基本装饰器用法"""
        call_count = 0

        @smart_retry(max_attempts=3, initial_delay_ms=10)
        async def decorated_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RetryableError("重试")
            return "done"

        result = await decorated_func()
        assert result == "done"
        assert call_count == 2

    async def test_decorator_with_args(self):
        """测试带参数的装饰器"""

        @smart_retry(max_attempts=2, initial_delay_ms=10)
        async def add(a: int, b: int) -> int:
            return a + b

        result = await add(1, 2)
        assert result == 3

    async def test_decorator_exhausted_raises(self):
        """测试装饰器耗尽后抛出异常"""

        @smart_retry(max_attempts=2, initial_delay_ms=10)
        async def always_fail():
            raise RetryableError("失败")

        with pytest.raises(RetryableError):
            await always_fail()


class TestFactoryFunctions:
    """测试工厂函数"""

    def test_create_step_retry_policy(self):
        """测试步骤级策略工厂"""
        policy = create_step_retry_policy()

        # 步骤级应该有更少的重试次数和更短的延迟
        assert policy.max_attempts <= 5
        assert policy.initial_delay_ms <= 1000

    def test_create_stage_retry_policy(self):
        """测试阶段级策略工厂"""
        policy = create_stage_retry_policy()

        # 阶段级应该有更多的重试次数
        assert policy.max_attempts >= 3

    def test_factory_with_custom_recovery(self):
        """测试工厂支持自定义恢复动作"""

        async def custom_recovery():
            pass

        policy = create_step_retry_policy(pre_retry_action=custom_recovery)

        assert policy.pre_retry_action is custom_recovery


@pytest.mark.asyncio
class TestRecoveryValidation:
    """测试恢复验证功能."""

    async def test_recovery_validator_passes(self):
        """测试恢复验证通过后继续重试."""
        recovery_called = False
        validation_called = False

        async def recovery_action():
            nonlocal recovery_called
            recovery_called = True

        async def recovery_validator():
            nonlocal validation_called
            validation_called = True
            return True  # 验证通过

        call_count = 0

        async def eventually_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RetryableError("失败")
            return "success"

        policy = RetryPolicy(
            max_attempts=3,
            initial_delay_ms=10,
            pre_retry_action=recovery_action,
            recovery_validator=recovery_validator,
            jitter=False,
        )
        handler = EnhancedRetryHandler(policy)
        result = await handler.execute(eventually_succeed)

        assert result.success is True
        assert recovery_called is True
        assert validation_called is True
        assert call_count == 2

    async def test_recovery_validator_fails_skips_retry(self):
        """测试恢复验证失败时跳过重试."""
        validation_results = [False, True]  # 第一次失败,第二次通过
        validation_index = 0

        async def recovery_action():
            pass

        async def recovery_validator():
            nonlocal validation_index
            result = validation_results[validation_index]
            validation_index += 1
            return result

        call_count = 0

        async def eventually_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RetryableError("失败")
            return "success"

        policy = RetryPolicy(
            max_attempts=5,
            initial_delay_ms=10,
            pre_retry_action=recovery_action,
            recovery_validator=recovery_validator,
            skip_retry_on_validation_failure=True,
            jitter=False,
        )
        handler = EnhancedRetryHandler(policy)
        result = await handler.execute(eventually_succeed)

        assert result.success is True
        # 调用3次:第1次失败 -> 恢复验证失败(跳过) -> 第2次失败 -> 恢复验证通过 -> 第3次成功
        assert call_count == 3


@pytest.mark.asyncio
class TestStateChecker:
    """测试状态检查器功能."""

    async def test_state_checker_passes(self):
        """测试状态检查通过后继续重试."""
        check_called = False

        async def state_checker():
            nonlocal check_called
            check_called = True
            return True  # 状态正常

        call_count = 0

        async def eventually_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RetryableError("失败")
            return "success"

        policy = RetryPolicy(
            max_attempts=3,
            initial_delay_ms=10,
            state_checker=state_checker,
            jitter=False,
        )
        handler = EnhancedRetryHandler(policy)
        result = await handler.execute(eventually_succeed)

        assert result.success is True
        assert check_called is True
        assert call_count == 2

    async def test_state_checker_fails_stops_retry(self):
        """测试状态检查失败时停止重试."""

        async def state_checker():
            return False  # 状态异常,不应重试

        call_count = 0

        async def always_fail():
            nonlocal call_count
            call_count += 1
            raise RetryableError("失败")

        policy = RetryPolicy(
            max_attempts=5,
            initial_delay_ms=10,
            state_checker=state_checker,
            jitter=False,
        )
        handler = EnhancedRetryHandler(policy)

        with pytest.raises(RetryableError):
            await handler.execute(always_fail)

        # 只调用一次,状态检查失败后停止重试
        assert call_count == 1

    async def test_state_checker_outcome(self):
        """测试状态检查失败时的 outcome."""

        async def state_checker():
            return False

        async def always_fail():
            raise RetryableError("失败")

        policy = RetryPolicy(
            max_attempts=3,
            initial_delay_ms=10,
            state_checker=state_checker,
            jitter=False,
        )
        handler = EnhancedRetryHandler(policy)

        with contextlib.suppress(RetryableError):
            await handler.execute(always_fail)

        # 检查 metrics
        metrics = handler.get_metrics()
        assert metrics["total_failures"] == 1


@pytest.mark.asyncio
class TestSmartRetryWithValidation:
    """测试 smart_retry 装饰器支持验证参数."""

    async def test_decorator_with_recovery_validator(self):
        """测试装饰器支持 recovery_validator 参数."""
        validator_called = False

        async def my_validator():
            nonlocal validator_called
            validator_called = True
            return True

        async def my_recovery():
            pass

        call_count = 0

        @smart_retry(
            max_attempts=3,
            initial_delay_ms=10,
            pre_retry_action=my_recovery,
            recovery_validator=my_validator,
        )
        async def my_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RetryableError("失败")
            return "ok"

        result = await my_func()
        assert result == "ok"
        assert validator_called is True

    async def test_decorator_with_state_checker(self):
        """测试装饰器支持 state_checker 参数."""
        checker_called = False

        async def my_checker():
            nonlocal checker_called
            checker_called = True
            return True

        call_count = 0

        @smart_retry(
            max_attempts=3,
            initial_delay_ms=10,
            state_checker=my_checker,
        )
        async def my_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RetryableError("失败")
            return "ok"

        result = await my_func()
        assert result == "ok"
        assert checker_called is True
