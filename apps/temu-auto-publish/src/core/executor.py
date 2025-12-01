"""
@PURPOSE: 工作流执行器 - 统一管理工作流执行、重试、状态保存和指标收集
@OUTLINE:
  - class WorkflowState: 工作流状态
  - class WorkflowExecutor: 工作流执行器
    - execute(): 执行工作流
    - resume(): 恢复工作流
    - save_state(): 保存状态
    - load_state(): 加载状态
@GOTCHAS:
  - 状态文件需要定期清理
  - 恢复时需要验证状态有效性
@TECH_DEBT:
  - TODO: 添加工作流超时控制
  - TODO: 添加并发工作流支持
@DEPENDENCIES:
  - 内部: src.core.retry_handler, src.core.performance_tracker
  - 外部: loguru, playwright
"""

import asyncio
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from loguru import logger
from playwright.async_api import Page

from src.core.performance_tracker import PerformanceTracker, get_tracker
from src.core.retry_handler import RetryHandler


# ========== 工作流状态 ==========

@dataclass
class WorkflowState:
    """工作流状态.
    
    Attributes:
        workflow_id: 工作流ID
        status: 状态（running/completed/failed）
        current_stage: 当前阶段
        completed_stages: 已完成的阶段列表
        failed_stages: 失败的阶段列表
        start_time: 开始时间
        update_time: 更新时间
        context: 上下文数据
        checkpoint_data: 检查点数据
    """
    workflow_id: str
    status: str = "running"
    current_stage: Optional[str] = None
    completed_stages: List[str] = field(default_factory=list)
    failed_stages: List[str] = field(default_factory=list)
    start_time: str = field(default_factory=lambda: datetime.now().isoformat())
    update_time: str = field(default_factory=lambda: datetime.now().isoformat())
    context: Dict[str, Any] = field(default_factory=dict)
    checkpoint_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return asdict(self)
    
    def to_json(self) -> str:
        """转换为JSON字符串."""
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowState":
        """从字典创建."""
        return cls(**data)
    
    @classmethod
    def from_json(cls, json_str: str) -> "WorkflowState":
        """从JSON字符串创建."""
        return cls.from_dict(json.loads(json_str))


# ========== 工作流执行器 ==========

