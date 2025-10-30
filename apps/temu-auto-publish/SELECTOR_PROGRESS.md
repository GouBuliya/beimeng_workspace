# 妙手ERP选择器获取进度

## ✅ 已完成

### 1. 登录页面
- URL: `https://erp.91miaoshou.com/sub_account/users`
- 用户名输入框: `aria-ref=e32`
- 密码输入框: `aria-ref=e35`
- 登录按钮: `aria-ref=e38`

### 2. 首页
- URL: `https://erp.91miaoshou.com/welcome`
- 产品菜单: `aria-ref=e11`
- 产品采集快捷入口: `aria-ref=e298`
- 待发布产品数量: `aria-ref=e87` (显示36165)

### 3. 产品采集页面
- URL: `https://erp.91miaoshou.com/common_collect_box/index`
- 链接采集tab(已选中): `aria-ref=e578`
- 链接输入框: `aria-ref=e617`
- 采集优化按钮: `aria-ref=e602`
- 采集设置按钮: `aria-ref=e607`
- 自动认领checkbox: `aria-ref=e751`
- 已选平台按钮: `aria-ref=e758`
- 采集并自动认领按钮: `aria-ref=e760`
- 采集并自动发布按钮: `aria-ref=e762`

### 4. 侧边菜单
- 通用功能菜单: `aria-ref=e524`
- 产品采集: `aria-ref=e529`
- 公用采集箱: `aria-ref=e530`

##  ⏳ 待探索

### 5. 公用采集箱页面（SOP核心）
- [ ] 采集箱列表
- [ ] 产品认领按钮
- [ ] 首次编辑入口
- [ ] 批量编辑入口

### 6. 首次编辑页面
- [ ] 标题编辑框
- [ ] 类目选择
- [ ] 图片上传
- [ ] 保存按钮

### 7. 批量编辑页面
- [ ] 全选checkbox
- [ ] 批量编辑18步的所有输入框

## 📊 完成度

- [█████░░░░░] 50% 已登录并进入产品采集
- [███░░░░░░░] 30% 选择器获取
- [░░░░░░░░░░]  0% 代码集成测试

## 🔍 关键发现

1. **妙手ERP使用动态aria-ref**：所有元素使用`aria-ref`定位，格式为`e[数字]`
2. **URL结构清晰**：
   - 登录：`/sub_account/users`
   - 首页：`/welcome`
   - 产品采集：`/common_collect_box/index`
   - 公用采集箱：`/common_collect_box/items`
3. **SOP对应页面**：公用采集箱 = SOP中的"妙手公共采集箱"

## 📝 下一步行动

1. ✅ 点击"公用采集箱"菜单
2. ✅ 获取采集箱页面的选择器
3. ✅ 探索认领和编辑功能
4. ✅ 完成所有选择器收集
5. ✅ 更新到 miaoshou_selectors.json

