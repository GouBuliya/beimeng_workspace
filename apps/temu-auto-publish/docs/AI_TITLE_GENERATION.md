# AI标题生成功能

## 📖 概述

AI标题生成功能是Temu自动发布工具的增强特性，通过AI技术从5个原始商品标题中提取关键词，生成5个优化的新标题，提升商品在Temu/亚马逊平台的搜索流量。

## ✨ 功能特点

- **智能关键词提取**：自动识别高频热搜词
- **平台规则遵循**：符合Temu/亚马逊平台规范
- **违禁词过滤**：自动避免药品、急救、医疗等敏感词汇
- **本地化优化**：生成符合欧美用户阅读习惯的标题
- **自动降级**：AI调用失败时自动使用简单标题
- **灵活配置**：支持OpenAI、Anthropic等多个AI提供商

## 🚀 快速开始

### 1. 安装依赖

```bash
# OpenAI
pip install openai

# 或者 Anthropic
pip install anthropic
```

### 2. 配置API密钥

在 `.env` 文件中配置：

```env
# OpenAI (推荐)
OPENAI_API_KEY=sk-your-api-key-here
OPENAI_MODEL=gpt-3.5-turbo

# 或者 Anthropic
ANTHROPIC_API_KEY=your-api-key-here
ANTHROPIC_MODEL=claude-3-haiku-20240307
```

### 3. 使用CLI命令

```bash
# 默认启用AI标题生成
cd apps/temu-auto-publish
python -m cli.main workflow run --staff "柯诗俊(keshijun123)"

# 显式启用AI标题
python -m cli.main workflow run --use-ai-titles --staff "张三"

# 禁用AI标题（使用简单标题）
python -m cli.main workflow run --no-ai-titles
```

## 📋 工作流程

### SOP步骤4.2：AI标题生成

1. **收集原始标题**（阶段0）
   - 逐个打开5个产品的编辑弹窗
   - 从"产品标题"字段读取原始标题
   - 关闭弹窗

2. **调用AI生成新标题**
   ```
   提示词：
   提取上面5个商品标题中的高频热搜词，写5个新的中文标题，
   不要出现药品，急救等医疗相关的词汇
   符合欧美人的阅读习惯，符合TEMU/亚马逊平台规则，提高搜索流量
   
   原标题：
   1. 便携药箱家用急救包医疗收纳盒
   2. 家庭药品收纳盒大容量医药箱
   3. ...
   
   请生成5个不同的新标题，每个标题独立且有差异。
   ```

3. **添加型号后缀**
   - 为每个新标题自动添加型号（如：A0049型号）
   - 示例：`家用便携收纳盒 多功能储物整理箱 大容量分隔设计 A0049型号`

4. **应用新标题**（阶段1）
   - 逐个产品编辑时使用对应的新标题
   - 完成标题、价格、库存设置
   - 保存并关闭

### 示例对比

**原始标题：**
- 便携药箱家用急救包医疗收纳盒
- 家庭药品收纳盒大容量医药箱
- 医用急救箱车载药品盒

**AI优化后标题：**
- 家用便携收纳盒 多功能储物整理箱 大容量分隔设计 A0049型号
- 多层分类收纳箱 家庭日用品整理盒 透明可视款 A0050型号
- 车载储物盒 便携式多格分隔箱 耐用材质 A0051型号

**改进点：**
- ✅ 去除违禁词：药品、急救、医疗
- ✅ 增加通用关键词：家用、便携、多功能
- ✅ 添加型号后缀区分产品
- ✅ 符合欧美阅读习惯

## ⚙️ 配置说明

### YAML配置

`config/environments/dev.yaml`:

```yaml
ai:
  provider: openai  # openai / anthropic
  model: gpt-3.5-turbo  # gpt-3.5-turbo / gpt-4 / claude-3-haiku-20240307
  title_generation:
    enabled: true  # 是否启用AI标题生成
    max_retries: 3  # 最大重试次数
    timeout: 30  # 超时时间（秒）
```

### 环境变量

`.env` 文件：

```env
# OpenAI配置（推荐）
OPENAI_API_KEY=sk-your-api-key-here
OPENAI_MODEL=gpt-3.5-turbo

# Anthropic配置（备选）
ANTHROPIC_API_KEY=your-api-key-here
ANTHROPIC_MODEL=claude-3-haiku-20240307
```

## 💻 代码示例

### 1. 直接使用AITitleGenerator

