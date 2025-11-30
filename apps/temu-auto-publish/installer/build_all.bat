@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo =========================================
echo   Temu Web Panel - 一键打包安装程序
echo =========================================
echo.

cd /d "%~dp0\.."

:: 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.12+
    pause
    exit /b 1
)

:: 检查 Inno Setup
set "ISCC="
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
) else if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
    set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"
)

echo [1/3] 构建便携版...
echo.
python installer\build_portable.py
if errorlevel 1 (
    echo [错误] 便携版构建失败
    pause
    exit /b 1
)

echo.
echo [2/3] 创建安装程序...

if defined ISCC (
    echo 使用 Inno Setup 创建安装程序...
    "%ISCC%" installer\installer.iss
    if errorlevel 1 (
        echo [警告] Inno Setup 编译失败，跳过安装程序创建
    ) else (
        echo [成功] 安装程序已创建
    )
) else (
    echo [提示] 未找到 Inno Setup，跳过安装程序创建
    echo        下载地址: https://jrsoftware.org/isdl.php
)

echo.
echo [3/3] 创建便携版压缩包...

:: 检查 7-Zip
set "SEVENZIP="
if exist "C:\Program Files\7-Zip\7z.exe" (
    set "SEVENZIP=C:\Program Files\7-Zip\7z.exe"
) else if exist "C:\Program Files (x86)\7-Zip\7z.exe" (
    set "SEVENZIP=C:\Program Files (x86)\7-Zip\7z.exe"
)

if defined SEVENZIP (
    echo 使用 7-Zip 创建压缩包...
    if not exist "dist" mkdir dist
    cd build\portable
    "%SEVENZIP%" a -t7z -mx=9 "..\..\dist\TemuWebPanel_Portable.7z" TemuWebPanel
    cd ..\..
    echo [成功] 便携版压缩包已创建
) else (
    echo [提示] 未找到 7-Zip，跳过压缩包创建
    echo        下载地址: https://www.7-zip.org/
)

echo.
echo =========================================
echo   打包完成！
echo =========================================
echo.
echo 输出文件:

if exist "dist\TemuWebPanel_Setup_*.exe" (
    echo   √ dist\TemuWebPanel_Setup_*.exe (安装程序)
)
if exist "dist\TemuWebPanel_Portable.7z" (
    echo   √ dist\TemuWebPanel_Portable.7z (便携版)
)
if exist "build\portable\TemuWebPanel" (
    echo   √ build\portable\TemuWebPanel\ (便携版目录)
)

echo.
pause


