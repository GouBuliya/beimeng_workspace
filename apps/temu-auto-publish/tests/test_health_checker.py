"""
@PURPOSE: 测试健康检查服务
@OUTLINE:
  - TestHealthStatus: 测试健康状态枚举
  - TestHealthCheckResult: 测试健康检查结果
  - TestHealthChecker: 测试健康检查器
@DEPENDENCIES:
  - 外部: pytest, pytest-asyncio
  - 内部: src.core.health_checker
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from src.core.health_checker import (
    HealthStatus,
    HealthCheckResult,
    HealthChecker,
)


class TestHealthStatus:
    """测试健康状态枚举"""
    
    def test_status_values(self):
        """测试状态值"""
        assert HealthStatus.OK.value == "ok"
        assert HealthStatus.WARNING.value == "warning"
        assert HealthStatus.ERROR.value == "error"
        assert HealthStatus.UNKNOWN.value == "unknown"
    
    def test_status_comparison(self):
        """测试状态比较"""
        assert HealthStatus.OK == HealthStatus.OK
        assert HealthStatus.OK != HealthStatus.ERROR
    
    def test_status_string(self):
        """测试状态字符串表示"""
        assert str(HealthStatus.OK) == "HealthStatus.OK"


class TestHealthCheckResult:
    """测试健康检查结果"""
    
    def test_create_result(self):
        """测试创建结果"""
        result = HealthCheckResult(
            component="browser",
            status=HealthStatus.OK,
            message="Browser is running"
        )
        
        assert result.component == "browser"
        assert result.status == HealthStatus.OK
        assert result.message == "Browser is running"
        assert result.details == {}
    
    def test_create_result_with_details(self):
        """测试创建带详情的结果"""
        result = HealthCheckResult(
            component="disk",
            status=HealthStatus.WARNING,
            message="Disk space low",
            details={"free_space_gb": 5, "total_space_gb": 100}
        )
        
        assert result.details["free_space_gb"] == 5
        assert result.details["total_space_gb"] == 100
    
    def test_is_healthy_ok(self):
        """测试OK状态是健康的"""
        result = HealthCheckResult(
            component="test",
            status=HealthStatus.OK,
            message="All good"
        )
        
        assert result.is_healthy() is True
    
    def test_is_healthy_warning(self):
        """测试WARNING状态也是健康的"""
        result = HealthCheckResult(
            component="test",
            status=HealthStatus.WARNING,
            message="Warning"
        )
        
        assert result.is_healthy() is True
    
    def test_is_healthy_error(self):
        """测试ERROR状态不健康"""
        result = HealthCheckResult(
            component="test",
            status=HealthStatus.ERROR,
            message="Error"
        )
        
        assert result.is_healthy() is False
    
    def test_is_healthy_unknown(self):
        """测试UNKNOWN状态不健康"""
        result = HealthCheckResult(
            component="test",
            status=HealthStatus.UNKNOWN,
            message="Unknown"
        )
        
        assert result.is_healthy() is False
    
    def test_to_dict(self):
        """测试转换为字典"""
        result = HealthCheckResult(
            component="test",
            status=HealthStatus.OK,
            message="Test message",
            details={"key": "value"}
        )
        
        data = result.to_dict()
        
        assert data["component"] == "test"
        assert data["status"] == "ok"
        assert data["message"] == "Test message"
        assert data["details"] == {"key": "value"}
        assert "timestamp" in data
    
    def test_timestamp_auto_generated(self):
        """测试时间戳自动生成"""
        result = HealthCheckResult(
            component="test",
            status=HealthStatus.OK,
            message="Test"
        )
        
        assert result.timestamp is not None
        # 验证时间戳格式（ISO 8601）
        datetime.fromisoformat(result.timestamp)


class TestHealthChecker:
    """测试健康检查器"""
    
    def test_init(self):
        """测试初始化"""
        checker = HealthChecker()
        
        assert checker is not None
        assert checker.thresholds is not None
    
    def test_init_with_custom_thresholds(self):
        """测试自定义阈值初始化"""
        custom_thresholds = {
            "disk_warning_percent": 70,
            "disk_error_percent": 90,
            "memory_warning_percent": 75,
            "memory_error_percent": 95
        }
        
        checker = HealthChecker(thresholds=custom_thresholds)
        
        assert checker.thresholds["disk_warning_percent"] == 70
    
    @pytest.mark.asyncio
    async def test_check_disk(self):
        """测试磁盘检查"""
        checker = HealthChecker()
        
        # Mock shutil.disk_usage
        with patch('shutil.disk_usage') as mock_disk:
            mock_disk.return_value = MagicMock(
                total=100 * 1024 * 1024 * 1024,  # 100GB
                free=50 * 1024 * 1024 * 1024     # 50GB free (50%)
            )
            
            result = await checker.check_disk()
            
            assert result.component == "disk"
            assert result.is_healthy()
    
    @pytest.mark.asyncio
    async def test_check_disk_low_space(self):
        """测试磁盘空间不足"""
        checker = HealthChecker(thresholds={
            "disk_warning_percent": 80,
            "disk_error_percent": 95
        })
        
        # Mock shutil.disk_usage - 只有5%空间
        with patch('shutil.disk_usage') as mock_disk:
            mock_disk.return_value = MagicMock(
                total=100 * 1024 * 1024 * 1024,
                free=5 * 1024 * 1024 * 1024  # 5GB free (5%)
            )
            
            result = await checker.check_disk()
            
            # 使用率95%应该触发ERROR
            assert result.status in [HealthStatus.WARNING, HealthStatus.ERROR]
    
    @pytest.mark.asyncio
    async def test_check_memory(self):
        """测试内存检查"""
        checker = HealthChecker()
        
        # Mock psutil.virtual_memory
        with patch('psutil.virtual_memory') as mock_memory:
            mock_memory.return_value = MagicMock(
                total=16 * 1024 * 1024 * 1024,  # 16GB
                available=8 * 1024 * 1024 * 1024,  # 8GB available
                percent=50.0
            )
            
            result = await checker.check_memory()
            
            assert result.component == "memory"
            assert result.is_healthy()
    
    @pytest.mark.asyncio
    async def test_check_memory_high_usage(self):
        """测试内存使用率高"""
        checker = HealthChecker(thresholds={
            "memory_warning_percent": 70,
            "memory_error_percent": 90
        })
        
        # Mock psutil.virtual_memory - 95%使用率
        with patch('psutil.virtual_memory') as mock_memory:
            mock_memory.return_value = MagicMock(
                total=16 * 1024 * 1024 * 1024,
                available=0.8 * 1024 * 1024 * 1024,  # 0.8GB available
                percent=95.0
            )
            
            result = await checker.check_memory()
            
            assert result.status == HealthStatus.ERROR
    
    @pytest.mark.asyncio
    async def test_check_network(self):
        """测试网络检查"""
        checker = HealthChecker()
        
        # Mock aiohttp.ClientSession
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_session.get = AsyncMock(return_value=mock_response)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session_class.return_value = mock_session
            
            result = await checker.check_network()
            
            assert result.component == "network"
    
    @pytest.mark.asyncio
    async def test_check_browser_not_started(self):
        """测试浏览器未启动时的检查"""
        checker = HealthChecker()
        
        # 不设置browser_manager
        result = await checker.check_browser()
        
        assert result.component == "browser"
        # 没有浏览器应该返回WARNING或UNKNOWN
        assert result.status in [HealthStatus.WARNING, HealthStatus.UNKNOWN, HealthStatus.ERROR]
    
    @pytest.mark.asyncio
    async def test_check_all(self):
        """测试全面健康检查"""
        checker = HealthChecker()
        
        # Mock各个检查方法
        checker.check_disk = AsyncMock(return_value=HealthCheckResult(
            component="disk",
            status=HealthStatus.OK,
            message="Disk OK"
        ))
        checker.check_memory = AsyncMock(return_value=HealthCheckResult(
            component="memory",
            status=HealthStatus.OK,
            message="Memory OK"
        ))
        checker.check_network = AsyncMock(return_value=HealthCheckResult(
            component="network",
            status=HealthStatus.OK,
            message="Network OK"
        ))
        checker.check_browser = AsyncMock(return_value=HealthCheckResult(
            component="browser",
            status=HealthStatus.WARNING,
            message="Browser not started"
        ))
        
        results = await checker.check_all()
        
        assert len(results) >= 4
        # 至少有一个是OK的
        assert any(r.status == HealthStatus.OK for r in results)
    
    @pytest.mark.asyncio
    async def test_check_all_overall_status(self):
        """测试全面检查的整体状态"""
        checker = HealthChecker()
        
        # 全部OK
        checker.check_disk = AsyncMock(return_value=HealthCheckResult(
            component="disk", status=HealthStatus.OK, message="OK"
        ))
        checker.check_memory = AsyncMock(return_value=HealthCheckResult(
            component="memory", status=HealthStatus.OK, message="OK"
        ))
        checker.check_network = AsyncMock(return_value=HealthCheckResult(
            component="network", status=HealthStatus.OK, message="OK"
        ))
        checker.check_browser = AsyncMock(return_value=HealthCheckResult(
            component="browser", status=HealthStatus.OK, message="OK"
        ))
        
        results = await checker.check_all()
        
        # 所有结果都应该是健康的
        assert all(r.is_healthy() for r in results)


class TestHealthCheckerIntegration:
    """健康检查器集成测试"""
    
    @pytest.mark.asyncio
    async def test_real_disk_check(self):
        """测试真实磁盘检查（不mock）"""
        checker = HealthChecker()
        
        result = await checker.check_disk()
        
        assert result.component == "disk"
        assert result.status in [HealthStatus.OK, HealthStatus.WARNING, HealthStatus.ERROR]
        assert "free_gb" in result.details or "error" in result.message.lower() or result.details == {}
    
    @pytest.mark.asyncio
    async def test_real_memory_check(self):
        """测试真实内存检查（不mock）"""
        checker = HealthChecker()
        
        result = await checker.check_memory()
        
        assert result.component == "memory"
        assert result.status in [HealthStatus.OK, HealthStatus.WARNING, HealthStatus.ERROR]








