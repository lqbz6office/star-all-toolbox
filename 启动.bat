@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
cd /d "%~dp0"
set "ROOT=%~dp0"
set "LOGDIR=%ROOT%logs"
set "LOG=%LOGDIR%\boot.log"
set "FLAG=%LOGDIR%\started.flag"
set "PYW=%ROOT%.venv\Scripts\pythonw.exe"
set "PY=%ROOT%.venv\Scripts\python.exe"
title Star All Tool Box

if not exist "%LOGDIR%" md "%LOGDIR%" >nul 2>&1

rem ---------- 1. 环境自检(缺哪样说清楚,停住不跑) ----------
if not exist "%PY%" (
    echo.
    echo [E0001] 没找到虚拟环境:%PY%
    echo         修复办法:双击运行「修复环境.bat」,或在命令行执行
    echo         .venv\Scripts\python.exe -m pip install PyQt5
    echo.
    pause
    exit /b 1
)
if not exist "%ROOT%StarATB\bin\adb.exe" (
    echo.
    echo [E0003] 没找到引擎:%ROOT%StarATB\bin\adb.exe
    echo         请把 AllToolBox 1.4.6.705 的 bin 目录内容放到 StarATB\bin 下,
    echo         或在程序里「云端资源」页重新下载组件。
    echo.
    pause
    exit /b 1
)

rem ---------- 2. 直接拉起(不再在这里查管理员/提权) ----------
rem 以前这里跑 net session(0.4s)+ mshta 提权(1~4s),是"启动慢/一闪而过"的主因。
rem 现在提权交给程序自己:非管理员照样开界面,顶部黄条一点就提权重启。

rem ---------- 3. 清理上次残留,记录本次启动 ----------
if exist "%FLAG%" del /q "%FLAG%" >nul 2>&1
if exist "%LOG%" for %%A in ("%LOG%") do if %%~zA GTR 2000000 del /q "%LOG%" >nul 2>&1
echo. >> "%LOG%"
echo [%date% %time%] ---- launcher start ---- >> "%LOG%"

rem ---------- 4. 拉起界面 ----------
start "" "%PYW%" "%ROOT%app\main.py"

rem ---------- 5. 等窗口出现(最多 20 秒);没等到就当场报错 ----------
set /a N=0
:wait
if exist "%FLAG%" goto ok
set /a N+=1
if !N! GEQ 20 goto fail
ping -n 2 127.0.0.1 >nul 2>&1
goto wait

:ok
del /q "%FLAG%" >nul 2>&1
exit /b 0

:fail
echo.
echo ================= 启动失败 =================
echo 界面没有起来。下面是运行日志的最后 25 行:
echo -------------------------------------------
if exist "%LOG%" (
    powershell -NoProfile -Command "Get-Content -LiteralPath '%LOG%' -Tail 25 -Encoding UTF8"
) else (
    echo 没有生成日志,可能是 pythonw 被杀软拦截或 .venv 损坏。
)
echo -------------------------------------------
echo 完整日志:%LOG%
echo.
echo 也可以双击「诊断启动.bat」,它带控制台会直接显示错误。
echo.
pause
exit /b 2
