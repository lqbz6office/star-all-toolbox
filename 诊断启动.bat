@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Star All Tool Box · 诊断运行
echo ============================================
echo  诊断模式:带控制台运行,所有错误都会打在这里
echo  关闭这个窗口 = 退出程序
echo ============================================
echo.
if not exist ".venv\Scripts\python.exe" (
    echo [E0001] 缺少 .venv\Scripts\python.exe
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -u "app\main.py"
echo.
echo ---- 程序已退出,退出码 %errorlevel% ----
echo 日志在 logs\boot.log
pause
