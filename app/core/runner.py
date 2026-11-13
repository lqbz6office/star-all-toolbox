#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""执行器 —— 不带 menu.exe 地把 bat 跑起来。

原版控制流是三层:

    main.bat → menu.exe 菜单 → menutmp.txt → set /p menu=<menutmp.txt
             → if "%MENU%"=="K" call X / goto Y

我们的图形界面替掉了第二层(menu.exe),但**保留第一层和第三层的语义**,
所以三个策略按优先级试,命中一个就行:

 1. `call`   —— 对应 bat 里的 `call 别的脚本`,直接调那个脚本,
                 同时把 MENU 塞进环境,保证脚本内部的二次分发也认得。
 2. `goto`   —— 对应 `goto 标签`。标签只在本文件内有意义,
                 所以等价于「带 MENU 调它自己」,让它自己的 if 分支跳过去。
 3. `unknown`—— 有 90 多个条目是动态菜单(比如 cloud.json 用 `for %%i in (%menu)`),
                 键不写在 if 里。这时按原版最原始的方式:**把值写进 menutmp.txt**,
                 再调脚本 —— 脚本 `set /p menu=<menutmp.txt` 就能读到。

这样 333 个条目全都能跑,不用逐个去反推 bat。
"""
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BIN = os.path.join(ROOT, "StarATB", "bin")
MENUTMP = os.path.join(BIN, "menutmp.txt")


def _q(s):
    return '"%s"' % s


def build(menu_key, value, act, source_bat, quiet=False):
    """返回要交给 cmd /c 的一行命令。

    menu_key   : 菜单文件名(backup.json)
    value      : 菜单项的值("1")
    act        : routes 里的动作 {kind,target,raw}
    source_bat : 声明这个菜单的 bat 文件名(main.bat)
    """
    kind = (act or {}).get("kind")
    target = (act or {}).get("target", "") or ""
    src = source_bat or (menu_key.replace(".json", ".bat") if menu_key else "")
    pre = 'cd /d "%s" && ' % BIN

    if kind == "call" and target:
        if target.lower().endswith(".exe"):
            return pre + 'set "MENU=%s" && %s' % (value, target)
        bat = target if target.lower().endswith(".bat") else target + ".bat"
        if not os.path.isfile(os.path.join(BIN, bat)):
            bat = target
        return pre + 'set "MENU=%s" && call %s' % (value, _q(bat))

    if kind == "goto" and src:
        # 标签只在本文件有效 ⇒ 带 MENU 调它自己,让它自己的分支跳
        return pre + 'set "MENU=%s" && call %s' % (value, _q(src))

    # 动态菜单:写 menutmp.txt 再调脚本(原版行为)
    if src:
        return (pre + 'echo %s> menutmp.txt && call %s' % (value, _q(src)))
    return ""


def write_menutmp(value):
    """给需要"菜单值"的脚本留一份,和原版一致。"""
    try:
        with io.open(MENUTMP, "w", encoding="gbk", errors="replace", newline="\r\n") as fh:
            fh.write(str(value) + "\n")
        return True
    except Exception:
        return False


def describe(act, source_bat):
    kind = (act or {}).get("kind")
    if kind == "call":
        return "执行 %s" % act.get("target", "")
    if kind == "goto":
        return "跳转 %s" % act.get("target", "")
    return "未标注(按菜单值调用 %s)" % (source_bat or "—")
