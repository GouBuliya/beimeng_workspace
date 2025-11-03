# Temu自动发布系统 - 生产环境使用指南

> 完整实现SOP步骤4-11的常态化自动发布脚本

## 📋 目录

1. [系统概述](#系统概述)
2. [快速开始](#快速开始)
3. [安装部署](#安装部署)
4. [配置说明](#配置说明)
5. [使用方式](#使用方式)
6. [定时任务](#定时任务)
7. [监控告警](#监控告警)
8. [故障排查](#故障排查)
9. [最佳实践](#最佳实践)

---

## 系统概述

### 功能特性

本系统实现了SOP步骤4-11的完整自动化：

**实现的SOP步骤：**
- ✅ 步骤4-6: 5→20工作流（首次编辑+认领）
- ✅ 步骤7: 批量编辑18步
- ✅ 步骤8-9: 选择店铺+设置供货价
- ✅ 步骤10-11: 批量发布+查看结果

**核心特性：**
- 🎯 双输入模式：支持Excel选品表和JSON配置
- 🔄 定时任务：基于Cron表达式的自动化调度
- 🔔 多渠道通知：钉钉、企业微信、邮件
- 🏥 健康检查：执行前自动检测系统状态
- 💾 断点续传：支持失败恢复和状态保存
- 📊 指标收集：完整的执行数据和统计分析
- 🛡️ 容错机制：自动重试和降级处理

### 系统架构

```
┌─────────────────────────────────────────────────────┐
│                   用户层                              │
│  CLI命令 / 定时任务 / 手动执行                        │
└──────────────────┬──────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────┐
│                核心层                                 │
│  ┌──────────┐ ┌──────────┐ ┌───────────┐            │
│  │生产脚本   │ │守护进程   │ │健康检查   │            │
│  └──────────┘ └──────────┘ └───────────┘            │
└──────────────────┬──────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────┐
│                工作流层                               │
│  5→20工作流 → 批量编辑 → 发布流程                     │
└──────────────────┬──────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────┐
│              控制器层                                 │
│  登录 / 采集箱 / 编辑 / 发布                          │
└──────────────────┬──────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────┐
│            浏览器自动化层                             │
│  Playwright + Chromium                              │
└─────────────────────────────────────────────────────┘
```

---

## 快速开始

### 前置要求

- Python 3.12+
- 至少10GB可用磁盘空间
- 2GB+ 可用内存
- 稳定的网络连接

### 5分钟快速上手

```bash
# 1. 进入项目目录
cd apps/temu-auto-publish

# 2. 安装依赖
uv sync

# 3. 安装Playwright浏览器
playwright install chromium

# 4. 配置环境变量（复制.env.example并编辑）
cp .env.example .env
# 编辑.env，填写MIAOSHOU_USERNAME和MIAOSHOU_PASSWORD

# 5. 验证环境
python scripts/validate_production.py validate

# 6. 运行测试(Dry-run模式)
python scripts/run_production.py data/input/example.xlsx --dry-run

# 7. 正式运行
python scripts/run_production.py data/input/selection.xlsx
```

---

## 安装部署

### 详细安装步骤

#### 1. 安装Python依赖

```bash
# 使用uv（推荐）
uv sync

# 或使用pip
pip install -r requirements.txt
```

#### 2. 安装Playwright浏览器

```bash
playwright install chromium
```

#### 3. 配置环境变量

创建`.env`文件：

```bash
# 登录凭证（必须）
MIAOSHOU_USERNAME=your_username
MIAOSHOU_PASSWORD=your_password

# AI配置（可选，用于标题生成）
OPENAI_API_KEY=sk-...

# 邮件通知配置（可选）
SMTP_USERNAME=your_email@example.com
SMTP_PASSWORD=your_password
```

#### 4. 配置生产环境

编辑`config/production.yaml`：

```yaml
# 关键配置项
notification:
  dingtalk:
    enabled: true
    webhook_url: "https://oapi.dingtalk.com/robot/send?access_token=YOUR_TOKEN"

scheduler:
  jobs:
    - name: "daily_publish"
      enabled: true
      schedule: "0 9 * * *"  # 每天9点
      input_type: "excel"
      input_path: "data/input/selection.xlsx"
```

#### 5. 验证安装

```bash
python scripts/validate_production.py validate
```

如果所有检查通过，说明安装成功！

### 目录结构

```
apps/temu-auto-publish/
├── config/                    # 配置文件
│   ├── production.yaml        # 生产环境配置
│   └── notification.yaml.template  # 通知配置模板
├── data/                      # 数据目录
│   ├── input/                 # 输入文件（Excel/JSON）
│   ├── output/                # 执行结果
│   ├── logs/                  # 日志文件
│   ├── metrics/               # 指标数据
│   └── workflow_states/       # 工作流状态
├── scripts/                   # 脚本
│   ├── run_production.py      # 生产环境主脚本
│   ├── scheduler_daemon.py    # 定时任务守护进程
│   └── validate_production.py # 环境验证脚本
├── src/                       # 源代码
│   ├── core/                  # 核心模块
│   │   ├── notification_service.py  # 通知服务
│   │   └── health_checker.py        # 健康检查
│   ├── workflows/             # 工作流
│   └── browser/               # 浏览器控制器
└── cli/                       # CLI命令
```

---

## 配置说明

### 环境变量配置（.env）

| 变量名 | 必须 | 说明 | 示例 |
|--------|------|------|------|
| `MIAOSHOU_USERNAME` | ✅ | 妙手ERP用户名 | `zhangsan` |
| `MIAOSHOU_PASSWORD` | ✅ | 妙手ERP密码 | `password123` |
| `OPENAI_API_KEY` | ❌ | OpenAI API密钥 | `sk-...` |
| `SMTP_USERNAME` | ❌ | SMTP用户名 | `user@example.com` |
| `SMTP_PASSWORD` | ❌ | SMTP密码 | `password` |

### 生产环境配置（production.yaml）

#### 通知配置

```yaml
notification:
  # 钉钉机器人
  dingtalk:
    enabled: true
    webhook_url: "https://oapi.dingtalk.com/robot/send?access_token=YOUR_TOKEN"
  
  # 企业微信机器人
  wecom:
    enabled: false
    webhook_url: "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY"
  
  # 邮件通知
  email:
    enabled: false
    smtp_host: "smtp.example.com"
    smtp_port: 587
    username: "your_email@example.com"
    password: ""
    from_addr: "noreply@example.com"
    to_addrs:
      - "admin@example.com"
```

#### 定时任务配置

```yaml
scheduler:
  jobs:
    - name: "morning_publish"      # 任务名称
      enabled: true                 # 是否启用
      schedule: "0 9 * * *"        # Cron表达式(每天9点)
      input_type: "excel"          # 输入类型(excel/json)
      input_path: "data/input/selection.xlsx"  # 输入文件路径
      staff_name: "张三"            # 人员筛选(可选)
      enable_batch_edit: true      # 是否批量编辑
      enable_publish: true         # 是否发布
      use_ai_titles: true          # 是否使用AI标题
```

#### Cron表达式说明

```
 ┌───────────── 分钟 (0 - 59)
 │ ┌───────────── 小时 (0 - 23)
 │ │ ┌───────────── 日 (1 - 31)
 │ │ │ ┌───────────── 月 (1 - 12)
 │ │ │ │ ┌───────────── 星期 (0 - 6) (0=周日)
 │ │ │ │ │
 * * * * *

示例：
0 9 * * *       # 每天9点
0 9,14 * * *    # 每天9点和14点
0 9 * * 1-5     # 工作日9点
0 */2 * * *     # 每2小时
30 8-18 * * 1-5 # 工作日8:30-18:30每小时
```

### 输入数据格式

#### Excel格式（推荐）

使用现有的选品表格式，包含以下列：

- 主品负责人
- 产品名称
- 标题后缀（型号编号）
- 产品颜色/规格
- 进货价/成本价

#### JSON格式

```json
{
  "staff_name": "张三",
  "products": [
    {
      "product_name": "药箱收纳盒",
      "model_number": "A0049",
      "cost_price": 15.0,
      "color_spec": "白色/大号",
      "collect_count": 5
    }
  ]
}
```

---

## 使用方式

### 方式1: 命令行手动执行

#### 基础用法

```bash
# 使用Excel输入
python scripts/run_production.py data/input/selection.xlsx

# 使用JSON输入
python scripts/run_production.py config/products.json --type json

# 指定人员筛选
python scripts/run_production.py selection.xlsx --staff-name "张三"
```

#### 高级选项

```bash
# Dry-run模式（不实际执行，仅测试）
python scripts/run_production.py selection.xlsx --dry-run

# 仅执行批量编辑，不发布
python scripts/run_production.py selection.xlsx --no-publish

# 不使用AI生成标题
python scripts/run_production.py selection.xlsx --no-ai-titles

# 跳过健康检查
python scripts/run_production.py selection.xlsx --skip-health-check

# 指定配置文件
python scripts/run_production.py selection.xlsx --config config/custom.yaml
```

#### 通过CLI命令执行

```bash
# 使用temu-auto-publish命令（需要安装）
temu-auto-publish workflow run -p selection.xlsx

# 查看工作流状态
temu-auto-publish workflow status

# 查看工作流历史
temu-auto-publish workflow list
```

### 方式2: 定时任务自动执行

#### 启动守护进程

```bash
# 启动定时任务守护进程
python scripts/scheduler_daemon.py start

# 后台运行（守护进程模式）
nohup python scripts/scheduler_daemon.py start > /dev/null 2>&1 &
```

#### 管理守护进程

```bash
# 查看状态
python scripts/scheduler_daemon.py status

# 停止守护进程
python scripts/scheduler_daemon.py stop

# 重启守护进程
python scripts/scheduler_daemon.py restart
```

#### 使用系统服务（推荐生产环境）

创建systemd服务：

```bash
# 复制服务文件
sudo cp scripts/deploy/systemd/temu-scheduler.service /etc/systemd/system/

# 重新加载systemd
sudo systemctl daemon-reload

# 启动服务
sudo systemctl start temu-scheduler

# 设置开机自启
sudo systemctl enable temu-scheduler

# 查看状态
sudo systemctl status temu-scheduler

# 查看日志
sudo journalctl -u temu-scheduler -f
```

---

## 监控告警

### 执行结果通知

系统会自动发送执行结果通知到配置的渠道（钉钉/企业微信/邮件）。

通知内容包括：
- 工作流ID和执行时间
- 各阶段执行结果
- 耗时统计
- 发布成功率
- 错误详情（如有）

### 健康检查

#### 手动健康检查

```bash
# 全面健康检查
temu-auto-publish health check

# 检查特定组件
temu-auto-publish health check --component browser
temu-auto-publish health check --component login
temu-auto-publish health check --component network

# JSON格式输出
temu-auto-publish health check --json
```

#### 自动健康检查

系统会在执行前自动进行健康检查，检查项包括：
- ✅ 浏览器状态
- ✅ 登录凭证
- ✅ 网络连接
- ✅ 磁盘空间
- ✅ 内存使用
- ✅ 依赖完整性
- ✅ 配置文件

### 指标监控

```bash
# 查看统计信息
temu-auto-publish monitor stats

# 查看最近24小时的统计
temu-auto-publish monitor stats --last 24h

# 查看特定工作流的统计
temu-auto-publish monitor stats --workflow workflow_20251103_140000

# 生成报告
temu-auto-publish monitor report --output report.html
```

### 日志查看

```bash
# 查看实时日志
tail -f data/logs/production.log

# 查看调度器日志
tail -f data/logs/scheduler.log

# 查看最近100行
tail -n 100 data/logs/production.log

# 搜索错误日志
grep "ERROR" data/logs/production.log

# 查看特定工作流的日志
grep "workflow_20251103_140000" data/logs/production.log
```

---

## 故障排查

### 常见问题

#### 1. 登录失败

**症状：** `登录失败` 或 `登录凭证错误`

**解决方法：**
```bash
# 1. 检查环境变量
cat .env | grep MIAOSHOU

# 2. 手动测试登录
python -c "
import os
from dotenv import load_dotenv
load_dotenv()
print('Username:', os.getenv('MIAOSHOU_USERNAME'))
print('Password:', '***' if os.getenv('MIAOSHOU_PASSWORD') else 'Not set')
"

# 3. 验证凭证有效性
temu-auto-publish health check --component login
```

#### 2. 浏览器启动失败

**症状：** `Playwright Chromium未安装` 或 `浏览器启动超时`

**解决方法：**
```bash
# 1. 重新安装浏览器
playwright install chromium

# 2. 检查浏览器状态
temu-auto-publish health check --component browser

# 3. 查看浏览器配置
cat config/browser_config.json
```

#### 3. 网络连接问题

**症状：** `网络请求超时` 或 `无法访问妙手ERP`

**解决方法：**
```bash
# 1. 检查网络连接
temu-auto-publish health check --component network

# 2. 手动测试连接
curl -I https://seller.kuajingmaihuo.com

# 3. 检查代理设置
env | grep -i proxy
```

#### 4. 磁盘空间不足

**症状：** `磁盘空间不足` 或 `无法写入文件`

**解决方法：**
```bash
# 1. 检查磁盘空间
df -h

# 2. 清理临时文件
rm -rf data/temp/*
rm -rf data/debug/*

# 3. 清理旧日志
find data/logs -name "*.log" -mtime +30 -delete

# 4. 压缩旧指标
find data/metrics -name "*.json" -mtime +90 -exec gzip {} \;
```

#### 5. 定时任务未执行

**症状：** 到了预定时间但任务没有运行

**解决方法：**
```bash
# 1. 检查守护进程状态
python scripts/scheduler_daemon.py status

# 2. 检查任务配置
grep -A 10 "jobs:" config/production.yaml

# 3. 查看调度器日志
tail -f data/logs/scheduler.log

# 4. 检查任务锁
ls -la data/job.lock  # 如果存在且长时间未释放，手动删除

# 5. 重启守护进程
python scripts/scheduler_daemon.py restart
```

### 调试模式

```bash
# 启用调试模式（在production.yaml中）
debug:
  enabled: true
  auto_screenshot: true
  auto_save_html: true

# 运行时启用详细日志
export LOG_LEVEL=DEBUG
python scripts/run_production.py selection.xlsx
```

### 获取帮助

如果遇到无法解决的问题：

1. **查看日志：** `data/logs/production.log`
2. **运行验证：** `python scripts/validate_production.py validate`
3. **查看健康状态：** `temu-auto-publish health check`
4. **联系技术支持：** 附带完整的错误日志和执行报告

---

## 最佳实践

### 1. 定期维护

```bash
# 每周执行一次
# 1. 清理临时文件
rm -rf data/temp/*

# 2. 压缩旧日志（保留最近30天）
find data/logs -name "*.log" -mtime +30 -exec gzip {} \;

# 3. 备份重要数据
tar -czf backup_$(date +%Y%m%d).tar.gz data/output data/workflow_states

# 4. 检查系统健康
temu-auto-publish health check

# 5. 更新依赖
uv sync
```

### 2. 监控建议

- **设置告警阈值：** 在配置中设置合理的警告和错误阈值
- **定期查看报告：** 每周查看一次执行统计报告
- **关注成功率：** 发布成功率应保持在90%以上
- **监控资源使用：** 定期检查磁盘和内存使用情况

### 3. 安全建议

- **凭证管理：** 不要将.env文件提交到git
- **定期更新密码：** 每月更新一次登录密码
- **日志脱敏：** 确保日志中不包含敏感信息
- **权限控制：** 限制生产脚本的执行权限

### 4. 性能优化

- **批量处理：** 每次处理5个产品效率最高
- **定时调度：** 避开高峰期（建议9:00-11:00或14:00-16:00）
- **资源限制：** 单个工作流不超过1小时
- **并发控制：** 同一时间只运行一个工作流

### 5. 数据备份

```bash
# 自动备份脚本（添加到crontab）
#!/bin/bash
BACKUP_DIR=/backup/temu-auto-publish
DATE=$(date +%Y%m%d)

# 备份输出数据
tar -czf $BACKUP_DIR/output_$DATE.tar.gz data/output

# 备份工作流状态
tar -czf $BACKUP_DIR/states_$DATE.tar.gz data/workflow_states

# 保留最近30天的备份
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete
```

### 6. 版本管理

```bash
# 记录每次更新
git log --oneline --graph

# 标记稳定版本
git tag -a v1.0.0 -m "生产版本1.0.0"

# 回滚到稳定版本
git checkout v1.0.0
```

---

## 附录

### A. 完整命令参考

#### 生产脚本命令

```bash
python scripts/run_production.py <input_file> [OPTIONS]

Options:
  --type, -t TEXT              输入类型(excel/json)
  --config, -c PATH            配置文件路径
  --staff-name, -s TEXT        人员名称
  --batch-edit/--no-batch-edit 是否批量编辑
  --publish/--no-publish       是否发布
  --ai-titles/--no-ai-titles   是否使用AI标题
  --dry-run                    Dry-run模式
  --skip-health-check          跳过健康检查
```

#### 守护进程命令

```bash
python scripts/scheduler_daemon.py {start|stop|status|restart} [OPTIONS]

Subcommands:
  start    启动守护进程
  stop     停止守护进程
  status   查看状态
  restart  重启守护进程

Options:
  --config PATH  配置文件路径
  --daemon       后台运行模式
```

#### CLI命令

```bash
temu-auto-publish [COMMAND] [OPTIONS]

Commands:
  workflow  工作流管理
  monitor   监控和指标
  debug     调试功能
  config    配置管理
  health    健康检查
  version   版本信息
  status    系统状态
  setup     初始化向导
```

### B. 配置文件模板

完整的配置文件模板请参考：
- `config/production.yaml` - 生产环境配置
- `config/notification.yaml.template` - 通知配置模板
- `.env.example` - 环境变量示例

### C. 相关文档

- [SOP操作文档](docs/projects/temu-auto-publish/guides/商品发布SOP-IT专用.md)
- [开发文档](README.md)
- [API文档](docs/api/)

---

## 更新日志

### v1.0.0 (2025-11-03)

- ✨ 首个生产版本发布
- ✅ 完整实现SOP步骤4-11
- 🔔 支持多渠道通知
- ⏰ 支持定时任务调度
- 🏥 完整的健康检查
- 📊 指标收集和报告

---

## 技术支持

如有问题或建议，请联系：

- **技术负责人：** [您的名字]
- **邮箱：** [您的邮箱]
- **文档地址：** [文档链接]

---

**⚠️ 重要提示：**

1. 首次使用请务必先执行验证：`python scripts/validate_production.py validate`
2. 建议先使用`--dry-run`模式测试
3. 定期备份重要数据
4. 保持系统和依赖更新

**祝使用愉快！🎉**

