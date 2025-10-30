# Day 5-7：妙手采集箱操作流程（v2.0 - 基于 SOP）

**目标**：完成妙手采集箱的搜索、采集、首次编辑、认领、批量编辑流程

**技术**：Playwright 页面操作 + 数据提取 + 表单填充

**重要**：基于实际 SOP 手册的妙手工具流程

---

## 流程概览（11 步）

```
Day 5: 步骤 2-3  搜索和采集 5 条链接
Day 6: 步骤 4    首次编辑 5 条
Day 6: 步骤 5-6  认领机制 5→20条
Day 7: 步骤 7    批量编辑 18 步
```

---

## Day 5：搜索和采集（SOP 步骤 2-3）

### 上午任务（3-4小时）

#### 5.1 使用 Codegen 录制搜索流程

**目标**：在 Temu 前端店铺搜索同款商品并采集链接

**SOP 要求**：
- 结合选品表中的规格（颜色/尺寸/形象）
- 搜索符合要求的同款商品
- 一次性采集 **5 条**链接
- 必须仔细筛选，避免尺寸不一致或外观不同

**Codegen 录制步骤**：
```bash
# 1. 启动录制（已登录状态）
uv run playwright codegen

# 2. 手动操作并记录：
#    - 访问 Temu 前端店铺
#    - 在搜索框输入关键词（如"药箱收纳盒"）
#    - 点击搜索
#    - 浏览搜索结果
#    - 复制商品链接（5个）
#    - 在妙手采集箱中添加链接

# 3. 保存生成的选择器
```

#### 5.2 实现搜索控制器

**更新文件**：`src/browser/search_controller.py`

