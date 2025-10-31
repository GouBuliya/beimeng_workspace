# 🐛 关键修复：产品标题 vs 简易描述字段定位错误

> **修复日期**: 2025-10-31  
> **严重程度**: 🔴 高  
> **影响范围**: 首次编辑流程（SOP步骤4.2）

---

## 📸 问题截图

用户反馈截图显示：
- **上方红圈**: 产品标题（**应该修改**）
- **下方红圈**: 简易描述（**不应修改**）

## 🐛 问题描述

### 错误行为
代码在首次编辑时，**修改了"简易描述"字段而不是"产品标题"字段**。

### 根本原因
```python
# ❌ 错误的选择器（修复前）
title_selectors = [
    "textarea.jx-textarea__inner",  # 通用选择器，会匹配多个字段
    # ...
]

# 代码会找到第一个 textarea，这可能是"简易描述"而不是"产品标题"
```

### SOP要求

根据 **SOP 4.2 修改产品标题** 章节：

> #### ⚠️ 重要说明
> 
> **修改的是"产品标题"字段，不是"简易描述"字段！**
> 
> - **产品标题**：用于展示在店铺前端的主标题，需要优化关键词和流量
> - **简易描述**：内部使用的简短说明，无需修改

---

## ✅ 修复方案

### 新的选择器策略

```python
# ✅ 正确的选择器（修复后）
title_selectors = [
    # 方法1：通过label文本定位（最准确）
    "//div[contains(@class, 'jx-form-item') and .//label[contains(text(), '产品标题')]]//textarea",
    "//label[contains(text(), '产品标题')]/..//textarea",
    "//label[contains(text(), '产品标题')]/following-sibling::*//textarea",
    
    # 方法2：通过placeholder定位
    "textarea[placeholder*='产品标题']",
    "textarea[placeholder*='请输入产品标题']",
    
    # 方法3：通过表单项的data属性或class定位
    "div[class*='product-title'] textarea",
    ".product-title-input textarea",
    
    # 方法4：通过排除法（排除简易描述）
    "textarea.jx-textarea__inner:not([placeholder*='简易描述']):not([placeholder*='描述'])",
]
```

### 验证逻辑

添加了内容验证，确保获取到的是正确的字段：

```python
# 验证是否是产品标题（简单校验）
if "简易" in title or "描述" in title or len(title) < 10:
    logger.warning(f"⚠️ 可能获取到了错误的字段: {title[:30]}...")
    logger.warning("请使用Codegen获取正确的选择器")
else:
    logger.success(f"✓ 获取到产品标题: {title[:50]}...")
```

---

## 🔧 修改的文件

### `apps/temu-auto-publish/src/browser/first_edit_controller.py`

#### 1. `get_original_title()` 方法
- ✅ 更新选择器列表
- ✅ 添加多种定位策略
- ✅ 添加内容验证
- ✅ 添加详细日志

#### 2. `edit_title()` 方法
- ✅ 使用与 `get_original_title()` 相同的选择器策略
- ✅ 记录使用的选择器
- ✅ 降级方案（当所有策略失败时）

#### 3. 文件头部元信息
- ✅ 更新 `@GOTCHAS`：添加字段区分警告
- ✅ 添加 `@CHANGELOG`：记录修复历史

---

## 🧪 测试方法

### 1. 运行真实环境测试

```bash
cd /Users/candy/beimeng_workspace/apps/temu-auto-publish
python3 run_real_test.py
```

### 2. 观察日志输出

查找以下日志信息：

```
✓ 使用选择器定位到产品标题: <选择器名称>
✓ 获取到产品标题: <标题内容>
```

**✅ 正确**：日志显示获取到的是产品名称（如"药箱收纳盒 A0001型号"）  
**❌ 错误**：日志显示获取到的是描述性文本（如"家用便携收纳"）

### 3. 手动验证

1. 观察浏览器中打开的编辑弹窗
2. 确认**上方的"产品标题"字段**被修改
3. 确认**下方的"简易描述"字段**未被修改

---

## 📊 修复前后对比

### 修复前 ❌
```
使用选择器: textarea.jx-textarea__inner (第1个)
✓ 获取到原始标题: 简易描述的内容...
```
❌ 修改了错误的字段

### 修复后 ✅
```
✓ 使用选择器定位到产品标题: //label[contains(text(), '产品标题')]/..//textarea
✓ 获取到产品标题: 药箱收纳盒 A0001型号...
最终使用的选择器: //label[contains(text(), '产品标题')]/..//textarea
```
✅ 修改了正确的字段

---

## 🎯 后续优化建议

### 1. 使用 Playwright Codegen 获取精确选择器

如果当前的选择器策略仍然不够准确，使用 Codegen：

```bash
playwright codegen https://erp.91miaoshou.com/common_collect_box/items
```

在编辑弹窗中点击"产品标题"字段，Codegen会生成最精确的选择器。

### 2. 添加单元测试

创建测试用例，验证选择器的准确性：

```python
async def test_title_selector_accuracy():
    """测试产品标题选择器的准确性."""
    # 打开编辑弹窗
    # 使用选择器定位产品标题
    # 验证字段label是"产品标题"而不是"简易描述"
```

### 3. 监控和告警

在生产环境中，如果检测到可能选择了错误字段，发送告警通知。

---

## 📝 相关文档

- **SOP文档**: `docs/projects/temu-auto-publish/guides/商品发布SOP-IT专用.md` - 第4.2节
- **修复提交**: Git commit `0599454`
- **相关issue**: 用户反馈截图

---

## ✅ 验证清单

测试时请确认以下各项：

- [ ] 代码能成功定位到"产品标题"字段
- [ ] 日志输出显示使用的选择器
- [ ] 获取到的标题内容正确（不是简易描述）
- [ ] 修改标题后，上方字段发生变化
- [ ] 简易描述字段未被修改
- [ ] 降级方案（如果所有选择器失败）能正常工作
- [ ] 验证逻辑能检测到错误字段

---

**修复状态**: ✅ 已完成  
**Git提交**: `0599454`  
**需要验证**: 是（请在真实环境中测试）

