# 首次编辑进入弹窗但不填写的诊断指南

## 🐛 问题症状

- ✅ 能够打开首次编辑弹窗
- ❌ 弹窗打开后没有进行任何填写操作
- ❌ 或者填写后立即失败并降级

---

## 🔍 可能的原因

### 1. JavaScript注入脚本找不到输入框

**原因**：妙手ERP页面结构变化，选择器失效

**解决**：已修复 - 移除硬编码的 `.collect-box-editor-dialog-V2`

### 2. Specs容器查找失败导致整体失败

**原因**：如果有specs但找不到 `.sku-setting` 容器，会标记为失败

**解决**：✅ 已修复 - 改为可选，不再强制要求

### 3. 调试信息不足

**原因**：原来的日志不显示具体哪些字段成功/失败

**解决**：✅ 已增强 - 添加详细的调试信息

---

## ✅ 已应用的修复

### 修复1: JavaScript注入脚本增强调试 (`data/assets/first_edit_inject.js`)

```javascript
// 新增调试信息
const result = {
  success: true,
  filled: [],      // 成功填写的字段
  missing: [],     // 缺失的字段
  debug: {         // 🆕 调试信息
    dialogFound: true/false,    // 是否找到弹窗
    totalInputs: 123,           // 页面上的输入框总数
    hasVariants: true/false,    // 是否有多规格
    hasSpecs: true/false,       // 是否有规格
  }
};
```

### 修复2: Specs容器改为可选

**之前**：找不到 `.sku-setting` → 标记为 `missing` → 整个注入失败
**现在**：找不到 → 只记录调试信息 → 继续填写其他字段

```javascript
// 修复前
if (!container) {
  result.missing.push("spec_container");  // ❌ 导致失败
  return;
}

// 修复后
if (!container) {
  result.debug.specContainerNotFound = true;  // ✅ 只记录
  console.warn('未找到规格容器，跳过规格填写');
  return;
}
```

### 修复3: 增强日志输出 (`src/browser/first_edit_executor.py`)

```python
# 新增详细日志
logger.info("调试信息: {}", result["debug"])
logger.success("已填写字段: {}", ", ".join(result.get("filled", [])))
logger.warning("缺失字段: {}", ", ".join(result.get("missing", [])))
```

---

## 🚀 如何诊断

### 步骤1: 重新运行并查看日志

重启 Web Panel 并触发首次编辑：

```bash
py -3 beimeng_workspace/apps/temu-auto-publish/web_panel/cli.py start --port 8899
```

### 步骤2: 观察新的日志输出

现在应该看到更详细的日志：

```
[INFO] 调试信息: {'dialogFound': True, 'totalInputs': 45, 'hasVariants': True, 'hasSpecs': False}
[SUCCESS] 已填写字段: title, product_number, price[row=1], stock[row=1], weight_g, length_cm, width_cm, height_cm
[WARNING] 缺失字段: supply_price[row=1], source_price[row=1]
```

### 步骤3: 根据日志判断问题

#### 情况A: 调试信息显示 `dialogFound: false`
**问题**：没有找到弹窗
**解决**：弹窗选择器需要更新

#### 情况B: 调试信息显示 `totalInputs: 0`
**问题**：页面还在加载，输入框未渲染
**解决**：需要增加等待时间

#### 情况C: `filled` 数组为空
**问题**：所有选择器都失效了
**解决**：需要用 Playwright Codegen 重新录制选择器

#### 情况D: 部分字段 `filled`，部分 `missing`
**问题**：某些字段的选择器失效
**解决**：只更新失效的字段选择器

---

## 🔧 进一步调试方法

### 方法1: 查看浏览器控制台

1. 打开浏览器开发者工具 (F12)
2. 切换到 Console 标签
3. 查看是否有 JavaScript 错误或警告

### 方法2: 手动测试注入脚本

在浏览器控制台中运行：

```javascript
// 测试注入脚本是否加载
console.log(typeof window.__FIRST_EDIT_APPLY__);  // 应该输出 "function"

// 手动测试填写
await window.__FIRST_EDIT_APPLY__({
  title: "测试标题",
  product_number: "A001",
  price: 99.9,
  stock: 100,
  weight_g: 500,
  length_cm: 10,
  width_cm: 10,
  height_cm: 10
});
// 查看返回结果
```

### 方法3: 检查页面HTML结构

1. 打开首次编辑弹窗
2. 在开发者工具中检查标题输入框
3. 查看实际的 HTML 属性：
   ```html
   <input placeholder="请输入产品标题" ...>
   <input aria-label="产品标题" ...>
   ```
4. 确认 JavaScript 注入脚本中的选择器是否匹配

---

## 📊 常见问题速查表

| 症状 | 可能原因 | 解决方法 |
|------|---------|---------|
| 弹窗打开后立即关闭 | 第一级失败，第二级也失败 | 查看日志中的 `missing` 字段 |
| 日志显示 `injector-not-found` | 注入脚本未加载 | 检查 `data/assets/first_edit_inject.js` 是否存在 |
| 日志显示大量 `missing` | 选择器全部失效 | 需要用 Codegen 重新录制 |
| 部分字段填写成功 | 某些选择器失效 | 只更新失效的选择器 |
| 填写成功但保存失败 | 保存按钮选择器问题 | 检查 `FirstEditController.save_changes()` |

---

## 🎯 预期的正常日志输出

```
[INFO] 首次编辑字段预览
[DEBUG] 已加载首次编辑注入脚本
[INFO] 调试信息: {
  'dialogFound': True,
  'totalInputs': 45,
  'hasVariants': False,
  'hasSpecs': False
}
[SUCCESS] 已填写字段: title, product_number, price, supply_price, source_price, stock, weight_g, length_cm, width_cm, height_cm
[SUCCESS] SKU 图片同步完成
[SUCCESS] ✓ 保存成功
```

---

## 🔄 如果还是不工作

### 选项1: 查看详细错误信息

运行后检查：
- 控制台日志中的 `[ERROR]` 和 `[WARNING]` 消息
- `result.debug` 对象的内容
- `result.missing` 数组的内容

### 选项2: 使用 Codegen 重新录制

```bash
# 录制新的选择器
uv run playwright codegen https://erp.91miaoshou.com
```

1. 手动打开首次编辑弹窗
2. 手动填写每个字段
3. 记录 Codegen 生成的选择器
4. 更新 `first_edit_inject.js` 中的选择器

### 选项3: 完全降级到 Codegen 方案

临时禁用 JavaScript 注入，只使用 Codegen：

```python
# 在 complete_publish_workflow.py 中修改
success = False  # 强制使用降级方案
# success = await first_edit_executor.apply(...)
```

---

## 📝 下一步行动

1. **重新运行** Web Panel
2. **查看日志**中的新调试信息
3. **告诉我**：
   - `debug` 对象显示什么？
   - `filled` 数组有哪些字段？
   - `missing` 数组有哪些字段？

有了这些信息，我可以精确定位问题并修复对应的选择器。


