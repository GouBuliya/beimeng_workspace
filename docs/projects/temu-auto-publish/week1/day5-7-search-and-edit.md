# Day 5-7：搜索采集和首次编辑

**目标**：完成站内搜索、链接采集和首次编辑流程

---

## Day 5：站内搜索和链接采集

### 上午任务（3-4小时）

#### 5.1 录制搜索流程

**流程设计**：
```
读取关键词 → 进入搜索页 → 输入关键词 → 点击搜索 → 等待结果
```

##### 创建影刀流程："Temu站内搜索采集"
- [ ] 创建流程，配置输入参数：
  - `keyword`: 搜索关键词
  - `collect_count`: 采集数量（默认 5）
- [ ] 配置输出参数：
  - `product_links`: 产品链接列表
  - `status`: 执行状态

##### 录制步骤
1. **导航到搜索页**
   - [ ] 录制：从后台首页进入搜索功能
   - [ ] 记录 URL 路径

2. **输入搜索关键词**
   - [ ] 定位搜索输入框
   - [ ] 输入 `${keyword}`
   - [ ] 点击搜索按钮
   - [ ] 等待结果加载（3-5秒）

3. **采集产品链接**
   - [ ] 定位产品列表
   - [ ] 循环提取链接（共 `${collect_count}` 个）
   - [ ] 保存到数组 `product_links`

#### 任务清单
- [ ] 录制完整搜索流程
- [ ] 测试不同关键词（至少3个）
- [ ] 处理无结果情况
- [ ] **验证标准**：能稳定采集到指定数量的链接

### 下午任务（3-4小时）

#### 5.2 链接提取优化

##### 商品筛选逻辑
- [ ] 研究商品列表结构
- [ ] 确定筛选条件：
  - 价格范围
  - 销量要求
  - 评分要求
- [ ] 在影刀中实现筛选

##### 去重处理
- [ ] 检查采集的链接是否有重复
- [ ] 添加去重逻辑

##### 数据输出
创建输出格式：
```json
{
  "keyword": "智能手表",
  "collected_at": "2025-10-29T14:30:00",
  "links": [
    {
      "url": "https://...",
      "title": "商品标题",
      "price": "199.00",
      "sales": "1000+"
    }
  ],
  "count": 5
}
```

#### 5.3 Python 集成

创建 `src/yingdao/search_controller.py`：

```python
"""搜索采集控制器"""

from typing import List, Dict
from loguru import logger


class SearchController:
    """搜索采集控制器"""
    
    def search_and_collect(
        self,
        keyword: str,
        collect_count: int = 5
    ) -> List[Dict]:
        """搜索并采集商品链接
        
        Args:
            keyword: 搜索关键词
            collect_count: 采集数量
        
        Returns:
            商品信息列表
        """
        logger.info(f"开始搜索: {keyword}, 目标数量: {collect_count}")
        
        # 调用影刀流程
        result = self.call_yingdao("Temu站内搜索采集", {
            "keyword": keyword,
            "collect_count": collect_count
        })
        
        links = result.get("product_links", [])
        logger.success(f"采集完成: {len(links)} 个链接")
        
        return links
```

- [ ] 实现 `search_controller.py`
- [ ] 测试完整流程
- [ ] **验证标准**：Python 能调用影刀完成搜索和采集

---

## Day 6-7：首次编辑流程

### Day 6 上午：认领商品（3-4小时）

#### 6.1 认领流程设计

**流程**：
```
打开采集的链接 → 点击认领 → 确认认领 → 重复4次（5条变20条）
```

##### 创建影刀流程："商品认领"
- [ ] 输入参数：`product_links`（链接列表）
- [ ] 输出参数：`claimed_ids`（认领成功的商品 ID）

##### 录制步骤
1. **循环处理每个链接**
   ```
   对于 product_links 中的每个 link:
     打开 link
     等待页面加载
     检查是否可认领
     如果可以：
       点击认领按钮 4次
       记录商品 ID
   ```

2. **异常处理**
   - [ ] 商品已被认领
   - [ ] 认领次数限制
   - [ ] 页面加载失败

#### 任务清单
- [ ] 录制认领流程
- [ ] 处理异常情况
- [ ] 测试至少 3 个商品
- [ ] **验证标准**：5 条变 20 条成功

### Day 6 下午：标题和类目编辑（3-4小时）

#### 6.2 标题编辑

##### 流程设计
1. **修改中文标题**
   - [ ] 定位标题输入框
   - [ ] 清空现有标题
   - [ ] 输入新标题（从 JSON 读取）
   - [ ] 保存

2. **触发英文标题生成**
   - [ ] 按空格键触发
   - [ ] 等待 AI 生成
   - [ ] 检查生成结果

##### 影刀实现
```
对于每个商品:
  打开编辑页
  
  // 修改标题
  清空 "中文标题" 输入框
  输入 ${ai_title}
  按 Space 键
  等待 3秒（AI 生成英文标题）
  
  // 验证
  检查英文标题是否已生成
```

#### 6.3 类目编辑

##### 类目核对
- [ ] 对比采集链接的类目
- [ ] 在编辑页面修改类目
- [ ] 处理类目树（多级选择）

##### 难点处理
- **类目树很深**：需要逐级展开
- **类目名称模糊匹配**：可能需要人工确认

