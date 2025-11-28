# Repository Guidelines

## Project Structure & Module Organization
- `apps/temu-auto-publish/` FastAPI web panel + Typer CLI for Temu publishing; `src/` holds workflows, selectors, and settings; `web_panel/` hosts the API/UI service; `scripts/` contains automation helpers.
- `apps/cli/hello/` is a minimal sample CLI and a good reference for style and Typer wiring.
- `packages/common/` stores shared config/logging helpers; reuse them before adding new utilities.
- `scripts/` holds automation utilities (e.g., `tools/update_ai_context.py`) plus data-processing samples under `data_processing/`.
- `docs/` powers the MkDocs site, while `tests/` covers cross-cutting integration; build outputs live in `build/` and `dist/` (do not edit manually).
- `.ai/` keeps structured metadata for agent context; refresh it whenever you add a component.

## Build, Test, and Development Commands
- `uv sync` installs dependencies; use `uv run` to execute tools inside the managed environment.
- `uv run ruff format .` and `uv run ruff check .` for formatting and linting.
- `uv run mypy .` for type checks aligned with `pyproject.toml`.
- `uv run pytest` (defaults to `--cov=.` and writes `htmlcov/`); scope runs with `uv run pytest tests/test_web_panel.py::test_run_with_upload`.
- `uv run python apps/temu-auto-publish/main.py --input data/selection.xlsx --headless` to invoke the Temu workflow; `uv run python -m apps.cli.hello greet World` for the demo app.
- `uv run pre-commit run --all-files` before pushing to mirror CI linting.

## Coding Style & Naming Conventions
- Python 3.12+, 4-space indent, LF endings, max line length 100; double quotes per Ruff formatter.
- Follow PEP8 naming (`snake_case` modules/functions, `PascalCase` classes, `SCREAMING_SNAKE_CASE` constants); `pep8-naming` is enforced via Ruff.
- Prefer typed function signatures and Google-style docstrings for public functions and workflows.
- Keep modules focused; avoid files > ~1000 lines, favor smaller components under `apps/temu-auto-publish/src`.

## Testing Guidelines
- Pytest is the default; async tests use `pytest.mark.asyncio` (see `tests/test_web_panel.py`).
- Place new tests next to the feature (`tests/` for integration, `apps/temu-auto-publish/tests/` for app-specific coverage).
- Maintain coverage implied by default `--cov=.`; review `htmlcov/index.html` locally before PRs.
- Use fixtures/helpers over hardcoded sleeps when hitting FastAPI or HTTPX clients.

## Commit & Pull Request Guidelines
- Follow Conventional Commit prefixes seen in history (`fix:`, `chore:`, `feat:`); keep subjects imperative; English or Chinese bodies are fine when specific.
- Keep commits focused and incremental; avoid mixing refactors with features.
- PRs should describe scope, testing commands run, and risk areas; link issues/tasks and attach screenshots for UI-facing changes (web panel).
- Ensure lint, type checks, and tests pass before requesting review.

## Agent & Security Notes
- Do not commit secrets; use `.env` or `TEMU_WEB_PANEL_ENV` to point to local credential files; scrub logs before sharing artifacts.
- When adding a new component or app, mirror README + `.ai.json` metadata and run `uv run python scripts/tools/update_ai_context.py` to refresh agent context.

# Beimeng Workspace - Cursor AI 规则

## 项目特定规则

说中文

### 代码风格
- 使用 Python 3.12+ 特性
- 单个文件不超过 1000 行
- 使用完整的类型提示
- Google Style docstrings
- 通过 ruff 和 mypy 检查

### 组件创建规范
创建任何新组件（app/script/package）时必须包含：
1. README.md - 完整的使用文档
2. .ai.json - AI 可解析的元数据（符合 .ai/schemas/component.schema.json）
3. examples/ - 至少一个可运行的示例
4. 完整的 Google Style docstrings
5. 类型提示

### AI Agent 友好设计
- 所有 CLI 使用 Typer 框架
- 输入输出优先使用 JSON/YAML
- 配置使用 Pydantic Settings
- 接口标准化且可预测
- 提供清晰的错误消息

### 文档要求
- 每个函数和类都要有 docstring
- 包含 Args, Returns, Raises, Examples
- README 包含安装、使用、配置、示例
- .ai.json 包含 interface、examples、ai_hints

### 工具使用
- 格式化: `ruff format`
- Lint: `ruff check --fix`
- 类型检查: `mypy`
- 测试: `pytest`

### Git 提交规范
- feat: 新功能
- fix: 修复 bug
- docs: 文档更新
- refactor: 重构
- test: 测试
- chore: 构建/工具更新

### 开发流程
1. 小步快跑，步步验证
2. 经常使用 git 保存进度
3. 创建组件后立即更新 AI 上下文: `python scripts/tools/update_ai_context.py`
4. 使用 pre-commit hooks 确保代码质量