```python
"""
@PURPOSE: 实现Temu前端店铺搜索和链接采集功能（妙手工具）
@OUTLINE:
  - class SearchController: 搜索采集控制器
    - async def search_and_collect(): 主入口（搜索+采集）
    - async def _navigate_to_store(): 导航到前端店铺
    - async def _search_keyword(): 输入关键词并搜索
    - async def _filter_products(): 筛选符合要求的商品
    - async def _collect_links(): 采集商品链接
    - async def _add_to_miaoshou(): 添加到妙手采集箱
@GOTCHAS:
  - 必须仔细筛选商品，确保尺寸、颜色、外观一致
  - 采集数量固定为 5 条（SOP 要求）
  - 图片验证在首次编辑时进行
@DEPENDENCIES:
  - 内部: miaoshou_controller, models.result
  - 外部: playwright, loguru
@RELATED: miaoshou_controller.py
"""

import asyncio
from typing import List
from playwright.async_api import Page
from loguru import logger

from src.models.result import SearchResult


class SearchController:
    """搜索采集控制器（妙手工具）"""
    
    # SOP 规定的采集数量
    COLLECT_COUNT = 5
    
    def __init__(self):
        """初始化搜索控制器"""
        # TODO: 使用 codegen 获取实际选择器
        self.search_input_selector = "待获取"
        self.search_button_selector = "待获取"
        self.product_list_selector = "待获取"
        self.product_link_selector = "待获取"
    
    async def search_and_collect(
        self,
        page: Page,
        keyword: str,
        spec_requirements: dict = None
    ) -> SearchResult:
        """搜索并采集商品链接（SOP 步骤 2-3）
        
        Args:
            page: Playwright 页面对象
            keyword: 搜索关键词
            spec_requirements: 规格要求（颜色、尺寸等）
        
        Returns:
            SearchResult: 搜索结果（包含 5 条链接）
        """
        logger.info(f"SOP 步骤2-3：搜索并采集同款商品")
        logger.info(f"关键词: {keyword}")
        
        try:
            # 1. 确保在前端店铺页面
            await self._ensure_store_front(page)
            
            # 2. 输入关键词并搜索
            await self._search_keyword(page, keyword)
            
            # 3. 等待结果加载
            await self._wait_for_results(page)
            
            # 4. 筛选符合要求的商品
            products = await self._filter_products(
                page,
                spec_requirements
            )
            
            # 5. 采集前 5 条链接
            collected_links = products[:self.COLLECT_COUNT]
            
            if len(collected_links) < self.COLLECT_COUNT:
                logger.warning(
                    f"仅找到 {len(collected_links)} 个符合要求的商品，"
                    f"少于目标 {self.COLLECT_COUNT} 个"
                )
            
            logger.success(f"采集完成: {len(collected_links)} 条链接")
            
            return SearchResult(
                success=True,
                keyword=keyword,
                products=collected_links,
                collected_count=len(collected_links)
            )
            
        except Exception as e:
            logger.error(f"搜索采集失败: {e}")
            await page.screenshot(path="data/temp/search_error.png")
            
            return SearchResult(
                success=False,
                keyword=keyword,
                products=[],
                collected_count=0,
                error_message=str(e)
            )
    
    async def _ensure_store_front(self, page: Page) -> None:
        """确保在前端店铺页面
        
        Args:
            page: 页面对象
        """
        if "seller" in page.url:
            logger.info("当前在后台，需要先访问店铺")
            # TODO: 调用 MiaoshouController.navigate_to_store_front()
        
        logger.debug(f"当前页面: {page.url}")
    
    async def _search_keyword(self, page: Page, keyword: str) -> None:
        """输入关键词并搜索
        
        Args:
            page: 页面对象
            keyword: 搜索关键词
        """
        logger.info(f"输入搜索关键词: {keyword}")
        
        # 定位搜索框
        await page.fill(self.search_input_selector, keyword)
        await asyncio.sleep(0.5)
    
        # 点击搜索或按回车
        await page.click(self.search_button_selector)
        logger.debug("已触发搜索")

async def _wait_for_results(self, page: Page) -> None:
        """等待搜索结果加载
        
        Args:
            page: 页面对象
        """
        logger.info("等待搜索结果加载...")
        
        # 等待商品列表出现
        await page.wait_for_selector(
            self.product_list_selector,
            timeout=30000
        )
    
        # 额外等待动态内容
        await asyncio.sleep(2)
    logger.debug("搜索结果已加载")

    async def _filter_products(
        self,
        page: Page,
        spec_requirements: dict = None
    ) -> List[dict]:
        """筛选符合要求的商品
        
        SOP 强调：必须仔细筛选，确保尺寸、颜色、外观一致
        
        Args:
            page: 页面对象
            spec_requirements: 规格要求
            
        Returns:
            符合要求的商品列表
        """
        logger.info("筛选商品...")
        
        # 提取所有商品
        products = await self._extract_all_products(page)
        
        # MVP 阶段：人工筛选
        # Phase 2：添加自动筛选逻辑（图片相似度、规格匹配等）
        
        logger.info(f"共找到 {len(products)} 个商品")
        logger.warning("⚠️ MVP阶段：请人工确认商品是否符合选品表规格")
        
        return products
    
    async def _extract_all_products(self, page: Page) -> List[dict]:
        """提取页面上的所有商品信息
        
        Args:
            page: 页面对象
            
        Returns:
            商品列表
        """
    products = []
    
        # 获取商品元素列表
        product_elements = await page.query_selector_all(
            self.product_link_selector
        )
    
        for element in product_elements:
        try:
            # 提取商品信息
                link = await element.get_attribute('href')
                title = await element.inner_text()
                
                # 提取图片（用于验证）
                img_element = await element.query_selector('img')
                image_url = await img_element.get_attribute('src') if img_element else None
            
            products.append({
                    'link': link,
                    'title': title,
                    'image_url': image_url
            })
            
        except Exception as e:
                logger.warning(f"提取商品信息失败: {e}")
            continue
    
    return products
    
    async def add_links_to_miaoshou(
        self,
        page: Page,
        links: List[str]
    ) -> bool:
        """将链接添加到妙手采集箱
        
        Args:
            page: 页面对象
            links: 商品链接列表
            
        Returns:
            是否添加成功
        """
        logger.info(f"将 {len(links)} 条链接添加到妙手采集箱...")
        
        try:
            # TODO: 实现添加逻辑
            # 可能的方式：
            # 1. 在妙手采集箱页面有一个"添加链接"入口
            # 2. 批量粘贴链接
            # 3. 或者在搜索结果页直接点击"采集"按钮
            
            logger.success("链接已添加到采集箱")
            return True
            
        except Exception as e:
            logger.error(f"添加链接失败: {e}")
            return False
```