#### 任务清单
- [ ] 实现标题编辑
- [ ] 实现类目编辑
- [ ] 测试各种类目深度
- [ ] **验证标准**：标题和类目修改成功

---

### Day 7：图片和保存（全天）

#### 7.1 图片处理（MVP 简化版）

**MVP 方案**：人工验证 + 脚本辅助
- [ ] 影刀截图保存轮播图
- [ ] Python 显示图片供人工确认
- [ ] 确认后影刀执行图片替换（如需要）

```python
# 图片确认脚本
def confirm_images(product_id: str) -> bool:
    """人工确认图片
    
    Returns:
        True 如果图片OK
    """
    image_dir = Path(f"data/temp/images/{product_id}")
    
    print(f"\n请确认商品 {product_id} 的图片:")
    for img in image_dir.glob("*.png"):
        print(f"  {img.name}")
    
    response = input("图片是否OK? (y/n): ")
    return response.lower() == 'y'
```

#### 7.2 保存和验证

##### 影刀流程
```
// 保存商品
点击 "保存" 按钮
等待保存完成

// 验证保存结果
if 出现 "保存成功" 提示:
  记录成功
  截图保存
else:
  记录失败原因
  截图保存
```

#### 7.3 批量处理整合

创建完整的首次编辑流程：

```python
def batch_first_edit(products: List[Dict]) -> List[Dict]:
    """批量首次编辑
    
    Args:
        products: 产品列表（包含采集的链接）
    
    Returns:
        编辑结果列表
    """
    results = []
    
    for idx, product in enumerate(products, 1):
        logger.info(f"\n处理 {idx}/{len(products)}: {product['keyword']}")
        
        try:
            # 1. 认领
            logger.info("  1. 认领商品...")
            claimed_ids = claim_products(product['links'])
            
            # 2. 编辑标题和类目
            logger.info("  2. 编辑标题和类目...")
            edit_title_and_category(
                claimed_ids,
                ai_title=product['ai_title'],
                category=product['category']
            )
            
            # 3. 图片确认
            logger.info("  3. 确认图片...")
            if confirm_images(claimed_ids[0]):
                logger.success("    图片OK")
            else:
                logger.warning("    需要人工处理图片")
            
            # 4. 保存
            logger.info("  4. 保存...")
            save_result = save_products(claimed_ids)
            
            results.append({
                "product_id": product['id'],
                "status": "success",
                "claimed_count": len(claimed_ids),
                "details": save_result
            })
            
            logger.success(f"  ✓ 完成")
            
        except Exception as e:
            logger.error(f"  ✗ 失败: {e}")
            results.append({
                "product_id": product['id'],
                "status": "failed",
                "error": str(e)
            })
    
    return results
```

#### 任务清单
- [ ] 实现图片确认流程（MVP版）
- [ ] 实现保存和验证
- [ ] 整合完整的首次编辑流程
- [ ] 端到端测试（至少 2 个完整产品）
- [ ] **验证标准**：能完成从认领到保存的全流程

---

## Day 5-7 交付物

### 必须完成 ✅
1. 站内搜索和链接采集（影刀流程 + Python 控制）
2. 商品认领流程（5条变20条）
3. 标题和类目编辑
4. 图片确认机制（MVP 版本）
5. 保存和结果验证
6. 完整的首次编辑流程

### 测试数据 📋
```
测试产品：
  - 产品A：简单类目（如电子产品）
  - 产品B：复杂类目（多级分类）
  - 产品C：特殊情况（如无货源）

预期结果：
  - 搜索成功率：>90%
  - 认领成功率：>80%
  - 编辑保存成功率：>70%
```

### 文件清单 📁
```
src/yingdao/
  ├── search_controller.py
  ├── edit_controller.py
  └── __init__.py

影刀流程/
  ├── Temu站内搜索采集.flow
  ├── 商品认领.flow
  ├── 标题类目编辑.flow
  └── 首次编辑完整流程.flow

data/temp/
  ├── search_results/
  ├── images/
  └── edit_logs/
```

---

## Week 1 总验收

### 验收标准 ✅
完成 Day 7 后，应该能够：

1. **自动化程度**
   - [ ] Excel → JSON 自动转换
   - [ ] 登录自动化（Cookie 复用）
   - [ ] 搜索采集自动化
   - [ ] 认领编辑半自动化（图片需要人工确认）

2. **稳定性**
   - [ ] 连续处理 3 个产品无崩溃
   - [ ] 异常情况有清晰日志
   - [ ] 失败能继续处理下一个

3. **数据完整性**
   - [ ] 所有步骤有日志记录
   - [ ] 结果数据格式正确
   - [ ] 失败原因能追溯

### 下一步
完成第一周后，继续 [第二周：批量编辑和发布](../week2/index.md)

---

## 常见问题

### 搜索结果不稳定
- **现象**：每次搜索结果不同
- **解决**：添加筛选条件（销量、评分），固定排序方式

### 认领失败
- **现象**：点击认领无反应
- **解决**：检查是否已达认领上限，增加等待时间

### 图片处理太慢
- **现象**：人工确认效率低
- **解决**：
  - MVP 阶段：批量确认
  - 优化：接入图像识别 API

### 类目选择困难
- **现象**：类目树太复杂
- **解决**：
  - 参考采集商品的类目
  - 建立常用类目映射表
  - 记录人工选择的类目供后续参考

---

**Week 1 完成！🎉**

