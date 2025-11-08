# 数据格式规范

本文档定义项目中所有数据交互的格式规范。

---

## 核心原则

1. **所有数据交互使用 JSON 格式**
2. **所有文件使用 UTF-8 编码**
3. **时间戳使用 ISO 8601 格式**
4. **价格保留 2 位小数**

---

## 1. 选品表输入（Excel）

### 文件位置
`data/input/products.xlsx`

### 表格结构

| 列名 | 类型 | 必填 | 说明 | 示例 |
|------|------|------|------|------|
| 商品名称 | 文本 | ✓ | 商品的原始名称 | "智能手表运动防水" |
| 成本价 | 数字 | ✓ | 商品成本，单位：元 | 150.00 |
| 类目 | 文本 | ✓ | 商品类目路径 | "电子产品/智能穿戴" |
| 关键词 | 文本 | ✓ | 站内搜索关键词 | "智能手表" |
| 实拍图数组 | JSON/文本 | ✗ | 用于构造首次编辑尺寸图等的图片文件名数组 | `["A045.jpg","A046.jpg"]` |
| 尺寸图链接 | 文本 | ✗ | 可直接访问的尺寸图 URL（支持别名: 尺寸图URL/size_chart_url/size_chart_image_url） | `https://.../A045.jpg` |
| 备注 | 文本 | ✗ | 其他说明信息 | "测试商品" |

### 示例

```
| 商品名称              | 成本价  | 类目                  | 关键词    | 备注     |
|---------------------|--------|----------------------|----------|---------|
| 智能手表运动防水      | 150.00 | 电子产品/智能穿戴    | 智能手表  | 测试商品 |
| 蓝牙耳机无线降噪      | 80.00  | 电子产品/音频设备    | 蓝牙耳机  |         |
```

### 验证规则
- 成本价必须 > 0
- 所有必填字段不能为空
- 成本价保留 2 位小数
- 若缺少 `尺寸图链接`，系统将尝试使用 `SIZE_CHART_BASE_URL` 环境变量与 `实拍图数组` 的首个文件名拼接生成外链。
- 使用拼接方式时，请确保 OSS 对象具备公共读权限或提供有效的签名 URL。

---

## 2. 任务数据（JSON）

### 文件位置
`data/output/task_{timestamp}.json`

### 数据结构

```json
{
  "task_id": "20251029_143000",
  "created_at": "2025-10-29T14:30:00+08:00",
  "status": "pending",
  "products": [
    {
      "id": "P001",
      "keyword": "智能手表",
      "original_name": "智能手表运动防水",
      "ai_title": "[TEMU_AI:智能手表]",
      "cost_price": 150.00,
      "suggested_price": 1125.00,
      "supply_price": 1500.00,
      "category": "电子产品/智能穿戴",
      "search_count": 5,
      "status": "pending",
      "collected_links": [],
      "claimed_ids": [],
      "edit_result": null,
      "publish_result": null
    }
  ],
  "statistics": {
    "total": 1,
    "pending": 1,
    "processing": 0,
    "success": 0,
    "failed": 0
  }
}
```

### 字段说明

#### 顶层字段
- `task_id`: 任务ID（格式：YYYYMMDD_HHMMSS）
- `created_at`: 创建时间（ISO 8601）
- `status`: 任务状态（pending|processing|completed|failed）
- `products`: 产品列表
- `statistics`: 统计信息

#### Product 对象
- `id`: 产品ID（格式：P001, P002, ...）
- `keyword`: 搜索关键词
- `original_name`: 原始商品名称
- `ai_title`: AI 生成的标题
- `cost_price`: 成本价
- `suggested_price`: 建议售价（成本价 × 7.5）
- `supply_price`: 供货价（成本价 × 10）
- `category`: 类目路径
- `search_count`: 需要采集的同款数量
- `status`: 产品状态（pending|collected|edited|published|failed）
- `collected_links`: 采集的链接列表
- `claimed_ids`: 认领后的商品ID列表
- `edit_result`: 编辑结果（见下文）
- `publish_result`: 发布结果（见下文）

---

## 3. 搜索采集结果

### 数据结构

```json
{
  "product_id": "P001",
  "keyword": "智能手表",
  "collected_at": "2025-10-29T14:35:00+08:00",
  "links": [
    {
      "url": "https://seller.temu.com/product/12345",
      "title": "【新款】智能手表运动防水心率监测",
      "price": "199.00",
      "sales": "1000+",
      "rating": "4.8"
    }
  ],
  "count": 5,
  "status": "success"
}
```

### 字段说明
- `product_id`: 对应的产品ID
- `keyword`: 搜索关键词
- `collected_at`: 采集时间
- `links`: 采集的商品链接列表
- `count`: 实际采集数量
- `status`: 采集状态（success|failed）

---

## 4. 编辑结果

### 数据结构

```json
{
  "product_id": "P001",
  "claimed_ids": [
    "TEMU001",
    "TEMU002",
    "TEMU003",
    "TEMU004",
    "TEMU005"
  ],
  "edited_at": "2025-10-29T14:40:00+08:00",
  "changes": {
    "title": {
      "before": "智能手表运动防水心率监测",
      "after": "【新款热卖】智能手表 运动防水 心率监测 多功能手表"
    },
    "category": {
      "before": "电子产品",
      "after": "电子产品/智能穿戴/智能手表"
    }
  },
  "images_confirmed": true,
  "saved": true,
  "status": "success",
  "error_message": null
}
```

