# 🎯 多规格场景填写问题修复

## 问题诊断

根据你的日志：

```
[INFO] 调试信息: {'dialogFound': True, 'totalInputs': 99, 'hasVariants': True, 'hasSpecs': True}
[SUCCESS] 已填写字段: spec_name, spec_option_1, spec_option_2, spec_option_3, length_cm, width_cm, height_cm
[WARNING] 缺失字段: title, product_number, weight_g, price[row=1], supply_price[row=1], ...
```

**问题根源：**
- 当商品有多规格（`hasVariants: True`）时
- 页面上有**两种输入框**：
  1. 全局字段：标题、型号、重量（在弹窗顶部）
  2. 规格字段：价格、库存（在规格表格的每一行内）

**原选择器问题：**
```javascript
// ❌ 这样会匹配到表格内的输入框
document.querySelectorAll("input[placeholder*='标题']")
// 返回：弹窗顶部的标题输入框 + 表格内的标题列（错误匹配）
```

---

## ✅ 修复方案

### 1. 增强标题选择器

**修复策略：**
1. 优先使用 `aria-label` 和表单项定位（更精确）
2. 过滤掉规格表格内的输入框
3. 添加调试信息记录使用的选择器

```javascript
// 新增多个候选选择器
const titleSelectors = [
  "input[aria-label*='标题']",                                    // 🆕 最稳定
  "input[aria-label*='产品标题']",                                // 🆕
  ".jx-form-item:has(label:has-text('产品标题')) input",         // 🆕
  ".pro-form-item:has(label:has-text('产品标题')) input",        // 🆕
  "input[placeholder*='产品标题']",
  "input[placeholder*='标题']",
];

// 🆕 关键：过滤掉表格内的输入框
const validElements = elements.filter(
  el => !el.closest('.pro-virtual-table__row, .pro-virtual-scroll__row')
);
```

### 2. 增强型号选择器

同样的策略应用到商品编号/型号字段。

### 3. 增强重量选择器

重量字段也需要排除表格内的输入框。

---

## 📊 修复前后对比

| 字段 | 修复前 | 修复后 |
|------|--------|--------|
| **标题** | ❌ 找不到 | ✅ 应该能找到 |
| **型号** | ❌ 找不到 | ✅ 应该能找到 |
| **重量** | ❌ 找不到 | ✅ 应该能找到 |
| 规格名称 | ✅ 成功 | ✅ 成功 |
| 规格选项 | ✅ 成功 | ✅ 成功 |
| 尺寸 | ✅ 成功 | ✅ 成功 |
| **价格/库存** | ❌ 找不到 | 📝 需要进一步测试 |

---

## 🔍 价格/库存字段的诊断

从日志看，价格/库存字段也缺失：
```
缺失字段: price[row=1], supply_price[row=1], source_price[row=1], stock[row=1]
```

这些字段**应该在规格表格内**，代码中已有处理（第180-223行）。

**可能的问题：**
1. 规格行选择器不对：`.pro-virtual-table__row.pro-virtual-scroll__row`
2. 字段选择器不对：`input[placeholder*='建议售价']`

让我检查一下调试信息是否有线索...

---

## 🚀 立即测试

### 1. 重新运行

JavaScript 注入脚本已修复，重新运行：

```bash
# 刷新页面，重新触发工作流
```

### 2. 观察新日志

现在应该看到：

```
[SUCCESS] 已填写字段: title, product_number, weight_g, spec_name, spec_option_1, ...
[INFO] 调试信息: {
  'titleSelector': 'input[aria-label*=标题]',          // 🆕 显示使用的选择器
  'productNumberSelector': '...',                      // 🆕
  'weightSelector': '...'                               // 🆕
}
```

### 3. 如果价格/库存仍然缺失

那需要进一步检查规格表格的结构。请告诉我：

1. 日志中 `debug` 对象显示什么？
2. 哪些字段成功了？
3. 哪些字段还是缺失？

---

## 💡 关键改进点

1. **优先级策略**：
   - 🥇 aria-label（最稳定）
   - 🥈 label + 表单项
   - 🥉 placeholder

2. **过滤表格内元素**：
   ```javascript
   .filter(el => !el.closest('.pro-virtual-table__row'))
   ```

3. **调试信息增强**：
   - 记录使用的选择器
   - 标记为什么找不到

---

## 📝 已修改文件

- ✅ `data/assets/first_edit_inject.js` - 增强标题、型号、重量选择器

---

## 🎯 下一步

1. **立即测试** - 看标题/型号/重量是否能填写了
2. **如果还有问题** - 告诉我最新的日志输出
3. **价格/库存** - 如果这些还缺失，可能需要调整规格表格的选择器

继续测试并告诉我结果！ 🚀


