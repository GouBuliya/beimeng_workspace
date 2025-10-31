# 🐛 调试机制使用指南

## 概述

新增的 `DebugHelper` 提供全方位的调试支持，帮助你快速定位和解决问题。

## 🎯 核心功能

### 1. 📸 自动截图
- 关键步骤自动截图
- 错误时自动截图
- 支持全页面/可见区域
- PNG/JPEG格式可选

### 2. 📄 HTML保存
- 保存完整页面HTML
- 用于离线分析
- 错误时自动保存

### 3. ⏱️ 性能分析
- 操作耗时统计
- 慢操作自动标记
- 性能摘要报告

### 4. 🔴 断点调试
- 暂停执行手动检查
- 可配置启用/禁用
- 支持自动继续

### 5. 🔍 Playwright追踪
- 记录详细执行轨迹
- 可视化分析工具
- 性能瓶颈识别

## 🚀 快速开始

### 1. 基础使用

```python
from src.utils.debug_helper import DebugHelper, DebugConfig

# 创建调试助手
debug = DebugHelper()

# 截图
await debug.screenshot(page, "step1_login")

# 保存HTML
await debug.save_html(page, "step1_login")

# 保存完整状态（截图+HTML）
await debug.save_state(page, "step1_login")
```

### 2. 自定义配置

```python
config = DebugConfig(
    enabled=True,               # 启用调试
    auto_screenshot=True,       # 自动截图
    auto_save_html=True,        # 自动保存HTML
    enable_timing=True,         # 启用计时
    enable_breakpoint=False,    # 断点（默认关闭）
    debug_dir=Path("my_debug")  # 自定义输出目录
)

debug = DebugHelper(config)
```

### 3. 在工作流中使用

```python
async def my_workflow(page):
    # 创建调试助手
    debug = DebugHelper()
    
    # 1. 保存初始状态
    await debug.save_state(page, "01_start")
    
    # 2. 执行操作并计时
    debug.start_timer("login")
    await login(page)
    debug.end_timer("login")
    
    # 3. 保存操作后状态
    await debug.save_state(page, "02_after_login")
    
    # 4. 错误处理
    try:
        await risky_operation(page)
    except Exception as e:
        await debug.save_error_state(page, "operation_failed", e)
        raise
    
    # 5. 显示性能摘要
    debug.log_performance_summary()
```

## 📊 功能详解

### 截图功能

```python
# 基础截图
await debug.screenshot(page, "my_screenshot")

# 全页面截图
await debug.screenshot(page, "full_page", full_page=True)

# 自动截图（配置后自动执行）
debug.config.auto_screenshot = True
await debug.save_state(page, "auto")  # 会自动截图
```

**输出示例**：
```
data/debug/
├── 20251031_120530_001_my_screenshot.png
├── 20251031_120532_002_full_page.png
└── 20251031_120535_003_auto.png
```

### HTML保存

```python
# 保存HTML
await debug.save_html(page, "page_state")

# 错误时自动保存
try:
    await operation()
except Exception as e:
    await debug.save_error_state(page, "error", e)
    # 会自动保存HTML
```

**输出示例**：
```
data/debug/
├── 20251031_120530_001_page_state.html
└── 20251031_120535_002_ERROR_error.html
```

### 性能分析

```python
# 开始计时
debug.start_timer("operation_name")

# 执行操作
await some_operation()

# 结束计时
duration = debug.end_timer("operation_name")
print(f"耗时: {duration}秒")

# 获取摘要
summary = debug.get_performance_summary()
print(summary)
# {
#     'total_operations': 5,
#     'total_time': 12.5,
#     'average_time': 2.5,
#     'slowest_operation': 'login',
#     'slowest_duration': 5.2
# }

# 记录摘要
debug.log_performance_summary()
```

**日志输出**：
```
⏱️  开始计时: login
⏱️  login 耗时 5.23秒
🐌 慢操作: login 耗时 5.23秒  # 超过阈值会警告

📊 性能分析摘要
  总操作数: 5
  总耗时: 12.50秒
  平均耗时: 2.50秒
  最慢操作: login (5.23秒)
```

### 断点调试

```python
# 启用断点模式
config = DebugConfig(enable_breakpoint=True)
debug = DebugHelper(config)

# 设置断点
await debug.breakpoint(page, "检查登录后的状态")
# 程序会暂停，等待按Enter继续

# 自动继续（测试用）
await debug.breakpoint(page, "测试断点", auto_continue=True)
# 等待30秒后自动继续
```

**输出**：
```
================================================================================
🔴 断点: 检查登录后的状态
  当前URL: https://erp.91miaoshou.com/welcome
  请在浏览器中手动检查页面状态
  按 Enter 继续...
```

### Playwright追踪

```python
# 启用追踪
config = DebugConfig(enable_trace=True)
debug = DebugHelper(config)

# 开始追踪
trace_path = await debug.enable_trace(page)

# 执行操作
await my_operations(page)

# 停止追踪
await debug.stop_trace(page, trace_path)

# 查看追踪
# 访问 https://trace.playwright.dev
# 上传 data/debug/trace_xxx.zip
```

## 📁 调试文件结构

