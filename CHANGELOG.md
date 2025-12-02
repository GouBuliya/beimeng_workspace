## [0.2.2](https://github.com/GouBuliya/beimeng_workspace/compare/v0.2.1...v0.2.2) (2025-12-02)


### Bug Fixes

* update release workflow to use build_windows_exe.py for Windows builds ([5841808](https://github.com/GouBuliya/beimeng_workspace/commit/5841808e3f8318ee38c250b4656aeab5147cacb1))

## [0.2.1](https://github.com/GouBuliya/beimeng_workspace/compare/v0.2.0...v0.2.1) (2025-12-02)


### Bug Fixes

* add conventional-changelog-conventionalcommits dependency for semantic-release ([68a57ef](https://github.com/GouBuliya/beimeng_workspace/commit/68a57efae5a829d8c6bf7d5cb2bdbc489a9ae606))

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Apache 2.0 LICENSE 文件
- CONTRIBUTING.md 贡献指南
- CHANGELOG.md 变更日志

### Changed
- 整理项目结构，移动脚本到 `scripts/` 和 `examples/` 目录
- 更新 .gitignore 添加 `.env.bak*` 规则

### Removed
- 删除 `src/browser/legacy/` 目录（旧版批量编辑控制器）
- 删除 `src/workflows/legacy/` 目录（旧版工作流实现）
- 删除 `execute_complete_workflow` 兼容函数
- 清理调试数据和敏感数据备份

### Fixed
- 移除 `.env.bak` 和 `.env.bak2` 敏感文件从 git 追踪

## [0.1.0] - 2024-12-01

### Added
- 初始版本发布
- Temu 自动发布核心功能
  - 妙手认领流程
  - 首次编辑 (5→20)
  - 批量编辑 18 步
  - 发布流程
- Web Panel 管理界面
- CLI 命令行工具
- 完整的测试套件
- MkDocs 文档站点

### Features
- 基于 Playwright 的浏览器自动化
- Pydantic Settings 配置管理
- Loguru 日志系统
- FastAPI Web 服务
- Typer CLI 框架

---

[Unreleased]: https://github.com/your-repo/beimeng-workspace/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/your-repo/beimeng-workspace/releases/tag/v0.1.0
