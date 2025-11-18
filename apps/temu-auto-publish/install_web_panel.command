#!/bin/bash
set -e
cd "$(dirname "$0")/../.."
echo "==============================================="
echo " Temu Web Panel Installer - keep this window open"
echo "==============================================="
uv run python apps/temu-auto-publish/web_panel/cli.py install
echo "All dependencies installed. You can close this window."

