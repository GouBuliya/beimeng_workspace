# 工作流使用指南

## 快速开始

### 1. 基本运行（不筛选人员）

```bash
python3 cli/main.py workflow run --no-publish
```

### 2. 筛选指定人员的产品

```bash
python3 cli/main.py workflow run --no-publish --staff "人员名称"
```

例如，如果要筛选"张三"的产品：

```bash
python3 cli/main.py workflow run --no-publish --staff "张三"
```

### 3. 完整工作流（包括发布）

```bash
python3 cli/main.py workflow run --publish --staff "张三" --shop "店铺A"
```

## 工作流步骤

1. **登录** - 自动登录妙手ERP
2. **导航到采集箱** - 进入公用采集箱页面
3. **切换到"全部"tab** - 显示所有产品
4. **筛选人员并搜索** (可选) - 如果指定了 `--staff`，则筛选该人员的产品
5. **5→20工作流**:
   - 编辑5个产品
   - 每个产品认领4次
   - 生成20个产品
6. **批量编辑** - 对20个产品执行批量编辑
7. **发布** (可选) - 如果启用了 `--publish`，则发布产品

## 环境配置

确保 `.env` 文件中配置了登录凭证：

```env
MIAOSHOU_USERNAME=your_username
MIAOSHOU_PASSWORD=your_password
```

或使用旧的变量名：

```env
TEMU_USERNAME=your_username
TEMU_PASSWORD=your_password
```

## 常见问题

### Q: 如何知道人员名称？
A: 人员名称是妙手ERP采集箱筛选框中显示的名称，通常是采集人或创建人的名字。

### Q: 如果不筛选人员会怎样？
A: 不筛选人员时，工作流会处理"全部"tab中的所有产品（前5个）。

### Q: 可以只执行部分步骤吗？
A: 目前工作流是端到端的，但可以通过 `--no-publish` 跳过发布步骤。

## 调试

如果遇到问题，可以查看日志文件：

```bash
# 查看最新的日志
tail -100 logs/latest.log

# 查看带颜色的详细日志
tail -100 /tmp/workflow_full.log
```

## 高级选项

查看所有可用选项：

```bash
python3 cli/main.py workflow run --help
```

主要选项：
- `--staff TEXT` - 人员名称（用于筛选）
- `--shop TEXT` - 店铺名称
- `--publish / --no-publish` - 是否启用发布（默认关闭）
- `--id TEXT` - 自定义工作流ID
- `-p, --products PATH` - 产品数据文件（JSON格式）
- `-c, --config PATH` - 配置文件（YAML/JSON格式）
- `-o, --output PATH` - 结果输出文件

## 示例

### 示例1：测试运行（使用默认数据）

```bash
python3 cli/main.py workflow run --no-publish
```

### 示例2：筛选"李四"的产品并发布到"店铺B"

```bash
python3 cli/main.py workflow run --publish --staff "李四" --shop "店铺B"
```

### 示例3：使用自定义产品文件

```bash
python3 cli/main.py workflow run --no-publish -p my_products.json --staff "王五"
```

my_products.json 示例：
```json
[
    {
        "keyword": "收纳盒",
        "model_number": "A001",
        "cost": 10.5,
        "stock": 100
    },
    {
        "keyword": "药箱",
        "model_number": "A002",
        "cost": 12.0,
        "stock": 200
    }
]
```