### 下午任务（3-4小时）

#### 5.3 图片验证辅助

创建图片验证辅助工具（可选，MVP 阶段可跳过）：

```python
# src/utils/image_validator.py

"""图片一致性验证辅助工具（可选）"""

from typing import List
from loguru import logger


class ImageValidator:
    """图片验证器（Phase 2 实现）"""
    
    def validate_similarity(
        self,
        reference_image: str,
        product_images: List[str]
    ) -> List[bool]:
        """验证商品图片与参考图片的相似度
        
        Args:
            reference_image: 选品表中的参考图片
            product_images: 采集的商品图片列表
            
        Returns:
            相似度验证结果列表
        """
        # TODO: Phase 2 实现
        # 使用 SSIM、特征匹配或视觉模型
        logger.warning("图片验证功能尚未实现，请人工确认")
        return [True] * len(product_images)
```

---

## Day 6 上午：首次编辑（SOP 步骤 4）

### 6.1 首次编辑流程

**目标**：对采集的 5 条链接进行首次编辑

**SOP 步骤 4 包括**：
1. 使用 AI 重新生成 5 个标题（必须加型号）
2. 核对类目
3. 核对并替换不一致图片（头图/轮播图/SKU图）
4. 补充尺寸图和产品视频
5. 保存修改

#### 实现首次编辑控制器

**新文件**：`src/browser/first_edit_controller.py`

