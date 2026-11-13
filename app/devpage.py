#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把「Star OS 开发者平台」原样嵌进来。

不是重新写一遍,也不是开个子进程弹个新窗口 —— 直接把它的
MainWindow.centralWidget() 取出来放进我们的 QStackedWidget:

    · 左侧「登录 / 上传模块 / 上传表盘 / 开发文档 / AI 教程 / 关于」原样保留;
    · 它的 Settings、token 包裹、GitHub App 上传链路全部复用,一份代码;
    · 唯一区别是不再需要单独一个 exe。

⚠ 依赖:dev_platform 会 import 主仓里的一堆模块(staros_license / staros_dev /
  staros_ghapp / plugin_build / plugin_publish),所以必须能读到 D:\\star os\\work。
  它自己会算 _ROOT 并塞 sys.path,这里只要按路径 import 即可。
"""
import os
import sys

DEV_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "work", "dev-platform")

_state = {"mod": None, "err": None}


def load():
    """导入 dev_platform(带缓存),失败不抛,返回 (mod, err)。"""
    if _state["mod"] or _state["err"]:
        return _state["mod"], _state["err"]
    if not os.path.isdir(DEV_DIR):
        _state["err"] = "找不到开发者平台目录:\n" + DEV_DIR
        return None, _state["err"]
    if DEV_DIR not in sys.path:
        sys.path.insert(0, DEV_DIR)
    try:
        import dev_platform as mod          # noqa: E402
        _state["mod"] = mod
        return mod, None
    except Exception as e:                   # 缺依赖时不炸整个工具箱
        import traceback
        _state["err"] = "%s\n\n%s" % (e, traceback.format_exc(limit=3))
        return None, _state["err"]


def build(parent=None):
    """返回一个 QWidget(开发者平台整页);失败时返回占位说明控件。"""
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget

    mod, err = load()
    if not mod:
        box = QWidget(parent)
        lay = QVBoxLayout(box)
        t = QLabel("开发者平台加载失败")
        t.setStyleSheet("color:#FFB4B4; font-size:14px; font-weight:600;")
        d = QLabel(err or "")
        d.setWordWrap(True)
        d.setTextInteractionFlags(Qt.TextSelectableByMouse)
        d.setStyleSheet("color:#9AA7BD; font-size:11px;")
        lay.addWidget(t)
        lay.addWidget(d)
        lay.addStretch(1)
        return box

    win = mod.MainWindow()
    page = win.centralWidget()
    page.setParent(parent)
    win.centralWidget()          # 保留引用,避免被回收
    page.setStyleSheet(getattr(mod, "STYLE", ""))
    # MainWindow 本身不再需要,但它的 pages 里存了 parent 指针,留着更安全
    page._dev_host = win
    return page


def selfcheck():
    """命令行自检:能不能导入。"""
    mod, err = load()
    if err:
        print("FAIL", err.splitlines()[0])
        return 1
    print("OK", mod.APP_NAME, mod.APP_VER, "pages:",
          [p.__class__.__name__ for p in ("x",)])
    return 0
