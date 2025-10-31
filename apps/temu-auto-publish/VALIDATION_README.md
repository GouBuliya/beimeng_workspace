# 阶段1功能验证工具包

## 📦 包含文件

1. **validate_stage1.py** - 自动化验证脚本（无需实际页面）
2. **test_weight_dimensions_live.py** - 重量/尺寸实际页面测试
3. **VALIDATION_GUIDE.md** - 完整验证指南

## 🚀 快速开始

### 步骤1：运行自动化验证

```bash
cd /Users/candy/beimeng_workspace/apps/temu-auto-publish
python validate_stage1.py
```

**测试内容：**
- ✅ 图片管理器API
- ✅ 重量/尺寸验证逻辑
- ✅ 工作流结构

**输出：** `data/output/stage1_validation_report.txt`

### 步骤2：实际页面测试（可选）

```bash
# 测试重量/尺寸设置
python test_weight_dimensions_live.py
```

**前提条件：**
- 已登录妙手ERP（cookie存在）
- 采集箱中有可编辑的产品

### 步骤3：使用Codegen验证选择器

```bash
# 启动Playwright Codegen
python -m playwright codegen https://erp.91miaoshou.com

# 或使用已有cookie
python -m playwright codegen --load-storage=data/temp/miaoshou_cookies.json https://erp.91miaoshou.com
```

## 📋 验证检查清单

### 图片管理器
- [ ] URL验证正常
- [ ] 图片格式检查正确
- [ ] 视频格式检查正确
- [ ] 删除图片选择器已录制
- [ ] 上传图片选择器已录制

### 重量/尺寸设置
- [ ] 物流信息Tab可切换
- [ ] 重量输入框可定位
- [ ] 尺寸输入框可定位
- [ ] 重量范围验证（5000-9999G）
- [ ] 尺寸规则验证（长>宽>高）

### 认领流程
- [ ] 5个产品循环编辑
- [ ] 每个产品认领4次
- [ ] 验证20条产品生成

## 📖 详细文档

查看 **VALIDATION_GUIDE.md** 获取：
- 完整的测试步骤
- Codegen使用指南
- 问题排查方法
- 调试技巧

## ⚠️ 注意事项

1. **自动化验证**可以离线运行，测试逻辑和API
2. **实际页面测试**需要登录和实际数据
3. 如果测试失败，使用**Codegen**验证选择器
4. 更新选择器后，重新运行测试

## 🔧 常见问题

### Q: 验证脚本报错
A: 检查依赖是否安装：`pip install playwright loguru`

### Q: 实际测试无法登录
A: 确保cookie文件存在：`data/temp/miaoshou_cookies.json`

### Q: 选择器未找到元素
A: 使用Codegen重新录制选择器

## 📞 需要帮助？

查看日志文件：
- 主日志：`data/logs/`
- 调试截图：`data/debug/`
- 验证报告：`data/output/stage1_validation_report.txt`

---

**工具版本：** 1.0  
**创建日期：** 2025-10-30  
**适用阶段：** 阶段1验证

