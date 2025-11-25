# 首次编辑模块：Codegen 转选择器方案指南

## 📊 现状分析

### 当前实现（混合方案）

首次编辑功能目前使用**两种方案并存**：

#### 1. 基于选择器列表的方案（`first_edit/` 目录）
```python
# src/browser/first_edit/title.py
title_selectors = [
    "xpath=//label[contains(text(), '产品标题')]/following-sibling::*/descendant::input[@type='text'][1]",
    "xpath=//label[contains(text(), '产品标题')]/following::input[@type='text'][1]",
    ".jx-overlay-dialog input.jx-input__inner[type='text']:visible",
]
```

**缺点：**
- ❌ 选择器硬编码在代码中
- ❌ 修改需要改代码、重新部署
- ❌ 难以维护和复用

#### 2. 基于 Codegen 录制的方案（`first_edit_dialog_codegen.py`）
```python
# src/browser/first_edit_dialog_codegen.py
async def fill_first_edit_dialog_codegen(page: Page, payload: dict) -> bool:
    # 使用 Playwright 推荐的高级定位器
    title_input = page.get_by_label("产品标题", exact=False)
    await title_input.fill(payload["title"])
```

**优点：**
- ✅ 使用 Playwright 推荐的语义化定位器
- ✅ 录制实际操作流程
- ✅ 更稳定、更接近真实用户行为

**缺点：**
- ❌ 仍然硬编码在代码中
- ❌ 修改需要改代码

---

## 🎯 目标方案：配置驱动

### 核心思想

将所有选择器（包括 codegen 生成的高级定位器）统一迁移到 JSON 配置文件，使用 `SelectorResolver` 动态解析。

### 架构设计

```
┌─────────────────────────────────────────┐
│   config/first_edit_selectors_v3.json   │  ← 所有选择器配置
└──────────────────┬──────────────────────┘
                   │ 读取配置
                   ↓
┌─────────────────────────────────────────┐
│     SelectorResolver (selector_resolver.py)  │  ← 配置解析器
│  - resolve_locator()                    │
│  - resolve_field()                      │
└──────────────────┬──────────────────────┘
                   │ 创建 Locator
                   ↓
┌─────────────────────────────────────────┐
│  FirstEditController (first_edit/)      │  ← 业务逻辑
│  - edit_title_v2()                      │
│  - set_sku_price_v2()                   │
└─────────────────────────────────────────┘
```

---

## 🔄 迁移步骤

### 步骤1：创建配置驱动工具

已完成：
- ✅ `src/browser/selector_resolver.py` - 选择器解析器
- ✅ `config/first_edit_selectors_v3.json` - 完整配置示例
- ✅ `src/browser/first_edit/base.py` - 集成解析器

### 步骤2：补充 JSON 配置

将 codegen 中的定位器转换为 JSON 配置：

```json
{
  "first_edit_dialog": {
    "fields": {
      "title": {
        "locators": [
          {"type": "get_by_label", "value": "产品标题", "exact": false},
          {"type": "get_by_placeholder", "value": "请输入产品标题"},
          {"type": "css", "value": "input[placeholder*='标题']"}
        ]
      }
    }
  }
}
```

支持的定位器类型：
- `get_by_label` - 最稳定，推荐优先使用
- `get_by_placeholder` - 通过占位符文本定位
- `get_by_role` - 通过 ARIA role 定位
- `get_by_text` - 通过文本内容定位
- `css` - CSS 选择器（降级方案）
- `xpath` - XPath 表达式（降级方案）

### 步骤3：重写业务逻辑

#### 迁移前（硬编码方式）

```python
# src/browser/first_edit/title.py
async def edit_title(self, page: Page, title: str) -> bool:
    title_selectors = [
        "xpath=//label[contains(text(), '产品标题')]/following::input[@type='text'][1]",
        ".jx-overlay-dialog input.jx-input__inner[type='text']:visible",
    ]
    
    for selector in title_selectors:
        try:
            locator = page.locator(selector)
            if await locator.count() > 0:
                await locator.first.fill(title)
                return True
        except Exception:
            continue
    return False
```

#### 迁移后（配置驱动）

```python
# src/browser/first_edit/title.py
async def edit_title_v2(self, page: Page, title: str) -> bool:
    resolver = self._get_resolver(page)
    
    # 从配置获取字段定义
    title_config = self.selectors["first_edit_dialog"]["fields"]["title"]
    
    # 自动尝试所有候选定位器，返回第一个可用的
    title_input = await resolver.resolve_field(title_config, timeout_ms=3000)
    
    if title_input is None:
        logger.error("无法找到标题输入框")
        return False
    
    await title_input.fill(title)
    return True
```

---

## 📝 完整迁移清单

