# Temu Auto Publish - 数据目录管理

本目录集中管理所有运行时数据、配置文件、输入输出文件和资源文件。

## 📁 目录结构

```
data/
├── assets/                    # 静态资源文件(保留,暂未使用)
├── debug/                     # HTML结构分析文件
│   ├── product_list_structure.html
│   └── product_list.png
├── debug_screenshots/         # 调试截图(开发用)
│   ├── batch_edit_page_screenshot.png
│   ├── debug_nav.png
│   ├── debug_packaging_*.png
│   └── staff_filter_page.png
├── html_structure/            # 页面结构配置(JSON)
│   ├── collection_box_table.json
│   ├── search_bar_selector.json
│   └── temu_batch_edit_steps.json
├── image/                     # 图片资源
│   ├── packaging.png          # 默认外包装图片
│   └── products/              # 产品图片目录
│       ├── README.md
│       ├── {标题后缀}_1.jpg   # 产品图片(按规范命名)
│       ├── {标题后缀}_2.jpg
│       └── ...
├── input/                     # 输入数据文件
│   ├── README.md              # 使用说明
│   ├── 10月品 .xlsx           # 原始产品数据
│   └── 10月品 _格式化.xlsx    # 格式化后的产品数据(推荐使用)
├── logs/                      # 运行日志
│   └── dev.log
├── manual/                    # 产品说明书文件
│   └── 超多小语种版说明书.pdf
├── metrics/                   # 性能指标记录
│   └── workflow_*.json
├── output/                    # 输出结果文件
│   ├── collection_to_edit/    # 采集箱编辑报告
│   └── workflow_*_result.json # 工作流执行结果
├── temp/                      # 临时文件
│   ├── miaoshou_cookies.json  # 登录Cookie缓存
│   └── screenshots/           # 运行时截图
│       └── *.png
└── workflow_states/           # 工作流状态快照
    └── workflow_*.json
```

## 📂 各目录详细说明

### 🖼️ `image/` - 图片资源

| 文件/目录 | 说明 | 用途 |
|-----------|------|------|
| `packaging.png` | 默认外包装图片 | 批量编辑时上传外包装图片 |
| `products/` | 产品图片目录 | 存放各产品的主图/规格图 |

**产品图片命名规范:**
- 格式: `{标题后缀}_{规格序号}.{jpg|png|webp}`
- 示例: `A026_1.jpg`, `A026_2.jpg`, `A055_1.png`
- 详见: `image/products/README.md`

### 📊 `input/` - 输入数据

| 文件 | 说明 | 状态 |
|------|------|------|
| `10月品 .xlsx` | 原始产品数据(WPS格式) | ⚠️ 仅供参考 |
| `10月品 _格式化.xlsx` | 格式化后的标准数据 | ✅ **推荐使用** |
| `README.md` | 详细使用说明 | 📖 必读 |

**标准列:**
- `产品名称` - 产品的名称
- `标题后缀` - 追加到标题的编号(如 A026)
- `产品颜色/规格` - 具体规格描述
- `规格序号` - 自动生成的序号(1, 2, 3...)
- `图片路径` - 产品图片相对路径(如 `products/A026_1.jpg`)
- `进货价`、`核价价格`、`发货地` - 可选字段

**使用方式:**
```bash
# 运行工作流
uv run python main.py --input "data/input/10月品 _格式化.xlsx"
```

### 📄 `manual/` - 产品说明书

| 文件 | 说明 | 格式 |
|------|------|------|
| `超多小语种版说明书.pdf` | 默认产品说明书 | PDF |

**使用场景:** 批量编辑第18步上传产品说明书时使用。

### 📝 `logs/` - 运行日志

所有脚本的运行日志都保存在此目录:
- `dev.log` - 开发模式日志
- 日志级别: DEBUG, INFO, WARNING, ERROR
- 日志格式: 时间戳 + 级别 + 模块 + 消息

### 📤 `output/` - 输出结果

| 子目录/文件 | 说明 |
|-------------|------|
| `collection_to_edit/` | 采集箱编辑报告(JSON) |
| `workflow_*_result.json` | 完整工作流执行结果 |

**结果文件包含:**
- 执行状态(成功/失败)
- 各阶段耗时
- 错误信息和堆栈
- 处理的产品数量

### 🔄 `temp/` - 临时文件

| 文件/目录 | 说明 | 是否保留 |
|-----------|------|----------|
| `miaoshou_cookies.json` | 登录Cookie缓存 | ✅ 保留(加速登录) |
| `screenshots/*.png` | 运行时截图 | ⚠️ 可定期清理 |

**Cookie 缓存说明:**
- 首次登录后自动保存
- 有效期通常为数天
- 过期后会自动重新登录

### 📊 `metrics/` & `workflow_states/` - 性能追踪

用于记录工作流的性能指标和状态快照:
- 各阶段执行时间
- 成功/失败次数
- 资源使用情况

