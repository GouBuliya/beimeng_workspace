# 🤖 AI标题生成功能配置指南

> 根据 **SOP 4.2** 要求，每次首次编辑时需要使用AI生成优化的产品标题

---

## 📋 功能说明

AI标题生成器会：
1. ✅ 收集5个产品的原始标题
2. ✅ 使用AI提取高频热搜词
3. ✅ 生成5个优化的新标题
4. ✅ 避免违禁词（药品、急救等医疗词汇）
5. ✅ 符合欧美阅读习惯和平台规则
6. ✅ 自动添加型号后缀

---

## 🚀 快速配置（3步完成）

### 步骤1：安装AI库

选择一个AI提供商（OpenAI或Anthropic）：

**选项A：使用 OpenAI（推荐，便宜且快速）**
```bash
cd /Users/candy/beimeng_workspace/apps/temu-auto-publish
pip install openai
```

**选项B：使用 Anthropic Claude（更强大）**
```bash
cd /Users/candy/beimeng_workspace/apps/temu-auto-publish
pip install anthropic
```

**选项C：两个都安装（最佳，有备份）**
```bash
cd /Users/candy/beimeng_workspace/apps/temu-auto-publish
pip install openai anthropic
```

### 步骤2：获取API密钥

**OpenAI API密钥：**
1. 访问 https://platform.openai.com/api-keys
2. 点击 "Create new secret key"
3. 复制API密钥（sk-...）

**Anthropic API密钥：**
1. 访问 https://console.anthropic.com/settings/keys
2. 点击 "Create Key"
3. 复制API密钥（sk-ant-...）

### 步骤3：配置 `.env` 文件

在 `apps/temu-auto-publish/.env` 文件中添加：

```bash
# AI标题生成配置（根据你的选择添加）

# OpenAI配置（推荐）
OPENAI_API_KEY=sk-your-openai-api-key-here
OPENAI_MODEL=gpt-3.5-turbo  # 可选：gpt-4, gpt-3.5-turbo等

# 或者使用 Anthropic配置
ANTHROPIC_API_KEY=sk-ant-your-anthropic-api-key-here
ANTHROPIC_MODEL=claude-3-haiku-20240307  # 可选：claude-3-sonnet, claude-3-opus等
```

---

## ⚙️ 配置示例

### 示例1：使用 OpenAI（成本低，速度快）

```bash
# AI标题生成配置
OPENAI_API_KEY=sk-proj-abc123xyz...
OPENAI_MODEL=gpt-3.5-turbo
```

### 示例2：使用 Anthropic Claude（质量高）

```bash
# AI标题生成配置
ANTHROPIC_API_KEY=sk-ant-api03-xyz...
ANTHROPIC_MODEL=claude-3-haiku-20240307
```

### 示例3：同时配置（自动选择可用的）

```bash
# AI标题生成配置（优先使用OpenAI）
OPENAI_API_KEY=sk-proj-abc123xyz...
OPENAI_MODEL=gpt-3.5-turbo

# 备用Anthropic配置
ANTHROPIC_API_KEY=sk-ant-api03-xyz...
ANTHROPIC_MODEL=claude-3-haiku-20240307
```

---

## 🧪 测试配置

配置完成后，运行测试：

```bash
cd /Users/candy/beimeng_workspace/apps/temu-auto-publish
python3 run_real_test.py
```

查看日志输出，应该看到：

```
✅ 正确：AI标题生成成功
INFO - AI标题生成器初始化: provider=openai, model=gpt-3.5-turbo
INFO - 开始生成标题: use_ai=True
INFO - AI生成成功，用时: 2.5秒
SUCCESS - ✓ AI标题生成完成

生成的新标题：
  1. 家用便携收纳盒 多功能储物整理箱 大容量分隔设计 A0001型号
  2. 多层分类收纳箱 家庭日用品整理盒 透明可视款 A0002型号
  ...
```

```
❌ 错误（配置有问题）：
WARNING - AI生成失败（尝试 1/3）: openai 库未安装
WARNING - ⚠️ AI生成失败，使用原标题作为降级方案
```

---

## 💰 成本估算

### OpenAI定价（2024年）

| 模型 | 输入成本 | 输出成本 | 单次调用成本 |
|------|---------|---------|-------------|
| gpt-3.5-turbo | $0.50/1M tokens | $1.50/1M tokens | ~$0.002 |
| gpt-4 | $30/1M tokens | $60/1M tokens | ~$0.05 |
| gpt-4-turbo | $10/1M tokens | $30/1M tokens | ~$0.015 |

