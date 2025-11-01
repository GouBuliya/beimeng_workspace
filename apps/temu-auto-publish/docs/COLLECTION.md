# 商品采集功能

## 📋 概述

商品采集功能实现了 SOP 步骤 1-3：
1. **访问前端店铺** - 自动访问Temu前端店铺
2. **站内搜索同款商品** - 根据选品表关键词搜索
3. **一次性采集5个同款商品链接** - 提取商品信息和链接

## 🏗️ 架构

### 核心组件

```
src/browser/collection_controller.py          # 采集控制器
src/data_processor/selection_table_reader.py  # 选品表读取器
src/workflows/collection_workflow.py          # 采集工作流
config/collection_selectors.json              # 页面选择器配置
run_collection_test.py                        # 采集测试脚本
```

### 数据流

```
Excel选品表 → SelectionTableReader → CollectionWorkflow
                                          ↓
                                    CollectionController
                                          ↓
                          访问店铺 → 搜索 → 采集链接
                                          ↓
                                    采集报告JSON
                                          ↓
                          妙手导入链接列表.txt
```

## 📊 数据格式

### 输入格式 - Excel选品表

根据SOP文档，选品表Excel结构如下：

| 主品负责人 | 产品名称 | 标题后缀 | 产品颜色/规格 | 采集数量 |
|----------|---------|---------|-------------|---------|
| 张三 | 药箱收纳盒 | A0049 | 白色/大号 | 5 |
| 李四 | 智能手表运动防水 | A0050 | 黑色/标准版 | 5 |

**必填字段**：
- `主品负责人` - 负责该产品的人员
- `产品名称` - 商品名称/搜索关键词
- `标题后缀` - 型号编号（格式: A0001-A9999）

**可选字段**：
- `产品颜色/规格` - 颜色和规格信息
- `产品图` - 主图URL
- `尺寸图` - 尺寸图URL
- `采集数量` - 采集数量（默认5）

### 输出格式 - 采集结果JSON

```json
{
  "timestamp": "2025-11-01T10:30:00",
  "summary": {
    "total_products": 10,
    "success": 9,
    "failed": 1,
    "success_rate": 90.0,
    "total_links": 45
  },
  "results": [
    {
      "product": {
        "owner": "张三",
        "product_name": "药箱收纳盒",
        "model_number": "A0049",
        "collect_count": 5
      },
      "collected_links": [
    {
        "url": "https://www.temu.com/product/12345",
        "title": "【新款】药箱收纳盒家用大容量...",
        "price": "¥39.90",
        "image": "https://img.temu.com/xxx.jpg",
        "index": 1
        }
      ],
      "success": true,
      "error": null,
      "timestamp": "2025-11-01T10:30:15"
    }
  ]
}
```

### 输出格式 - 妙手导入链接

```text
# 妙手ERP采集链接导入清单
# 生成时间: 2025-11-01 10:30:00
#============================================================

## 产品: 药箱收纳盒 (A0049)
## 采集数量: 5

1. https://www.temu.com/product/12345
   标题: 【新款】药箱收纳盒家用大容量...
   价格: ¥39.90

2. https://www.temu.com/product/67890
   标题: 药品收纳盒家庭医药箱大号...
   价格: ¥45.00

...
```

## 🚀 使用方法

### 方法 1：使用完整采集工作流（推荐）

```python
from src.workflows.collection_workflow import CollectionWorkflow

# 初始化工作流
workflow = CollectionWorkflow()

# 执行采集（需要已登录Temu并在店铺页面）
result = await workflow.execute(
    page=page,
    selection_table_path="data/input/selection_table.xlsx",
    skip_visit_store=False,  # 是否跳过访问店铺步骤
    save_report=True  # 是否保存采集报告
)

# 查看结果
print(f"成功采集 {result['summary']['success']} 个产品")
print(f"总链接数: {result['summary']['total_links']}")
print(f"报告文件: {result['report_file']}")
```

