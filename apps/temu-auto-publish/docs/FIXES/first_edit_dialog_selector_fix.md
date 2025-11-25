# 首次编辑弹窗填写失败问题修复

## 🐛 问题描述

**错误信息：**
```
第1个商品标题更新异常: 字段填写失败, 缺失: spec_container, title, product_number, 
weight_g, price[row=1], supply_price[row=1], source_price[row=1], stock[row=1], ...
```

**根本原因：**
妙手 ERP 的首次编辑弹窗结构发生变化，原有的弹窗选择器失效：
- 原选择器：`.collect-box-editor-dialog-V2, .jx-overlay-dialog`
- 无法找到弹窗容器，导致所有字段定位失败

---

## 🔧 修复方案

### 1. 增强弹窗检测逻辑 (`_fill_basic_specs`)

#### 修复前
```python
dialog = page.locator(".collect-box-editor-dialog-V2, .jx-overlay-dialog").first
await dialog.wait_for(state="visible", timeout=3_000)
```

#### 修复后
```python
# 尝试多种弹窗选择器
dialog_selectors = [
    ".collect-box-editor-dialog-V2",
    ".jx-overlay-dialog",
    "[role='dialog']",        # 新增：ARIA role
    ".jx-dialog",             # 新增：通用 jx 弹窗
    ".pro-dialog",            # 新增：pro 系列弹窗
    ".el-dialog"              # 新增：element-ui 弹窗
]

dialog = None
for selector in dialog_selectors:
    try:
        candidate = page.locator(selector).first
        if await candidate.count() > 0:
            await candidate.wait_for(state="visible", timeout=2_000)
            dialog = candidate
            logger.debug(f"✓ 使用弹窗选择器: {selector}")
            break
    except Exception:
        continue

if dialog is None:
    # 降级：使用整个页面作为搜索范围
    logger.warning("未能定位首次编辑弹窗容器，使用全局范围搜索")
    dialog = page.locator("body")
```

**优势：**
- ✅ 支持 6 种不同的弹窗选择器
- ✅ 自动尝试并选择第一个可用的
- ✅ 降级方案：使用全局搜索
- ✅ 添加调试信息保存（截图 + HTML）

---

### 2. 增强标题输入框检测 (`_fill_title`)

#### 修复前
```python
candidate_locators = [
    dialog.locator("input.jx-input__inner[type='text']"),
    dialog.locator("input[placeholder*='标题']"),
    page.get_by_placeholder("请输入标题", exact=False),
]
```

#### 修复后
```python
candidate_locators = [
    # 基于 label 的语义化定位器（最稳定）
    page.get_by_label("产品标题", exact=False),
    page.get_by_label("标题", exact=False),
    # 基于 placeholder 的定位器
    page.get_by_placeholder("请输入产品标题", exact=False),
    page.get_by_placeholder("请输入标题", exact=False),
    page.get_by_placeholder("标题", exact=False),
    # 基于弹窗内的 CSS 选择器
    dialog.locator("input.jx-input__inner[type='text']").first,
    dialog.locator("input[placeholder*='标题']").first,
    # 全局 CSS 选择器（降级方案）
    page.locator("input[placeholder*='标题']").first,
    page.locator("input[placeholder*='产品']").first,
]
```

**优势：**
- ✅ 优先使用语义化定位器（`get_by_label`）
- ✅ 9 种候选选择器，覆盖各种情况
- ✅ 从最稳定到最宽松的降级策略
- ✅ 添加调试截图

---

## 📊 选择器优先级策略

修复后的选择器按以下优先级排序：

| 优先级 | 类型 | 示例 | 稳定性 |
|--------|------|------|--------|
| 🔴 高 | 语义化定位器 | `get_by_label("产品标题")` | ⭐⭐⭐⭐⭐ |
| 🟡 中 | Placeholder | `get_by_placeholder("请输入标题")` | ⭐⭐⭐⭐ |
| 🟢 低 | ARIA role | `[role='dialog']` | ⭐⭐⭐ |
| ⚪ 降级 | CSS 选择器 | `.jx-dialog` | ⭐⭐ |
| ⚪ 最后 | 全局搜索 | `page.locator("body")` | ⭐ |

---

## 🎯 调试功能增强

### 新增调试信息保存

当弹窗或字段无法定位时，自动保存：

1. **截图**：`data/temp/screenshots/dialog_not_found.png`
2. **HTML 快照**：`data/debug/html/dialog_not_found.html`
3. **标题输入框截图**：`data/temp/screenshots/title_input_not_found.png`

**如何使用：**
```bash
# 运行后查看调试信息
ls -lh data/temp/screenshots/
ls -lh data/debug/html/
```

---

## ✅ 测试验证

### 测试场景

1. **正常情况**：使用第一个选择器成功
2. **弹窗结构变化**：自动降级到其他选择器
3. **所有选择器失败**：使用全局搜索作为兜底

### 预期结果

- ✅ 能够定位到首次编辑弹窗
- ✅ 能够填写标题、价格、库存等字段
- ✅ 失败时有清晰的调试信息

---

## 🔄 后续建议

### 短期方案（已完成）
- ✅ 增加多个候选选择器
- ✅ 实现智能降级策略
- ✅ 添加调试信息保存

### 长期方案（推荐）
使用前面创建的**选择器配置方案**：

1. 将所有选择器迁移到 `config/first_edit_selectors_v3.json`
2. 使用 `SelectorResolver` 动态解析
3. 运维人员可以自助修改配置

**优势：**
- 修改选择器不需要改代码
- 重启即可生效，无需重新部署
- 更容易维护和追踪变化

**参考文档：**
- `docs/FIRST_EDIT_MIGRATION.md` - 完整迁移指南
- `src/browser/selector_resolver.py` - 选择器解析器
- `config/first_edit_selectors_v3.json` - 配置示例

---

## 📝 修改文件清单

| 文件 | 修改内容 |
|------|----------|
| `src/browser/first_edit_dialog_codegen.py` | 增强 `_fill_basic_specs()` 和 `_fill_title()` |

---

## 🚀 立即测试

重新运行 Web Panel，应该能够成功填写首次编辑弹窗：

```bash
# 重启 Web Panel
py -3 beimeng_workspace/apps/temu-auto-publish/web_panel/cli.py start --port 8899
```

如果仍然失败，请检查：
1. 调试截图：`data/temp/screenshots/dialog_not_found.png`
2. HTML 快照：`data/debug/html/dialog_not_found.html`
3. 查看日志中使用了哪个选择器

---

## 💡 关键改进点

1. **鲁棒性提升**：从 2 个选择器增加到 6+ 个选择器
2. **智能降级**：自动尝试多个候选，而不是直接失败
3. **调试友好**：失败时自动保存截图和 HTML
4. **日志清晰**：显示使用了哪个选择器成功
5. **语义化优先**：优先使用 Playwright 推荐的 `get_by_*` 定位器

---

**状态：** ✅ 已修复并增强  
**版本：** v2.1 (增强版)  
**最后更新：** 2025-11-22


