"""登录控制器.

负责调用影刀执行 Temu 登录流程。
"""

import json
from pathlib import Path

from loguru import logger

from .cookie_manager import CookieManager


class LoginController:
    """登录控制器.
    
    管理 Temu 登录流程，包括 Cookie 管理和影刀调用。
    
    Attributes:
        config: 配置信息
        cookie_manager: Cookie 管理器
        
    Examples:
        >>> controller = LoginController()
        >>> success = controller.login("username", "password")
    """

    def __init__(self, config_path: str = "config/yingdao_config.json"):
        """初始化控制器.
        
        Args:
            config_path: 影刀配置文件路径
        """
        self.config_path = Path(config_path)
        self.cookie_manager = CookieManager()
        self.load_config()

    def load_config(self) -> None:
        """加载配置."""
        if not self.config_path.exists():
            logger.warning(f"配置文件不存在: {self.config_path}，使用默认配置")
            self.config = {"login": {"timeout": 30, "retry_times": 3}}
            return

        with open(self.config_path, encoding="utf-8") as f:
            self.config = json.load(f)
        logger.info("配置已加载")

    def call_yingdao(self, flow_name: str, params: dict) -> dict:
        """调用影刀流程.
        
        Args:
            flow_name: 流程名称
            params: 参数字典
            
        Returns:
            执行结果
            
        Note:
            这里需要根据影刀的实际调用方式实现
            可能是命令行、API 或文件交互
            
        Examples:
            >>> controller = LoginController()
            >>> result = controller.call_yingdao("Temu后台登录", {
            ...     "username": "test",
            ...     "password": "test"
            ... })
        """
        # 示例：通过 JSON 文件交互
        task_file = Path("data/temp/yingdao_task.json")
        result_file = Path("data/temp/yingdao_result.json")

        # 确保目录存在
        task_file.parent.mkdir(parents=True, exist_ok=True)

        # 写入任务
        with open(task_file, "w", encoding="utf-8") as f:
            json.dump({"flow": flow_name, "params": params}, f, ensure_ascii=False, indent=2)

        logger.info(f"调用影刀流程: {flow_name}")
        logger.info(f"任务文件: {task_file}")

        # TODO: 这里应该触发影刀执行
        # 目前需要手动运行影刀
        print(f"\n{'='*60}")
        print(f"请在影刀中运行流程：{flow_name}")
        print(f"任务文件：{task_file}")
        print(f"完成后，影刀需要将结果写入：{result_file}")
        print(f"{'='*60}\n")

        input("完成后按回车继续...")

        # 读取结果
        if result_file.exists():
            with open(result_file, encoding="utf-8") as f:
                result = json.load(f)
            logger.success("读取到影刀执行结果")
            return result
        else:
            logger.error(f"未找到影刀执行结果: {result_file}")
            raise FileNotFoundError("未找到影刀执行结果")

    def login(self, username: str, password: str, force: bool = False) -> bool:
        """执行登录.
        
        Args:
            username: 用户名
            password: 密码
            force: 强制重新登录（忽略 Cookie）
            
        Returns:
            True 如果登录成功
            
        Examples:
            >>> controller = LoginController()
            >>> success = controller.login("user", "pass")
        """
        logger.info("=" * 60)
        logger.info("开始登录流程")
        logger.info("=" * 60)

        # 1. 检查 Cookie
        if not force and self.cookie_manager.is_valid():
            logger.success("✓ 使用已保存的 Cookie，跳过登录")
            return True

        # 2. 执行登录
        logger.info("Cookie 无效，开始登录...")

        try:
            result = self.call_yingdao(
                "Temu后台登录", {"username": username, "password": password}
            )

            if result.get("status") == "success":
                logger.success("✓ 登录成功")

                # 保存 Cookie（如果影刀返回了）
                if "cookies" in result.get("result", {}):
                    self.cookie_manager.save(result["result"]["cookies"])

                return True
            else:
                error_msg = result.get("error_message", "未知错误")
                logger.error(f"✗ 登录失败: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"登录过程出错: {e}")
            return False


# 测试代码
if __name__ == "__main__":
    controller = LoginController()

    # 测试登录
    success = controller.login(username="test_user", password="test_pass")

    if success:
        print("✓ 登录流程测试通过")
    else:
        print("✗ 登录失败")