### 方法 2：独立使用采集控制器

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

### 方法 3：运行测试脚本（最简单）

```bash
# 确保已配置.env文件
cd /Users/candy/beimeng_workspace/apps/temu-auto-publish

# 运行采集测试
python3 run_collection_test.py
```

**测试脚本功能**：
1. ✅ 测试选品表读取
2. ✅ 创建示例选品表（如不存在）
3. ✅ 自动登录Temu
4. ✅ 执行完整采集流程
5. ✅ 生成采集报告和妙手导入链接

### 方法 4：准备选品表

使用Python代码创建示例选品表：

```python
from src.data_processor.selection_table_reader import SelectionTableReader

reader = SelectionTableReader()

# 创建示例选品表
reader.create_sample_excel(
    output_path="data/input/my_selection.xlsx",
    num_samples=5
)
```

或手动创建Excel文件（参考上面的"输入格式"）。

## 🔧 配置说明

### 环境变量配置 (`.env`)

```bash
# Temu账号（用于登录和采集）
TEMU_SHOP_URL=https://agentseller.temu.com/
TEMU_USERNAME=你的账号
TEMU_PASSWORD=你的密码
```

### 选择器配置 (`config/collection_selectors.json`)

```json
{
  "store": {
    "visit_button": "button:has-text('一键访问店铺'), a:has-text('访问店铺')",
    "search_input": "input[type='search'], input[placeholder*='搜索']",
    "search_button": "button:has-text('搜索'), button[type='submit']"
  },
  "product": {
    "item_card": ".product-card, .item-card, [data-product-id]",
    "product_link": "a[href*='/product/'], a[href*='/goods/']",
    "product_title": ".title, .product-title, h3",
    "product_price": ".price, .product-price"
  },
  "collection_box": {
    "miaoshou_extension": ".miaoshou-extension, #miaoshou-plugin",
    "add_button": "button:has-text('添加到采集箱'), .add-to-collection"
  }
}
```

**选择器说明**：
- 支持多个选择器（用逗号分隔），按顺序尝试
- 可以使用Playwright支持的所有选择器语法
- 包括CSS选择器、文本选择器（`:has-text`）、XPath等
- 如果页面结构变化，修改此文件更新选择器

### 自定义选择器示例

如果Temu页面更新导致选择器失效，可以：

1. 使用浏览器开发者工具检查元素
2. 找到稳定的选择器（class、id、data属性）
3. 更新`config/collection_selectors.json`

例如，如果产品卡片的class名变了：

```json
{
  "product": {
    "item_card": ".new-product-card, .goods-item"
  }
}
```

## ⚠️ 注意事项

### 1. 选品表准备（SOP要求）

根据 SOP 文档，采集前必须：
- ✅ **仔细阅读选品表**：记下型号编号（如A0049型号）
- ✅ **确认产品规格**：可售颜色、尺寸、展示形象
- ✅ **准备关键词**：使用精准关键词搜索

### 2. 商品筛选标准（SOP步骤2）

采集的商品必须符合选品表的规格：
- ✅ **尺寸一致**：与选品表中的尺寸规格完全匹配
- ✅ **外观相似**：产品整体外观、形状、设计相似
- ✅ **颜色匹配**：颜色选项与选品表要求一致
- ✅ **质量可靠**：优先选择评分高、销量好的商品

### 3. SOP常见错误（务必避免）

❌ **错误案例①：搜索出的产品尺寸不一致**
- 示例：选品表要求30cm，但采集了50cm的商品
- 后果：图片需要在妙手中删除替换

❌ **错误案例②：搜索出的产品长得不一样**
- 示例：外观、形状明显不同
- 后果：必须在妙手中将不匹配的图片删除

### 4. 采集数量

- **默认采集 5 个商品**（SOP要求）
- 可通过 `collect_count` 参数调整（1-10）
- 建议不超过 10 个，避免页面加载过慢

