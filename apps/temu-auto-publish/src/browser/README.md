```
@PURPOSE: 说明浏览器自动化模块的组成、职责与使用方式
@OUTLINE:
  - 模块概览与目录结构
  - 核心控制器说明
  - 支撑组件与配置
  - 使用示例与调试建议
@DEPENDENCIES:
  - 内部: src.config.settings, src.utils.*, src.data_processor.*
  - 外部: playwright, loguru
```

# Browser 模块说明

浏览器模块封装了基于 Playwright 的自动化能力，覆盖 Temu 发布流程中所有与页面交互相关的职责。模块遵循“控制器 + 支撑组件”模式：  
- **控制器** 负责具体业务流程（如首次编辑、批量编辑、认领、发布等）  
- **支撑组件** 提供浏览器生命周期、选择器加载、等待策略、媒体处理等通用能力

---

## 目录结构

```
src/browser/
├── README.md                # 当前文档
├── __init__.py              # 模块导出
├── browser_manager.py       # 浏览器生命周期管理
├── login_controller.py      # 妙手ERP登录流程
├── collection_controller.py # 采集/认领流程控制
├── miaoshou_controller.py   # 妙手采集箱操作
├── first_edit_controller.py # 首次编辑（弹窗交互）
├── batch_edit_controller.py # 批量编辑18步（新版主实现）
├── publish_controller.py    # 店铺选择与发布
├── image_manager.py         # 媒体资源校验与上传
├── first_edit_dialog_codegen.py / batch_edit_codegen.py # Codegen录制脚本
├── first_edit_executor.py   # 首次编辑任务编排
├── utils/                   # 智能等待、定位器、批量编辑辅助工具
└── legacy/                  # 兼容旧流程的历史版本
```

---

## 核心控制器

| 控制器 | 主要职责 | 备注 |
| --- | --- | --- |
| `BrowserManager` | 启动/关闭浏览器、上下文与页面管理；注入等待策略、Cookie 管理 | 所有控制器共享实例 |
| `LoginController` | 处理妙手 ERP 登录、Cookie 复用、登录后弹窗 | 支持 `login_if_needed` 快速验证 |
| `CollectionController` | 解析选品表、导航到采集页、认领/筛选商品 | 依赖 `SelectionTableReader` |
| `MiaoshouController` | 妙手采集箱操作（勾选、批量按钮、Tab 切换） | 强依赖选择器配置 |
| `FirstEditController` | 首次编辑弹窗交互（标题、规格、媒体） | 与 `first_edit_dialog_codegen` 协同 |
| `BatchEditController` | Temu 全托管批量编辑 18 步流程（新版主实现） | 依赖 `utils.batch_edit_helpers` |
| `PublishController` | 店铺选择、供货价设置、批量发布 | 整合价格计算器 |
| `ImageManager` | 图片/视频 URL 校验与上传 API 入口 | 供工作流和测试调用 |

> 历史版本的 `BatchEditController` 被保存在 `browser/legacy/`，仅供调试或回溯使用。

---

## 支撑组件

- `utils/page_waiter.py`：统一的智能等待策略，替代硬编码 `sleep`
- `utils/smart_locator.py`：复杂定位器封装，简化多层选择器
- `utils/batch_edit_helpers.py`：批量编辑的步骤重试、校验和性能记录
- `codegen/` 文件夹：由 Playwright Codegen 生成的脚本，负责对复杂表单的回放

所有组件均通过类型提示与 Google Style docstring 描述，促进 AI 编程与人类协作。

---

## 配置与依赖

- **选择器配置**：默认使用 `config/miaoshou_selectors_v2.json`，旧版 `miaoshou_selectors.json` 保留兼容
- **浏览器配置**：`config/browser_config.json` 中定义启动参数、超时时间、反检测策略
- **环境变量**：登录账号、图片根路径等通过 `.env` 与 `config/settings.py` 管理

---

## 使用示例

```python
from src.browser.browser_manager import BrowserManager
from src.browser.first_edit_controller import FirstEditController

async with BrowserManager() as manager:
    page = manager.page
    controller = FirstEditController()
    await controller.edit_title(page, new_title="2025新版多功能收纳柜")
```

运行端到端工作流时，`CompletePublishWorkflow` 会自动实例化并协调上述控制器，无需额外集成。

---

## 调试建议

- 打开 `config/settings.py` 中的 `debug.enabled`、`debug.auto_save_html` 以保留失败现场
- 使用 `data/debug/` 目录下生成的 HTML/截图快速定位选择器问题
- 对复杂弹窗优先录制 Codegen，随后在控制器中封装重试逻辑

---

## 相关文档

- `../workflows/README.md`：了解工作流如何编排各控制器
- `../data_processor/README.md`：选品表、价格计算等数据输入说明
- 项目根目录 `README.md`：安装、快速开始、整体架构介绍

