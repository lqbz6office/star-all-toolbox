@echo off
chcp 65001 >nul
cd /d "%~dp0"
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo 需要管理员权限，正在提权...
    mshta vbscript:CreateObject("Shell.Application").ShellExecute("%~f0","","","runas",1)(window.close)
    exit /b
)
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0app\main.py"
