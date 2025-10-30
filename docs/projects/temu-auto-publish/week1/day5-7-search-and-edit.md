# Day 5-7：搜索采集和首次编辑

**目标**：完成站内搜索、链接采集和首次编辑流程

**技术**：Playwright 页面导航 + 数据提取 + 表单操作

---

## Day 5：站内搜索和链接采集

### 上午任务（3-4小时）

#### 5.1 使用 Codegen 录制搜索流程

**第一步：使用 Playwright Codegen 录制**

```bash
# 启动录制工具（需要先手动登录）
uv run playwright codegen https://seller.temu.com

# 手动操作：
# 1. 进入搜索页面
# 2. 输入关键词
# 3. 点击搜索
# 4. 等待结果加载
# 5. 记录产品列表的选择器
```

**流程设计**：
```
登录成功 → 导航到搜索页 → 输入关键词 → 点击搜索 → 等待结果 → 提取链接
```

#### 5.2 实现 SearchController

参考已有的 `src/browser/search_controller.py`，它已经实现了基础框架：

```python
"""
@PURPOSE: 实现Temu站内搜索和商品链接采集功能
@OUTLINE:
  - class SearchController: 搜索采集控制器
    - async def search_and_collect(): 主入口（搜索+采集）
    - async def _navigate_to_search(): 导航到搜索页
    - async def _input_and_search(): 输入关键词并搜索
    - async def _wait_for_results(): 等待搜索结果加载
    - async def _extract_products(): 提取商品信息
@DEPENDENCIES:
  - 内部: browser_manager, models.result
  - 外部: playwright, loguru
"""

class SearchController:
    """搜索采集控制器"""
    
    async def search_and_collect(
        self,
        page: Page,
        keyword: str,
        collect_count: int = 5
    ) -> SearchResult:
        """搜索并采集商品链接
        
        Args:
            page: Playwright 页面对象
            keyword: 搜索关键词
            collect_count: 采集数量
        
        Returns:
            SearchResult: 搜索结果（包含链接列表）
        """
        logger.info(f"开始搜索: {keyword}, 目标: {collect_count} 个")
        
        try:
            # 1. 导航到搜索页
            await self._navigate_to_search(page)
            
            # 2. 输入关键词并搜索
            await self._input_and_search(page, keyword)
            
            # 3. 等待结果加载
            await self._wait_for_results(page)
            
            # 4. 提取商品信息
            products = await self._extract_products(page, collect_count)
            
            logger.success(f"采集完成: {len(products)} 个商品")
            
            return SearchResult(
                success=True,
                keyword=keyword,
                products=products,
                collected_count=len(products)
            )
            
        except Exception as e:
            logger.error(f"搜索失败: {e}")
            await page.screenshot(path=f"data/temp/search_error_{int(time.time())}.png")
            
            return SearchResult(
                success=False,
                keyword=keyword,
                error_message=str(e)
            )
```

#### 5.3 完善具体实现（使用 Codegen 获取的选择器）

```python
async def _navigate_to_search(self, page: Page) -> None:
    """导航到搜索页"""
    # TODO: 使用 codegen 录制的实际 URL
    await page.goto("https://seller.temu.com/search")
    await page.wait_for_load_state("networkidle")
    logger.debug("已进入搜索页")


async def _input_and_search(self, page: Page, keyword: str) -> None:
    """输入关键词并搜索"""
    # TODO: 使用 codegen 获取的实际选择器
    search_input = 'input[placeholder*="搜索"]'  # 示例选择器
    search_button = 'button:has-text("搜索")'    # 示例选择器
    
    # 输入关键词
    await page.fill(search_input, keyword)
    logger.debug(f"已输入关键词: {keyword}")
    
    # 随机延迟（模拟人类）
    await asyncio.sleep(random.uniform(0.5, 1.5))
    
    # 点击搜索
    await page.click(search_button)
    logger.debug("已点击搜索按钮")


async def _wait_for_results(self, page: Page) -> None:
    """等待搜索结果加载"""
    # TODO: 使用 codegen 获取产品列表容器选择器
    results_container = 'div.product-list'  # 示例选择器
    
    await page.wait_for_selector(results_container, timeout=10000)
    
    # 等待网络空闲（确保数据加载完成）
    await page.wait_for_load_state("networkidle")
    logger.debug("搜索结果已加载")


async def _extract_products(self, page: Page, count: int) -> List[Dict]:
    """提取商品信息"""
    products = []
    
    # TODO: 使用 codegen 获取产品项的选择器
    product_items = await page.query_selector_all('div.product-item')
    
    for i, item in enumerate(product_items[:count]):
        try:
            # 提取商品信息
            # TODO: 根据实际页面结构调整
            link = await item.get_attribute('href')
            title = await item.inner_text('h3.title')
            price = await item.inner_text('span.price')
            
            products.append({
                "url": link,
                "title": title,
                "price": price,
                "index": i + 1
            })
            
        except Exception as e:
            logger.warning(f"提取第 {i+1} 个商品失败: {e}")
            continue
    
    return products
```

