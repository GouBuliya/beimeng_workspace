# 环境配置说明

## 📋 概述

本项目使用 `.env` 文件管理敏感配置信息（账号密码、API密钥等）。

---

## 🔧 配置步骤

### 1. 创建 `.env` 文件

在项目目录下创建 `.env` 文件：

```bash
cd /Users/candy/beimeng_workspace/apps/temu-auto-publish
touch .env
```

### 2. 配置内容

编辑 `.env` 文件，添加以下配置：

```bash
# Temu 店铺账号配置
TEMU_SHOP_URL=https://agentseller.temu.com/
TEMU_USERNAME=your_temu_username
TEMU_PASSWORD=your_temu_password

# 妙手ERP账号配置（主要工作平台）
MIAOSHOU_URL=https://erp.91miaoshou.com/sub_account/users
MIAOSHOU_USERNAME=your_miaoshou_username
MIAOSHOU_PASSWORD=your_miaoshou_password

# AI服务配置（可选）
# OpenAI API配置
# OPENAI_API_KEY=your_openai_api_key
# OPENAI_BASE_URL=https://api.openai.com/v1
# OPENAI_MODEL=gpt-4

# Anthropic API配置
# ANTHROPIC_API_KEY=your_anthropic_api_key
# ANTHROPIC_MODEL=claude-sonnet-4-20250514

# 其他配置
# DEBUG=false
# LOG_LEVEL=INFO
```

### 3. 替换占位符

将上述配置中的占位符替换为真实值：
- `your_miaoshou_username` → 真实的妙手ERP用户名
- `your_miaoshou_password` → 真实的妙手ERP密码
- 其他API密钥按需配置

---

## ✅ 当前配置状态

`.env` 文件当前包含以下配置：

```bash
# Temu 店铺账号配置
TEMU_SHOP_URL=https://agentseller.temu.com/
TEMU_USERNAME=13256225796
TEMU_PASSWORD=T12345678.

# 妙手ERP账号配置（主要工作平台）
MIAOSHOU_URL=https://erp.91miaoshou.com/sub_account/users
MIAOSHOU_USERNAME=lyl12345678
MIAOSHOU_PASSWORD=Lyl12345678.
```

✅ 妙手ERP账号已配置  
✅ Temu店铺账号已配置

---

## 📦 依赖安装

使用 `.env` 需要安装 `python-dotenv`：

```bash
pip install python-dotenv
```

或使用项目依赖管理工具：

```bash
cd /Users/candy/beimeng_workspace/apps/temu-auto-publish
pip install -r requirements.txt
```

---

## 🚀 使用方式

### 在测试脚本中使用

`run_real_test.py` 已配置从 `.env` 读取：

```python
from dotenv import load_dotenv
import os

# 加载.env
load_dotenv()

# 读取配置
username = os.getenv("MIAOSHOU_USERNAME")
password = os.getenv("MIAOSHOU_PASSWORD")
```

### 运行测试

```bash
cd /Users/candy/beimeng_workspace/apps/temu-auto-publish
python3 run_real_test.py
```

测试脚本会：
1. ✅ 自动加载 `.env` 配置
2. ✅ 读取妙手ERP账号密码
3. ✅ 使用真实账号登录
4. ✅ 执行5→20认领流程

---

## 🔒 安全性

### ✅ 已配置的安全措施

1. **`.env` 已在 `.gitignore` 中**
   - 不会被提交到Git仓库
   - 敏感信息不会泄露

2. **验证命令**：
   ```bash
   cd /Users/candy/beimeng_workspace
   grep ".env" .gitignore
   ```
   
   输出：
   ```
   .env
   .env.local
   .env.*.local
   apps/temu-auto-publish/.env
   ```

### ⚠️ 注意事项

1. **不要提交 `.env` 到Git**
   - `.env` 包含敏感信息
   - 确保始终在 `.gitignore` 中

2. **定期更换密码**
   - 定期更新 `.env` 中的密码
   - 使用强密码

3. **团队协作**
   - 每个团队成员维护自己的 `.env`
   - 不要共享 `.env` 文件
   - 只共享 `.env.example` 模板

---

## 📝 环境变量说明

### 必需配置

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `MIAOSHOU_USERNAME` | 妙手ERP用户名 | `lyl12345678` |
| `MIAOSHOU_PASSWORD` | 妙手ERP密码 | `Lyl12345678.` |

### 可选配置

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `TEMU_USERNAME` | Temu店铺用户名 | - |
| `TEMU_PASSWORD` | Temu店铺密码 | - |
| `OPENAI_API_KEY` | OpenAI API密钥 | - |
| `ANTHROPIC_API_KEY` | Anthropic API密钥 | - |

---

## 🧪 测试验证

### 验证环境变量加载

运行测试脚本查看是否成功加载：

```bash
python3 run_real_test.py
```

**成功输出**：
```
✓ 环境变量已从 .../apps/temu-auto-publish/.env 加载
使用账号: lyl12345678
```

**失败输出**：
```
⚠️ python-dotenv未安装，请运行: pip install python-dotenv
或
❌ 未找到妙手ERP账号配置
```

---

## 🔧 故障排查

### 问题1：python-dotenv未安装

**错误信息**：
```
⚠️ python-dotenv未安装
```

**解决方案**：
```bash
pip install python-dotenv
```

### 问题2：未找到配置

**错误信息**：
```
❌ 未找到妙手ERP账号配置
```

**解决方案**：
1. 检查 `.env` 文件是否存在
2. 检查配置项是否正确
3. 确保格式正确（无引号，无空格）

### 问题3：登录失败

**可能原因**：
1. 账号密码错误
2. `.env` 配置有误
3. 网络问题

**解决步骤**：
1. 验证 `.env` 中的账号密码
2. 手动登录妙手ERP测试
3. 检查网络连接

---

## 📚 相关文档

- [测试脚本说明](./REAL_TEST_REPORT.md)
- [开发指南](./README.md)
- [阶段2报告](./STAGE2_TASK1_REPORT.md)

---

**文档更新时间**: 2025-10-31  
**状态**: ✅ 配置就绪，可以运行测试

