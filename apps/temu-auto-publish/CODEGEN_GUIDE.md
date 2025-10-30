# Playwright Codegen 使用指南

## 目标
使用 Playwright Codegen 获取妙手工具的所有页面选择器，用于自动化操作。

## 启动命令
```bash
cd /Users/candy/beimeng_workspace
uv run playwright codegen https://seller.temu.com
```

## 操作流程

### 1️⃣ 登录页面（5分钟）
**目标页面**：https://seller.temu.com/login

**需要获取的选择器**：
- [ ] 用户名输入框 (`username_input`)
- [ ] 密码输入框 (`password_input`)
- [ ] 登录按钮 (`login_button`)
- [ ] 验证码容器 (`captcha_container`)（如果有）

**操作步骤**：
1. 打开登录页面
2. 点击用户名输入框 → 复制生成的选择器
3. 点击密码输入框 → 复制生成的选择器
4. 点击登录按钮 → 复制生成的选择器
5. 完成登录

---

### 2️⃣ 卖家后台首页（5分钟）
**目标页面**：https://seller.temu.com

**需要获取的选择器**：
- [ ] 「一键访问店铺」按钮 (`store_front_button`)
- [ ] 用户信息区域 (`user_info`)

**操作步骤**：
1. 等待页面加载
2. 找到「一键访问店铺」按钮 → 复制选择器（不要点击）
3. 找到用户信息区域 → 复制选择器

---

### 3️⃣ 前端店铺 & 妙手采集箱（15分钟）
**目标页面**：前端店铺 → 妙手工具 → 采集箱

**需要获取的选择器**：
- [ ] 妙手采集箱URL（记录完整URL）
- [ ] 采集箱标题 (`collection_box_title`)
- [ ] 搜索输入框 (`search_input`)
- [ ] 「采集同款」按钮 (`collect_button`)
- [ ] 链接列表容器 (`link_list`)
- [ ] 单条链接项 (`link_item`)
- [ ] 「认领」按钮 (`claim_button`)
- [ ] 分页大小选择器 (`page_size_selector`)

**操作步骤**：
1. 点击「一键访问店铺」（进入前端）
2. 导航到妙手工具（记录URL路径）
3. 进入采集箱（记录完整URL）
4. 在搜索框输入关键词 → 复制选择器
5. 点击「采集同款」按钮 → 复制选择器
6. 查看链接列表 → 复制列表和单项选择器
7. 找到「认领」按钮 → 复制选择器
8. 找到分页大小下拉框 → 复制选择器

---

### 4️⃣ 首次编辑页面（20分钟）
**目标页面**：点击第一条链接的「编辑」按钮

**需要获取的选择器**：
- [ ] 编辑按钮 (`edit_button`)
- [ ] 主图上传控件 (`main_image_upload`)
- [ ] 视频上传控件 (`video_upload`)
- [ ] 中文标题输入框 (`title_cn_input`)
- [ ] 英文标题输入框 (`title_en_input`)
- [ ] 类目选择器 (`category_selector`)
- [ ] 建议售价输入框 (`price_input`)
- [ ] 详情图上传控件 (`detail_image_upload`)
- [ ] 保存按钮 (`save_button`)

**操作步骤**：
1. 返回采集箱
2. 点击第一条链接的「编辑」按钮 → 复制选择器
3. 依次点击各个输入框和控件 → 复制选择器
4. **不要实际保存**，只获取选择器

---

### 5️⃣ 批量编辑页面（30分钟）
**目标页面**：选中多条商品 → 批量编辑

**需要获取的选择器**：
- [ ] 全选复选框 (`select_all`)
- [ ] 批量编辑按钮 (`batch_edit_button`)
- [ ] 预览按钮 (`preview_button`)
- [ ] 保存按钮 (`save_button`)

**18步流程选择器**：
- [ ] 步骤1：标题输入框 (`step_01_title`)
- [ ] 步骤2：英文标题输入框 (`step_02_english_title`)
- [ ] 步骤3：类目属性选择器 (`step_03_category_attrs`)
- [ ] 步骤5：包装形状选择器 (`step_05_packaging_shape`)
- [ ] 步骤5：包装类型选择器 (`step_05_packaging_type`)
- [ ] 步骤6：产地选择器 (`step_06_origin`)
- [ ] 步骤9：重量输入框 (`step_09_weight`)
- [ ] 步骤10：长度输入框 (`step_10_length`)
- [ ] 步骤10：宽度输入框 (`step_10_width`)
- [ ] 步骤10：高度输入框 (`step_10_height`)
- [ ] 步骤11：SKU输入框 (`step_11_sku`)
- [ ] 步骤12：SKU类目选择器 (`step_12_sku_category`)
- [ ] 步骤14：建议售价输入框 (`step_14_suggested_price`)
- [ ] 步骤18：手动上传按钮 (`step_18_manual_upload`)