### 需要迁移的模块

| 模块 | 文件 | 主要功能 | 优先级 |
|------|------|---------|--------|
| 标题编辑 | `first_edit/title.py` | `edit_title()` | 🔴 高 |
| SKU 价格/库存 | `first_edit/sku.py` | `set_sku_price()`, `set_sku_stock()` | 🔴 高 |
| 物流信息 | `first_edit/logistics.py` | `set_package_weight()`, `set_package_dimensions()` | 🟡 中 |
| 图片上传 | `first_edit/media.py` | `upload_main_images()`, `upload_size_chart()` | 🟡 中 |
| 弹窗操作 | `first_edit/dialog.py` | `open_edit_dialog()`, `close_dialog()` | 🟢 低 |

### 迁移步骤模板

对每个模块执行以下步骤：

1. **分析现有选择器**
   ```bash
   # 查看当前使用的选择器
   grep -n "page.locator\|page.get_by" src/browser/first_edit/title.py
   ```

2. **转换为 JSON 配置**
   ```json
   "title": {
     "locators": [
       {"type": "get_by_label", "value": "产品标题"},
       {"type": "css", "value": "input[placeholder*='标题']"}
     ]
   }
   ```

3. **重写业务方法**
   ```python
   async def edit_title_v2(self, page: Page, title: str) -> bool:
       resolver = self._get_resolver(page)
       config = self.selectors["first_edit_dialog"]["fields"]["title"]
       input_field = await resolver.resolve_field(config)
       await input_field.fill(title)
   ```

4. **测试验证**
   ```bash
   # 运行测试
   pytest tests/test_first_edit_v2.py -v
   ```

---

## 💡 优势对比

| 特性 | 硬编码方式 | Codegen 方式 | 配置驱动方式 |
|------|-----------|-------------|-------------|
| 维护成本 | ❌ 高 | ❌ 高 | ✅ 低 |
| 修改便捷性 | ❌ 需改代码 | ❌ 需改代码 | ✅ 改配置即可 |
| 部署要求 | ❌ 需重新部署 | ❌ 需重新部署 | ✅ 重启即可 |
| 选择器稳定性 | ❌ 低（CSS/XPath） | ✅ 高（语义化） | ✅ 高（语义化） |
| 运维友好 | ❌ 需开发介入 | ❌ 需开发介入 | ✅ 运维可自助 |
| 降级支持 | ❌ 无 | ❌ 无 | ✅ 多候选自动降级 |

---

## 🚀 快速开始

### 1. 使用示例

```python
from src.browser.first_edit.controller import FirstEditController

controller = FirstEditController(
    selector_path="config/first_edit_selectors_v3.json"
)

# 使用配置驱动方式填写标题
await controller.edit_title_v2(page, "新产品标题")
```

### 2. 修改选择器配置

当妙手 ERP 界面更新时，只需修改 JSON 配置：

```json
{
  "first_edit_dialog": {
    "fields": {
      "title": {
        "locators": [
          {"type": "get_by_label", "value": "产品名称"},  ← 改这里
          {"type": "css", "value": "input[name='title']"}
        ]
      }
    }
  }
}
```

重启服务即可生效，**无需修改代码**。

### 3. 录制新的选择器

使用 Playwright Codegen 录制操作：

```bash
uv run playwright codegen https://erp.91miaoshou.com
```

将生成的定位器转换为 JSON 格式：

```python
# Codegen 生成：
page.get_by_label("产品标题").fill("xxx")

# 转换为 JSON：
{
  "type": "get_by_label",
  "value": "产品标题",
  "exact": false
}
```

---

## 📚 参考文档

- `src/browser/selector_resolver.py` - 选择器解析器实现
- `src/browser/first_edit/MIGRATION_GUIDE.py` - 迁移示例代码
- `config/first_edit_selectors_v3.json` - 完整配置示例
- [Playwright Locators](https://playwright.dev/python/docs/locators) - 官方文档

---

## ⚠️ 注意事项

1. **向后兼容**：保留旧的方法名，新方法添加 `_v2` 后缀
2. **逐步迁移**：优先迁移高频使用的功能（标题、价格、库存）
3. **充分测试**：每个迁移的功能都需要测试验证
4. **配置备份**：修改配置前备份原文件

---

## 🎉 总结

通过将 codegen 转为选择器配置方案，我们实现了：

✅ **集中管理**：所有选择器集中在 JSON 配置  
✅ **灵活维护**：修改配置即可，无需改代码  
✅ **高级定位器**：支持 `get_by_label` 等语义化定位  
✅ **自动降级**：多个候选定位器自动尝试  
✅ **运维友好**：运维人员可以自助修改配置

这是一个**更专业、更易维护**的长期方案！