#### 任务清单
- [ ] 使用 `playwright codegen` 录制搜索流程
- [ ] 获取所有关键元素的选择器
- [ ] 完善 `search_controller.py` 中的 TODO 部分
- [ ] 测试不同关键词（至少 3 个）
- [ ] 处理无结果情况
- [ ] **验证标准**：能稳定采集到指定数量的链接

### 下午任务（3-4小时）

#### 5.4 优化和异常处理

##### 商品筛选逻辑（可选）
```python
async def _filter_products(self, products: List[Dict]) -> List[Dict]:
    """根据条件筛选商品"""
    filtered = []
    
    for product in products:
        # 解析价格
        price_str = product.get("price", "0")
        price = float(price_str.replace("¥", "").replace(",", ""))
        
        # 筛选条件
        if price > 0 and price < 10000:  # 价格在合理范围
            filtered.append(product)
    
    return filtered
```

##### 去重处理
```python
def _deduplicate_products(self, products: List[Dict]) -> List[Dict]:
    """去重（基于 URL）"""
    seen_urls = set()
    unique_products = []
    
    for product in products:
        url = product.get("url")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_products.append(product)
    
    logger.debug(f"去重: {len(products)} -> {len(unique_products)}")
    return unique_products
```

#### 5.5 创建测试脚本

创建 `examples/test_search.py`：

```python
"""测试搜索功能"""

import asyncio
from playwright.async_api import async_playwright

from src.browser.browser_manager import BrowserManager
from src.browser.login_controller import LoginController
from src.browser.search_controller import SearchController
from config.settings import settings


async def main():
    """测试搜索流程"""
    async with async_playwright() as p:
        # 1. 启动浏览器
        browser_manager = BrowserManager(p)
        page = await browser_manager.start()
        
        # 2. 登录
        login_controller = LoginController()
        await login_controller.login(
            page,
            page.context,
            settings.temu_username,
            settings.temu_password
        )
        
        # 3. 搜索采集
        search_controller = SearchController()
        result = await search_controller.search_and_collect(
            page,
            keyword="智能手表",
            collect_count=5
        )
        
        # 4. 输出结果
        print(f"\n采集结果:")
        print(f"  成功: {result.success}")
        print(f"  数量: {result.collected_count}")
        for i, product in enumerate(result.products, 1):
            print(f"  {i}. {product['title']} - {product['url']}")
        
        # 5. 关闭浏览器
        await browser_manager.close()


if __name__ == "__main__":
    asyncio.run(main())
```

运行测试：
```bash
uv run python examples/test_search.py
```

---

## Day 6-7：首次编辑流程

### Day 6 上午：认领商品（3-4小时）

#### 6.1 使用 Codegen 录制认领流程

```bash
# 录制认领操作
uv run playwright codegen https://seller.temu.com/product/detail/[ID]

# 手动操作：
# 1. 打开商品详情页
# 2. 找到认领按钮
# 3. 点击认领
# 4. 确认认领（如有弹窗）
# 5. 记录所有选择器
```

#### 6.2 实现 EditController 认领功能

参考已有的 `src/browser/edit_controller.py`：