**操作步骤**：
1. 返回采集箱
2. 点击全选复选框 → 复制选择器
3. 点击「批量编辑」按钮 → 复制选择器
4. 依次找到18步中的每个输入框和选择器
5. 复制所有选择器
6. **不要实际保存**

---

### 6️⃣ 发布页面（10分钟）
**目标页面**：批量编辑完成后的发布页面

**需要获取的选择器**：
- [ ] 店铺选择下拉框 (`shop_select`)
- [ ] 供货价输入框 (`supply_price_input`)
- [ ] 发布按钮 (`publish_button`)
- [ ] 确认按钮 (`confirm_button`)
- [ ] 发布结果提示 (`publish_result`)

**操作步骤**：
1. 假设已到发布页面
2. 依次点击各个控件 → 复制选择器
3. **不要实际发布**

---

## 📝 记录格式

将获取到的选择器记录到这里（或直接更新到 `config/miaoshou_selectors.json`）：

### 登录页面
```json
"login": {
  "url": "https://seller.temu.com/login",
  "username_input": "【填写这里】",
  "password_input": "【填写这里】",
  "login_button": "【填写这里】",
  "captcha_container": "【填写这里】"
}
```

### 卖家后台
```json
"seller_backend": {
  "home_url": "https://seller.temu.com",
  "store_front_button": "【填写这里】",
  "user_info": "【填写这里】"
}
```

### 妙手采集箱
```json
"miaoshou": {
  "collection_box_url": "【填写这里】",
  "collection_box_title": "【填写这里】",
  "search_input": "【填写这里】",
  "collect_button": "【填写这里】",
  "link_list": "【填写这里】",
  "link_item": "【填写这里】",
  "claim_button": "【填写这里】",
  "page_size_selector": "【填写这里】"
}
```

### 首次编辑
```json
"first_edit": {
  "edit_button": "【填写这里】",
  "main_image_upload": "【填写这里】",
  "video_upload": "【填写这里】",
  "title_cn_input": "【填写这里】",
  "title_en_input": "【填写这里】",
  "category_selector": "【填写这里】",
  "price_input": "【填写这里】",
  "detail_image_upload": "【填写这里】",
  "save_button": "【填写这里】"
}
```

### 批量编辑
```json
"batch_edit": {
  "select_all": "【填写这里】",
  "batch_edit_button": "【填写这里】",
  "preview_button": "【填写这里】",
  "save_button": "【填写这里】",
  "steps": {
    "step_01_title": "【填写这里】",
    "step_02_english_title": "【填写这里】",
    "step_03_category_attrs": "【填写这里】",
    "step_05_packaging_shape": "【填写这里】",
    "step_05_packaging_type": "【填写这里】",
    "step_06_origin": "【填写这里】",
    "step_09_weight": "【填写这里】",
    "step_10_length": "【填写这里】",
    "step_10_width": "【填写这里】",
    "step_10_height": "【填写这里】",
    "step_11_sku": "【填写这里】",
    "step_12_sku_category": "【填写这里】",
    "step_14_suggested_price": "【填写这里】",
    "step_18_manual_upload": "【填写这里】"
  }
}
```

### 发布页面
```json
"publish": {
  "shop_select": "【填写这里】",
  "supply_price_input": "【填写这里】",
  "publish_button": "【填写这里】",
  "confirm_button": "【填写这里】",
  "publish_result": "【填写这里】"
}
```

---

## ⚡ 快速技巧

### 优先使用的选择器类型（按优先级）：
1. `data-testid` 属性（最稳定）
   ```
   [data-testid="login-button"]
   ```

2. `text` + `role` 组合（可读性好）
   ```
   button:has-text("登录")
   [role="button"]:has-text("保存")
   ```

3. `placeholder` 属性（输入框）
   ```
   input[placeholder="请输入用户名"]
   ```

4. CSS 类名（最后选择，可能变化）
   ```
   .btn-primary
   ```

### 复制选择器方法：
1. Codegen 自动生成的选择器会显示在右侧代码面板
2. 直接复制 `page.click("选择器")` 中的选择器部分
3. 去掉多余的引号和代码

---

## ✅ 完成后的操作

1. 将所有选择器更新到 `config/miaoshou_selectors.json`
2. 运行测试验证选择器有效性
3. 如有失效选择器，重新获取并更新

---

## 预计时间
- 总计：**约 90 分钟**
- 建议：分批完成，每次 20-30 分钟

---

## 注意事项
⚠️ **不要实际执行以下操作**：
- ❌ 不要实际保存商品编辑
- ❌ 不要实际发布商品
- ❌ 不要删除或修改现有商品
- ✅ 只获取选择器，不执行实际操作

---

## 完成标志
当你完成所有选择器获取后，请告诉我，我会帮你更新到配置文件并测试。