```
data/debug/
├── 20251031_120530_001_login_page.png          # 截图
├── 20251031_120530_001_login_page.html         # HTML
├── 20251031_120532_002_after_login.png
├── 20251031_120532_002_after_login.html
├── 20251031_120535_003_ERROR_failed.png        # 错误截图
├── 20251031_120535_003_ERROR_failed.html       # 错误HTML
└── trace_20251031_120530.zip                   # Playwright追踪
```

**文件命名规则**：
- 格式：`时间戳_序号_名称.扩展名`
- 时间戳：`YYYYMMDD_HHMMSS_mmm`（精确到毫秒）
- 序号：3位数字，防止冲突
- 名称：自定义，会自动清理非法字符

## 💡 使用场景

### 场景1：调试失败的测试

```python
try:
    await click_button(page)
except Exception as e:
    # 保存错误现场
    await debug.save_error_state(page, "click_failed", e)
    # 现在可以查看截图和HTML来分析原因
```

### 场景2：性能优化

```python
# 测量每个步骤的耗时
debug.start_timer("step1")
await step1()
debug.end_timer("step1")

debug.start_timer("step2")
await step2()
debug.end_timer("step2")

# 查看哪个步骤最慢
debug.log_performance_summary()
```

### 场景3：重现问题

```python
# 启用全面调试
debug = DebugHelper(DebugConfig(
    auto_screenshot=True,
    auto_save_html=True,
    enable_timing=True
))

# 执行操作
for i in range(10):
    await debug.save_state(page, f"step_{i}")
    await process_item(page, i)

# 如果第5步失败，可以查看 step_5.png 和 step_5.html
```

### 场景4：手动验证

```python
# 在关键步骤设置断点
config = DebugConfig(enable_breakpoint=True)
debug = DebugHelper(config)

await login(page)
await debug.breakpoint(page, "验证登录是否成功")
# 程序暂停，手动检查浏览器

await navigate_to_page(page)
await debug.breakpoint(page, "验证页面是否正确")
# 手动检查

# 按Enter继续
```

## ⚙️ 配置选项

### DebugConfig 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `enabled` | bool | True | 是否启用调试 |
| `debug_dir` | Path | `data/debug` | 调试文件输出目录 |
| `auto_screenshot` | bool | True | 自动截图 |
| `screenshot_on_error` | bool | True | 错误时截图 |
| `screenshot_format` | str | "png" | 截图格式（png/jpeg） |
| `auto_save_html` | bool | True | 自动保存HTML |
| `save_html_on_error` | bool | True | 错误时保存HTML |
| `enable_timing` | bool | True | 启用计时 |
| `log_slow_operations` | bool | True | 记录慢操作 |
| `slow_threshold` | float | 5.0 | 慢操作阈值（秒） |
| `enable_breakpoint` | bool | False | 启用断点 |
| `breakpoint_wait_time` | int | 30 | 断点自动继续时间（秒） |
| `enable_video` | bool | False | 录制视频（影响性能） |
| `enable_trace` | bool | False | Playwright追踪 |

### 快速配置

```python
from src.utils.debug_helper import create_debug_helper

# 最小配置（只截图）
debug = create_debug_helper(
    screenshot=True,
    html=False,
    timing=False
)

# 完整调试（所有功能）
debug = create_debug_helper(
    screenshot=True,
    html=True,
    timing=True,
    breakpoint=True
)

# 禁用调试
debug = create_debug_helper(enabled=False)
```

## 🎓 最佳实践

### 1. 开发时启用全部功能

```python
# 开发环境
if os.getenv("ENV") == "development":
    debug = DebugHelper(DebugConfig(
        auto_screenshot=True,
        auto_save_html=True,
        enable_timing=True,
        enable_breakpoint=True
    ))
else:
    debug = DebugHelper(DebugConfig(enabled=False))
```

### 2. 生产环境只记录错误

```python
debug = DebugHelper(DebugConfig(
    auto_screenshot=False,  # 关闭自动截图
    screenshot_on_error=True,  # 只在错误时截图
    auto_save_html=False,
    save_html_on_error=True,
    enable_timing=True
))
```

### 3. 性能测试时只开启计时

```python
debug = DebugHelper(DebugConfig(
    auto_screenshot=False,
    auto_save_html=False,
    enable_timing=True  # 只测量性能
))
```

### 4. 关键步骤手动保存

```python
# 只在关键步骤保存状态
await debug.save_state(page, "01_before_critical_operation")
await critical_operation()
await debug.save_state(page, "02_after_critical_operation")
```

## 🧪 测试调试功能

```bash
# 运行演示脚本
python3 demo_debug.py
```

演示内容：
1. ✅ 自动截图
2. ✅ 自动保存HTML
3. ✅ 性能计时
4. ✅ 错误状态保存
5. ✅ 性能摘要

查看输出文件：
```bash
ls -lh data/debug/
```

## 📚 相关文件

- `src/utils/debug_helper.py` - DebugHelper实现
- `demo_debug.py` - 完整功能演示
- `data/debug/` - 调试文件输出目录

---

**总结**：DebugHelper 提供了强大的调试能力，让你可以轻松定位和解决问题！🐛✨