class WorkflowExecutor:
    """工作流执行器 - 统一执行入口.
    
    功能：
    1. 集成重试机制
    2. 集成指标收集
    3. 支持断点续传
    4. 自动保存状态
    
    Examples:
        >>> executor = WorkflowExecutor()
        >>> result = await executor.execute(
        ...     workflow_func=my_workflow,
        ...     page=page,
        ...     config=config
        ... )
    """
    
    def __init__(
        self,
        retry_handler: Optional[RetryHandler] = None,
        perf_tracker: Optional[PerformanceTracker] = None,
        state_dir: Optional[Path] = None
    ):
        """初始化执行器.

        Args:
            retry_handler: 重试处理器
            perf_tracker: 性能追踪器
            state_dir: 状态文件存储目录
        """
        self.retry_handler = retry_handler or RetryHandler()
        self.perf_tracker = perf_tracker or get_tracker()
        self.state_dir = state_dir or Path("data/workflow_states")
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self.current_workflow_id: Optional[str] = None
        self.current_state: Optional[WorkflowState] = None

        logger.debug("工作流执行器已初始化")
    
    async def execute(
        self,
        workflow_func: Callable,
        page: Page,
        config: Dict[str, Any],
        workflow_id: Optional[str] = None,
        enable_retry: bool = True,
        enable_metrics: bool = True,
        enable_state_save: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """执行工作流.
        
        Args:
            workflow_func: 工作流函数
            page: Playwright页面对象
            config: 工作流配置
            workflow_id: 工作流ID（可选）
            enable_retry: 是否启用重试
            enable_metrics: 是否启用指标收集
            enable_state_save: 是否启用状态保存
            **kwargs: 传递给工作流函数的额外参数
            
        Returns:
            工作流执行结果
        """
        # 生成工作流ID
        if workflow_id is None:
            workflow_id = f"workflow_{uuid.uuid4().hex[:8]}_{int(datetime.now().timestamp())}"
        
        self.current_workflow_id = workflow_id

        # 初始化状态
        self.current_state = WorkflowState(workflow_id=workflow_id)

        # 开始性能追踪
        if enable_metrics:
            self.perf_tracker.start_workflow(workflow_id)

        logger.info(f"=" * 80)
        logger.info(f"开始执行工作流: {workflow_id}")
        logger.info(f"=" * 80)

        start_time = asyncio.get_event_loop().time()

        try:
            # 执行工作流（带重试）
            if enable_retry:
                result = await self.retry_handler.execute(
                    workflow_func,
                    page,
                    config,
                    workflow_id=workflow_id,
                    **kwargs
                )
            else:
                result = await workflow_func(page, config, workflow_id=workflow_id, **kwargs)

            # 更新状态
            self.current_state.status = "completed"
            duration = asyncio.get_event_loop().time() - start_time

            # 结束性能追踪
            if enable_metrics:
                self.perf_tracker.end_workflow(success=True)

            logger.success(f"✓ 工作流完成: {workflow_id}, 耗时: {duration:.2f}秒")

            return result

        except Exception as e:
            # 更新状态
            self.current_state.status = "failed"
            duration = asyncio.get_event_loop().time() - start_time

            # 结束性能追踪
            if enable_metrics:
                self.perf_tracker.end_workflow(success=False, error=str(e))

            logger.error(f"✗ 工作流失败: {workflow_id}, 耗时: {duration:.2f}秒, 错误: {e}")

            raise

        finally:
            # 保存状态
            if enable_state_save:
                self.save_state()
    
    async def resume(
        self,
        workflow_func: Callable,
        page: Page,
        state_file: Path,
        **kwargs
    ) -> Dict[str, Any]:
        """从状态文件恢复并继续执行工作流.
        
        Args:
            workflow_func: 工作流函数
            page: Playwright页面对象
            state_file: 状态文件路径
            **kwargs: 传递给工作流函数的额外参数
            
        Returns:
            工作流执行结果
        """
        # 加载状态
        state = self.load_state(state_file)
        
        if state is None:
            raise ValueError(f"无法加载状态文件: {state_file}")
        
        if state.status == "completed":
            logger.info(f"工作流已完成: {state.workflow_id}")
            return {"success": True, "message": "工作流已完成"}
        
        self.current_workflow_id = state.workflow_id
        self.current_state = state
        
        logger.info(f"恢复工作流: {state.workflow_id}")
        logger.info(f"  已完成阶段: {state.completed_stages}")
        logger.info(f"  当前阶段: {state.current_stage}")
        
        # 构建配置（包含恢复信息）
        config = {
            "resume": True,
            "completed_stages": state.completed_stages,
            "checkpoint_data": state.checkpoint_data,
            **state.context
        }
        
        # 继续执行
        return await self.execute(
            workflow_func,
            page,
            config,
            workflow_id=state.workflow_id,
            **kwargs
        )
    
    def save_state(self, state_file: Optional[Path] = None):
        """保存工作流状态.
        
        Args:
            state_file: 状态文件路径，如果为None则使用默认路径
        """
        if self.current_state is None:
            logger.warning("没有活动的工作流状态")
            return
        
        if state_file is None:
            state_file = self.state_dir / f"{self.current_state.workflow_id}.json"
        
        # 更新时间
        self.current_state.update_time = datetime.now().isoformat()
        
        try:
            state_file.write_text(self.current_state.to_json(), encoding="utf-8")
            logger.debug(f"状态已保存: {state_file.name}")
        except Exception as e:
            logger.error(f"保存状态失败: {e}")
    
    def load_state(self, state_file: Path) -> Optional[WorkflowState]:
        """加载工作流状态.
        
        Args:
            state_file: 状态文件路径
            
        Returns:
            工作流状态，如果加载失败则返回None
        """
        if not state_file.exists():
            logger.error(f"状态文件不存在: {state_file}")
            return None
        
        try:
            json_str = state_file.read_text(encoding="utf-8")
            state = WorkflowState.from_json(json_str)
            logger.info(f"状态已加载: {state_file.name}")
            return state
        except Exception as e:
            logger.error(f"加载状态失败: {e}")
            return None
    
    def update_stage(self, stage_name: str, checkpoint_data: Optional[Dict[str, Any]] = None):
        """更新当前阶段.
        
        Args:
            stage_name: 阶段名称
            checkpoint_data: 检查点数据
        """
        if self.current_state is None:
            return
        
        self.current_state.current_stage = stage_name
        
        if checkpoint_data:
            self.current_state.checkpoint_data.update(checkpoint_data)
        
        logger.debug(f"当前阶段: {stage_name}")
    
    def complete_stage(self, stage_name: str):
        """标记阶段完成.
        
        Args:
            stage_name: 阶段名称
        """
        if self.current_state is None:
            return
        
        if stage_name not in self.current_state.completed_stages:
            self.current_state.completed_stages.append(stage_name)
        
        logger.success(f"✓ 阶段完成: {stage_name}")
        
        # 自动保存状态
        self.save_state()
    
    def fail_stage(self, stage_name: str, error: Exception):
        """标记阶段失败.
        
        Args:
            stage_name: 阶段名称
            error: 错误信息
        """
        if self.current_state is None:
            return
        
        if stage_name not in self.current_state.failed_stages:
            self.current_state.failed_stages.append(stage_name)
        
        logger.error(f"✗ 阶段失败: {stage_name}, 错误: {error}")
        
        # 自动保存状态
        self.save_state()


# 便捷函数
def create_executor(
    enable_retry: bool = True,
    max_attempts: int = 3
) -> WorkflowExecutor:
    """创建工作流执行器（便捷方法）.
    
    Args:
        enable_retry: 是否启用重试
        max_attempts: 最大重试次数
        
    Returns:
        配置好的执行器
    """
    retry_handler = None
    if enable_retry:
        from src.core.retry_handler import RetryConfig
        retry_handler = RetryHandler(RetryConfig(max_attempts=max_attempts))
    
    return WorkflowExecutor(retry_handler=retry_handler)

