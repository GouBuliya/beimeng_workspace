@echo off
color 0a
echo ================================================
echo   Temu Web Panel Launcher - keep this window open
echo ================================================
cd /d "%~dp0\..\.."
set CMD=uv run python apps/temu-auto-publish/web_panel/cli.py start
echo 命令: %CMD%
%CMD%
if %ERRORLEVEL% NEQ 0 (
    color 0c
    echo ERROR: start failed, please capture this window for support
) else (
    echo DONE: you can now close this window
)
pause

