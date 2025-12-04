# [1.6.0](https://github.com/GouBuliya/beimeng_workspace/compare/v1.5.1...v1.6.0) (2025-12-04)


### Bug Fixes

* 添加 publish_repeat_count 配置字段 ([8b632c5](https://github.com/GouBuliya/beimeng_workspace/commit/8b632c558d4824fafb3750d2c0c42d716c042332))


### Features

* Add scripts for testing and debugging API interactions and image uploads ([794ba13](https://github.com/GouBuliya/beimeng_workspace/commit/794ba136ea54de92032bada0a46e2b270a427a34))

## [1.5.1](https://github.com/GouBuliya/beimeng_workspace/compare/v1.5.0...v1.5.1) (2025-12-04)


### Bug Fixes

* 修复二次编辑阶段遗漏问题 ([7fd6ede](https://github.com/GouBuliya/beimeng_workspace/commit/7fd6ede82dde10eea42b95fa6008bc703e27476b))

# [1.5.0](https://github.com/GouBuliya/beimeng_workspace/compare/v1.4.0...v1.5.0) (2025-12-04)


### Bug Fixes

* 认领阶段只认领首次编辑成功的产品 ([0ecdc8d](https://github.com/GouBuliya/beimeng_workspace/commit/0ecdc8d842803145797b49c5faff7ba2b94d8aa5))


### Features

* 添加版本号显示到 Web 前端 ([e36448b](https://github.com/GouBuliya/beimeng_workspace/commit/e36448b643d2ddd02503649e1b56439644f1414d))

# [1.4.0](https://github.com/GouBuliya/beimeng_workspace/compare/v1.3.0...v1.4.0) (2025-12-04)


### Bug Fixes

* 二次编辑添加英语标题设置为空格 ([fd02793](https://github.com/GouBuliya/beimeng_workspace/commit/fd02793596f79cd8824cd3d01b2d7090f7337e29))
* 修复二次编辑获取 SKU 信息的参数和返回值解析 ([e313e43](https://github.com/GouBuliya/beimeng_workspace/commit/e313e43f01942c33d8f48a36452077f52f742ae6))
* 修复标题型号后缀累积问题 ([f40a416](https://github.com/GouBuliya/beimeng_workspace/commit/f40a41610ab611ff0f8c681d291fd8ac5cac5847))
* 发布阶段支持超过 100 个产品 ([d8934a3](https://github.com/GouBuliya/beimeng_workspace/commit/d8934a39c9b30344dc321552b93244d3467d158d))
* 增强供货价字段检测，添加调试日志定位价格计算问题 ([daf16a1](https://github.com/GouBuliya/beimeng_workspace/commit/daf16a1af6b40fe407f1489ad1a9b874654fea56))
* 外包装上传前先勾选产品，增强按钮点击鲁棒性 ([b8b6624](https://github.com/GouBuliya/beimeng_workspace/commit/b8b66244d118b76cc1df9500ada3828f215c249c))
* 批量编辑分批保存，每批最多 20 个产品 ([65f4f8c](https://github.com/GouBuliya/beimeng_workspace/commit/65f4f8c02f074457db3d0452e0b37e6a8d29f65d))
* 改进外包装图片上传，增加遮罩等待和弹窗处理 ([4132d6d](https://github.com/GouBuliya/beimeng_workspace/commit/4132d6df13354dcc7e8147c485916a75eaf02dd8))
* 首次编辑重量改为 9527g ([c1e74a5](https://github.com/GouBuliya/beimeng_workspace/commit/c1e74a5d0cb1f6c763123807ca23232553a04f7b))


### Features

* 二次编辑添加价格计算（供货价 × 10） ([8f94c84](https://github.com/GouBuliya/beimeng_workspace/commit/8f94c8490c402af4d757bd4d2a902893f364931b))
* 批量编辑运行 3 遍以增加成功率 ([2986c55](https://github.com/GouBuliya/beimeng_workspace/commit/2986c55b6b6a312e0816583a301af0c4ec3be077))
* 首次编辑增加标题后缀检测，避免重复添加 ([c073744](https://github.com/GouBuliya/beimeng_workspace/commit/c073744cda1610188480be548b47b7f60b65e3db))
* 首次编辑失败的产品不参与后续认领 ([afb29a6](https://github.com/GouBuliya/beimeng_workspace/commit/afb29a6c8dea2dbc4730c8dd6f88a274f31ec1f8))


### Performance Improvements

* 取消批量编辑轮次间的 1 秒等待 ([45dc6c9](https://github.com/GouBuliya/beimeng_workspace/commit/45dc6c9391a238f1b6fb22e23c712ac3f526473c))
* 批量编辑每批次上限从 20 提升到 1000 ([f8ed68b](https://github.com/GouBuliya/beimeng_workspace/commit/f8ed68bbafb47922a129048ad943661e3375471c))

# [1.3.0](https://github.com/GouBuliya/beimeng_workspace/compare/v1.2.1...v1.3.0) (2025-12-03)


### Features

* 认领/发布次数默认值改为 5 次 ([2474f57](https://github.com/GouBuliya/beimeng_workspace/commit/2474f574ceded788c1ebdc327cefa04b26f59cd7))

## [1.2.1](https://github.com/GouBuliya/beimeng_workspace/compare/v1.2.0...v1.2.1) (2025-12-03)


### Bug Fixes

* Cookie 登录导航超时时自动执行手动登录兜底 ([8ac8353](https://github.com/GouBuliya/beimeng_workspace/commit/8ac83530fb29cf595a353896742b3198a043f993))

## [0.2.3](https://github.com/GouBuliya/beimeng_workspace/compare/v0.2.2...v0.2.3) (2025-12-02)


### Bug Fixes

* multiple CI/CD issues ([257004c](https://github.com/GouBuliya/beimeng_workspace/commit/257004ca2c8478958814f9901b29c318285f1e5a))

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
