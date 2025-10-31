# 智能状态检测和容错机制

## 🎯 功能概述

新增的 `StateDetector` 类提供智能的页面状态检测和自动恢复能力，让工作流更加健壮，即使中途出错也能自动恢复。

## 📦 核心组件

### 1. PageState 枚举

定义了所有可能的页面状态：

```python
class PageState(Enum):
    UNKNOWN = "unknown"           # 未知状态
    LOGIN_PAGE = "login"          # 登录页
    HOME_PAGE = "home"            # 首页
    COLLECTION_BOX = "collection_box"  # 采集箱列表
    EDIT_DIALOG_OPEN = "edit_dialog"   # 编辑弹窗打开
    BATCH_EDIT = "batch_edit"     # 批量编辑页面
    PUBLISH_PAGE = "publish"      # 发布页面
```

### 2. StateDetector 类

提供状态检测和恢复方法：

#### 核心方法

| 方法 | 功能 | 返回值 |
|------|------|--------|
| `detect_current_state(page)` | 自动检测当前页面状态 | PageState |
| `is_login_page(page)` | 检查是否在登录页 | bool |
| `is_collection_box(page)` | 检查是否在采集箱 | bool |
| `is_edit_dialog_open(page)` | 检查编辑弹窗是否打开 | bool |
| `close_any_dialog(page)` | 关闭所有打开的弹窗 | bool |
| `recover_to_collection_box(page)` | 恢复到采集箱列表页 | bool |
| `ensure_state(page, expected_state)` | 确保处于期望状态 | bool |

## 🚀 使用方法

### 1. 基础使用

```python
from src.utils.state_detector import StateDetector, PageState

# 创建检测器
detector = StateDetector()

# 检测当前状态
current_state = await detector.detect_current_state(page)
print(f"当前状态: {current_state}")

# 检查特定状态
if await detector.is_edit_dialog_open(page):
    print("编辑弹窗已打开")
```

### 2. 自动恢复到期望状态

```python
# 确保在采集箱列表页，如果不是则自动恢复
if await detector.ensure_state(page, PageState.COLLECTION_BOX):
    print("✓ 已在采集箱列表页")
    # 继续执行业务逻辑
else:
    print("✗ 无法恢复到采集箱")
```

### 3. 容错处理

```python
try:
    # 执行某些操作
    await some_operation(page)
except Exception as e:
    logger.error(f"操作失败: {e}")
    
    # 关闭所有弹窗
    await detector.close_any_dialog(page)
    
    # 恢复到采集箱
    await detector.recover_to_collection_box(page)
```

### 4. 在工作流中使用

```python
class MyWorkflow:
    def __init__(self):
        self.detector = StateDetector()
    
    async def process_product(self, page, index):
        # 1. 确保在正确的页面
        if not await self.detector.ensure_state(page, PageState.COLLECTION_BOX):
            return False
        
        # 2. 如果有残留弹窗，先关闭
        if await self.detector.is_edit_dialog_open(page):
            await self.detector.close_any_dialog(page)
        
        # 3. 执行业务逻辑
        # ...
```

## 🔍 状态检测逻辑

### 检测优先级

`detect_current_state()` 按以下顺序检测：

1. **登录页** - 检查URL是否包含 "login" 或有登录按钮
2. **编辑弹窗** - 检查是否有弹窗且包含编辑相关元素
3. **采集箱** - 检查URL是否包含 "common_collect_box/items"
4. **首页** - 检查URL是否包含 "welcome"
5. **批量编辑** - 检查URL或内容
6. **发布页** - 检查URL

### 编辑弹窗检测

检查以下指标：
- `.jx-dialog`, `.el-dialog`, `[role='dialog']` 存在
- 包含"基本信息"、"销售属性"等文本
- 有标题输入框或保存按钮

## 🛡️ 容错特性

### 1. 自动关闭弹窗

`close_any_dialog()` 尝试多种方式关闭弹窗：

```python
# 尝试的选择器
- button[aria-label='关闭']
- button[aria-label='Close']
- .jx-dialog__headerbtn
- .el-dialog__headerbtn
- button:has-text('取消')
- button:has-text('关闭')

# 兜底方案
- 按 ESC 键
```

### 2. 自动恢复到采集箱

`recover_to_collection_box()` 执行：

1. 关闭所有弹窗
2. 检测当前状态
3. 如果不在采集箱，导航到采集箱URL
4. 验证恢复是否成功

### 3. 智能状态确保

`ensure_state()` 逻辑：

```python
if current_state == expected_state:
    return True  # 已经是期望状态

if auto_recover:
    # 尝试自动恢复
    return recover_to_state()
else:
    return False  # 不自动恢复
```

## 📝 日志输出

StateDetector 提供详细的日志：

```
🔍 检查状态是否为: collection_box
📍 当前状态: 编辑弹窗打开
⚠️ 当前状态(edit_dialog) != 期望状态(collection_box)，尝试恢复...
🔄 尝试关闭所有打开的弹窗...
找到2个关闭按钮: button[aria-label='关闭']
✓ 已关闭2个弹窗
🔄 尝试恢复到采集箱列表页...
✓ 成功恢复到采集箱列表页
✓ 已处于期望状态: collection_box
```

## 🎓 最佳实践

### 1. 在关键操作前检查状态

```python
# ✅ 好的做法
await detector.ensure_state(page, PageState.COLLECTION_BOX)
await click_edit_button(page, 0)

# ❌ 不好的做法
await click_edit_button(page, 0)  # 可能不在正确的页面
```

### 2. 异常处理中使用恢复

```python
try:
    await risky_operation(page)
except Exception:
    await detector.close_any_dialog(page)
    await detector.recover_to_collection_box(page)
```

### 3. 循环中定期检查

```python
for i in range(5):
    # 每次循环前检查状态
    if not await detector.ensure_state(page, PageState.COLLECTION_BOX):
        break
    
    await process_product(page, i)
```

## 🚨 注意事项

1. **性能影响**：状态检测需要时间（通常100-500ms），不要过度使用
2. **网络延迟**：恢复操作需要导航，可能需要2-5秒
3. **并发问题**：同一个Page对象不能并发使用StateDetector
4. **选择器变化**：如果网站UI更新，可能需要更新检测逻辑

## 📊 效果对比

### 修改前
```python
# 编辑可能失败
await click_edit(page, 0)  # 如果有弹窗残留，会失败
```

### 修改后
```python
# 自动处理异常状态
await detector.ensure_state(page, PageState.COLLECTION_BOX)  # 自动关闭残留弹窗
await click_edit(page, 0)  # 成功
```

## 🔗 相关文件

- `src/utils/state_detector.py` - StateDetector实现
- `src/workflows/five_to_twenty_workflow.py` - 使用示例
- `config/miaoshou_selectors_v2.json` - 选择器配置

---

**总结**：StateDetector 让工作流具备了"自愈"能力，即使中途出错也能自动恢复，大大提高了系统的健壮性！🛡️

