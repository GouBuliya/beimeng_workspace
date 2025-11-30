# Docker 快速启动指南

> 🐳 使用 Docker 容器固定配置和环境，一键部署 Temu 自动发布系统

## 📋 环境要求

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) 20.10+
- 至少 8GB 内存
- 至少 10GB 磁盘空间

### 安装 Docker Desktop (Windows)

1. 下载：https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe
2. 运行安装程序，勾选 "Use WSL 2 instead of Hyper-V"
3. 安装完成后重启电脑
4. 启动 Docker Desktop

验证安装：
```powershell
docker --version
# 输出: Docker version 24.x.x
```

---

## 🚀 快速启动

### Windows

```batch
# 1. 进入项目目录
cd d:\codespace\beimeng_workspace\apps\temu-auto-publish

# 2. 构建镜像（首次需要，约 5-10 分钟）
docker\docker-start.bat build

# 3. 启动服务
docker\docker-start.bat prod

# 4. 打开浏览器访问
# http://localhost:8000
```

### Linux / macOS

```bash
# 1. 进入项目目录
cd /path/to/beimeng_workspace/apps/temu-auto-publish

# 2. 给脚本执行权限
chmod +x docker/docker-start.sh

# 3. 构建并启动
./docker/docker-start.sh build
./docker/docker-start.sh prod
```

---

## 📁 目录说明

启动后，请将文件放到以下目录：

| 目录 | 用途 | 示例 |
|------|------|------|
| `data/input/` | 放置选品表 Excel | `selection.xlsx` |
| `data/output/` | 查看执行结果 | 自动生成 |
| `data/logs/` | 查看运行日志 | 自动生成 |

---

## 🔧 常用命令

| 操作 | Windows | Linux/Mac |
|------|---------|-----------|
| 构建镜像 | `docker\docker-start.bat build` | `./docker/docker-start.sh build` |
| 启动服务 | `docker\docker-start.bat prod` | `./docker/docker-start.sh prod` |
| 启动调试模式 | `docker\docker-start.bat debug` | `./docker/docker-start.sh debug` |
| 停止服务 | `docker\docker-start.bat stop` | `./docker/docker-start.sh stop` |
| 查看日志 | `docker-compose logs -f` | `docker-compose logs -f` |
| 进入容器 | `docker-compose exec temu-app bash` | `docker-compose exec temu-app bash` |

---

## 🖥️ 调试模式（VNC 可视化）

需要查看浏览器操作时，使用调试模式：

```batch
docker\docker-start.bat debug
```

访问方式：
- **Web Panel**: http://localhost:8001
- **VNC (浏览器访问)**: http://localhost:6080/vnc.html
- **VNC (客户端)**: vnc://localhost:5900

---

## ❓ 常见问题

### Q: 构建镜像很慢？

A: 首次构建需要下载基础镜像（约 2GB），请耐心等待。后续构建会使用缓存，速度很快。

### Q: 端口被占用？

A: 修改 `docker-compose.yml` 中的端口映射：
```yaml
ports:
  - "9000:8000"  # 改成 9000
```

### Q: 如何更新到最新版本？

```bash
git pull
docker\docker-start.bat build
docker\docker-start.bat prod
```

### Q: 数据会丢失吗？

A: 不会。`data/` 目录挂载到主机，即使删除容器数据也会保留。

---

## 📖 详细文档

完整文档请参考：[Docker 部署指南](../docs/DOCKER.md)


