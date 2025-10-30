"""
@PURPOSE: 应用配置管理，使用Pydantic Settings管理配置，支持从.env文件加载
@OUTLINE:
  - class Settings: Temu自动发布应用配置主类
  - def ensure_directories(): 确保数据目录存在
  - def get_absolute_path(): 获取绝对路径
@GOTCHAS:
  - 敏感信息（账号密码）应存储在.env文件中
  - 不要将.env提交到git
@DEPENDENCIES:
  - 外部: pydantic, pydantic_settings
@RELATED: __init__.py
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Temu 自动发布应用配置.
    
    从 .env 文件或环境变量加载配置。
    
    Attributes:
        temu_username: Temu 商家账号用户名
        temu_password: Temu 商家账号密码
        data_input_dir: 输入数据目录
        data_output_dir: 输出数据目录
        data_temp_dir: 临时数据目录
        data_logs_dir: 日志目录
        yingdao_flow_id: 影刀流程ID
        price_multiplier: 价格倍率（建议售价 = 成本 × multiplier）
        supply_price_multiplier: 供货价倍率（供货价 = 成本 × multiplier）
        collect_count: 默认采集同款数量
        log_level: 日志级别
        
    Examples:
        >>> from config.settings import settings
        >>> settings.temu_username
        'your_username'
        >>> settings.price_multiplier
        7.5
    """

    # Temu 账号配置
    temu_username: str = Field(default="", description="Temu 用户名")
    temu_password: str = Field(default="", description="Temu 密码")

    # 路径配置
    data_input_dir: str = Field(default="data/input", description="输入目录")
    data_output_dir: str = Field(default="data/output", description="输出目录")
    data_temp_dir: str = Field(default="data/temp", description="临时目录")
    data_logs_dir: str = Field(default="data/logs", description="日志目录")

    # 浏览器配置
    browser_headless: bool = Field(default=False, description="浏览器无头模式")
    browser_config_file: str = Field(default="config/browser_config.json", description="浏览器配置文件")

    # 业务规则配置
    price_multiplier: float = Field(default=7.5, description="价格倍率（2.5×3）")
    supply_price_multiplier: float = Field(default=10.0, description="供货价倍率")
    collect_count: int = Field(default=5, ge=1, le=10, description="采集数量")

    # 日志配置
    log_level: str = Field(default="INFO", description="日志级别")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

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
        ]:
            full_path = self.get_absolute_path(dir_path)
            full_path.mkdir(parents=True, exist_ok=True)


# 全局配置实例
settings = Settings()


