@echo off
chcp 65001 >nul
cd /d "%~dp0"

rem ---- 引擎检查:没有 bin 就没法干活,先去云端资源页补
if not exist "%~dp0StarATB\bin\adb.exe" (
    echo [错误] 找不到 StarATB\bin\adb.exe
    echo        请把 AllToolBox 1.4.6.705 的 bin 目录放到 StarATB\bin
    pause
    exit /b 1
)

rem ---- 管理员权限(引擎里的 adb / 刷写工具要求)
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo 需要管理员权限,正在提权...
    mshta vbscript:CreateObject("Shell.Application").ShellExecute("%~f0","","","runas",1)(window.close)
    exit /b
)

if exist "%~dp0.venv\Scripts\pythonw.exe" (
    start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0app\main.py"
) else (
    echo 没找到虚拟环境,用系统 Python 启动...
    start "" pythonw "%~dp0app\main.py"
)
