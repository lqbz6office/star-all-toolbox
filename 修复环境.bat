@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Star All Tool Box · 修复环境
echo 正在检查运行环境...
if not exist ".venv\Scripts\python.exe" (
    echo.
    echo [E0001] 没有虚拟环境 .venv
    echo   先装 Python 3.13,然后在本目录执行:
    echo       python -m venv .venv
    echo   再重新运行本脚本。
    echo.
    pause
    exit /b 1
)
echo 虚拟环境 OK,开始安装 / 升级 PyQt5(阿里源)...
".venv\Scripts\python.exe" -m pip install -i https://mirrors.aliyun.com/pypi/simple/ --upgrade PyQt5
echo.
echo 自检:
".venv\Scripts\python.exe" -c "import PyQt5; from PyQt5.QtWidgets import QApplication; print('  PyQt5 可用')"
echo.
pause