```python
"""
@PURPOSE: 实现商品编辑和发布功能，包括认领、标题类目编辑、批量18步编辑
@OUTLINE:
  - class EditController: 编辑控制器
    - async def claim_and_edit(): 完整编辑流程（认领+编辑）
    - async def _claim_products(): 认领商品（5条变20条）
    - async def _edit_title_and_category(): 修改标题和类目
    - async def _batch_edit_18_steps(): 批量18步编辑
    - async def _save_product(): 保存商品
"""

async def _claim_products(
    self,
    page: Page,
    product_links: List[str]
) -> List[str]:
    """认领商品（5条变20条）
    
    Args:
        page: Playwright 页面
        product_links: 商品链接列表
    
    Returns:
        认领成功的商品 ID 列表
    """
    claimed_ids = []
    
    for idx, link in enumerate(product_links, 1):
        logger.info(f"处理第 {idx}/{len(product_links)} 个链接")
        
        try:
            # 1. 打开商品页
            await page.goto(link)
            await page.wait_for_load_state("networkidle")
            
            # 2. 检查是否可认领
            # TODO: 使用实际选择器
            claim_button = 'button:has-text("认领")'
            
            if await page.is_visible(claim_button):
                # 3. 认领 4 次（5 条变 20 条：1+4=5, 5×4=20）
                for i in range(4):
                    await page.click(claim_button)
                    await asyncio.sleep(random.uniform(1, 2))
                    logger.debug(f"  认领第 {i+1} 次")
                
                # 4. 获取商品 ID
                # TODO: 从 URL 或页面提取商品 ID
                product_id = self._extract_product_id(link)
                claimed_ids.append(product_id)
                
                logger.success(f"  ✓ 认领成功: {product_id}")
            else:
                logger.warning(f"  ⚠ 商品不可认领: {link}")
        
        except Exception as e:
            logger.error(f"  ✗ 认领失败: {e}")
            await page.screenshot(path=f"data/temp/claim_error_{idx}.png")
    
    return claimed_ids
```

#### 任务清单
- [ ] 录制认领流程
- [ ] 完善 `_claim_products` 方法
- [ ] 处理异常情况（已认领、次数限制）
- [ ] 测试至少 3 个商品
- [ ] **验证标准**：5 条成功变 20 条

### Day 6 下午：标题和类目编辑（3-4小时）

#### 6.3 录制编辑流程

```bash
# 录制编辑操作
uv run playwright codegen https://seller.temu.com/product/edit/[ID]

# 手动操作：
# 1. 定位标题输入框
# 2. 清空并输入新标题
# 3. 按空格键触发 AI（如需要）
# 4. 定位类目选择器
# 5. 修改类目
# 6. 记录所有选择器
```

#### 6.4 实现标题编辑

```python
async def _edit_title_and_category(
    self,
    page: Page,
    product_id: str,
    new_title: str,
    category: str
) -> bool:
    """修改标题和类目
    
    Args:
        page: Playwright 页面
        product_id: 商品 ID
        new_title: 新标题（AI 生成的）
        category: 类目路径（如 "电子产品/智能穿戴"）
    
    Returns:
        True 如果修改成功
    """
    logger.info(f"编辑商品: {product_id}")
    
    try:
        # 1. 进入编辑页
        edit_url = f"https://seller.temu.com/product/edit/{product_id}"
        await page.goto(edit_url)
        await page.wait_for_load_state("networkidle")
        
        # 2. 修改中文标题
        # TODO: 使用实际选择器
        cn_title_input = 'input[name="title_cn"]'
        await page.fill(cn_title_input, "")  # 清空
        await page.fill(cn_title_input, new_title)
        logger.debug(f"  标题已修改: {new_title[:30]}...")
        
        # 3. 触发英文标题 AI 生成（如果是 Temu AI 模式）
        await page.press(cn_title_input, "Space")
        await asyncio.sleep(3)  # 等待 AI 生成
        
        # 4. 验证英文标题已生成
        # TODO: 使用实际选择器
        en_title_input = 'input[name="title_en"]'
        en_title = await page.input_value(en_title_input)
        
        if en_title:
            logger.debug(f"  英文标题已生成: {en_title[:30]}...")
        else:
            logger.warning("  ⚠ 英文标题未生成")
        
        # 5. 修改类目（如需要）
        if category:
            await self._select_category(page, category)
        
        return True
        
    except Exception as e:
        logger.error(f"编辑失败: {e}")
        await page.screenshot(path=f"data/temp/edit_error_{product_id}.png")
        return False
```