```python
"""
@PURPOSE: 妙手采集箱首次编辑控制器（SOP步骤4）
@OUTLINE:
  - class FirstEditController: 首次编辑控制器
    - async def edit_all_links(): 编辑所有5条链接
    - async def edit_single_link(): 编辑单条链接
    - async def _regenerate_title(): AI重新生成标题
    - async def _verify_category(): 核对类目
    - async def _check_and_replace_images(): 检查并替换图片
    - async def _add_size_chart_and_video(): 补充尺寸图和视频
@GOTCHAS:
  - 标题必须添加型号后缀（SOP要求）
  - 图片验证是关键，必须确保一致性
  - MVP阶段图片验证可以人工介入
@DEPENDENCIES:
  - 内部: title_generator
  - 外部: playwright, loguru
"""

import asyncio
from typing import List
from playwright.async_api import Page
from loguru import logger

from src.data_processor.title_generator import TitleGenerator


class FirstEditController:
    """首次编辑控制器（SOP 步骤 4）"""
    
    def __init__(self):
        """初始化首次编辑控制器"""
        self.title_gen = TitleGenerator(mode="placeholder")
        
        # TODO: 使用 codegen 获取选择器
        self.title_input_selector = "待获取"
        self.category_selector = "待获取"
        self.image_upload_selector = "待获取"
        self.save_button_selector = "待获取"
    
    async def edit_all_links(
        self,
        page: Page,
        links: List[dict],
        model_prefix: str = "A",
        start_number: int = 1
    ) -> bool:
        """编辑所有 5 条链接（SOP 步骤 4）
        
        Args:
            page: 页面对象
            links: 链接列表（包含原标题）
            model_prefix: 型号前缀
            start_number: 起始编号
            
        Returns:
            是否全部编辑成功
        """
        logger.info("SOP 步骤4：妙手采集箱首次编辑（5条）")
        
        # 1. AI 生成新标题（批量）
        original_titles = [link['title'] for link in links]
        new_titles = self.title_gen.generate_with_model_suffix(
            original_titles,
            model_prefix=model_prefix,
            start_number=start_number,
            add_modifiers=True
        )
        
        logger.info(f"已生成 {len(new_titles)} 个新标题")
        
        # 2. 逐个编辑链接
        success_count = 0
        for i, (link, new_title) in enumerate(zip(links, new_titles), 1):
            logger.info(f"编辑第 {i}/5 条链接...")
            
            if await self.edit_single_link(page, link, new_title):
                success_count += 1
            else:
                logger.warning(f"第 {i} 条链接编辑失败")
        
        logger.info(f"首次编辑完成: {success_count}/{len(links)} 条成功")
        return success_count == len(links)
    
    async def edit_single_link(
        self,
        page: Page,
        link: dict,
        new_title: str
    ) -> bool:
        """编辑单条链接
        
        Args:
            page: 页面对象
            link: 链接信息
            new_title: 新标题（已包含型号）
            
        Returns:
            是否编辑成功
        """
        try:
            # 1. 打开编辑页面
            # TODO: 在妙手采集箱中找到该链接并点击编辑
            
            # 2. 修改标题
            await self._update_title(page, new_title)
        
            # 3. 核对类目
            await self._verify_category(page, link.get('category'))
            
            # 4. 检查并替换图片
            await self._check_and_replace_images(page, link)
            
            # 5. 补充尺寸图和视频
            await self._add_size_chart_and_video(page, link)
            
            # 6. 保存修改
            await self._save_changes(page)
            
            logger.success("链接编辑成功")
            return True
            
        except Exception as e:
            logger.error(f"链接编辑失败: {e}")
            await page.screenshot(path=f"data/temp/edit_error_{int(time.time())}.png")
            return False
    
    async def _update_title(self, page: Page, new_title: str) -> None:
        """更新标题
        
        Args:
            page: 页面对象
            new_title: 新标题
        """
        logger.info(f"更新标题: {new_title}")
        
        await page.fill(self.title_input_selector, "")  # 清空
        await page.fill(self.title_input_selector, new_title)
        await asyncio.sleep(0.5)
        
        logger.debug("标题已更新")
    
    async def _verify_category(
    self,
    page: Page,
        expected_category: str = None
    ) -> None:
        """核对类目
        
        SOP 要求：有些类目上不了（如药品/电子）
    
    Args:
            page: 页面对象
            expected_category: 预期类目
        """
        logger.info("核对类目...")
        
        # TODO: 检查当前类目是否正确
        # MVP 阶段：提示人工确认
        logger.warning("⚠️ 请人工确认类目是否正确且可用")
        
        # Phase 2: 自动验证类目
    
    async def _check_and_replace_images(
        self,
        page: Page,
        link: dict
    ) -> None:
        """检查并替换不一致图片（SOP 强调）
        
        SOP 要求：
        - 检查头图、轮播图、SKU图
        - 将不一致的图片全部删除/替换
        - 坚决不允许遗漏
        - SKU图后续换成实拍图
        
        Args:
            page: 页面对象
            link: 链接信息
        """
        logger.info("检查图片一致性...")
        
        # TODO: 实现图片检查逻辑
        # MVP 阶段：人工确认
        logger.warning("⚠️ 请人工确认图片是否一致，删除/替换不一致的图片")
        
        # Phase 2: 使用图像相似度算法自动检测
    
    async def _add_size_chart_and_video(
        self,
        page: Page,
        link: dict
    ) -> None:
        """补充尺寸图和产品视频
        
        SOP 步骤：
        1. 在站内找到之前采集的5个商品链接
        2. 找到符合规格的尺寸图和视频
        3. 复制图片/视频地址
        4. 使用网络图片上传
        
        Args:
            page: 页面对象
            link: 链接信息
        """
        logger.info("补充尺寸图和视频...")
        
        # TODO: 实现素材补充逻辑
        # 1. 从原商品链接提取尺寸图和视频URL
        # 2. 在编辑页面上传网络图片
        
        logger.warning("⚠️ MVP阶段：请人工补充尺寸图和视频")
    
    async def _save_changes(self, page: Page) -> None:
        """保存修改
        
        Args:
            page: 页面对象
        """
        logger.info("保存修改...")
        
        await page.click(self.save_button_selector)
        await asyncio.sleep(2)
        
        logger.success("修改已保存")
```

---

## Day 6 下午：认领机制（SOP 步骤 5-6）

### 6.2 认领和验证

**目标**：将 5 条链接各认领 4 次，得到 20 条

**SOP 步骤 5-6**：
1. 5 条链接全部首次编辑完成后
2. 挨个点击认领按钮 4 次
3. 验证采集箱中有 20 条（5 × 4）

#### 实现认领控制器

**更新文件**：`src/browser/miaoshou_controller.py`（添加认领功能）

