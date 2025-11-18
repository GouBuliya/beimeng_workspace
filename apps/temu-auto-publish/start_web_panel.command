#!/bin/bash
set -e
cd "$(dirname "$0")/../.."
echo "==============================================="
echo " Temu Web Panel Launcher - keep this window open"
echo "==============================================="
CMD=(uv run python apps/temu-auto-publish/web_panel/cli.py start)
echo "Running: ${CMD[*]}"
"${CMD[@]}"