### Anthropic定价（2024年）

| 模型 | 输入成本 | 输出成本 | 单次调用成本 |
|------|---------|---------|-------------|
| claude-3-haiku | $0.25/1M tokens | $1.25/1M tokens | ~$0.001 |
| claude-3-sonnet | $3/1M tokens | $15/1M tokens | ~$0.01 |
| claude-3-opus | $15/1M tokens | $75/1M tokens | ~$0.05 |

**推荐：**
- **开发测试**: `gpt-3.5-turbo` 或 `claude-3-haiku` (~$0.001-0.002/次)
- **生产环境**: `gpt-4-turbo` 或 `claude-3-sonnet` (~$0.01-0.015/次)

**估算：** 每天发布100个产品（20批次），成本约 $0.04-0.20

---

## 🔧 高级配置

### 自定义AI提示词

如果需要修改AI提示词，编辑 `src/data_processor/ai_title_generator.py`:

```python
PROMPT_TEMPLATE = """提取上面5个商品标题中的高频热搜词，写5个新的中文标题，
不要出现药品，急救等医疗相关的词汇
符合欧美人的阅读习惯，符合TEMU/亚马逊平台规则，提高搜索流量

原标题：
{titles}

请生成5个不同的新标题，每个标题独立且有差异。
每行一个标题，不要编号，不要其他说明文字。"""
```

### 调整重试和超时

在 `five_to_twenty_workflow.py` 中：

```python
self.ai_title_generator = AITitleGenerator(
    provider="openai",
    max_retries=3,  # 最大重试次数
    timeout=30      # 超时时间（秒）
)
```

---

## ❓ 常见问题

### Q1: 安装后仍然提示"库未安装"？

**A:** 确保在正确的Python环境中安装：

```bash
# 检查当前Python
which python3

# 确认安装位置
python3 -m pip show openai
python3 -m pip show anthropic
```

### Q2: API调用失败"Invalid API key"？

**A:** 检查API密钥配置：

1. 确认 `.env` 文件中的密钥正确
2. 确认没有多余的空格或引号
3. 重新运行程序（重新加载环境变量）

```bash
# 验证环境变量
python3 -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('OPENAI_API_KEY'))"
```

### Q3: AI生成太慢？

**A:** 优化方案：

1. 使用更快的模型：`gpt-3.5-turbo` 或 `claude-3-haiku`
2. 减少超时时间：`timeout=15`
3. 使用国内API代理（如果可用）

### Q4: AI生成的标题不符合要求？

**A:** 调整提示词：

- 添加更具体的要求
- 提供标题示例
- 增加关键词约束

### Q5: 想禁用AI，只使用原标题？

**A:** 在工作流初始化时设置：

```python
workflow = FiveToTwentyWorkflow(use_ai_titles=False)
```

---

## 📊 AI生成效果对比

### 原始标题（示例）
```
1. 便携药箱家用急救包医疗收纳盒
2. 家庭药品收纳盒大容量医药箱
3. 急救箱收纳整理盒多功能药品盒
4. 医疗用品收纳箱便携式药盒
5. 家用药箱收纳盒急救用品整理箱
```

### AI优化后（示例）
```
1. 家用便携收纳盒 多功能储物整理箱 大容量分隔设计 A0001型号
2. 多层分类收纳箱 家庭日用品整理盒 透明可视款 A0002型号
3. 便携式储物盒 户外旅行收纳整理箱 防水防潮 A0003型号
4. 大容量收纳盒 桌面整理箱 多格分类储物盒 A0004型号
5. 车载收纳箱 后备箱整理盒 可折叠储物箱 A0005型号
```

**改进点：**
- ✅ 去除医疗相关词汇（药品、急救、医疗）
- ✅ 添加通用关键词（收纳、整理、储物）
- ✅ 增加使用场景（家用、户外、车载）
- ✅ 添加产品特点（大容量、防水、可折叠）
- ✅ 符合平台规则和欧美习惯

---

## 🎯 下一步

1. **立即配置**：选择AI提供商并获取API密钥
2. **安装依赖**：运行 `pip install openai` 或 `pip install anthropic`
3. **测试验证**：运行 `python3 run_real_test.py`
4. **观察效果**：查看AI生成的标题是否符合要求

---

## 📞 技术支持

如遇问题，请检查：
1. `.env` 文件配置是否正确
2. API密钥是否有效
3. 网络连接是否正常
4. Python依赖是否安装成功

**日志位置**：控制台输出中搜索 "AI标题生成" 相关信息

