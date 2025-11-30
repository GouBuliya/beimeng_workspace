#!/bin/bash
# Docker 快速启动脚本 (Linux/Mac)
# 
# @PURPOSE: 一键启动 Docker 容器
# @USAGE: ./docker/docker-start.sh [mode]
#   mode: 
#     - prod (默认): 生产模式，无界面
#     - debug: 调试模式，带 VNC

set -e

cd "$(dirname "$0")/.."

MODE=${1:-prod}

echo "========================================="
echo "  Temu Auto Publish - Docker 启动"
echo "========================================="
echo ""

case $MODE in
    prod|production)
        echo ">>> 启动生产环境..."
        docker-compose up -d temu-app
        echo ""
        echo "✅ 启动成功！"
        echo "   Web Panel: http://localhost:8000"
        echo ""
        echo "📋 常用命令:"
        echo "   查看日志: docker-compose logs -f"
        echo "   进入容器: docker-compose exec temu-app bash"
        echo "   停止服务: docker-compose down"
        ;;
    
    debug|dev)
        echo ">>> 启动调试环境（含 VNC）..."
        docker-compose --profile debug up -d
        echo ""
        echo "✅ 启动成功！"
        echo "   Web Panel: http://localhost:8001"
        echo "   VNC 访问: vnc://localhost:5900"
        echo "   Web VNC: http://localhost:6080/vnc.html"
        echo ""
        echo "📋 常用命令:"
        echo "   查看日志: docker-compose logs -f temu-app-debug"
        echo "   进入容器: docker-compose exec temu-app-debug bash"
        echo "   停止服务: docker-compose --profile debug down"
        ;;
    
    build)
        echo ">>> 构建镜像..."
        docker-compose build
        echo "✅ 构建完成！"
        ;;
    
    stop)
        echo ">>> 停止所有服务..."
        docker-compose --profile debug down
        echo "✅ 已停止！"
        ;;
    
    *)
        echo "用法: $0 [prod|debug|build|stop]"
        echo ""
        echo "  prod   - 启动生产环境（默认）"
        echo "  debug  - 启动调试环境（含 VNC）"
        echo "  build  - 构建镜像"
        echo "  stop   - 停止所有服务"
        exit 1
        ;;
esac