### 5. 搜索技巧（SOP步骤2）

- **使用精准关键词**：直接使用选品表中的产品名称
- **多翻几页**：不要只看第一页，符合要求的商品可能在后面
- **对比规格**：每个商品都要仔细对比尺寸、颜色、外观

### 6. 添加到妙手采集箱

目前采集功能主要负责：
- ✅ 搜索商品
- ✅ 提取商品信息（标题、价格、图片、URL）
- ✅ 记录商品链接
- ✅ 生成采集报告

**添加到妙手采集箱** 有两种方式：

**方式1：使用妙手浏览器插件（推荐）**
- 在Temu商品详情页，点击妙手插件的"采集商品"按钮
- 商品会自动添加到妙手公用采集箱

**方式2：手动复制链接**
- 使用`export_links_for_miaoshou()`导出链接列表
- 在妙手ERP中手动导入

### 7. 采集结果验证

采集完成后，必须检查：
- ✅ 采集数量是否达标（5个/产品）
- ✅ 商品是否符合选品表要求
- ✅ 链接是否有效
- ✅ 图片、标题、价格是否正确提取

## 🧪 测试

### 快速测试（推荐）

```bash
cd /Users/candy/beimeng_workspace/apps/temu-auto-publish

# 运行采集测试脚本
python3 run_collection_test.py
```

### 测试流程

测试脚本会自动执行：

**测试1：选品表读取**
1. ✅ 创建示例选品表（如不存在）
2. ✅ 读取Excel文件
3. ✅ 验证数据格式
4. ✅ 显示产品信息

**测试2：完整采集工作流**
1. ✅ 加载.env环境变量
2. ✅ 启动浏览器
3. ✅ 登录Temu商家后台
4. ✅ 访问前端店铺（SOP步骤1）
5. ✅ 搜索商品（SOP步骤2）
6. ✅ 采集5个链接（SOP步骤3）
7. ✅ 生成采集报告
8. ✅ 导出妙手导入链接

### 预期输出

```
============================================================
【SOP步骤1】访问Temu前端店铺
============================================================
✓ 成功访问前端店铺

============================================================
【SOP步骤2】站内搜索同款商品: 药箱收纳盒
============================================================
✓ 搜索成功，找到 50 个商品

============================================================
【SOP步骤3】一次性采集 5 个同款商品链接
============================================================
✓ 第 1 个商品: 【新款】药箱收纳盒家用大容量...
✓ 第 2 个商品: 药品收纳盒家庭医药箱大号...
✓ 第 3 个商品: 便携医药箱应急收纳盒...
✓ 第 4 个商品: 家庭急救包大容量医疗箱...
✓ 第 5 个商品: 多层药品收纳整理盒...

============================================================
采集完成：成功采集 5 个商品链接
============================================================

【采集结果】
总产品数: 2
成功: 2
失败: 0
总链接数: 10
报告文件: data/output/collection/collection_report_20251101_103000.json
妙手导入链接: data/output/collection/miaoshou_links.txt
```

### 手动测试

如果需要手动测试特定功能：

