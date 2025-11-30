# Docker 容器化部署指南

本文档介绍如何使用 Docker 容器来**固定配置和运行环境**，确保在任何机器上都能稳定运行 Temu 自动发布系统。

## 为什么使用 Docker？

| 优势 | 说明 |
|------|------|
| 🔒 **环境一致性** | 固定 Python 3.12 + Playwright 版本，避免"我电脑上能跑"问题 |
| 📦 **开箱即用** | 预装所有依赖，包括浏览器和中文字体 |
| 🔄 **易于更新** | `docker-compose pull` 一键更新 |
| 🖥️ **远程调试** | VNC 模式可远程查看浏览器操作 |
| 💾 **数据隔离** | 数据持久化到主机，容器删除不丢失 |

## 目录

- [快速开始](#快速开始)
- [环境要求](#环境要求)
- [镜像说明](#镜像说明)
- [配置说明](#配置说明)
- [常用命令](#常用命令)
- [数据持久化](#数据持久化)
- [调试模式](#调试模式)
- [打包 Windows EXE](#打包-windows-exe)
- [故障排除](#故障排除)

## 快速开始

### Windows

```batch
# 构建镜像
docker\docker-start.bat build

# 启动服务
docker\docker-start.bat prod

# 访问 Web Panel
# http://localhost:8000
```

### Linux/Mac

```bash
# 给脚本执行权限
chmod +x docker/docker-start.sh

# 构建镜像
./docker/docker-start.sh build

# 启动服务
./docker/docker-start.sh prod
```

## 环境要求

- Docker 20.10+
- Docker Compose 2.0+
- 至少 8GB 内存
- 至少 10GB 磁盘空间

## 镜像说明

### 基础镜像

使用微软官方 Playwright Python 镜像：`mcr.microsoft.com/playwright/python:v1.49.0-noble`

该镜像预装了：
- Python 3.12
- Playwright 运行时
- Chromium、Firefox、WebKit 浏览器
- 必要的系统依赖

### 镜像构成

| 镜像标签 | 用途 | 大小 |
|---------|------|------|
| `temu-auto-publish:latest` | 生产环境 | ~2.5GB |
| `temu-auto-publish:debug` | 调试环境（含 VNC） | ~3GB |

## 配置说明

### 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `TEMU_WEB_PANEL_ENV` | `production` | 环境标识 |
| `WEB_PANEL_HOST` | `0.0.0.0` | Web Panel 监听地址 |
| `WEB_PANEL_PORT` | `8000` | Web Panel 端口 |
| `TZ` | `Asia/Shanghai` | 时区设置 |

### 端口映射

| 容器端口 | 主机端口 | 服务 |
|---------|---------|------|
| 8000 | 8000 | Web Panel (生产) |
| 8000 | 8001 | Web Panel (调试) |
| 5900 | 5900 | VNC 服务 (调试) |
| 6080 | 6080 | noVNC Web (调试) |

### 资源限制

默认配置：
- CPU: 2-4 核
- 内存: 4-8 GB

可在 `docker-compose.yml` 中调整：

```yaml
deploy:
  resources:
    limits:
      cpus: '4'
      memory: 8G
    reservations:
      cpus: '2'
      memory: 4G
```

## 常用命令

### 基本操作

```bash
# 构建镜像
docker-compose build

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down

# 进入容器
docker-compose exec temu-app bash
```

### 调试模式

```bash
# 启动调试环境（含 VNC）
docker-compose --profile debug up -d

# 访问方式：
# - Web Panel: http://localhost:8001
# - VNC: vnc://localhost:5900
# - Web VNC: http://localhost:6080/vnc.html

# 停止调试环境
docker-compose --profile debug down
```

### 在容器中运行命令

```bash
# 运行工作流
docker-compose exec temu-app python main.py --input data/input/test.xlsx

# 运行 CLI 命令
docker-compose exec temu-app python -m cli.main workflow run

# Python 交互式
docker-compose exec temu-app python
```

## 数据持久化

以下目录通过 Volume 挂载，数据会保留在主机上：

| 主机目录 | 容器目录 | 用途 |
|---------|---------|------|
| `./data/input` | `/app/data/input` | 输入文件（Excel、图片） |
| `./data/output` | `/app/data/output` | 输出结果 |
| `./data/logs` | `/app/data/logs` | 日志文件 |
| `./data/workflow_states` | `/app/data/workflow_states` | 工作流状态（断点续传） |
| `./config` | `/app/config` | 配置文件（只读） |

浏览器数据（登录状态等）保存在 Docker Volume 中：
- `temu-browser-data`

## 调试模式

调试模式支持通过 VNC 远程查看浏览器界面，适合：

1. 排查自动化脚本问题
2. 观察浏览器实际操作
3. 手动干预操作流程

### 访问 VNC

**方式一：VNC 客户端**
- 地址：`localhost:5900`
- 无密码

**方式二：浏览器访问 (noVNC)**
- 打开：http://localhost:6080/vnc.html
- 点击 "Connect"

### 在调试模式运行非 headless 浏览器

```python
# 配置文件或代码中设置
browser:
  headless: false  # 显示浏览器界面
```

## 故障排除

### 镜像构建失败

```bash
# 清理并重新构建
docker-compose build --no-cache
```

### 容器无法启动

```bash
# 查看详细日志
docker-compose logs temu-app

# 检查端口占用
netstat -tulpn | grep 8000
```

### VNC 无法连接

```bash
# 检查 VNC 服务状态
docker-compose exec temu-app-debug ps aux | grep vnc

# 重启调试容器
docker-compose --profile debug restart temu-app-debug
```

### 浏览器启动失败

```bash
# 检查 Playwright 浏览器
docker-compose exec temu-app playwright install --dry-run

# 查看系统依赖
docker-compose exec temu-app playwright install-deps
```

### 内存不足

```bash
# 增加 Docker 内存限制（Docker Desktop）
# Settings -> Resources -> Memory -> 8GB+

# 或修改 docker-compose.yml 中的资源限制
```

## 生产环境注意事项

1. **安全性**
   - 不要在镜像中包含敏感配置
   - 使用环境变量或 secrets 管理敏感信息

2. **日志管理**
   - 配置日志轮转避免磁盘满
   - 考虑接入集中式日志系统

3. **监控**
   - 健康检查已配置
   - 建议接入 Prometheus/Grafana 监控

4. **备份**
   - 定期备份 `data/` 目录
   - 特别是 `workflow_states` 目录

## 打包 Windows EXE

由于 PyInstaller 只能打包当前平台的可执行文件，提供以下几种方式打包 Windows exe：

### 方式一：本地 Windows 打包（推荐）

在 Windows 本机直接运行打包脚本：

```batch
# 使用打包脚本
docker\build-exe.bat

# 或直接运行 Python
python build_windows_exe.py
```

输出位置：`dist/TemuWebPanel.exe`

### 方式二：GitHub Actions 自动打包

推送代码后，在 GitHub 上：

1. **手动触发**：
   - 进入 Actions → Build Windows EXE → Run workflow

2. **自动触发**：
   - 创建 tag 推送：`git tag v1.0.0 && git push --tags`

打包完成后可在 Actions 的 Artifacts 中下载 exe。

### 方式三：Windows 容器打包

需要 Docker Desktop 切换到 Windows 容器模式：

```powershell
# 切换到 Windows 容器
& $Env:ProgramFiles\Docker\Docker\DockerCli.exe -SwitchDaemon

# 构建 Windows 镜像
docker build -f Dockerfile.windows -t temu-builder:windows .

# 运行打包
docker run -v ${PWD}\dist:C:\app\dist temu-builder:windows
```

## 更新部署

```bash
# 拉取最新代码
git pull

# 重新构建镜像
docker-compose build

# 重启服务
docker-compose up -d
```

## 📋 快速参考卡片

### 一分钟速查

```bash
# === 基本操作 ===
docker\docker-start.bat build    # 构建镜像
docker\docker-start.bat prod     # 启动生产环境
docker\docker-start.bat debug    # 启动调试环境（VNC）
docker\docker-start.bat stop     # 停止所有服务

# === 日志和调试 ===
docker-compose logs -f                          # 查看实时日志
docker-compose exec temu-app bash               # 进入容器
docker-compose exec temu-app python main.py     # 运行脚本

# === 服务管理 ===
docker-compose restart                          # 重启服务
docker-compose down                             # 停止并删除容器
docker-compose down -v                          # 停止并删除容器+数据卷
```

### 访问地址

| 服务 | 生产模式 | 调试模式 |
|------|---------|---------|
| Web Panel | http://localhost:8000 | http://localhost:8001 |
| VNC (浏览器) | - | http://localhost:6080/vnc.html |
| VNC (客户端) | - | vnc://localhost:5900 |

### 文件位置

| 用途 | 主机路径 | 说明 |
|------|---------|------|
| 输入文件 | `./data/input/` | 放置 Excel 选品表 |
| 输出结果 | `./data/output/` | 执行结果和报告 |
| 日志文件 | `./data/logs/` | 运行日志 |
| 配置文件 | `./config/` | 选择器和环境配置 |


