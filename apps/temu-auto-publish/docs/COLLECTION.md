# 商品采集功能

## 📋 概述

商品采集功能实现了 SOP 步骤 1-3：
1. 访问前端店铺
2. 站内搜索同款商品
3. 一次性采集5个同款商品链接

## 🏗️ 架构

### 核心组件

```
src/browser/collection_controller.py  # 采集控制器
config/collection_selectors.json      # 采集页面选择器配置
src/workflows/full_publish_workflow.py  # 完整工作流（含采集）
tests/test_collection.py              # 采集功能测试
```

### 数据流

```
选品表 → 搜索关键词 → 前端搜索 → 采集链接 → 妙手采集箱 → 编辑 → 发布
```

## 📊 数据格式

### 输入格式

```python
products_data = [
    {
        "keyword": "药箱收纳盒",      # 搜索关键词
        "collect_count": 5,           # 采集数量（默认5）
        "cost": 10.0,                 # 成本价
        "stock": 100,                 # 库存
        "filters": {                  # 可选筛选条件
            "color": "白色",
            "size": "大号"
        }
    }
]
```

### 输出格式

```python
collected_links = [
    {
        "url": "https://www.temu.com/product/12345",
        "title": "【新款】药箱收纳盒家用大容量...",
        "price": "¥39.90",
        "image": "https://img.temu.com/xxx.jpg",
        "index": 1
    },
    # ... 更多商品
]
```

## 🚀 使用方法

### 方法 1：独立使用采集控制器

```python
from src.browser.collection_controller import CollectionController

# 初始化控制器
ctrl = CollectionController()

# 步骤1：访问店铺
await ctrl.visit_store(page)

# 步骤2-3：搜索并采集
links = await ctrl.search_and_collect(
    page,
    keyword="药箱收纳盒",
    count=5
)

# 查看结果
for link in links:
    print(f"{link['title']}: {link['url']}")
```

### 方法 2：使用完整工作流

```python
from src.workflows.full_publish_workflow import FullPublishWorkflow

# 初始化工作流
workflow = FullPublishWorkflow()

# 准备产品数据
products = [
    {
        "keyword": "药箱收纳盒",
        "collect_count": 5,
        "cost": 10.0,
        "stock": 100
    }
]

# 执行完整流程（采集 + 编辑 + 发布）
result = await workflow.execute(
    page,
    products,
    enable_batch_edit=True,
    enable_publish=False
)
```

### 方法 3：运行测试脚本

```bash
# 测试采集功能
cd /Users/candy/beimeng_workspace/apps/temu-auto-publish
python3 tests/test_collection.py
```

## 🔧 配置说明

### 选择器配置 (`config/collection_selectors.json`)

```json
{
  "store": {
    "visit_button": "button:has-text('一键访问店铺')",
    "search_input": "input[type='search']",
    "search_button": "button:has-text('搜索')"
  },
  "product": {
    "item_card": ".product-card",
    "product_link": "a[href*='/product/']",
    "product_title": ".title",
    "product_price": ".price"
  }
}
```

### 自定义选择器

如果页面结构发生变化，可以修改 `collection_selectors.json` 中的选择器。

## ⚠️ 注意事项

### 1. 商品筛选

根据 SOP 要求，采集的商品必须符合选品表的规格：
- ✅ 尺寸一致
- ✅ 外观相似
- ✅ 颜色匹配
- ❌ 避免不匹配的商品

### 2. 采集数量

- 默认采集 5 个商品
- 可通过 `collect_count` 参数调整
- 建议不超过 10 个，避免页面加载过慢

### 3. 搜索关键词

- 使用准确的关键词（来自选品表）
- 避免过于宽泛的关键词
- 可使用多个关键词测试，选择最佳结果

### 4. 添加到采集箱

目前采集功能主要负责：
- ✅ 搜索商品
- ✅ 提取商品信息
- ✅ 记录商品链接

**添加到妙手采集箱** 可能需要：
- 妙手浏览器插件
- 手动复制链接到妙手

## 🧪 测试

### 运行单元测试

```bash
python3 tests/test_collection.py
```

### 测试流程

1. ✅ 登录妙手ERP
2. ✅ 访问前端店铺
3. ✅ 搜索 "药箱收纳盒"
4. ✅ 采集 5 个商品链接
5. ✅ 显示采集结果

### 预期输出

```
✅ 成功采集 5 个商品:

  [1] 【新款】药箱收纳盒家用大容量医药箱急救箱...
      价格: ¥39.90
      链接: https://www.temu.com/product/12345...

  [2] 药品收纳盒家庭医药箱大号便携式急救包...
      价格: ¥45.00
      链接: https://www.temu.com/product/67890...
  
  ...
```

## 📈 后续优化

### 1. 智能筛选

- [ ] 基于图片相似度筛选
- [ ] 基于价格范围筛选
- [ ] 基于销量/评分筛选

### 2. 自动验证

- [ ] 自动检查尺寸匹配
- [ ] 自动检查外观一致性
- [ ] 自动过滤不符合要求的商品

### 3. 批量采集

- [ ] 支持多个关键词批量采集
- [ ] 支持从 Excel 读取关键词
- [ ] 自动生成采集报告

### 4. 妙手集成

- [ ] 自动添加到妙手采集箱
- [ ] 使用妙手插件 API
- [ ] 自动检查采集箱状态

## 🔗 相关文档

- [SOP 文档](../../../docs/projects/temu-auto-publish/guides/商品发布SOP-IT专用.md)
- [数据格式规范](../../../docs/projects/temu-auto-publish/guides/data-format.md)
- [工作流文档](./QUICKSTART.md)

## ❓ 常见问题

### Q: 采集的商品不符合要求怎么办？

A: 可以通过以下方式优化：
1. 调整搜索关键词
2. 添加筛选条件（颜色、尺寸等）
3. 在编辑阶段删除不匹配的图片

### Q: 采集数量不足 5 个怎么办？

A: 检查：
1. 搜索关键词是否正确
2. 前端店铺是否有足够的同款商品
3. 页面是否完全加载

### Q: 如何将采集的链接添加到妙手？

A: 目前支持两种方式：
1. 自动记录链接，手动复制到妙手
2. 使用妙手插件（需要插件支持）

---

**版本**: 1.0  
**更新日期**: 2025-10-31  
**作者**: AI Assistant

