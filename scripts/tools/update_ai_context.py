"""
@PURPOSE: 自动更新.ai/context.json的工具，扫描项目并更新全局上下文
@OUTLINE:
  - class ContextUpdater: 上下文更新器主类
  - def discover_components(): 发现所有组件
  - def update_context(): 更新context.json文件
@DEPENDENCIES:
  - 标准库: json, datetime, pathlib
  - 外部: loguru
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger


class ContextUpdater:
    """上下文更新器"""

    def __init__(self, workspace_root: Path):
        """初始化更新器

        Args:
            workspace_root: 工作空间根目录
        """
        self.workspace_root = workspace_root
        self.ai_dir = workspace_root / ".ai"
        self.context_file = self.ai_dir / "context.json"

    def discover_components(self) -> dict[str, list[dict[str, Any]]]:
        """发现所有组件

        Returns:
            包含 apps, scripts, packages 的字典
        """
        components: dict[str, list[dict[str, Any]]] = {
            "apps": [],
            "scripts": [],
            "packages": [],
        }

        # 发现 apps
        apps_dir = self.workspace_root / "apps"
        if apps_dir.exists():
            for app_path in apps_dir.rglob("*/.ai.json"):
                app_dir = app_path.parent
                components["apps"].append(self._load_component_metadata(app_dir))

        # 发现 scripts
        scripts_dir = self.workspace_root / "scripts"
        if scripts_dir.exists():
            for script_ai_json in scripts_dir.rglob(".ai.json"):
                script_dir = script_ai_json.parent
                # 避免重复添加（如果父目录已经在列表中）
                if script_dir not in [
                    self.workspace_root / c.get("path", "") for c in components["scripts"]
                ]:
                    components["scripts"].append(
                        self._load_component_metadata(script_dir)
                    )

        # 发现 packages
        packages_dir = self.workspace_root / "packages"
        if packages_dir.exists():
            for pkg_ai_json in packages_dir.rglob(".ai.json"):
                pkg_dir = pkg_ai_json.parent
                components["packages"].append(
                    self._load_component_metadata(pkg_dir)
                )

        return components

    def _load_component_metadata(self, component_path: Path) -> dict[str, Any]:
        """加载组件的元数据

        Args:
            component_path: 组件路径

        Returns:
            组件元数据字典
        """
        ai_json_path = component_path / ".ai.json"
        try:
            with open(ai_json_path) as f:
                metadata = json.load(f)
                # 添加相对路径
                metadata["path"] = str(component_path.relative_to(self.workspace_root))
                return metadata
        except Exception as e:
            logger.warning(f"无法加载 {ai_json_path}: {e}")
            return {
                "name": component_path.name,
                "path": str(component_path.relative_to(self.workspace_root)),
                "type": "unknown",
                "description": "元数据加载失败",
            }

    def update_context(self) -> None:
        """更新上下文文件"""
        logger.info("开始更新 AI 上下文...")

        # 加载现有上下文
        try:
            with open(self.context_file) as f:
                context = json.load(f)
        except FileNotFoundError:
            logger.error(f"上下文文件不存在: {self.context_file}")
            return

        # 发现组件
        components = self.discover_components()

        # 更新上下文
        context["components"] = components
        context["last_updated"] = datetime.now(timezone.utc).isoformat()

        # 写入文件
        with open(self.context_file, "w") as f:
            json.dump(context, f, indent=2, ensure_ascii=False)

        logger.success(f"上下文已更新: {self.context_file}")
        logger.info(
            f"发现: {len(components['apps'])} 个应用, "
            f"{len(components['scripts'])} 个脚本, "
            f"{len(components['packages'])} 个包"
        )


def main() -> None:
    """主函数"""
    workspace_root = Path(__file__).parent.parent.parent
    updater = ContextUpdater(workspace_root)
    updater.update_context()


if __name__ == "__main__":
    main()