```python
async def claim_links(
    self,
    page: Page,
    link_count: int = 5,
    claim_times: int = 4
) -> bool:
    """认领链接（SOP 步骤 5）
    
    将每条链接认领多次，用于后续批量编辑和发布
    
    Args:
        page: 页面对象
        link_count: 链接数量（默认 5）
        claim_times: 每条认领次数（默认 4）
    
    Returns:
        是否认领成功
    """
    logger.info(f"SOP 步骤5：认领链接（{link_count}条 × {claim_times}次）")
    
    try:
        # TODO: 使用 codegen 获取链接列表和认领按钮选择器
        
        for i in range(1, link_count + 1):
            logger.info(f"认领第 {i} 条链接...")
            
            for j in range(1, claim_times + 1):
                # 定位到第 i 条链接的认领按钮
                claim_button = f"待获取选择器_link{i}_claim"
                
                await page.click(claim_button)
                await asyncio.sleep(random.uniform(1, 2))
                
                logger.debug(f"  第 {j}/{claim_times} 次认领")
            
            logger.success(f"第 {i} 条链接认领完成")
        
        logger.success(f"所有链接认领完成（预期生成 {link_count * claim_times} 条）")
        return True
        
    except Exception as e:
        logger.error(f"认领失败: {e}")
        await page.screenshot(path="data/temp/claim_error.png")
        return False

async def verify_claims(
    self,
    page: Page,
    expected_count: int = 20
) -> bool:
    """验证认领结果（SOP 步骤 6）
    
    检查采集箱中是否有预期数量的链接
    
    Args:
        page: 页面对象
        expected_count: 预期数量（默认 20）
        
    Returns:
        是否验证通过
    """
    logger.info(f"SOP 步骤6：验证认领结果（预期 {expected_count} 条）")
    
    try:
        # 1. 设置每页显示 20 条
        # TODO: 找到分页控件，选择"20条/页"
        
        # 2. 统计链接数量
        # TODO: 获取链接列表元素
        link_elements = await page.query_selector_all("待获取_链接列表选择器")
        actual_count = len(link_elements)
        
        logger.info(f"当前采集箱中有 {actual_count} 条链接")
        
        # 3. 验证数量
        if actual_count == expected_count:
            logger.success(f"✓ 验证通过：{actual_count} 条")
            return True
        else:
            logger.error(f"✗ 验证失败：预期 {expected_count} 条，实际 {actual_count} 条")
            return False
        
    except Exception as e:
        logger.error(f"验证失败: {e}")
        return False
```

---

## Day 7：批量编辑 18 步（SOP 步骤 7）

### 7.1 批量编辑流程

**目标**：对 20 条链接执行 18 步批量编辑

**SOP 步骤 7 详细步骤**：
1. 标题（预览+保存）
2. 英语标题（空格触发 AI）
3. 类目属性（参考采集链接）⚠️ 复杂
4. 主货号（跳过）
5. 外包装（长方体/硬包装）
6. 产地（浙江）
7. 定制品（跳过）
8. 敏感属性（跳过）
9. 重量（5000-9999G 随机）
10. 尺寸（50-99cm，长>宽>高）
11. 平台 SKU（自定义编码）
12. SKU 分类（组合装 500 件）
13. 尺码表（跳过）
14. 建议售价（成本价 × 10）
15. 包装清单（跳过）
16. 轮播图（跳过）
17. 颜色图（跳过）
18. 产品说明书（上传文件）

#### 实现批量编辑控制器

**新文件**：`src/browser/batch_edit_controller.py`

