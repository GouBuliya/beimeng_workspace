@echo off
REM Docker 快速启动脚本 (Windows)
REM 
REM @PURPOSE: 一键启动 Docker 容器
REM @USAGE: docker-start.bat [mode]
REM   mode: prod (默认), debug, build, stop

cd /d "%~dp0\.."

set MODE=%1
if "%MODE%"=="" set MODE=prod

echo =========================================
echo   Temu Auto Publish - Docker 启动
echo =========================================
echo.

if "%MODE%"=="prod" goto :prod
if "%MODE%"=="production" goto :prod
if "%MODE%"=="debug" goto :debug
if "%MODE%"=="dev" goto :debug
if "%MODE%"=="build" goto :build
if "%MODE%"=="stop" goto :stop
if "%MODE%"=="exe" goto :exe
goto :usage

:prod
echo ^>^>^> 启动生产环境...
docker-compose up -d temu-app
echo.
echo √ 启动成功！
echo    Web Panel: http://localhost:8000
echo.
echo 常用命令:
echo    查看日志: docker-compose logs -f
echo    进入容器: docker-compose exec temu-app bash
echo    停止服务: docker-compose down
goto :end

:debug
echo ^>^>^> 启动调试环境（含 VNC）...
docker-compose --profile debug up -d
echo.
echo √ 启动成功！
echo    Web Panel: http://localhost:8001
echo    VNC 访问: vnc://localhost:5900
echo    Web VNC: http://localhost:6080/vnc.html
echo.
echo 常用命令:
echo    查看日志: docker-compose logs -f temu-app-debug
echo    进入容器: docker-compose exec temu-app-debug bash
echo    停止服务: docker-compose --profile debug down
goto :end

:build
echo ^>^>^> 构建镜像...
docker-compose build
echo √ 构建完成！
goto :end

:stop
echo ^>^>^> 停止所有服务...
docker-compose --profile debug down
echo √ 已停止！
goto :end

:exe
echo ^>^>^> 打包 Windows exe...
call "%~dp0build-exe.bat"
goto :end

:usage
echo 用法: docker-start.bat [prod^|debug^|build^|stop^|exe]
echo.
echo   prod   - 启动生产环境（默认）
echo   debug  - 启动调试环境（含 VNC）
echo   build  - 构建 Docker 镜像
echo   stop   - 停止所有服务
echo   exe    - 打包 Windows exe
exit /b 1

:end



