# 快速开始指南

> 妙手ERP商品发布自动化系统 - 5分钟快速上手

## 📋 前置要求

### 1. 系统要求
- Python 3.12+
- macOS / Linux / Windows
- 稳定的网络连接

### 2. 账号准备
- 妙手ERP账号和密码
- 阿里云DashScope API Key (用于AI标题生成)

## 🚀 快速开始

### 步骤1: 安装依赖

```bash
cd /Users/candy/beimeng_workspace

# 安装项目依赖
uv sync --extra temu --extra dev

# 安装Playwright浏览器
uv run playwright install chromium
```

### 步骤2: 配置环境

创建 `.env` 文件：

```bash
cd apps/temu-auto-publish
cp .env.example .env
vim .env
```

填写配置：

```env
# 妙手ERP账号配置
MIAOSHOU_URL=https://erp.91miaoshou.com/sub_account/users
MIAOSHOU_USERNAME=你的用户名
MIAOSHOU_PASSWORD=你的密码

# AI标题生成配置
DASHSCOPE_API_KEY=你的阿里云API_KEY
OPENAI_MODEL=qwen3-vl-plus
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

### 步骤3: 准备测试数据

确保妙手ERP的**公用采集箱**中有至少5个"未认领"的产品。

如果没有，可以手动添加一些测试商品到采集箱。

### 步骤4: 运行测试

```bash
cd apps/temu-auto-publish
python3 run_real_test.py
```

测试将自动执行：
1. ✅ 登录妙手ERP（使用Cookie智能登录）
2. ✅ 导航到公用采集箱
3. ✅ 首次编辑5个产品：
   - AI生成优化标题
   - 核对商品类目
   - 设置价格和库存
   - 设置重量和尺寸
4. ✅ 每个产品认领4次（共20个产品）
5. ✅ 验证认领成功

**预计用时**: 3-5分钟

## 📊 测试结果

成功运行后，您应该看到：

```
================================================================================
📊 测试结果
================================================================================
✅ 测试通过！5→20认领流程执行成功

执行内容：
  ✓ 首次编辑了5条商品
  ✓ 每条商品认领了4次
  ✓ 总计生成20条待编辑商品

验证项：
  ✓ AI标题生成：已应用
  ✓ 图片管理：已处理
  ✓ 重量设置：已设置
  ✓ 尺寸设置：已设置
  ✓ 认领流程：已完成
```

## 🎯 核心功能演示

### AI标题生成

脚本会自动调用AI模型优化产品标题：

```
原标题: 360度旋转衣架收纳架
AI生成: 360度旋转不锈钢衣架带6杆落地收纳架 附鞋架 易装省空间 卧室玄关衣柜适用 A0001型号
```

### 类目核对

自动检查商品类目是否合规：
- ✅ 合规类目：家居用品、收纳整理等
- ❌ 不合规类目：药品、医疗器械、电子产品等

### 智能价格计算

自动计算建议售价和供货价：
```
成本价: ¥150
建议售价: ¥1500 (成本 × 10)
供货价: ¥1125 (成本 × 7.5)
```

## 🔧 故障排查

### Q: 登录失败？

**原因**: 账号密码错误或Cookie过期

**解决方案**:
```bash
# 1. 检查.env中的账号密码
cat apps/temu-auto-publish/.env

# 2. 删除旧的Cookie重新登录
rm apps/temu-auto-publish/data/cookies/miaoshou_cookies.json

# 3. 重新运行测试
python3 run_real_test.py
```

### Q: AI标题生成失败？

**原因**: API Key无效或余额不足

**解决方案**:
```bash
# 1. 检查API Key配置
grep DASHSCOPE_API_KEY apps/temu-auto-publish/.env

# 2. 测试API Key是否有效
# 访问阿里云DashScope控制台检查额度

# 3. 如果暂时不需要AI生成，可以关闭
# 在.env中删除或注释DASHSCOPE_API_KEY
```

### Q: 找不到产品？

**原因**: 公用采集箱中没有"未认领"的产品

**解决方案**:
1. 登录妙手ERP
2. 进入"通用功能 → 产品采集 → 公用采集箱"
3. 切换到"未认领"tab
4. 确保至少有5个产品

### Q: 元素定位失败？

**原因**: 妙手ERP界面更新，选择器失效

**解决方案**:
```bash
# 使用Playwright Codegen重新录制选择器
uv run playwright codegen https://erp.91miaoshou.com

# 更新选择器配置
vim apps/temu-auto-publish/config/miaoshou_selectors_v2.json
```

## 📚 下一步

### 查看详细文档

- [README.md](README.md) - 完整项目文档
- [AI标题生成文档](docs/AI_TITLE_GENERATION.md)
- [调试指南](docs/DEBUG_GUIDE.md)
- [商品发布SOP](../../docs/projects/temu-auto-publish/guides/商品发布SOP-IT专用.md)

### 探索其他功能

- **批量编辑18步** - 二次编辑流程（开发中）
- **多店铺发布** - 批量发布功能（开发中）
- **完整采集流程** - 站内搜索和采集（计划中）

### 参与开发

遵循工程化规范：
```bash
# 代码格式化
uv run ruff format apps/temu-auto-publish

# Lint检查
uv run ruff check apps/temu-auto-publish --fix

# 类型检查
uv run mypy apps/temu-auto-publish
```

## 💡 提示

1. **首次运行建议使用非headless模式**，可以观察自动化过程
2. **Cookie会自动保存**，第二次运行会更快
3. **AI标题生成需要时间**，平均每个标题1.5秒
4. **保持网络畅通**，整个流程需要稳定的网络连接
5. **遇到问题查看日志**：`tail -f data/logs/temu_automation.log`

---

**🎉 恭喜！您已成功运行妙手ERP自动化系统！**

如有问题，请参考详细文档或提交Issue。
