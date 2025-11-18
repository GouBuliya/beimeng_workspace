"""
@PURPOSE: 应用配置管理，使用Pydantic Settings管理配置，支持多环境和从YAML加载
@OUTLINE:
  - class DebugConfig: 调试配置
  - class LoggingConfig: 日志配置
  - class BrowserConfig: 浏览器配置
  - class RetryConfig: 重试配置
  - class MetricsConfig: 指标配置
  - class BusinessConfig: 业务配置
  - class WorkflowConfig: 工作流配置
  - class Settings: 应用配置主类
  - def load_environment_config(): 加载环境配置
  - def get_settings(): 获取全局配置实例
@GOTCHAS:
  - 敏感信息（账号密码）应存储在.env文件中
  - 不要将.env提交到git
  - 环境配置文件优先级: 环境变量 > YAML > 默认值
@TECH_DEBT:
  - TODO: 添加配置热重载
  - TODO: 添加配置加密支持
@DEPENDENCIES:
  - 外部: pydantic, pydantic_settings, pyyaml
@RELATED: __init__.py
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# ========== 子配置类 ==========

class DebugConfig(BaseSettings):
    """调试配置.
    
    Attributes:
        enabled: 是否启用调试
        auto_screenshot: 自动截图
        auto_save_html: 自动保存HTML
        enable_timing: 启用计时
        enable_breakpoint: 启用断点
        screenshot_format: 截图格式
        screenshot_on_error: 错误时截图
        save_html_on_error: 错误时保存HTML
        debug_dir: 调试目录
    """
    enabled: bool = Field(default=True, description="是否启用调试")
    auto_screenshot: bool = Field(default=True, description="自动截图")
    auto_save_html: bool = Field(default=False, description="自动保存HTML")
    enable_timing: bool = Field(default=True, description="启用计时")
    enable_breakpoint: bool = Field(default=False, description="启用断点")
    screenshot_format: str = Field(default="png", description="截图格式")
    screenshot_on_error: bool = Field(default=True, description="错误时截图")
    save_html_on_error: bool = Field(default=True, description="错误时保存HTML")
    debug_dir: str = Field(default="data/debug", description="调试目录")


class LoggingConfig(BaseSettings):
    """日志配置.
    
    Attributes:
        level: 日志级别
        format: 日志格式
        output: 输出目标列表
        file_path: 文件路径
        rotation: 轮转大小
        retention: 保留时间
    """
    level: str = Field(default="INFO", description="日志级别")
    format: str = Field(default="detailed", description="日志格式")
    output: List[str] = Field(default=["console", "file"], description="输出目标")
    file_path: str = Field(default="data/logs/app.log", description="文件路径")
    rotation: str = Field(default="10 MB", description="轮转大小")
    retention: str = Field(default="7 days", description="保留时间")


class BrowserConfig(BaseSettings):
    """浏览器配置.
    
    Attributes:
        headless: 无头模式
        slow_mo: 慢速模式（毫秒）
        timeout: 默认超时（毫秒）
        viewport: 视口大小
        user_agent: 用户代理
    """
    headless: bool = Field(default=False, description="无头模式")
    slow_mo: int = Field(default=0, description="慢速模式（毫秒）")
    timeout: int = Field(default=30000, description="默认超时（毫秒）")
    viewport: Dict[str, int] = Field(
        default={"width": 1280, "height": 720},
        description="视口大小"
    )
    user_agent: Optional[str] = Field(default=None, description="用户代理")


class RetryConfig(BaseSettings):
    """重试配置.
    
    Attributes:
        enabled: 是否启用重试
        max_attempts: 最大重试次数
        backoff_factor: 退避因子
        initial_delay: 初始延迟（秒）
        max_delay: 最大延迟（秒）
    """
    enabled: bool = Field(default=True, description="是否启用重试")
    max_attempts: int = Field(default=3, ge=1, description="最大重试次数")
    backoff_factor: float = Field(default=2.0, ge=1.0, description="退避因子")
    initial_delay: float = Field(default=1.0, ge=0.1, description="初始延迟（秒）")
    max_delay: float = Field(default=60.0, ge=1.0, description="最大延迟（秒）")


class MetricsConfig(BaseSettings):
    """指标配置.
    
    Attributes:
        enabled: 是否启用指标收集
        storage_dir: 存储目录
        export_format: 导出格式
    """
    enabled: bool = Field(default=True, description="是否启用指标收集")
    storage_dir: str = Field(default="data/metrics", description="存储目录")
    export_format: str = Field(default="json", description="导出格式")


class BusinessConfig(BaseSettings):
    """业务配置.
    
    Attributes:
        price_multiplier: 建议售价倍率
        supply_price_multiplier: 供货价倍率
        real_supply_multiplier: 真实供货价倍率
        collect_count: 采集数量
        claim_count: 认领次数
        collection_owner: 妙手采集箱创建人员显示名(不含账号)
    """
    price_multiplier: float = Field(default=10.0, description="建议售价倍率")
    supply_price_multiplier: float = Field(default=7.5, description="供货价倍率")
    real_supply_multiplier: float = Field(default=2.5, description="真实供货价倍率")
    collect_count: int = Field(default=5, ge=1, le=10, description="采集数量")
    claim_count: int = Field(default=4, ge=1, le=10, description="认领次数")
    collection_owner: str = Field(
        default="李英亮",
        description="妙手采集箱创建人员显示名(不含账号, 会与账号拼接)",
    )


class WorkflowConfig(BaseSettings):
    """工作流配置.
    
    Attributes:
        enable_state_save: 启用状态保存
        state_dir: 状态目录
        auto_resume: 自动恢复
        checkpoint_interval: 检查点间隔
    """
    enable_state_save: bool = Field(default=True, description="启用状态保存")
    state_dir: str = Field(default="data/workflow_states", description="状态目录")
    auto_resume: bool = Field(default=False, description="自动恢复")
    checkpoint_interval: int = Field(default=5, ge=1, description="检查点间隔")


# ========== 主配置类 ==========

class Settings(BaseSettings):
    """应用配置主类.
    
    从环境变量、.env文件和YAML配置文件加载配置。
    优先级：环境变量 > YAML > 默认值
    
    Attributes:
        environment: 运行环境
        temu_username: Temu用户名
        temu_password: Temu密码
        data_input_dir: 输入目录
        data_output_dir: 输出目录
        data_temp_dir: 临时目录
        data_logs_dir: 日志目录
        browser_config_file: 浏览器配置文件
        debug: 调试配置
        logging: 日志配置
        browser: 浏览器配置
        retry: 重试配置
        metrics: 指标配置
        business: 业务配置
        workflow: 工作流配置
        
    Examples:
        >>> from config.settings import settings
        >>> settings.environment
        'development'
        >>> settings.debug.enabled
        True
    """
    
    # 环境配置
    environment: str = Field(default="development", description="运行环境")
    
    # Temu 账号配置（从.env加载）
    temu_username: str = Field(default="", description="Temu 用户名")
    temu_password: str = Field(default="", description="Temu 密码")
    miaoshou_username: str = Field(default="", description="妙手 用户名")
    miaoshou_password: str = Field(default="", description="妙手 密码")
    
    # 路径配置
    data_input_dir: str = Field(default="data/input", description="输入目录")
    data_output_dir: str = Field(default="data/output", description="输出目录")
    data_temp_dir: str = Field(default="data/temp", description="临时目录")
    data_logs_dir: str = Field(default="data/logs", description="日志目录")
    
    # 浏览器配置文件
    browser_config_file: str = Field(
        default="config/browser_config.json",
        description="浏览器配置文件"
    )
    
    # 子配置
    debug: DebugConfig = Field(default_factory=DebugConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    browser: BrowserConfig = Field(default_factory=BrowserConfig)
    retry: RetryConfig = Field(default_factory=RetryConfig)
    metrics: MetricsConfig = Field(default_factory=MetricsConfig)
    business: BusinessConfig = Field(default_factory=BusinessConfig)
    workflow: WorkflowConfig = Field(default_factory=WorkflowConfig)
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_nested_delimiter="__",  # 支持 DEBUG__ENABLED=true
    )
    
    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """验证环境名称."""
        valid_envs = ["development", "staging", "production"]
        if v not in valid_envs:
            raise ValueError(f"环境必须是: {valid_envs}")
        return v
    
    def get_absolute_path(self, relative_path: str) -> Path:
        """将相对路径转换为绝对路径.
        
        Args:
            relative_path: 相对路径
            
        Returns:
            绝对路径
        """
        base_dir = Path(__file__).parent.parent
        return base_dir / relative_path
    
    def ensure_directories(self) -> None:
        """确保所有必需的目录存在."""
        for dir_path in [
            self.data_input_dir,
            self.data_output_dir,
            self.data_temp_dir,
            self.data_logs_dir,
            self.debug.debug_dir,
            self.metrics.storage_dir,
            self.workflow.state_dir,
        ]:
            full_path = self.get_absolute_path(dir_path)
            full_path.mkdir(parents=True, exist_ok=True)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（隐藏敏感信息）."""
        data = self.model_dump()
        # 隐藏密码
        if data.get("temu_password"):
            data["temu_password"] = "***"
        if data.get("miaoshou_password"):
            data["miaoshou_password"] = "***"
        return data


