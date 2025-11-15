@echo off
color 0e
echo ================================================
echo   Temu Web Panel Installer - keep this window open
echo ================================================
cd /d "%~dp0\..\.."
set CMD=uv run python apps/temu-auto-publish/web_panel/cli.py install
echo Command: %CMD%
%CMD%
if %ERRORLEVEL% NEQ 0 (
    color 0c
    echo ERROR: install failed, please capture this window for support
) else (
    echo DONE: dependencies installed successfully
)
pause