### AI 提示模板
使用 .ai/prompts/ 中的模板来指导 AI：
- create_component.md - 创建新组件
- code_review.md - 代码审查

### 工程化思维
- 不要做玩具，使用 SOTA 模式
- 考虑可维护性和可扩展性
- 遵循 SOLID 原则
- 优先使用已有的 packages/common 组件

### 文件元信息协议（File Metadata Protocol）

所有源代码文件必须在文件最前方包含元信息注释块，用于描述文件的核心信息。

#### 强制字段
- `@PURPOSE:` 文件的核心作用和功能（必填）
- `@OUTLINE:` 文件的结构大纲，包括主要类/函数/模块（必填）

#### 可选字段
- `@GOTCHAS:` 易出错点、注意事项、常见陷阱
- `@TECH_DEBT:` 已知的技术债务和待优化项
- `@DEPENDENCIES:` 关键依赖关系（内部/外部模块）
- `@CHANGELOG:` 重要修改历史记录
- `@AUTHOR:` 作者信息
- `@RELATED:` 相关文件引用

#### 格式规范

**Python 文件示例：**
```python
"""
@PURPOSE: 实现用户认证和授权功能
@OUTLINE:
  - class AuthService: 主认证服务类
  - def login(username, password): 用户登录
  - def verify_token(token): 验证JWT令牌
@GOTCHAS:
  - 密码必须在存储前进行哈希处理
  - Token过期时间为24小时，需要定期刷新
@TECH_DEBT:
  - TODO: 添加多因素认证支持
  - TODO: 实现OAuth2.0集成
@DEPENDENCIES:
  - 内部: packages.common.logger, packages.common.config
  - 外部: jwt, bcrypt
@RELATED: user_service.py, permission_manager.py
"""
```

**TypeScript/JavaScript 文件示例：**
```typescript
/**
 * @PURPOSE: 实现前端路由管理和导航守卫
 * @OUTLINE:
 *   - class Router: 核心路由管理器
 *   - function setupGuards(): 配置导航守卫
 *   - function handleNavigation(): 处理路由跳转
 * @GOTCHAS:
 *   - 路由守卫必须返回boolean或Promise<boolean>
 *   - 避免在守卫中进行重定向循环
 * @DEPENDENCIES:
 *   - 外部: vue-router, pinia
 */
```

#### 规则说明

1. **位置要求**：元信息注释必须位于文件最开始（在任何import语句之前）
2. **格式要求**：
   - 使用对应语言的多行注释语法
   - 每个字段以 `@KEYWORD:` 开头（关键字后跟冒号）
   - 多行内容使用缩进延续
3. **内容要求**：
   - @PURPOSE 应简洁明了，1-2句话说明核心功能
   - @OUTLINE 列出主要的类、函数、导出内容
   - 其他字段根据实际情况填写，不强制
4. **维护要求**：
   - 文件结构发生重大变化时必须更新 @OUTLINE
   - 添加重要功能时更新 @CHANGELOG
   - 发现新的易错点时补充到 @GOTCHAS

#### 使用 MCP 工具快速查看文件元信息

**推荐使用 `mcp_file-info` 工具**来快速获取文件的元信息，而不是完整读取文件：

**获取文件全部元信息：**
```
使用 mcp_file-info_get_file_metadata 工具
- 参数: file_path（相对或绝对路径）
- 返回: 文件的所有元信息字段（PURPOSE, OUTLINE, DEPENDENCIES等）
```

**获取特定字段：**
```
使用 mcp_file-info_get_specific_metadata 工具
- 参数: file_path, fields（字段列表）
- 可用字段: PURPOSE, OUTLINE, GOTCHAS, TECH_DEBT, DEPENDENCIES, CHANGELOG, AUTHOR, RELATED
- 返回: 仅包含指定字段的元信息
```

**使用场景：**
- ✅ 快速了解文件用途和结构（只需元信息，无需读取整个文件）
- ✅ 检查文件依赖关系（@DEPENDENCIES字段）
- ✅ 查看已知问题和注意事项（@GOTCHAS字段）
- ✅ 了解技术债务（@TECH_DEBT字段）
- ✅ 批量检查多个文件的元信息

**示例：**
```python
# 获取文件的PURPOSE和OUTLINE
mcp_file-info_get_specific_metadata(
    file_path="apps/temu-auto-publish/src/browser/browser_manager.py",
    fields=["PURPOSE", "OUTLINE"]
)

# 获取文件的全部元信息
mcp_file-info_get_file_metadata(
    file_path="packages/common/logger.py"
)
```

**注意：**
- 所有源代码文件都已符合元信息协议规范（合规率100%）
- 优先使用MCP工具获取元信息，比读取整个文件更高效
- 如果需要查看具体实现代码，再使用 read_file 工具

