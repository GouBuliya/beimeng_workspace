# 阶段1功能验证与测试指南

> 本指南帮助您验证和测试已实现的阶段1功能

## 📋 目录

1. [快速验证](#1-快速验证)
2. [使用Playwright Codegen](#2-使用playwright-codegen)
3. [实际页面测试](#3-实际页面测试)
4. [问题排查](#4-问题排查)

---

## 1. 快速验证

### 1.1 运行自动化验证脚本

```bash
cd apps/temu-auto-publish
python validate_stage1.py
```

**测试内容：**
- ✅ 图片管理器API（URL验证、格式检查）
- ✅ 重量/尺寸验证逻辑
- ✅ 工作流结构完整性

**预期输出：**
```
==========================================
验证总结
==========================================
总计通过: XX
总计失败: XX
成功率: XX.X%
```

**报告位置：** `data/output/stage1_validation_report.txt`

---

## 2. 使用Playwright Codegen

### 2.1 启动Codegen

```bash
cd apps/temu-auto-publish

# 方式1：直接启动
python -m playwright codegen https://erp.91miaoshou.com

# 方式2：使用已有cookie（推荐）
python -m playwright codegen --load-storage=data/temp/miaoshou_cookies.json https://erp.91miaoshou.com
```

### 2.2 录制操作获取选择器

#### 操作A：录制图片删除

1. **导航路径：**
   ```
   通用功能 → 产品采集 → 公用采集箱
   ```

2. **选择产品并打开编辑：**
   - 点击第一个产品的"编辑"按钮
   - 等待编辑弹窗打开

3. **切换到产品图片Tab：**
   - 点击"产品图片"标签

4. **删除图片操作：**
   - 将鼠标悬停在要删除的图片上
   - 记录删除按钮的选择器（通常是`×`图标）
   - 点击删除按钮
   - 如果有确认弹窗，记录确认按钮选择器

5. **记录的选择器示例：**
   ```python
   # 图片元素
   image_card = "div.image-card, .upload-list-item"
   
   # 删除按钮（悬停后显示）
   delete_btn = "button.el-icon-delete, .image-delete-btn"
   
   # 确认删除按钮
   confirm_delete = "button:has-text('确定'), button.el-button--primary"
   ```

#### 操作B：录制"使用网络图片"上传

1. **在产品图片Tab中：**
   - 找到上传区域

2. **点击上传并选择网络图片：**
   - 点击"上传图片"或"+"按钮
   - 选择"使用网络图片"选项
   - 记录URL输入框选择器
   - 记录确认按钮选择器

3. **记录的选择器示例：**
   ```python
   # 上传按钮
   upload_btn = "button:has-text('上传'), .upload-trigger"
   
   # 网络图片选项
   network_image_option = "text='使用网络图片', .menu-item:has-text('网络图片')"
   
   # URL输入框
   url_input = "input[placeholder*='图片链接'], input[placeholder*='URL']"
   
   # 确认上传
   confirm_upload = "button:has-text('确定'), button.el-button--primary"
   ```

#### 操作C：录制重量/尺寸设置

1. **在编辑弹窗中：**
   - 点击"物流信息"Tab

2. **找到重量输入框：**
   - 记录"包裹重量"输入框选择器

3. **找到尺寸输入框：**
   - 记录"包裹长度"输入框选择器
   - 记录"包裹宽度"输入框选择器
   - 记录"包裹高度"输入框选择器

4. **记录的选择器示例：**
   ```python
   # 物流信息Tab
   logistics_tab = "text='物流信息', .tab-pane:has-text('物流信息')"
   
   # 重量输入框
   weight_input = "input[placeholder*='包裹重量']"
   
   # 尺寸输入框
   length_input = "input[placeholder*='包裹长度'], input[placeholder*='长']"
   width_input = "input[placeholder*='包裹宽度'], input[placeholder*='宽']"
   height_input = "input[placeholder*='包裹高度'], input[placeholder*='高']"
   ```

### 2.3 更新选择器配置

将录制的选择器更新到配置文件：

**文件：** `config/miaoshou_selectors_v2.json`

```json
{
  "first_edit_dialog": {
    "product_images": {
      "image_card": "div.image-card",
      "delete_btn": "button.el-icon-delete",
      "confirm_delete": "button:has-text('确定')",
      "upload_btn": "button:has-text('上传')",
      "network_image_option": "text='使用网络图片'",
      "url_input": "input[placeholder*='图片链接']",
      "confirm_upload": "button:has-text('确定')"
    },
    "logistics_info": {
      "package_weight": "input[placeholder*='包裹重量']",
      "package_length": "input[placeholder*='包裹长度']",
      "package_width": "input[placeholder*='包裹宽度']",
      "package_height": "input[placeholder*='包裹高度']"
    }
  }
}
```

---

## 3. 实际页面测试

### 3.1 测试图片管理

创建测试脚本：`test_image_manager_live.py`

```python
import asyncio
from playwright.async_api import async_playwright
from src.browser.browser_manager import BrowserManager
from src.browser.login_controller import LoginController
from src.browser.miaoshou_controller import MiaoshouController
from src.browser.first_edit_controller import FirstEditController
from src.browser.image_manager import ImageManager

async def test_image_upload():
    """测试图片上传功能."""
    async with async_playwright() as p:
        browser_manager = BrowserManager()
        await browser_manager.start(p, headless=False)
        page = browser_manager.page
        
        # 登录
        login_ctrl = LoginController()
        await login_ctrl.login_with_cookies(page)
        
        # 导航到采集箱
        miaoshou_ctrl = MiaoshouController()
        await miaoshou_ctrl.navigate_to_collection_box(page)
        
        # 打开第一个产品编辑
        await miaoshou_ctrl.click_edit_product_by_index(page, 0)
        
        # 测试图片上传
        image_manager = ImageManager()
        test_url = "https://example.com/test-image.jpg"
        
        success = await image_manager.upload_image_from_url(
            page,
            test_url,
            "size_chart"
        )
        
        print(f"图片上传测试: {'✓ 成功' if success else '✗ 失败'}")
        
        await browser_manager.stop()

if __name__ == "__main__":
    asyncio.run(test_image_upload())
```

**运行测试：**
```bash
python test_image_manager_live.py
```

### 3.2 测试重量/尺寸设置

创建测试脚本：`test_weight_dimensions_live.py`

```python
import asyncio
from playwright.async_api import async_playwright
from src.browser.browser_manager import BrowserManager
from src.browser.login_controller import LoginController
from src.browser.miaoshou_controller import MiaoshouController
from src.browser.first_edit_controller import FirstEditController

async def test_weight_dimensions():
    """测试重量/尺寸设置功能."""
    async with async_playwright() as p:
        browser_manager = BrowserManager()
        await browser_manager.start(p, headless=False)
        page = browser_manager.page
        
        # 登录
        login_ctrl = LoginController()
        await login_ctrl.login_with_cookies(page)
        
        # 导航到采集箱
        miaoshou_ctrl = MiaoshouController()
        await miaoshou_ctrl.navigate_to_collection_box(page)
        
        # 打开第一个产品编辑
        await miaoshou_ctrl.click_edit_product_by_index(page, 0)
        
        # 测试重量设置
        first_edit_ctrl = FirstEditController()
        weight_success = await first_edit_ctrl.set_package_weight_in_logistics(
            page,
            7500  # 7500G
        )
        
        print(f"重量设置测试: {'✓ 成功' if weight_success else '✗ 失败'}")
        
        # 测试尺寸设置
        dimensions_success = await first_edit_ctrl.set_package_dimensions_in_logistics(
            page,
            89,  # 长
            64,  # 宽
            32   # 高
        )
        
        print(f"尺寸设置测试: {'✓ 成功' if dimensions_success else '✗ 失败'}")
        
        await browser_manager.stop()

if __name__ == "__main__":
    asyncio.run(test_weight_dimensions())
```

**运行测试：**
```bash
python test_weight_dimensions_live.py
```

### 3.3 测试完整认领流程

创建测试脚本：`test_claim_workflow_live.py`

```python
import asyncio
from playwright.async_api import async_playwright
from src.browser.browser_manager import BrowserManager
from src.browser.login_controller import LoginController
from src.browser.miaoshou_controller import MiaoshouController
from src.workflows.five_to_twenty_workflow import FiveToTwentyWorkflow

async def test_claim_workflow():
    """测试5→20认领流程."""
    async with async_playwright() as p:
        browser_manager = BrowserManager()
        await browser_manager.start(p, headless=False)
        page = browser_manager.page
        
        # 登录
        login_ctrl = LoginController()
        await login_ctrl.login_with_cookies(page)
        
        # 导航到采集箱
        miaoshou_ctrl = MiaoshouController()
        await miaoshou_ctrl.navigate_to_collection_box(page)
        await miaoshou_ctrl.filter_by_staff(page, "你的名字")
        await miaoshou_ctrl.switch_tab(page, "all")
        
        # 准备测试数据（5个产品）
        products_data = [
            {
                "keyword": "测试商品",
                "model_number": f"A{str(i+1).zfill(4)}",
                "cost": 10.0 + i,
                "stock": 100
            }
            for i in range(5)
        ]
        
        # 执行5→20工作流
        workflow = FiveToTwentyWorkflow(use_ai_titles=False)
        result = await workflow.execute(page, products_data, claim_times=4)
        
        print("\n" + "=" * 60)
        print("工作流测试结果:")
        print("=" * 60)
        print(f"编辑成功: {result['edited_count']}/5")
        print(f"认领成功: {result['claimed_count']}/{result['edited_count']}")
        print(f"最终产品数: {result['final_count']} (期望: 20)")
        print(f"执行结果: {'✓ 成功' if result['success'] else '✗ 失败'}")
        
        if result['errors']:
            print("\n错误列表:")
            for error in result['errors']:
                print(f"  - {error}")
        
        await browser_manager.stop()

if __name__ == "__main__":
    asyncio.run(test_claim_workflow())
```

**运行测试：**
```bash
python test_claim_workflow_live.py
```

---

## 4. 问题排查

### 4.1 常见问题

#### 问题1：选择器未找到元素

**症状：**
```
未找到包裹重量输入框（物流信息Tab）
提示：需要使用 Playwright Codegen 录制实际操作获取准确选择器
```

**解决方法：**
1. 使用Codegen录制实际操作
2. 找到正确的选择器
3. 更新 `config/miaoshou_selectors_v2.json`

#### 问题2：图片上传失败

**症状：**
```
上传图片功能需要Codegen验证选择器
```

**解决方法：**
1. 使用Codegen录制"使用网络图片"操作
2. 记录所有相关选择器：
   - 上传按钮
   - 网络图片选项
   - URL输入框
   - 确认按钮
3. 更新 `image_manager.py` 中的选择器

#### 问题3：页面加载超时

**症状：**
```
TimeoutError: Waiting for selector timed out
```

**解决方法：**
1. 增加等待时间：
   ```python
   await page.wait_for_timeout(2000)  # 等待2秒
   ```

2. 使用智能等待：
   ```python
   await page.wait_for_selector(selector, state="visible", timeout=10000)
   ```

### 4.2 调试技巧

#### 开启详细日志

在脚本开头添加：
```python
import logging
from loguru import logger

logger.add("debug.log", level="DEBUG")
```

#### 保存页面截图

```python
# 在关键步骤后截图
await page.screenshot(path=f"data/debug/step_{step_number}.png")
```

#### 开启慢动作模式

```python
browser_manager = BrowserManager()
await browser_manager.start(p, headless=False, slow_mo=500)  # 每步延迟500ms
```

### 4.3 验证检查清单

#### 图片管理器
- [ ] URL验证功能正常
- [ ] 图片格式检查正确
- [ ] 视频格式检查正确
- [ ] 删除图片选择器已验证
- [ ] 上传图片选择器已验证
- [ ] 错误处理和重试正常

#### 重量/尺寸设置
- [ ] 物流信息Tab可以切换
- [ ] 重量输入框可以找到
- [ ] 尺寸输入框可以找到
- [ ] 重量范围验证（5000-9999G）
- [ ] 尺寸范围验证（50-99cm）
- [ ] 长>宽>高规则验证

#### 认领流程
- [ ] 5个产品循环编辑正常
- [ ] 每个产品认领4次正常
- [ ] 最终生成20条产品
- [ ] AI标题生成可用（可选）
- [ ] 错误处理和日志完整

---

## 5. 下一步行动

### 5.1 验证完成后

如果所有测试通过：
```bash
# 提交验证结果
git add -A
git commit -m "test: 阶段1功能验证通过"
```

### 5.2 发现问题时

1. **记录问题：**
   - 截图保存到 `data/debug/`
   - 记录错误日志
   - 记录复现步骤

2. **更新选择器：**
   - 使用Codegen获取正确选择器
   - 更新配置文件
   - 重新测试

3. **报告问题：**
   - 创建详细的问题报告
   - 包含截图和日志
   - 说明预期行为和实际行为

---

## 📞 需要帮助？

如果在验证过程中遇到问题：

1. 查看 `data/logs/` 中的日志文件
2. 查看 `data/debug/` 中的截图
3. 参考 `STAGE1_COMPLETION_REPORT.md`
4. 联系开发团队

---

**文档版本：** 1.0  
**更新日期：** 2025-10-30  
**适用阶段：** 阶段1（40% → 70%）

