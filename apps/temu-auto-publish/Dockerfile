# Temu Auto Publish - Docker Container
# 基于 Playwright 官方 Python 镜像，预装浏览器环境
#
# @PURPOSE: 提供固定的 Python + Playwright 运行环境
# @USAGE:
#   构建: docker build -t temu-auto-publish .
#   运行: docker-compose up -d
#   进入: docker exec -it temu-auto-publish bash

# ==============================================================================
# 阶段1: 构建依赖
# ==============================================================================
FROM mcr.microsoft.com/playwright/python:v1.49.0-noble AS builder

WORKDIR /build

# 安装构建工具
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 创建虚拟环境并安装依赖
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# ==============================================================================
# 阶段2: 生产镜像
# ==============================================================================
FROM mcr.microsoft.com/playwright/python:v1.49.0-noble AS production

# 设置工作目录
WORKDIR /app

# 安装额外的运行时依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    # 中文字体支持
    fonts-wqy-zenhei \
    fonts-wqy-microhei \
    # 用于调试
    vim \
    curl \
    htop \
    # 清理
    && rm -rf /var/lib/apt/lists/* \
    && fc-cache -fv

# 从构建阶段复制虚拟环境
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONIOENCODING=utf-8 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    # Playwright 环境变量
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    # 应用环境变量
    TEMU_WEB_PANEL_ENV=production \
    WEB_PANEL_HOST=0.0.0.0 \
    WEB_PANEL_PORT=8000

# 复制应用代码
COPY . .

# 创建数据目录
RUN mkdir -p /app/data/input \
             /app/data/output \
             /app/data/logs \
             /app/data/temp \
             /app/data/debug \
             /app/data/metrics \
             /app/data/workflow_states

# 暴露端口 (Web Panel)
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# 默认启动 Web Panel
CMD ["python", "-m", "uvicorn", "web_panel.api:app", "--host", "0.0.0.0", "--port", "8000"]



