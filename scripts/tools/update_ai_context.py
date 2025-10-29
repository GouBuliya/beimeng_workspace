#!/usr/bin/env python3
"""自动更新 .ai/context.json 的工具

此工具扫描项目目录，发现所有组件并更新全局上下文文件。
适用于 AI Agent 获取项目的最新状态。

Usage:
    python scripts/tools/update_ai_context.py
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
            for app_path in apps_dir.iterdir():
                if app_path.is_dir() and (app_path / ".ai.json").exists():
                    components["apps"].append(self._load_component_metadata(app_path))

        # 发现 scripts
        scripts_dir = self.workspace_root / "scripts"
        if scripts_dir.exists():
            for script_path in scripts_dir.rglob("*.py"):
                if script_path.parent / ".ai.json" in script_path.parent.iterdir():
                    parent_dir = script_path.parent
                    if parent_dir not in [
                        c["path"] for c in components["scripts"]
                    ]:
                        components["scripts"].append(
                            self._load_component_metadata(parent_dir)
                        )

        # 发现 packages
        packages_dir = self.workspace_root / "packages"
        if packages_dir.exists():
            for pkg_path in packages_dir.iterdir():
                if pkg_path.is_dir() and (pkg_path / ".ai.json").exists():
                    components["packages"].append(
                        self._load_component_metadata(pkg_path)
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

