# Contributing to Beimeng Workspace

感谢您考虑为 Beimeng Workspace 做出贡献！本文档提供了贡献指南和最佳实践。

## 目录

- [行为准则](#行为准则)
- [如何贡献](#如何贡献)
- [开发环境设置](#开发环境设置)
- [提交指南](#提交指南)
- [代码风格](#代码风格)
- [测试要求](#测试要求)
- [Pull Request 流程](#pull-request-流程)

## 行为准则

请在所有互动中保持尊重和专业。我们致力于为所有人提供一个友好、安全和包容的环境。

## 如何贡献

### 报告 Bug

1. 在 [Issues](https://github.com/your-repo/issues) 中搜索是否已有相同问题
2. 如果没有，创建新 Issue，包含：
   - 清晰的标题和描述
   - 复现步骤
   - 预期行为 vs 实际行为
   - 环境信息（OS、Python 版本等）
   - 相关日志或截图

### 建议新功能

1. 先在 Issues 中讨论您的想法
2. 解释用例和预期效果
3. 等待维护者反馈后再开始实现

### 贡献代码

1. Fork 仓库
2. 创建功能分支 (`git checkout -b feat/amazing-feature`)
3. 进行更改
4. 确保测试通过
5. 提交 Pull Request

## 开发环境设置

```bash
# 克隆仓库
git clone https://github.com/your-repo/beimeng-workspace.git
cd beimeng-workspace

# 安装 uv（如果尚未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 安装依赖
uv sync

# 安装 pre-commit hooks
uv run pre-commit install
```

## 提交指南

我们使用 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Type 类型

| Type | 说明 |
|------|------|
| `feat` | 新功能 |
| `fix` | Bug 修复 |
| `docs` | 文档更新 |
| `style` | 代码格式（不影响功能） |
| `refactor` | 重构（不新增功能或修复 Bug） |
| `perf` | 性能优化 |
| `test` | 测试相关 |
| `chore` | 构建/工具更新 |

### 示例

```
feat(temu-auto-publish): 添加批量编辑的并发支持

- 实现并发执行器
- 添加资源限制配置
- 优化内存使用

Closes #123
```

## 代码风格

### Python 规范

- Python 3.12+
- 4 空格缩进，LF 换行符
- 最大行长 100 字符
- 双引号字符串
- 遵循 PEP 8 命名规范

### 工具使用

```bash
# 代码格式化
uv run ruff format .

# 代码检查
uv run ruff check .

# 类型检查
uv run mypy .

# 运行测试
uv run pytest
```

### 文件元信息协议

所有源文件必须包含元信息注释：

```python
"""
@PURPOSE: 文件的核心作用和功能
@OUTLINE:
  - class/function: 描述
@GOTCHAS:
  - 注意事项
@DEPENDENCIES:
  - 内部: 模块依赖
  - 外部: 第三方库
"""
```

## 测试要求

- 新功能必须有对应的测试
- 修复 Bug 应添加回归测试
- 保持测试覆盖率不低于当前水平

```bash
# 运行所有测试
uv run pytest

# 运行特定测试
uv run pytest tests/test_web_panel.py

# 查看覆盖率
uv run pytest --cov=. --cov-report=html
```

## Pull Request 流程

1. **创建 PR 前**
   - 确保代码通过所有检查 (`uv run pre-commit run --all-files`)
   - 更新相关文档
   - 添加/更新测试

2. **PR 描述应包含**
   - 更改摘要
   - 关联的 Issue（如有）
   - 测试计划
   - 截图（UI 相关更改）

3. **审查流程**
   - 至少一名维护者审查
   - CI 检查必须通过
   - 解决所有评论

4. **合并**
   - Squash and merge（保持历史整洁）
   - 删除已合并的分支

## 组件创建规范

创建新组件（app/script/package）时必须包含：

1. `README.md` - 完整的使用文档
2. `.ai.json` - AI 可解析的元数据
3. `examples/` - 至少一个可运行的示例
4. 完整的 Google Style docstrings
5. 类型提示

创建后运行：
```bash
uv run python scripts/tools/update_ai_context.py
```

## 获取帮助

- 查阅 [CLAUDE.md](./CLAUDE.md) 了解 AI 辅助开发指南
- 在 Issues 中提问
- 查看 [docs/](./docs/) 目录获取更多文档

---

再次感谢您的贡献！🎉
