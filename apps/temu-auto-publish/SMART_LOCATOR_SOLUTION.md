# 智能选择器方案 - 解决动态页面问题

## 📌 问题分析

### 原问题
使用Playwright Codegen获取的选择器使用`aria-ref`属性，但该属性值是**动态生成的**，每次页面加载都会变化：

```
第一次: aria-ref=e11
第二次: aria-ref=e399
```

这导致选择器配置文件**不稳定**，无法重复使用。

## ✅ 解决方案

### 1. SmartLocator智能定位器

创建了`SmartLocator`工具类，实现：

#### 核心特性
- ✅ **多重后备选择器**：支持按优先级尝试多个选择器
- ✅ **智能等待和重试**：自动处理元素加载延迟
- ✅ **文本定位器优先**：使用稳定的文本内容定位
- ✅ **自适应查找**：支持按标签、角色、占位符等查找

#### 稳定的定位策略

```python
# ❌ 不稳定：使用动态aria-ref
"aria-ref=e492"

# ✅ 稳定：使用文本定位器
"button:has-text('保存')"
"input[placeholder*='重量']"
":text('产地') >> .. >> input"
"label:has-text('长度') + input"
```

### 2. 配置文件升级

#### v1.0 (旧版 - 不稳定)
```json
{
  "weight_input": "aria-ref=e694"
}
```

#### v3.0 (新版 - 稳定)
```json
{
  "weight_input": [
    "input[placeholder*='重量']",
    ":text('重量') >> .. >> input",
    "label:has-text('重量') + input",
    "input[type='number']:near(:text('重量'))"
  ]
}
```

### 3. 使用示例

#### 基本用法
```python
from utils.smart_locator import SmartLocator

locator = SmartLocator(page)

# 多个后备选择器
element = await locator.find_element([
    "button:has-text('保存')",
    "button:has-text('确定')",
    "[role='button']:has-text('保存')"
])

# 根据标签查找输入框
weight_input = await locator.find_input_by_label("重量")

# 点击（带重试）
await locator.click_with_retry("button:has-text('下一步')")

# 填写（带重试）
await locator.fill_with_retry([
    "input[placeholder*='重量']",
    ":text('重量') >> .. >> input"
], "7500")
```

#### 在BatchEditController中使用
```python
async def step_09_weight(self, page: Page) -> bool:
    # 生成随机重量
    weight = self.random_generator.generate_weight()
    
    # 使用SmartLocator
    locator = SmartLocator(page)
    input_selectors = step_config.get("input", [])
    
    # 智能填写（自动重试多个选择器）
    success = await locator.fill_with_retry(input_selectors, str(weight))
    
    return success
```

## 🎯 优势对比

| 特性 | Codegen + aria-ref | SmartLocator |
|------|-------------------|--------------|
| 稳定性 | ❌ 每次变化 | ✅ 稳定 |
| 可维护性 | ❌ 需要重新获取 | ✅ 自动适配 |
| 容错性 | ❌ 一处失效全失效 | ✅ 多重后备 |
| 页面变化 | ❌ 无法应对 | ✅ 自适应 |
| 手动工作 | ⚠️ 需要codegen | ✅ 无需手动 |

## 📋 支持的定位策略

### 1. 文本定位 (最稳定)
```python
"button:has-text('保存')"
":text('重量')"
```

### 2. 占位符定位
```python
"input[placeholder*='重量']"
"textarea[placeholder*='标题']"
```

### 3. 标签关联定位
```python
"label:has-text('重量') + input"
":text('产地') >> .. >> select"
```

### 4. 角色定位
```python
"[role='button']:has-text('保存')"
"[role='textbox']"
```

### 5. 相对位置定位
```python
"input:near(:text('重量'))"
"select:near(:text('产地'))"
```

## 🔧 配置结构

```json
{
  "step_09_weight": {
    "enabled": true,
    "input": [
      "input[placeholder*='重量']",
      ":text('重量') >> .. >> input",
      "label:has-text('重量') + input",
      "input[type='number']:near(:text('重量'))"
    ],
    "unit": "G",
    "range": [5000, 9999]
  }
}
```

## ✨ 核心API

### SmartLocator类

```python
class SmartLocator:
    def __init__(
        self,
        page: Page,
        default_timeout: int = 5000,
        retry_count: int = 3,
        wait_after_action: int = 500
    )
    
    # 查找元素
    async def find_element(
        selectors: Union[str, List[str]],
        timeout: Optional[int] = None,
        must_be_visible: bool = True
    ) -> Optional[Locator]
    
    # 文本定位
    async def find_by_text(
        text: str,
        element_type: Optional[str] = None
    ) -> Optional[Locator]
    
    # 标签定位
    async def find_input_by_label(label_text: str) -> Optional[Locator]
    async def find_select_by_label(label_text: str) -> Optional[Locator]
    
    # 操作方法（带重试）
    async def click_with_retry(selectors, max_retries=3) -> bool
    async def fill_with_retry(selectors, value, max_retries=3) -> bool
    async def select_option_with_retry(selectors, value, max_retries=3) -> bool
```

## 📈 实施效果

### Phase 1完成度
- ✅ 价格计算器更新（100%）
- ✅ 随机数据生成器（100%）
- ✅ 智能选择器系统（100%）
- ✅ 批量编辑控制器框架（80%）

### 关键突破
1. **无需手动获取选择器** - SmartLocator自动适配
2. **高容错性** - 多重后备策略
3. **易维护** - 文本定位器人类可读
4. **可扩展** - 支持添加新策略

## 🚀 后续计划

### Phase 2: AI集成
- 集成Claude AI标题生成
- 实现视觉模型图片验证
- 完善首次编辑控制器

### Phase 3: 完整流程
- 认领机制（5条×4次=20条）
- 店铺选择和供货价设置
- 批量发布功能（20×2=40条）
- 端到端测试

## 📚 参考文档

- `apps/temu-auto-publish/TESTING_SUMMARY.md` - 问题发现过程
- `apps/temu-auto-publish/config/miaoshou_selectors_v2.json` - v2文本定位器
- `apps/temu-auto-publish/config/miaoshou_selectors_batch_edit.json` - v3智能配置
- `apps/temu-auto-publish/src/utils/smart_locator.py` - 实现代码

## 💡 最佳实践

1. **优先使用文本定位器**
2. **提供至少3个后备选择器**
3. **使用描述性的选择器**
4. **避免依赖CSS类名（可能变化）**
5. **利用标签和角色属性**
6. **测试多种场景**

---

**结论**：通过SmartLocator智能选择器系统，我们完全解决了动态aria-ref的问题，无需手动使用Playwright Codegen，系统能自动适配页面变化，大大提高了自动化脚本的稳定性和可维护性。