#### 6.5 类目选择（复杂）

```python
async def _select_category(self, page: Page, category_path: str) -> None:
    """选择类目（处理多级分类）
    
    Args:
        category_path: 类目路径，如 "电子产品/智能穿戴/智能手表"
    """
    categories = category_path.split("/")
    
    # TODO: 使用实际选择器
    category_selector = 'div.category-selector'
    
    for level, category_name in enumerate(categories, 1):
        logger.debug(f"  选择第 {level} 级类目: {category_name}")
        
        # 点击展开
        await page.click(f"{category_selector} .level-{level}")
        
        # 查找并点击目标类目
        # 这里需要根据实际页面结构实现
        await page.click(f"text={category_name}")
        await asyncio.sleep(1)
    
    logger.debug("  类目选择完成")
```

### Day 7：图片确认和保存（全天）

#### 7.1 图片处理（MVP 简化版）

**MVP 方案**：人工验证

```python
async def _confirm_images(
    self,
    page: Page,
    product_id: str
) -> bool:
    """图片确认（人工）
    
    Returns:
        True 如果图片 OK
    """
    logger.info("图片确认...")
    
    # 1. 截图轮播图区域
    # TODO: 使用实际选择器
    image_container = 'div.product-images'
    await page.locator(image_container).screenshot(
        path=f"data/temp/images/{product_id}_carousel.png"
    )
    
    # 2. 显示给用户确认
    print(f"\n{'='*60}")
    print(f"商品 {product_id} 的图片已保存到:")
    print(f"  data/temp/images/{product_id}_carousel.png")
    print(f"{'='*60}")
    
    response = input("图片是否OK? (y/n): ")
    
    if response.lower() == 'y':
        logger.success("  ✓ 图片确认通过")
        return True
    else:
        logger.warning("  ⚠ 图片需要人工处理")
        return False
```

#### 7.2 保存商品

```python
async def _save_product(self, page: Page, product_id: str) -> bool:
    """保存商品
    
    Returns:
        True 如果保存成功
    """
    logger.info("保存商品...")
    
    try:
        # TODO: 使用实际选择器
        save_button = 'button:has-text("保存")'
        await page.click(save_button)
        
        # 等待保存完成
        # TODO: 根据实际页面调整
        success_message = 'div.success-toast'
        await page.wait_for_selector(success_message, timeout=10000)
        
        logger.success("  ✓ 保存成功")
        
        # 截图记录
        await page.screenshot(path=f"data/temp/saved_{product_id}.png")
        
        return True
        
    except TimeoutError:
        logger.error("  ✗ 保存超时")
        await page.screenshot(path=f"data/temp/save_error_{product_id}.png")
        return False
```

#### 7.3 完整流程整合

创建 `examples/test_full_workflow.py`：

```python
"""测试完整首次编辑流程"""

import asyncio
from playwright.async_api import async_playwright

from src.browser.browser_manager import BrowserManager
from src.browser.login_controller import LoginController
from src.browser.search_controller import SearchController
from src.browser.edit_controller import EditController
from config.settings import settings


async def main():
    """完整流程：登录 → 搜索 → 认领 → 编辑 → 保存"""
    async with async_playwright() as p:
        browser_manager = BrowserManager(p)
        page = await browser_manager.start()
        
        # 1. 登录
        logger.info("=" * 60)
        logger.info("步骤 1: 登录")
        logger.info("=" * 60)
        login_controller = LoginController()
        await login_controller.login(page, page.context)
        
        # 2. 搜索采集
        logger.info("\n" + "=" * 60)
        logger.info("步骤 2: 搜索采集")
        logger.info("=" * 60)
        search_controller = SearchController()
        search_result = await search_controller.search_and_collect(
            page,
            keyword="智能手表",
            collect_count=5
        )
        
        # 3. 认领和编辑
        logger.info("\n" + "=" * 60)
        logger.info("步骤 3: 认领和编辑")
        logger.info("=" * 60)
        edit_controller = EditController()
        
        # 认领
        claimed_ids = await edit_controller._claim_products(
            page,
            [p["url"] for p in search_result.products]
        )
        
        # 编辑第一个商品
        if claimed_ids:
            await edit_controller._edit_title_and_category(
                page,
                claimed_ids[0],
                new_title="【智能穿戴】高端智能手表 多功能运动手环",
                category="电子产品/智能穿戴"
            )
            
            # 图片确认
            if await edit_controller._confirm_images(page, claimed_ids[0]):
                # 保存
                await edit_controller._save_product(page, claimed_ids[0])
        
        logger.info("\n" + "=" * 60)
        logger.info("✓ 完整流程测试完成")
        logger.info("=" * 60)
        
        await browser_manager.close()


if __name__ == "__main__":
    asyncio.run(main())
```

