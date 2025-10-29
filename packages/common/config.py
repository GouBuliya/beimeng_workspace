"""配置管理模块

提供应用配置的基类和工具。

Examples:
    创建自定义配置::

        from packages.common.config import BaseAppConfig
        from pydantic import Field

        class MyConfig(BaseAppConfig):
            api_key: str = Field(..., description="API密钥")
            timeout: int = Field(default=30, description="超时时间")

        config = MyConfig()
"""

from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseAppConfig(BaseSettings):
    """应用配置基类

    所有应用配置应继承此类，获得：
    - 自动从环境变量加载
    - .env 文件支持
    - 类型验证
    - 文档字符串

    Attributes:
        log_level: 日志级别
        debug: 调试模式
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    log_level: str = Field(default="INFO", description="日志级别")
    debug: bool = Field(default=False, description="是否启用调试模式")

    def to_dict(self) -> dict[str, Any]:
        """转换为字典

        Returns:
            配置字典
        """
        return self.model_dump()

    def save_to_file(self, file_path: Path) -> None:
        """保存配置到文件

        Args:
            file_path: 文件路径（支持 .json, .yaml, .toml）
        """
        import json

        if file_path.suffix == ".json":
            with open(file_path, "w") as f:
                json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        elif file_path.suffix in [".yaml", ".yml"]:
            import yaml

            with open(file_path, "w") as f:
                yaml.dump(self.to_dict(), f, default_flow_style=False, allow_unicode=True)
        else:
            raise ValueError(f"不支持的文件格式: {file_path.suffix}")

    @classmethod
    def from_file(cls, file_path: Path) -> "BaseAppConfig":
        """从文件加载配置

        Args:
            file_path: 文件路径

        Returns:
            配置实例
        """
        import json

        if file_path.suffix == ".json":
            with open(file_path) as f:
                data = json.load(f)
        elif file_path.suffix in [".yaml", ".yml"]:
            import yaml

            with open(file_path) as f:
                data = yaml.safe_load(f)
        else:
            raise ValueError(f"不支持的文件格式: {file_path.suffix}")

        return cls(**data)