```python
# 测试选品表读取
from src.data_processor.selection_table_reader import SelectionTableReader

reader = SelectionTableReader()
products = reader.read_excel("data/input/selection.xlsx")
print(f"读取到 {len(products)} 个产品")

# 测试采集控制器
from src.browser.collection_controller import CollectionController

ctrl = CollectionController()
await ctrl.visit_store(page)
links = await ctrl.search_and_collect(page, "药箱收纳盒", count=5)
print(f"采集到 {len(links)} 个链接")
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

### Q1: 选品表格式不对怎么办？

**A**: 确保Excel包含必填字段：
- 主品负责人
- 产品名称
- 标题后缀（型号编号，如A0001）

可以使用示例生成器：
```python
from src.data_processor.selection_table_reader import SelectionTableReader
reader = SelectionTableReader()
reader.create_sample_excel("data/sample.xlsx", num_samples=3)
```

### Q2: 采集的商品不符合要求怎么办？

**A**: 优化策略：
1. **调整搜索关键词** - 使用更精准的关键词
2. **手动筛选** - 采集后人工审核链接
3. **编辑阶段处理** - 在SOP步骤4首次编辑时删除不匹配的图片

### Q3: 采集数量不足5个怎么办？

**A**: 检查：
1. **搜索关键词是否正确** - 参考选品表的"产品名称"
2. **Temu是否有足够同款** - 尝试更宽泛的关键词
3. **页面是否完全加载** - 增加等待时间
4. **选择器是否失效** - 检查`config/collection_selectors.json`

### Q4: 如何将采集的链接添加到妙手？

**A**: 两种方式：

**方式1：使用妙手插件（推荐）**
1. 安装妙手浏览器插件
2. 访问采集的商品详情页
3. 点击插件的"采集"按钮

**方式2：手动导入**
1. 运行采集工作流生成`miaoshou_links.txt`
2. 打开妙手ERP - 产品采集
3. 手动导入链接列表

### Q5: 选择器失效怎么办？

**A**: Temu页面更新导致选择器失效时：
1. 打开浏览器开发者工具（F12）
2. 检查元素结构
3. 更新`config/collection_selectors.json`中的选择器
4. 支持多个备选选择器（用逗号分隔）

示例：
```json
{
  "product": {
    "item_card": ".product-card, .new-card, [data-product]"
  }
}
```

### Q6: 测试时浏览器无法启动？

**A**: 检查：
1. **Playwright是否安装** - `python -m playwright install chromium`
2. **端口是否被占用** - 关闭其他CDP端口进程
3. **权限问题** - MacOS需要允许浏览器控制权限

### Q7: 采集报告在哪里？

**A**: 采集报告保存在：
- **JSON报告**: `data/output/collection/collection_report_YYYYMMDD_HHMMSS.json`
- **妙手链接**: `data/output/collection/miaoshou_links_YYYYMMDD_HHMMSS.txt`

### Q8: 如何批量采集多个产品？

**A**: 使用选品表：
1. 在Excel中添加多个产品行
2. 每行一个产品（产品名称+型号）
3. 运行`run_collection_test.py`
4. 工作流会自动逐个采集

### Q9: 采集速度慢怎么办？

**A**: 优化建议：
1. **减少采集数量** - 从5个减少到3个
2. **调整等待时间** - 修改`page.wait_for_timeout()`参数
3. **关闭无头模式** - 便于调试，但速度较慢
4. **并发采集** - 未来优化项（当前串行处理）

### Q10: 采集的图片无法显示？

**A**: 检查：
1. **图片URL是否有效** - 某些图片有防盗链
2. **网络连接** - 确保可以访问Temu CDN
3. **图片格式** - 支持JPG、PNG、WebP

## 📝 版本历史

- **v2.0** (2025-11-01) - 完整采集模块开发
  - ✅ 新增SelectionTableReader（Excel读取）
  - ✅ 新增CollectionWorkflow（完整工作流）
  - ✅ 新增run_collection_test.py（测试脚本）
  - ✅ 完善CollectionController功能
  - ✅ 更新文档和使用指南
  
- **v1.0** (2025-10-31) - 初始版本
  - ✅ CollectionController基础框架
  - ✅ visit_store, search_products, collect_links功能

## 🔗 相关文档

- [商品发布SOP - IT专用](../../../docs/projects/temu-auto-publish/guides/商品发布SOP-IT专用.md)
- [项目主README](../README.md)
- [快速开始指南](../QUICKSTART.md)
- [AI标题生成文档](./AI_TITLE_GENERATION.md)
- [调试指南](./DEBUG_GUIDE.md)

---

**作者**: AI Assistant
**最后更新**: 2025-11-01  
**许可证**: MIT
