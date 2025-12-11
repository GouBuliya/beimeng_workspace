"""
@PURPOSE: 定义工作流相关的自定义异常
@OUTLINE:
  - AccountMismatchError: 妙手账号与后台绑定不匹配
@DEPENDENCIES:
  - 外部: 无
"""

from __future__ import annotations


class AccountMismatchError(Exception):
    """妙手账号与后台绑定不匹配时抛出此异常.

    当用户实际使用的妙手账号与后台注册绑定的账号不一致时，
    工作流将抛出此异常并停止运行。
    """

    def __init__(
        self,
        actual_username: str,
        bound_username: str,
        message: str | None = None,
    ) -> None:
        """初始化账号不匹配异常.

        Args:
            actual_username: 实际使用的妙手账号
            bound_username: 后台绑定的妙手账号
            message: 自定义错误消息（可选）
        """
        self.actual_username = actual_username
        self.bound_username = bound_username
        self.message = message or (
            f"账号不匹配！当前使用的妙手账号 [{actual_username}] "
            f"与后台绑定的账号 [{bound_username}] 不一致，请检查配置"
        )
        super().__init__(self.message)