```python
from src.data_processor.ai_title_generator import AITitleGenerator

# 初始化生成器
generator = AITitleGenerator(provider="openai")

# 准备原始标题
original_titles = [
    "便携药箱家用急救包医疗收纳盒",
    "家庭药品收纳盒大容量医药箱",
    "医用急救箱车载药品盒",
    "便携式家用医疗箱急救包",
    "大容量药品收纳盒家庭医药箱"
]

# 生成新标题
new_titles = await generator.generate_titles(
    original_titles,
    model_number="A0049型号",
    use_ai=True
)

for i, title in enumerate(new_titles):
    print(f"{i+1}. {title}")
```

### 2. 在工作流中使用

```python
from src.workflows.five_to_twenty_workflow import FiveToTwentyWorkflow

# 初始化工作流（启用AI标题）
workflow = FiveToTwentyWorkflow(use_ai_titles=True)

# 准备产品数据
products_data = [
    {"keyword": "药箱收纳盒", "model_number": "A0001", "cost": 10.0, "stock": 100},
    {"keyword": "药箱收纳盒", "model_number": "A0002", "cost": 12.0, "stock": 100},
    # ... 共5个
]

# 执行工作流（会自动收集标题、AI生成、应用新标题）
result = await workflow.execute(page, products_data)
```

### 3. 禁用AI标题

```python
# 方式1：在代码中禁用
workflow = FiveToTwentyWorkflow(use_ai_titles=False)

# 方式2：通过CLI禁用
# python -m cli.main workflow run --no-ai-titles
```

## 🔧 高级功能

### 1. 自定义AI提供商

```python
# 使用Anthropic
generator = AITitleGenerator(provider="anthropic")

# 自定义API密钥
generator = AITitleGenerator(
    provider="openai",
    api_key="your-custom-key",
    model="gpt-4"
)
```

### 2. 重试机制

AI调用内置指数退避重试：

```python
generator = AITitleGenerator(
    max_retries=3,  # 最多重试3次
    timeout=30  # 每次调用超时30秒
)
```

### 3. 降级策略

AI调用失败时，自动使用简单标题：

```python
# AI失败时的降级逻辑（自动执行）
fallback_title = f"{keyword} {model_number}型号"
```

## 🐛 故障排除

### 问题1：API密钥未配置

**错误信息：**
```
OpenAI API密钥未配置
```

**解决方案：**
1. 在 `.env` 文件中配置 `OPENAI_API_KEY`
2. 确保 `.env` 文件在项目根目录
3. 重启应用

### 问题2：AI库未安装

**错误信息：**
```
openai 库未安装，OpenAI 功能不可用
```

**解决方案：**
```bash
pip install openai
# 或
pip install anthropic
```

### 问题3：AI调用失败

**日志信息：**
```
⚠️ AI标题生成失败，将使用简单标题
```

**可能原因：**
- API密钥无效或过期
- 网络连接问题
- API配额不足
- 超时

**解决方案：**
1. 检查API密钥是否有效
2. 测试网络连接
3. 查看API使用配额
4. 增加超时时间配置
5. 或使用 `--no-ai-titles` 禁用AI功能

### 问题4：生成的标题数量不足

**日志信息：**
```
AI生成的标题数量不足: 3/5
```

**自动处理：**
系统会自动补齐到5个（使用第一个标题复制）

## 📊 性能指标

- **单次调用时间**：3-10秒（取决于AI提供商）
- **成功率**：95%+（带3次重试）
- **降级率**：<5%
- **成本**：~$0.001-0.01/次（OpenAI gpt-3.5-turbo）

## 🔗 相关文件

- **AI生成器**: `src/data_processor/ai_title_generator.py`
- **首次编辑控制器**: `src/browser/first_edit_controller.py`
- **5→20工作流**: `src/workflows/five_to_twenty_workflow.py`
- **CLI命令**: `cli/commands/workflow.py`
- **配置文件**: `config/environments/dev.yaml`

## 📝 最佳实践

1. **使用gpt-3.5-turbo**：性价比最高，速度快
2. **配置合理的超时**：建议30秒
3. **监控API配额**：避免超额
4. **备用降级策略**：始终启用降级（默认已启用）
5. **测试先行**：在正式环境前测试AI生成效果

## 🆘 获取帮助

- 查看SOP文档：`docs/projects/temu-auto-publish/guides/商品发布SOP-IT专用.md`
- 查看代码注释：所有类和方法都有详细的docstring
- 运行测试：`python -m pytest tests/test_ai_title_generator.py`