# ========== 配置加载 ==========

def load_environment_config(env: str = "development") -> Dict[str, Any]:
    """从YAML文件加载环境配置，支持别名引用."""

    config_dir = Path(__file__).parent / "environments"
    target_file = config_dir / f"{env}.yaml"

    def _load(file_path: Path, seen: set[Path]) -> Dict[str, Any]:
        if file_path in seen:
            raise ValueError(f"检测到环境配置的循环引用: {file_path}")
        seen.add(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"环境配置文件不存在: {file_path}")

        with file_path.open("r", encoding="utf-8") as handle:
            content = yaml.safe_load(handle)

        if content is None:
            return {}

        if isinstance(content, str):
            alias = content.strip()
            if not alias:
                raise ValueError(f"环境配置别名不能为空: {file_path}")

            if alias.endswith((".yaml", ".yml")):
                alias_file = file_path.parent / alias
            else:
                alias_file = file_path.parent / f"{alias}.yaml"

            return _load(alias_file, seen)

        if not isinstance(content, dict):
            raise TypeError(
                f"环境配置 {file_path} 必须是字典或别名字符串, 当前类型: {type(content).__name__}",
            )

        return content

    return _load(target_file, set())


def create_settings(env: Optional[str] = None) -> Settings:
    """创建配置实例.
    
    Args:
        env: 环境名称，如果为None则从环境变量获取
        
    Returns:
        配置实例
    """
    # 确定环境
    if env is None:
        env = os.getenv("ENVIRONMENT", "development")
    
    # 加载YAML配置
    yaml_config = load_environment_config(env)
    
    # 创建配置实例（YAML配置作为默认值）
    settings = Settings(
        environment=env,
        debug=DebugConfig(**yaml_config.get("debug", {})),
        logging=LoggingConfig(**yaml_config.get("logging", {})),
        browser=BrowserConfig(**yaml_config.get("browser", {})),
        retry=RetryConfig(**yaml_config.get("retry", {})),
        metrics=MetricsConfig(**yaml_config.get("metrics", {})),
        business=BusinessConfig(**yaml_config.get("business", {})),
        workflow=WorkflowConfig(**yaml_config.get("workflow", {})),
    )
    
    # 确保目录存在
    settings.ensure_directories()
    
    return settings


# ========== 全局配置实例 ==========

# 从环境变量获取环境名称
_env = os.getenv("ENVIRONMENT", "development")
settings = create_settings(_env)
