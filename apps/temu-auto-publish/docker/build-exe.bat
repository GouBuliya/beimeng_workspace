@echo off
REM Windows exe 打包脚本
REM 
REM @PURPOSE: 在本地 Windows 环境打包 exe（推荐方式）
REM @USAGE: docker\build-exe.bat

cd /d "%~dp0\.."

echo =========================================
echo   Temu Auto Publish - 打包 Windows exe
echo =========================================
echo.

REM 检查是否在虚拟环境中
if defined VIRTUAL_ENV (
    echo 检测到虚拟环境: %VIRTUAL_ENV%
) else (
    echo 提示: 建议在虚拟环境中运行
)

REM 确保 PyInstaller 已安装
echo ^>^>^> 检查 PyInstaller...
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo 安装 PyInstaller...
    pip install pyinstaller
)

REM 确保依赖已安装
echo ^>^>^> 检查依赖...
pip install -r requirements.txt -q

REM 运行打包脚本
echo ^>^>^> 开始打包...
python build_windows_exe.py

if errorlevel 1 (
    echo.
    echo × 打包失败！
    exit /b 1
)

echo.
echo √ 打包完成！
echo   输出位置: dist\TemuWebPanel.exe
echo.

REM 显示文件信息
if exist dist\TemuWebPanel.exe (
    echo 文件信息:
    for %%F in (dist\TemuWebPanel.exe) do echo   大小: %%~zF bytes
)

pause