### 字段说明
- `product_id`: 产品ID
- `claimed_ids`: 认领成功的商品ID列表（应该有 5-20 个）
- `edited_at`: 编辑时间
- `changes`: 修改内容记录
- `images_confirmed`: 图片是否已确认
- `saved`: 是否已保存
- `status`: 编辑状态（success|failed）
- `error_message`: 错误信息（如果失败）

---

## 5. 发布结果

### 数据结构

```json
{
  "product_id": "P001",
  "published_at": "2025-10-29T14:50:00+08:00",
  "items": [
    {
      "temu_id": "TEMU001",
      "shop_id": "SHOP123",
      "supply_price": 1500.00,
      "status": "published",
      "publish_url": "https://temu.com/product/xxxxx"
    }
  ],
  "total_published": 20,
  "success_count": 18,
  "failed_count": 2,
  "status": "partial_success"
}
```

### 字段说明
- `product_id`: 产品ID
- `published_at`: 发布时间
- `items`: 发布的商品列表
- `total_published`: 总发布数量
- `success_count`: 成功数量
- `failed_count`: 失败数量
- `status`: 发布状态（success|partial_success|failed）

---

## 6. 影刀交互数据

### 任务输入（Python → 影刀）

```json
{
  "flow": "Temu后台登录",
  "task_id": "20251029_143000_login",
  "params": {
    "username": "test_user",
    "password": "test_pass"
  },
  "config": {
    "timeout": 30,
    "retry_times": 3
  }
}
```

### 执行结果（影刀 → Python）

```json
{
  "task_id": "20251029_143000_login",
  "flow": "Temu后台登录",
  "status": "success",
  "result": {
    "login_status": "success",
    "session_id": "xxxxx",
    "cookie_saved": true
  },
  "execution_time": 12.5,
  "completed_at": "2025-10-29T14:30:15+08:00",
  "error_message": null,
  "logs": [
    "打开浏览器",
    "导航到登录页",
    "输入用户名",
    "输入密码",
    "点击登录",
    "登录成功"
  ]
}
```

---

## 7. 日志格式

### 日志文件
`data/logs/temu_auto_{date}.log`

### 日志级别
- `DEBUG`: 详细的调试信息
- `INFO`: 一般信息
- `SUCCESS`: 成功操作（使用 loguru）
- `WARNING`: 警告信息
- `ERROR`: 错误信息

### 日志格式
```
2025-10-29 14:30:00.123 | INFO     | module:function:line - 消息内容
```

### 示例
```log
2025-10-29 14:30:00.123 | INFO     | processor:process_excel:45 - 开始处理选品表
2025-10-29 14:30:00.456 | DEBUG    | excel_reader:read:67 - 读取到 5 行数据
2025-10-29 14:30:01.789 | SUCCESS  | processor:process_excel:78 - ✓ 任务数据已生成
2025-10-29 14:30:02.012 | ERROR    | login_controller:login:123 - ✗ 登录失败: 用户名或密码错误
```

---

## 8. 配置文件格式

### .env 文件
```env
# Temu 账号
TEMU_USERNAME=your_username
TEMU_PASSWORD=your_password

# 路径配置
DATA_INPUT_DIR=data/input
DATA_OUTPUT_DIR=data/output
DATA_TEMP_DIR=data/temp

# 影刀配置
YINGDAO_FLOW_ID=flow_123

# 业务规则
PRICE_MULTIPLIER=7.5
COLLECT_COUNT=5
```

### yingdao_config.json
```json
{
  "login": {
    "url": "https://seller.temu.com/login",
    "timeout": 30,
    "retry_times": 3,
    "cookie_max_age_hours": 24
  },
  "search": {
    "timeout": 10,
    "retry_times": 2,
    "wait_after_search": 3
  },
  "edit": {
    "timeout": 60,
    "save_timeout": 10,
    "wait_after_action": 2
  },
  "browser": {
    "headless": false,
    "window_size": "1920x1080"
  }
}
```

---

## 数据验证

### Pydantic 模型示例

```python
from pydantic import BaseModel, Field, validator
from typing import List, Optional
from datetime import datetime


class ProductInput(BaseModel):
    """选品表输入数据"""
    name: str = Field(..., min_length=1, description="商品名称")
    cost_price: float = Field(..., gt=0, description="成本价")
    category: str = Field(..., description="类目")
    keyword: str = Field(..., description="关键词")
    notes: str = Field(default="", description="备注")
    
    @validator("cost_price")
    def round_price(cls, v):
        return round(v, 2)


class TaskProduct(BaseModel):
    """任务产品数据"""
    id: str = Field(..., pattern=r"^P\d{3}$")
    keyword: str
    original_name: str
    ai_title: str
    cost_price: float
    suggested_price: float
    supply_price: float
    category: str
    search_count: int = Field(default=5, ge=1, le=10)
    status: str = Field(default="pending")
    
    @validator("suggested_price", "supply_price")
    def round_price(cls, v):
        return round(v, 2)
```

---

## 文件命名规范

### 规则
- 使用小写字母和下划线
- 包含时间戳的文件使用 `YYYYMMDD_HHMMSS` 格式
- 临时文件放在 `data/temp/`
- 正式输出放在 `data/output/`

### 示例
```
data/
├── input/
│   └── products_20251029.xlsx
├── output/
│   ├── task_20251029_143000.json
│   └── result_20251029_150000.json
├── temp/
│   ├── yingdao_task.json
│   ├── yingdao_result.json
│   └── temu_cookies.json
└── logs/
    └── temu_auto_20251029.log
```

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0 | 2025-10-29 | 初始版本 |

---

**遵循这些规范可以确保数据交互的一致性和可维护性。**

