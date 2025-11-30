#!/bin/bash
# Debug 容器启动脚本
# 启动 Xvfb、VNC、noVNC 和应用服务

set -e

echo "==> Starting Xvfb virtual display..."
Xvfb :99 -screen 0 ${SCREEN_WIDTH}x${SCREEN_HEIGHT}x${SCREEN_DEPTH} &
sleep 2

echo "==> Starting Fluxbox window manager..."
fluxbox &
sleep 1

echo "==> Starting x11vnc server on port 5900..."
x11vnc -display :99 -forever -shared -rfbport 5900 -nopw &
sleep 1

echo "==> Starting noVNC on port 6080..."
/usr/share/novnc/utils/novnc_proxy --vnc localhost:5900 --listen 6080 &
sleep 1

echo "==> VNC Access:"
echo "    - Direct VNC: vnc://localhost:5900"
echo "    - Web VNC: http://localhost:6080/vnc.html"

echo "==> Starting Web Panel on port 8000..."
exec python -m uvicorn web_panel.api:app --host 0.0.0.0 --port 8000 --reload