```python
"""
@PURPOSE: 妙手采集箱批量编辑控制器（SOP步骤7，18个固定步骤）
@OUTLINE:
  - class BatchEditController: 批量编辑控制器
    - async def batch_edit_18_steps(): 执行完整18步
    - async def _step_01_title(): 步骤1 - 标题
    - async def _step_02_english_title(): 步骤2 - 英语标题
    - ... (18个步骤方法)
    - async def _preview_and_save(): 预览并保存
@GOTCHAS:
  - 每步必须预览后保存（SOP要求）
  - 步骤3（类目属性）最复杂，需要参考采集链接
  - 随机数据生成要符合范围要求
@DEPENDENCIES:
  - 内部: random_generator, price_calculator
  - 外部: playwright, loguru
"""

import asyncio
import random
from playwright.async_api import Page
from loguru import logger

from src.data_processor.price_calculator import PriceCalculator


class BatchEditController:
    """批量编辑控制器（SOP 步骤 7）"""
    
    def __init__(self):
        """初始化批量编辑控制器"""
        self.price_calc = PriceCalculator()
        
        # TODO: 使用 codegen 获取选择器
        self.batch_edit_button = "待获取"
        self.preview_button = "待获取"
        self.save_button = "待获取"
    
    async def batch_edit_18_steps(
        self,
        page: Page,
        product_data: dict
    ) -> bool:
        """执行完整的 18 步批量编辑（SOP 步骤 7）
        
        Args:
            page: 页面对象
            product_data: 产品数据（包含成本价等）
    
    Returns:
            是否全部步骤成功
    """
        logger.info("SOP 步骤7：批量编辑 18 步（20条链接）")
        
        # 1. 全选 20 条链接
        await self._select_all_links(page)
        
        # 2. 点击批量编辑
        await page.click(self.batch_edit_button)
        await asyncio.sleep(2)
        
        # 3. 执行 18 个步骤
        steps = [
            (1, self._step_01_title, "标题"),
            (2, self._step_02_english_title, "英语标题"),
            (3, self._step_03_category_attrs, "类目属性"),
            (4, self._skip_step, "主货号"),
            (5, self._step_05_packaging, "外包装"),
            (6, self._step_06_origin, "产地"),
            (7, self._skip_step, "定制品"),
            (8, self._skip_step, "敏感属性"),
            (9, self._step_09_weight, "重量"),
            (10, self._step_10_dimensions, "尺寸"),
            (11, self._step_11_platform_sku, "平台SKU"),
            (12, self._step_12_sku_category, "SKU分类"),
            (13, self._skip_step, "尺码表"),
            (14, self._step_14_suggested_price, "建议售价"),
            (15, self._skip_step, "包装清单"),
            (16, self._skip_step, "轮播图"),
            (17, self._skip_step, "颜色图"),
            (18, self._step_18_manual, "产品说明书"),
        ]
        
        for step_num, func, name in steps:
            logger.info(f"执行步骤 {step_num}/18: {name}")
            
            try:
                await func(page, product_data)
                await self._preview_and_save(page)
                await asyncio.sleep(random.uniform(2, 3))
                
                logger.success(f"✓ 步骤 {step_num} 完成")
                
            except Exception as e:
                logger.error(f"✗ 步骤 {step_num} 失败: {e}")
                await page.screenshot(
                    path=f"data/temp/batch_edit_step{step_num}_error.png"
                )
        return False
        
        logger.success("✓✓✓ 批量编辑 18 步全部完成")
        return True
    
    async def _select_all_links(self, page: Page) -> None:
        """全选 20 条链接
        
        Args:
            page: 页面对象
        """
        logger.debug("全选 20 条链接...")
        
        # TODO: 找到全选按钮并点击
        select_all_button = "待获取"
        await page.click(select_all_button)
        await asyncio.sleep(1)
    
    async def _preview_and_save(self, page: Page) -> None:
        """预览并保存（每步必须执行）
        
        Args:
            page: 页面对象
        """
        # 点击预览
        await page.click(self.preview_button)
        await asyncio.sleep(1)
        
        # 点击保存
        await page.click(self.save_button)
        await asyncio.sleep(1)
        
        # 等待保存完成提示
        # TODO: 等待"保存成功"提示
    
    async def _skip_step(self, page: Page, data: dict) -> None:
        """跳过步骤（不需要改动）
        
        Args:
            page: 页面对象
            data: 产品数据
        """
        logger.debug("跳过此步骤（不需要改动）")
    
    async def _step_01_title(self, page: Page, data: dict) -> None:
        """步骤 1：标题（不需要改动）"""
        pass
    
    async def _step_02_english_title(self, page: Page, data: dict) -> None:
        """步骤 2：英语标题（空格触发 AI）"""
        logger.debug("在英语标题框按空格触发 AI")
        
        # TODO: 定位英语标题输入框
        english_title_input = "待获取"
        
        await page.click(english_title_input)
        await page.keyboard.press("Space")
        await asyncio.sleep(0.5)
    
    async def _step_03_category_attrs(self, page: Page, data: dict) -> None:
        """步骤 3：类目属性（复杂逻辑）⚠️
        
        SOP 要求：参考采集链接的类目属性
        """
        logger.warning("⚠️ 类目属性是最复杂的步骤，MVP阶段建议人工确认")
        
        # TODO: Phase 2 实现
        # 1. 展开类目属性
        # 2. 找到采集链接的同类目
        # 3. 复制其类目属性
        # 4. 填充到编辑页面
    
    async def _step_05_packaging(self, page: Page, data: dict) -> None:
        """步骤 5：外包装（长方体/硬包装）"""
        logger.debug("设置外包装：长方体 + 硬包装")
        
        # TODO: 选择外包装形状和类型
        # 外包装形状：长方体
        # 外包装类型：硬包装
        # 添加图片（如果需要）
    
    async def _step_06_origin(self, page: Page, data: dict) -> None:
        """步骤 6：产地（浙江）"""
        logger.debug("设置产地：浙江")
        
        # TODO: 输入"浙江"，选择"中国大陆/浙江省"
        origin_input = "待获取"
        await page.fill(origin_input, "浙江")
        # 等待下拉列表并选择
    
    async def _step_09_weight(self, page: Page, data: dict) -> None:
        """步骤 9：重量（5000-9999G 随机）"""
        weight = random.randint(5000, 9999)
        logger.debug(f"设置重量：{weight}G")
        
        # TODO: 填充重量
        weight_input = "待获取"
        await page.fill(weight_input, str(weight))
    
    async def _step_10_dimensions(self, page: Page, data: dict) -> None:
        """步骤 10：尺寸（50-99cm，长>宽>高）"""
        # 生成符合要求的尺寸
        length = random.randint(70, 99)
        width = random.randint(60, length - 1)
        height = random.randint(50, width - 1)
        
        logger.debug(f"设置尺寸：{length} × {width} × {height} cm")
            
        # TODO: 填充长宽高
        # length_input, width_input, height_input = "待获取"
    
    async def _step_11_platform_sku(self, page: Page, data: dict) -> None:
        """步骤 11：平台 SKU（自定义编码）"""
        logger.debug("设置平台 SKU（自定义编码）")
        
        # TODO: 点击"自定义 SKU 编码"（不需要填写内容）
        sku_button = "待获取"
        await page.click(sku_button)
    
    async def _step_12_sku_category(self, page: Page, data: dict) -> None:
        """步骤 12：SKU 分类（组合装 500 件）"""
        logger.debug("设置 SKU 分类：组合装500件")
        
        # TODO: 选择"组合装500件"，不是独立包装
        sku_category_selector = "待获取"
        await page.select_option(sku_category_selector, "组合装500件")
    
    async def _step_14_suggested_price(self, page: Page, data: dict) -> None:
        """步骤 14：建议售价（成本价 × 10）"""
        cost_price = data.get('cost_price', 0)
        suggested_price = self.price_calc.calculate_suggested_price(cost_price)
        
        logger.debug(f"设置建议售价：{suggested_price} 元")
        
        # TODO: 填充建议售价
        price_input = "待获取"
        await page.fill(price_input, str(suggested_price))
    
    async def _step_18_manual(self, page: Page, data: dict) -> None:
        """步骤 18：产品说明书（上传文件）"""
        logger.debug("上传产品说明书")
        
        # TODO: 上传文件
        # MVP 阶段：使用统一模板文件
        manual_file = "data/templates/product_manual.pdf"
        
        upload_input = "待获取"
        await page.set_input_files(upload_input, manual_file)
```

---

## 验收标准 ✅

### Day 5 验收
- [ ] 搜索功能正常
- [ ] 能采集到 5 条链接
- [ ] 链接已添加到妙手采集箱

### Day 6 验收
- [ ] 首次编辑功能实现
- [ ] 标题生成带型号
- [ ] 认领机制正常（5→20）
- [ ] 验证通过（20 条存在）

### Day 7 验收
- [ ] 批量编辑 18 步全部实现
- [ ] 固定值正确填充
- [ ] 随机值符合范围
- [ ] 计算值准确

---

## 下一步

完成 Day 5-7 后，继续 Week 2 的发布流程和集成测试。

---

**注意**：所有选择器都需要使用 `playwright codegen` 获取实际值，本文档中的选择器仅为占位符。