### 🐛 `debug_screenshots/` - 调试截图

开发和调试过程中的截图，包括:
- 页面结构分析截图
- DOM 元素定位截图
- 错误状态截图

**提示:** 生产环境可忽略此目录。

### 🔧 `html_structure/` - 页面结构配置

存储页面元素的 JSON 配置文件:
- `collection_box_table.json` - 采集箱表格结构
- `search_bar_selector.json` - 搜索栏选择器
- `temu_batch_edit_steps.json` - Temu批量编辑步骤

**用途:** 供选择器配置和页面结构分析使用。

## 🚀 快速开始

### 1. 准备产品数据

```bash
# 格式化原始 Excel
cd apps/temu-auto-publish
uv run python scripts/format_product_excel.py "data/input/10月品 .xlsx"
```

### 2. 准备产品图片

将产品图片按命名规范放入 `data/image/products/`:

```bash
# 示例: 卫生间收纳柜(A026)的3个规格
cp 图片1.jpg data/image/products/A026_1.jpg
cp 图片2.jpg data/image/products/A026_2.jpg
cp 图片3.jpg data/image/products/A026_3.jpg
```

### 3. 运行工作流

```bash
uv run python main.py --input "data/input/10月品 _格式化.xlsx"
```

### 4. 查看结果

- 日志: `data/logs/dev.log`
- 输出: `data/output/workflow_*_result.json`
- 截图: `data/temp/screenshots/`

## 📋 文件命名规范

### Excel 文件
- 原始文件: `{月份}品 .xlsx`
- 格式化文件: `{月份}品 _格式化.xlsx`

### 产品图片
- 多规格: `{标题后缀}_{规格序号}.{扩展名}`
- 单规格: `{标题后缀}.{扩展名}`
- 示例: `A026_1.jpg`, `A055.png`

### 说明书文件
- 格式: `{描述}.pdf`
- 示例: `超多小语种版说明书.pdf`

### 输出文件
- 工作流结果: `workflow_{时间戳}_result.json`
- 报告: `{类型}_report_{时间戳}.json`

## 🔒 数据安全

### 敏感文件 (已添加到 .gitignore)
- `temp/miaoshou_cookies.json` - Cookie 缓存
- `logs/*.log` - 可能包含敏感信息
- `temp/screenshots/*.png` - 可能包含敏感截图

### 建议
- 定期清理 `temp/screenshots/` (保留最近7天)
- 定期备份 `input/` 和 `output/`
- Cookie 过期后自动失效，无需手动删除

## 🧹 维护清理

### 定期清理脚本示例

```bash
# 清理7天前的临时截图
find data/temp/screenshots -type f -mtime +7 -delete

# 清理30天前的输出结果
find data/output -type f -mtime +30 -delete

# 清理旧的性能指标
find data/metrics -type f -mtime +90 -delete
```

### 磁盘空间管理

各目录的典型大小:
- `image/products/`: 100-500MB (取决于产品图片数量)
- `temp/screenshots/`: 50-200MB
- `logs/`: 10-50MB
- `output/`: 5-20MB
- 其他: < 10MB

**建议:** 定期清理 `temp/` 和旧的 `output/` 文件。

## ❓ 常见问题

### Q: 为什么要集中管理数据文件?

A: 
- ✅ 便于备份和迁移
- ✅ 清晰的文件组织
- ✅ 避免代码和数据混杂
- ✅ 便于 .gitignore 管理

### Q: 可以修改目录结构吗?

A: 不建议。如需修改，需同时更新:
- `config/settings.py` 中的路径配置
- 相关脚本的路径引用
- README 文档

### Q: 如何备份数据?

A: 
```bash
# 备份整个 data 目录
tar -czf temu-data-backup-$(date +%Y%m%d).tar.gz data/

# 仅备份输入和输出
tar -czf temu-io-backup-$(date +%Y%m%d).tar.gz data/input/ data/output/
```

### Q: 图片文件太大怎么办?

A: 可以使用图片压缩工具:
```bash
# 使用 ImageMagick 批量压缩
mogrify -resize 1200x1200\> -quality 85 data/image/products/*.jpg
```

## 📚 相关文档

- [产品数据输入说明](input/README.md)
- [产品图片管理说明](image/products/README.md)
- [格式化工具使用](../scripts/format_product_excel.py)

## 🔗 快速链接

| 用途 | 路径 | 说明 |
|------|------|------|
| 格式化 Excel | `input/10月品 _格式化.xlsx` | 主要输入文件 |
| 产品图片 | `image/products/` | 图片存放目录 |
| 外包装图片 | `image/packaging.png` | 默认外包装 |
| 产品说明书 | `manual/超多小语种版说明书.pdf` | 默认说明书 |
| 运行日志 | `logs/dev.log` | 查看日志 |
| 输出结果 | `output/` | 查看结果 |

---

**最后更新:** 2025-11-07  
**维护者:** Temu Auto Publish Team

