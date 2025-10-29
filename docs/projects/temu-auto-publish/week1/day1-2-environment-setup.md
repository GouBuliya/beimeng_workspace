# Day 1-2：环境准备

**目标**：完成所有开发环境的搭建和配置

---

## Day 1：影刀和 Python 环境

### 上午任务（2-3小时）

#### 1.1 安装影刀客户端
- [ ] 下载影刀桌面版（官网：https://www.yingdao.com/）
- [ ] 安装并完成注册
- [ ] 创建第一个测试流程（官方教程）
- [ ] 熟悉界面：录制器、编辑器、运行器
- [ ] **验证标准**：能成功录制并运行一个简单的浏览器自动化任务

#### 1.2 Python 环境搭建
- [ ] 确认 Python 版本（要求 3.12+）
- [ ] 确认已安装 uv（如未安装：`pip install uv`）
- [ ] 在 beimeng_workspace 创建项目目录
  ```bash
  mkdir -p apps/temu-auto-publish
  cd apps/temu-auto-publish
  ```
- [ ] 从模板创建基础文件
  ```bash
  cp ../../docs/templates/README.template.md README.md
  cp ../../docs/templates/.ai.template.json .ai.json
  touch __init__.py main.py
  mkdir -p examples config
  ```

### 下午任务（2-3小时）

#### 1.3 依赖安装
创建 `requirements.txt`：
- [ ] `pandas` - Excel 读取
- [ ] `openpyxl` - Excel 处理
- [ ] `requests` - API 调用
- [ ] `pydantic` - 数据验证
- [ ] `loguru` - 日志记录

```bash
uv pip install pandas openpyxl requests pydantic loguru
```

#### 1.4 测试 Python 环境
创建测试脚本 `test_env.py`：
```python
import pandas as pd
from loguru import logger

logger.info("环境测试开始")
df = pd.DataFrame({"test": [1, 2, 3]})
logger.success(f"Pandas 工作正常，测试数据：{len(df)} 行")
```

- [ ] 运行测试脚本
- [ ] **验证标准**：无错误输出，日志正常显示

---

## Day 2：数据交互和版本控制

### 上午任务（2-3小时）

#### 2.1 确定数据交互方式
- [ ] 创建数据交互目录
  ```bash
  mkdir -p data/{input,output,temp}
  ```
- [ ] 设计 JSON 数据结构（见下方）
- [ ] 创建示例数据文件
  - `data/input/product_sample.xlsx` - 选品表样本
  - `data/output/task_sample.json` - 任务数据样本
  - `data/output/result_sample.json` - 结果数据样本

#### 2.2 JSON 数据结构设计

**任务数据格式** (`task.json`)：
```json
{
  "task_id": "20251029_001",
  "created_at": "2025-10-29T10:00:00",
  "products": [
    {
      "id": "P001",
      "keyword": "智能手表",
      "cost_price": 150.00,
      "suggested_price": 1125.00,
      "category": "电子产品/智能穿戴",
      "search_count": 5,
      "status": "pending"
    }
  ]
}
```

**结果数据格式** (`result.json`)：
```json
{
  "task_id": "20251029_001",
  "completed_at": "2025-10-29T12:00:00",
  "products": [
    {
      "id": "P001",
      "status": "success|failed",
      "collected_links": ["url1", "url2", "url3", "url4", "url5"],
      "published_count": 20,
      "error_message": null
    }
  ],
  "statistics": {
    "total": 1,
    "success": 1,
    "failed": 0
  }
}
```

- [ ] 创建数据结构文档
- [ ] 用 Pydantic 定义数据模型

### 下午任务（2-3小时）

#### 2.3 Git 仓库初始化
- [ ] 创建 `.gitignore` 添加排除项：
  ```
  data/input/*.xlsx
  data/output/*.json
  data/temp/*
  *.log
  .env
  ```
- [ ] 提交初始代码
  ```bash
  git add apps/temu-auto-publish
  git commit -m "feat(temu): 初始化 Temu 自动发布项目"
  ```

#### 2.4 影刀-Python 联调测试
创建简单的联调流程：

**Python 端** (`test_integration.py`)：
```python
import json
from pathlib import Path

# 1. 生成测试任务
task = {
    "task_id": "test_001",
    "action": "login",
    "data": {"username": "test"}
}

task_file = Path("data/temp/task.json")
task_file.write_text(json.dumps(task, ensure_ascii=False, indent=2))
print(f"任务已生成：{task_file}")

# 2. 等待影刀执行（手动运行影刀）
input("请运行影刀流程，完成后按回车...")

# 3. 读取结果
result_file = Path("data/temp/result.json")
if result_file.exists():
    result = json.loads(result_file.read_text())
    print(f"执行结果：{result}")
else:
    print("未找到结果文件")
```

**影刀端**（简单流程）：
- [ ] 创建新流程"测试联调"
- [ ] 读取 `data/temp/task.json`
- [ ] 打开浏览器访问 Temu（或任意网站）
- [ ] 写入结果到 `data/temp/result.json`

- [ ] 运行联调测试
- [ ] **验证标准**：Python 能生成任务，影刀能读取并执行，Python 能读取结果

#### 2.5 创建配置文件
创建 `config/settings.py`：
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Temu 账号
    temu_username: str = ""
    temu_password: str = ""
    
    # 路径配置
    data_input_dir: str = "data/input"
    data_output_dir: str = "data/output"
    data_temp_dir: str = "data/temp"
    
    # 影刀配置
    yingdao_flow_id: str = ""  # 影刀流程 ID
    
    # 业务规则
    price_multiplier: float = 7.5  # 成本×2.5×3
    collect_count: int = 5  # 采集同款数量
    
    class Config:
        env_file = ".env"

settings = Settings()
```

创建 `.env.example`（模板文件）：
```env
TEMU_USERNAME=your_username
TEMU_PASSWORD=your_password
YINGDAO_FLOW_ID=flow_123
```

- [ ] 创建配置文件
- [ ] 创建 `.env` 文件（不提交到 Git）
- [ ] 测试配置加载

---

## Day 1-2 交付物

### 必须完成 ✅
1. 影刀客户端已安装且能正常运行
2. Python 环境已配置，所有依赖已安装
3. 项目目录结构已创建
4. 数据交互格式已确定（JSON Schema）
5. 简单的 Python-影刀联调已跑通
6. Git 仓库已初始化并完成首次提交

### 可选完成 📋
1. 熟悉影刀更多功能（变量、条件判断等）
2. 研究 Temu 后台页面结构
3. 准备测试用的选品表样本

---

## 遇到问题怎么办？

### 影刀安装问题
- **现象**：安装失败或启动报错
- **解决**：查看官方文档，可能需要管理员权限或关闭杀毒软件

### Python 依赖安装失败
- **现象**：`uv pip install` 报错
- **解决**：检查网络，尝试使用国内镜像源
  ```bash
  uv pip install -i https://pypi.tuna.tsinghua.edu.cn/simple pandas
  ```

### 联调测试失败
- **现象**：影刀读不到任务文件
- **解决**：检查路径是否正确（相对路径 vs 绝对路径）

---

## 下一步
完成 Day 1-2 后，继续 [Day 3：Python 数据处理层](day3-data-processing.md)