---

## Day 5-7 交付物

### 必须完成 ✅
1. ✅ 站内搜索和链接采集（SearchController）
2. ✅ 商品认领流程（5条变20条）
3. ✅ 标题和类目编辑
4. ✅ 图片确认机制（MVP 版本）
5. ✅ 保存和结果验证
6. ✅ 完整端到端流程测试

### 文件清单 📁
```
src/browser/
  ├── search_controller.py    # 搜索控制器（需完善选择器）
  └── edit_controller.py      # 编辑控制器（需完善选择器）

examples/
  ├── test_search.py          # 搜索测试
  └── test_full_workflow.py   # 完整流程测试

data/temp/
  ├── screenshots/            # 各种截图
  ├── images/                 # 商品图片截图
  └── *.png                   # 错误截图
```

### 测试 Checklist 📋
```
☐ 搜索采集成功（至少 3 个关键词）
☐ 认领成功（5 条变 20 条）
☐ 标题修改成功
☐ 类目修改成功（至少测试 2 种类目）
☐ 英文标题 AI 生成成功（如使用 Temu AI）
☐ 图片确认流程顺畅
☐ 保存成功并有确认
☐ 完整流程端到端测试通过
```

---

## Week 1 总验收

### 验收标准 ✅
完成 Day 7 后，应该能够：

1. **自动化程度**
   - [x] Excel → JSON 自动转换（Day 3）
   - [x] 登录自动化（Cookie 复用，Day 4）
   - [x] 搜索采集自动化（Day 5）
   - [x] 认领编辑半自动化（图片需人工确认，Day 6-7）

2. **稳定性**
   - [ ] 连续处理 3 个产品无崩溃
   - [ ] 异常情况有清晰日志
   - [ ] 失败能继续处理下一个

3. **数据完整性**
   - [ ] 所有步骤有日志记录
   - [ ] 结果数据格式正确
   - [ ] 失败原因能追溯

---

## 常见问题

### 搜索结果不稳定
- **现象**：每次搜索结果不同
- **解决**：添加筛选条件（销量、评分），固定排序方式

### 认领失败
- **现象**：点击认领无反应
- **解决**：检查是否已达认领上限，增加等待时间

### 类目选择困难
- **现象**：类目树太复杂
- **解决**：
  - 参考采集商品的类目
  - 建立常用类目映射表
  - 记录人工选择的类目供后续参考

### 选择器失效
- **现象**：页面更新后元素找不到
- **解决**：
  - 使用多种定位策略（ID/CSS/XPath/Text）
  - 实现 fallback 机制
  - 定期使用 codegen 更新选择器

---

## 与影刀方案的对比

| 项目 | 影刀方案 | Playwright 方案 |
|------|---------|----------------|
| 搜索采集 | 录制回放 | 代码化提取 |
| 数据提取 | 影刀节点 | CSS/XPath 选择器 |
| 循环处理 | 影刀循环 | Python for/async |
| 异常处理 | 有限 | 完全可控 |
| 调试 | 困难 | IDE 断点 |
| 扩展性 | 受限 | 灵活 |

**Playwright 优势**：
- ✅ 数据提取更灵活
- ✅ 异步并发处理
- ✅ 完全代码化，易维护
- ✅ 调试友好

---

**Week 1 完成！🎉**

下一步：[第二周：批量编辑和发布](../week2/index.md)
