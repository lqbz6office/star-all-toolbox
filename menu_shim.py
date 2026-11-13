#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""menu.exe 的替代品 —— 把引擎的终端菜单接到图形界面上。

背景(实测,见 2026-11-13 日志):
    AllToolBox 的每个 bat 都是这样等用户输入的:
        del menutmp.txt
        menu.exe .\menu\xxx.json      ← 原始 exe 在管道下**整块缓冲**,界面看不到选项
        set /p MENU=<menutmp.txt
    原版 menu.exe 把菜单打到控制台、读一个按键、把 value 写进 menutmp.txt。
    但它的 stdout 一旦是管道就不 flush,输入框也拿不到提示 ⇒ 我们只能盲打。

本程序完全替代那一层:
    menu.exe <json>  →  读 json → 把选项写进 _gui\\req.txt
                     →  等界面把选择写进 _gui\\ans.txt
                     →  把 value 写进 menutmp.txt,退出 0

    没有界面在跑(或超时)时退化成原版行为:打印编号列表 + 从 stdin 读一行。

所以引擎一个字节都不用改,49 个菜单 / 全部向导步骤都变成界面上的按钮。
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))
GUI = os.path.join(HERE, "_gui")
REQ = os.path.join(GUI, "req.txt")
ANS = os.path.join(GUI, "ans.txt")


def _atomic_write(path, text, enc="utf-8"):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding=enc, errors="replace", newline="\n") as f:
        f.write(text)
    for _ in range(20):
        try:
            os.replace(tmp, path)
            return True
        except OSError:
            time.sleep(0.02)
    return False


def _load(path):
    """返回 (标题, [(value, label)]) —— 结构不认识的返回 None。"""
    try:
        with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
            d = json.load(f)
    except Exception:
        return None
    if isinstance(d, list):
        d = {"options": d}
    if not isinstance(d, dict):
        return None
    opts = d.get("options")
    if not isinstance(opts, list) or not opts:
        return None
    out = []
    for it in opts:
        if isinstance(it, dict):
            v = it.get("value", it.get("key", it.get("id", "")))
            l = it.get("label", it.get("text", it.get("name", ""))) or str(v)
            out.append((str(v), str(l)))
        else:
            out.append((str(it), str(it)))
    title = d.get("title") or d.get("prompt") or d.get("info") or ""
    return str(title), out


def _write_menutmp(value):
    with open(os.path.join(HERE, "menutmp.txt"), "w",
              encoding="gbk", errors="replace", newline="\r\n") as f:
        f.write(str(value) + "\r\n")


def _console(opts):
    """没有界面时的原版行为:打印编号,读一行。"""
    for i, (_v, l) in enumerate(opts, 1):
        sys.stdout.write("  %d. %s\n" % (i, l))
    sys.stdout.write("选择: ")
    sys.stdout.flush()
    line = sys.stdin.readline().strip()
    if not line:
        return None
    if line.isdigit() and 1 <= int(line) <= len(opts):
        return opts[int(line) - 1][0]
    for v, l in opts:
        if line in (v, l):
            return v
    return None


def main():
    args = [a for a in sys.argv[1:] if a.strip()]
    # -s(多选)/--logo 这类开关:只有**脱离界面**时才交还原版;
    # 在界面里交还原版会卡死(它读的是真控制台,我们这边是管道)。
    flags = [a for a in args if a.startswith("-")]
    paths = [a for a in args if not a.startswith("-")]
    gui = os.environ.get("STARATB_MENU_GUI") == "1" and os.path.isdir(GUI)
    if flags and not gui:
        real = os.path.join(HERE, "menu_engine.exe")
        if os.path.isfile(real):
            os.execv(real, [real] + sys.argv[1:])
        sys.exit(1)
    if not paths:
        sys.exit(1)

    p = paths[0]
    if not os.path.isabs(p):
        p = os.path.join(os.getcwd(), p)
    if not os.path.isfile(p):
        p = os.path.join(HERE, p)
    got = _load(p) if (paths and p.lower().endswith(".json")) else None

    if got is None:
        # ---- pause 模式 --------------------------------------------------
        # 引擎里 260 多处 `pause.exe`(还有 `pause.exe EXIT`),它在管道下不吭声地卡住。
        # 没有界面 ⇒ 交还原版;有界面 ⇒ 要一个「继续」,界面会自动点。
        if gui:
            token = "%d-%d" % (os.getpid(), int(time.time() * 1000) % 100000)
            if _atomic_write(REQ, "%s\n__PAUSE__\nok\t继续\n" % token):
                deadline = time.time() + 120
                while time.time() < deadline:
                    try:
                        with open(ANS, "r", encoding="utf-8", errors="replace") as f:
                            head = f.read().split("\n")
                    except OSError:
                        head = []
                    if len(head) >= 2 and head[0].strip() == token:
                        try:
                            os.remove(ANS)
                        except OSError:
                            pass
                        sys.exit(0)
                    time.sleep(0.05)
        real = os.path.join(HERE, "pause_engine.exe")
        if os.path.isfile(real):
            os.execv(real, [real] + sys.argv[1:])
        sys.exit(0)

    if not gui:
        v = _console(got[1])
        if v is None:
            sys.exit(1)
        _write_menutmp(v)
        sys.exit(0)

    title, opts = got
    token = "%d-%d" % (os.getpid(), int(time.time() * 1000) % 100000)
    lines = [token, title]
    for v, l in opts:
        lines.append("%s\t%s" % (v, l.replace("\t", " ")))
    if not _atomic_write(REQ, "\n".join(lines) + "\n"):
        v = _console(opts)
        _write_menutmp(v)
        sys.exit(0)

    # 等界面点按钮(最多 10 分钟,免得没人点就卡死)
    deadline = time.time() + 600
    v = None
    while time.time() < deadline:
        try:
            with open(ANS, "r", encoding="utf-8", errors="replace") as f:
                head = f.read().split("\n")
        except OSError:
            head = []
        if len(head) >= 2 and head[0].strip() == token:
            v = head[1].strip()
            try:
                os.remove(ANS)
            except OSError:
                pass
            break
        time.sleep(0.05)

    if v is None:                      # 没人理 ⇒ 退回控制台
        v = _console(opts)
    if v is None:
        sys.exit(1)
    _write_menutmp(v)
    sys.exit(0)


if __name__ == "__main__":
    main()
