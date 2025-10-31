# 快速开始指南

## 运行演示脚本

### 前置要求

1. **设置登录凭证**（必须）

```bash
export MIAOSHOU_USERNAME="你的妙手ERP用户名"
export MIAOSHOU_PASSWORD="你的妙手ERP密码"
```

或者在 `~/.zshrc` 或 `~/.bashrc` 中永久设置：

```bash
# 添加到 ~/.zshrc
echo 'export MIAOSHOU_USERNAME="你的用户名"' >> ~/.zshrc
echo 'export MIAOSHOU_PASSWORD="你的密码"' >> ~/.zshrc
source ~/.zshrc
```

2. **准备测试数据**

确保妙手ERP的公用采集箱中有至少5个"未认领"的产品。

### 运行演示

```bash
cd /Users/candy/beimeng_workspace/apps/temu-auto-publish

# 运行演示脚本
python demo_quick_workflow.py

# 选择演示模式：
# 1 - 演示5→20工作流（推荐首次测试）
# 2 - 演示完整工作流（包含批量编辑，不包含发布）
```

### 演示模式说明

#### 模式1：5→20工作流
- ✅ 演示首次编辑5个产品
- ✅ 演示每个产品认领4次
- ✅ 验证最终生成20条产品
- ⏱️  预计用时：3-5分钟

#### 模式2：完整工作流
- ✅ 执行5→20工作流
- ⚠️  尝试批量编辑（可能因选择器缺失而失败）
- ⏭️  跳过发布（演示模式）
- ⏱️  预计用时：5-10分钟

---

## 运行测试

### 数据验证测试（无需登录）

```bash
pytest tests/test_complete_workflow.py::test_workflow_data_validation -v
```

### 5→20工作流测试（需要登录）

```bash
# 设置环境变量后运行
export MIAOSHOU_USERNAME="你的用户名"
export MIAOSHOU_PASSWORD="你的密码"

pytest tests/test_complete_workflow.py::test_five_to_twenty_workflow_only -v -s
```

### 完整工作流测试（需要登录）

```bash
pytest tests/test_complete_workflow.py::test_complete_workflow_without_publish -v -s
```

---

## 常见问题

### 1. 登录失败

**症状：** `✗ 登录失败`

**解决方案：**
- 检查用户名和密码是否正确
- 确认环境变量已正确设置：`echo $MIAOSHOU_USERNAME`
- 查看错误截图：`data/temp/screenshots/login_error_*.png`

### 2. 产品数量不足

**症状：** `产品数量不足，当前只有X个产品`

**解决方案：**
- 在妙手ERP中手动采集至少5个产品到公用采集箱
- 确保切换到"未认领"tab有至少5个产品

### 3. 批量编辑失败

**症状：** `批量编辑步骤执行失败`

**原因：** 部分选择器尚未获取（需要使用Playwright Codegen）

**解决方案：**
- 这是预期的行为
- 5→20工作流仍然可以正常运行
- 参考 `QUICK_WORKFLOW_SUMMARY.md` 中的"待完成工作"部分

### 4. 认领失败

**症状：** `认领产品失败`

**可能原因：**
- 产品已被认领
- 认领按钮选择器错误
- 网络延迟

**解决方案：**
- 刷新页面，确保产品在"未认领"tab中
- 检查日志输出，查找具体错误信息

---

## 下一步

查看详细的实施总结：
```bash
cat QUICK_WORKFLOW_SUMMARY.md
```

查看待办事项和选择器获取方法。

---

**文档更新：** 2025-10-30

