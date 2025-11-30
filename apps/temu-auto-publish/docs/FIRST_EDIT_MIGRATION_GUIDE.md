# First Edit Migration Guide

## 目的

演示如何使用选择器配置方案重写首次编辑的标题填写功能

## 概述

- 使用 `SelectorResolver` 从 JSON 配置动态创建定位器
- 对比传统硬编码选择器 vs 配置驱动方案

## 代码示例

### 使用选择器配置方案的标题编辑功能

```python
from __future__ import annotations

from loguru import logger
from playwright.async_api import Page

from .base import FirstEditBase


class FirstEditTitleMixinV2(FirstEditBase):
    """使用选择器配置方案的标题编辑功能."""

    async def edit_title_v2(self, page: Page, title: str) -> bool:
        """使用配置驱动的方式填写产品标题.

        Args:
            page: Playwright 页面对象.
            title: 新的产品标题.

        Returns:
            True 如果填写成功，否则 False.

        Examples:
            >>> controller = FirstEditController()
            >>> await controller.edit_title_v2(page, "新产品标题")
        """
        logger.info(f"使用选择器配置填写标题: {title}")

        try:
            # 从 JSON 配置获取标题字段配置
            resolver = self._get_resolver(page)
            title_field_config = self.selectors.get("first_edit_dialog", {}).get(
                "fields", {}
            ).get("title", {})

            # 如果配置中没有 fields.title，降级到旧的 basic_info.title_input
            if not title_field_config:
                title_field_config = {
                    "locators": [
                        self.selectors.get("first_edit_dialog", {})
                        .get("basic_info", {})
                        .get("title_input", "input[placeholder*='标题']")
                    ]
                }

            # 解析字段配置，获取第一个可用的定位器
            title_input = await resolver.resolve_field(title_field_config, timeout_ms=3000)

            if title_input is None:
                logger.error("无法找到标题输入框")
                return False

            # 清空并填写标题
            await title_input.click()
            await title_input.fill("")  # 清空
            await title_input.type(title, delay=50)  # 逐字输入，模拟人工

            # 验证填写结果
            filled_value = await title_input.input_value()
            if filled_value.strip() != title.strip():
                logger.warning(f"标题填写验证失败: 期望='{title}', 实际='{filled_value}'")
                return False

            logger.success(f"✓ 标题已填写: {title}")
            return True

        except Exception as exc:
            logger.error(f"填写标题失败: {exc}")
            return False
```

## 对比示例：传统硬编码方式 vs 配置驱动方式

### 【传统方式】- 硬编码在代码中

```python
async def edit_title_old_way(page: Page, title: str) -> bool:
    """传统硬编码选择器的方式."""
    title_selectors = [
        "xpath=//label[contains(text(), '产品标题')]/following-sibling::*/descendant::input[@type='text'][1]",
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

### 【配置驱动方式】- 选择器在 JSON 中维护

#### miaoshou_selectors_v2.json 配置示例:

```json
{
  "first_edit_dialog": {
    "fields": {
      "title": {
        "locators": [
          {"type": "get_by_label", "value": "产品标题"},
          {"type": "get_by_placeholder", "value": "请输入产品标题"},
          {"type": "xpath", "value": "//label[contains(text(), '产品标题')]/following::input[@type='text'][1]"}
        ]
      }
    }
  }
}
```

#### 使用示例：

```python
resolver = SelectorResolver(page)
title_config = selectors["first_edit_dialog"]["fields"]["title"]
title_input = await resolver.resolve_field(title_config)
await title_input.fill(title)
```

## 迁移步骤总结

### 步骤 1: 补充 JSON 配置

在 `config/miaoshou_selectors_v2.json` 中添加：

```json
{
  "first_edit_dialog": {
    "fields": {
      "title": {
        "locators": [
          {"type": "get_by_label", "value": "产品标题"},
          {"type": "get_by_placeholder", "value": "请输入产品标题"},
          {"type": "css", "value": "input[placeholder*='标题']"}
        ]
      },
      "price": {
        "locators": [
          {"type": "get_by_label", "value": "建议售价"},
          {"type": "get_by_placeholder", "value": "请输入售价"}
        ]
      },
      "stock": {
        "locators": [
          {"type": "get_by_label", "value": "库存"},
          {"type": "get_by_placeholder", "value": "请输入库存"}
        ]
      }
    }
  }
}
```

### 步骤 2: 使用 SelectorResolver

```python
from src.browser.selector_resolver import SelectorResolver

resolver = SelectorResolver(page)
title_config = selectors["first_edit_dialog"]["fields"]["title"]
title_input = await resolver.resolve_field(title_config)
await title_input.fill(title)
```

### 步骤 3: 迁移现有功能

1. `title.py` -> 使用 `resolver.resolve_field()` 获取标题输入框
2. `sku.py` -> 使用 `resolver.resolve_field()` 获取价格/库存输入框
3. `logistics.py` -> 使用 `resolver.resolve_field()` 获取重量/尺寸输入框
4. `media.py` -> 使用 `resolver.resolve_field()` 获取上传按钮

## 优势对比

### 【传统硬编码方式】

- ✗ 选择器散落在代码各处
- ✗ 需要改代码才能更新选择器
- ✗ 难以复用和维护
- ✗ 需要重新部署才能生效

### 【配置驱动方式】

- ✓ 选择器集中在 JSON 配置文件
- ✓ 修改配置文件即可更新
- ✓ 支持多个候选定位器自动降级
- ✓ 支持 codegen 推荐的高级定位器
- ✓ 运维人员可以直接修改配置
- ✓ 无需重新部署，重启即可生效













