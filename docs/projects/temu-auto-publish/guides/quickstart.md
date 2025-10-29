# 快速开始

5 分钟快速上手 Temu 商品发布自动化项目

---

## 前置要求

- ✅ Python 3.12+
- ✅ uv 包管理器
- ✅ 影刀客户端
- ✅ Temu 商家账号

---

## 第一步：克隆项目（如果还没有）

```bash
cd /Users/candy/beimeng_workspace
```

项目已在 `apps/temu-auto-publish/` 目录下。

---

## 第二步：安装依赖

```bash
cd apps/temu-auto-publish

# 安装 Python 依赖
uv pip install pandas openpyxl requests pydantic loguru pyyaml
```

---

## 第三步：配置环境

### 创建配置文件

```bash
# 复制配置模板
cp .env.example .env

# 编辑配置
vim .env  # 或使用你喜欢的编辑器
```

填写以下信息：
```env
TEMU_USERNAME=your_username
TEMU_PASSWORD=your_password
YINGDAO_FLOW_ID=flow_123
```

---

## 第四步：准备测试数据

### 创建选品表

在 `data/input/` 目录创建 `products_sample.xlsx`，包含以下列：

| 商品名称 | 成本价 | 类目 | 关键词 | 备注 |
|---------|--------|------|--------|------|
| 智能手表运动防水 | 150 | 电子产品/智能穿戴 | 智能手表 | 测试商品 |
| 蓝牙耳机无线降噪 | 80 | 电子产品/音频设备 | 蓝牙耳机 | |

---

## 第五步：运行测试

### 测试数据处理

```bash
# 测试 Excel 读取
python src/data_processor/excel_reader.py

# 测试价格计算
python src/data_processor/price_calculator.py

# 测试完整流程
python src/data_processor/processor.py
```

预期输出：
```
✓ 读取完成: 2 个产品
✓ 任务数据已生成: data/output/task.json
```

### 测试影刀连接

```bash
# 测试联调
python test_integration.py
```

按提示在影刀中运行测试流程。

---

## 下一步

恭喜！环境搭建完成。

现在可以：

1. **继续开发**
   - 查看 [Day 1-2 环境准备](../week1/day1-2-environment-setup.md) 了解详细配置
   - 查看 [Day 3 数据处理](../week1/day3-data-processing.md) 开始核心开发

2. **了解架构**
   - 查看 [架构设计](architecture.md) 理解系统结构
   - 查看 [数据格式规范](data-format.md) 了解数据流

3. **开发影刀流程**
   - 查看 [Day 4 登录流程](../week1/day4-yingdao-login.md)
   - 查看 [影刀开发指南](yingdao-development.md)

---

## 常见问题

### uv pip install 很慢
```bash
# 使用国内镜像
uv pip install -i https://pypi.tuna.tsinghua.edu.cn/simple pandas
```

### 影刀找不到文件
检查路径是否正确，建议使用绝对路径：
```python
from pathlib import Path
workspace_root = Path(__file__).parent.parent.parent
task_file = workspace_root / "data/temp/task.json"
```

### Python 模块导入错误
确保在项目根目录运行：
```bash
cd /Users/candy/beimeng_workspace
export PYTHONPATH=.
python apps/temu-auto-publish/src/...
```

---

**准备就绪！开始开发吧！** 🚀

