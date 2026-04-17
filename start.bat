@echo off
chcp 65001 >nul
echo ============================================
echo   OmniPublish V2.0
echo ============================================
echo.

cd /d "%~dp0"

:: 检查 Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] 未找到 Python，请先安装 Python 3.10+
    echo         下载地址: https://www.python.org/downloads/
    echo         安装时请勾选 "Add Python to PATH"
    pause
    exit /b 1
)
python --version

:: 创建虚拟环境（首次）
if not exist "venv" (
    echo [SETUP] 首次运行，创建虚拟环境...
    python -m venv venv
)
call venv\Scripts\activate.bat

:: 安装依赖
echo [SETUP] 检查依赖...
pip install -q -r backend\requirements.txt
echo [OK] 依赖就绪

:: 确保 data 目录存在
if not exist "data" mkdir data

:: 首次运行复制配置
if not exist "config.json" (
    if exist "config.json.example" (
        echo [SETUP] 首次运行，复制配置文件...
        copy config.json.example config.json >nul
        echo [INFO] 已创建 config.json
        echo [INFO] 请编辑 config.json，填入你的 api_key 后重新运行本脚本
        pause
        exit /b 0
    )
)

:: 检查 FFmpeg
where ffmpeg >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] FFmpeg 已安装
) else (
    echo [WARN] 未找到 FFmpeg（视频水印功能不可用）
    echo        下载地址: https://ffmpeg.org/download.html
)

:: 启动
echo.
echo [START] 启动 OmniPublish...
echo         访问: http://localhost:9527
echo         账号: admin / admin123
echo         关闭此窗口即可停止服务
echo.

cd backend
python main.py
pause
