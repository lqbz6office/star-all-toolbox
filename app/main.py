#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Star All Tool Box —— 液态玻璃外壳。

底下的引擎(2.8G 的 bin/)一个字没改,还是原来那套 bat;
这里只是把 menu.exe 那层命令行菜单换成图形界面:
左边是主菜单,中间是当前菜单的条目,下面是执行日志。

危险动作(Root / 刷机 / 抹机 / EDL)二次确认。
"""
import json
import os
import re
import sys

from PyQt5.QtCore import QProcess, QProcessEnvironment, QSize, Qt, QTimer
from PyQt5.QtGui import QColor, QFont, QFontMetrics, QIcon, QPainter, QPixmap
from PyQt5.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel,
                             QLineEdit, QMessageBox, QPlainTextEdit,
                             QPushButton, QScrollArea, QSizePolicy, QStackedWidget,
                             QVBoxLayout, QWidget)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import glass
import devpage
from core import about as about_mod
from core import resources, runner, staros
from core import updater
from core.errors import StarError
from glass import (ACCENT, DANGER, GlassPanel, OK, TEXT, TEXT_DIM, WARN,
                   apply_acrylic, apply_round_corners, enable_shadow)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BIN = os.path.join(ROOT, "StarATB", "bin")
ROUTES = os.path.join(HERE, "routes.json")

DANGER_WORDS = ("root", "刷", "edl", "9008", "抹", "格式化", "清空", "解bl",
                "twrp", "recovery", "降级", "wipe", "erase", "patch")
ANSI = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]|\x1b\][^\x07]*\x07")

STYLE = """
QLabel { color: %(text)s; }
QScrollArea { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 2px; }
QScrollBar::handle:vertical { background: rgba(255,255,255,0.16); border-radius: 4px; min-height: 28px; }
QScrollBar::handle:vertical:hover { background: rgba(255,255,255,0.28); }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; }
QLineEdit {
  background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.10);
  border-radius: 10px; padding: 7px 12px; color: %(text)s; selection-background-color: #2F6BD8;
}
QLineEdit:focus { border: 1px solid rgba(91,157,255,0.65); background: rgba(255,255,255,0.09); }
QPlainTextEdit {
  background: rgba(0,0,0,0.28); border: 1px solid rgba(255,255,255,0.08);
  border-radius: 12px; color: #C8D2E4; padding: 8px;
}
""" % {"text": TEXT}


# --------------------------------------------------------------- 小组件
class NavButton(QPushButton):
    """左侧导航:选中时是一块发光的玻璃条。"""

    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(38)
        self.setStyleSheet("""
            QPushButton {
                text-align: left; padding-left: 14px; border: none; border-radius: 10px;
                color: %s; font-size: 13px; background: transparent;
            }
            QPushButton:hover { background: rgba(255,255,255,0.06); }
            QPushButton:checked {
                background: rgba(255,255,255,0.11);
                color: #FFFFFF; font-weight: 600;
            }
        """ % TEXT_DIM)
        f = self.font()
        f.setFamily("Microsoft YaHei UI")
        self.setFont(f)


class Card(QFrame):
    """条目卡片:标题 + 副标题(动作预览) + 右侧箭头。"""

    def __init__(self, title, sub, danger=False, on_click=None, parent=None):
        super().__init__(parent)
        self._hover = False
        self._danger = danger
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(58)
        self._on_click = on_click

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 0, 14, 0)
        lay.setSpacing(12)

        box = QVBoxLayout()
        box.setSpacing(2)
        t = QLabel(title)
        t.setStyleSheet("color:%s; font-size:13px;" % ("#FFB4B4" if danger else TEXT))
        s = QLabel(sub)
        s.setStyleSheet("color:%s; font-size:11px;" % TEXT_DIM)
        s.setMinimumWidth(10)
        s.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        box.addWidget(t)
        box.addWidget(s)
        lay.addLayout(box, 1)

        arrow = QLabel("›")
        arrow.setStyleSheet("color:rgba(255,255,255,0.32); font-size:16px;")
        lay.addWidget(arrow)

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self._on_click:
            self._on_click()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing)
        from PyQt5.QtGui import QBrush, QColor, QPainterPath, QPen
        r = self.rect().adjusted(0, 0, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(r.x() + 0.5, r.y() + 0.5, r.width(), r.height(), 12, 12)
        base = QColor(255, 255, 255, 20) if self._hover else QColor(255, 255, 255, 11)
        if self._danger:
            base = QColor(255, 90, 90, 26 if self._hover else 14)
        p.fillPath(path, QBrush(base))
        p.setPen(QPen(QColor(255, 255, 255, 34 if self._hover else 18), 1))
        p.drawPath(path)


# --------------------------------------------------------------- 主窗口
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Star All Tool Box")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.resize(1120, 720)

        self._drag = None
        self._proc = None
        from PyQt5.QtCore import QObject, pyqtSignal

        class _Sig(QObject):
            info = pyqtSignal(object)
            err = pyqtSignal(object)

        self._sigs = _Sig()
        self._sigs.info.connect(self._on_update_info)
        self._sigs.err.connect(self.show_error)
        self._sig_info = self._sigs.info
        self._sig_err = self._sigs.err
        self._mode = "home"
        self._cur_menu = "main.json"
        self.data = json.load(open(ROUTES, encoding="utf-8"))
        self._build()
        QTimer.singleShot(60, self._native)

    # -- 原生玻璃
    def _native(self):
        hwnd = int(self.winId())
        glass.apply_acrylic(hwnd, alpha=0xB4)
        apply_round_corners(hwnd, 2)
        enable_shadow(hwnd)
        self._poll_device()

    # -- 结构
    def _build(self):
        self.setStyleSheet(STYLE)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(1, 1, 1, 1)
        outer.setSpacing(0)

        # ---------- 顶栏
        top = QWidget()
        tl = QHBoxLayout(top)
        tl.setContentsMargins(22, 14, 16, 8)
        tl.setSpacing(12)

        mark = QLabel("S")
        mark.setFixedSize(26, 26)
        mark.setAlignment(Qt.AlignCenter)
        mark.setStyleSheet("""
            background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 rgba(255,255,255,0.92), stop:1 rgba(190,205,235,0.72));
            color:#171920; border-radius:9px; font-weight:800; font-size:14px;
        """)

        brand = QVBoxLayout()
        brand.setSpacing(0)
        b1 = QLabel("STAR ALL TOOL BOX")
        b1.setStyleSheet("color:#F2F5FA; font-size:12px; font-weight:700; letter-spacing:2px;")
        b2 = QLabel("小天才工具箱 · 图形外壳")
        b2.setStyleSheet("color:%s; font-size:10px; letter-spacing:1px;" % TEXT_DIM)
        brand.addWidget(b1)
        brand.addWidget(b2)

        tl.addWidget(mark)
        tl.addLayout(brand)
        tl.addStretch(1)

        self.dev = QLabel("未连接")
        self.dev.setStyleSheet("""
            color:%s; font-size:11px; padding:5px 11px; border-radius:11px;
            background: rgba(255,255,255,0.07); border:1px solid rgba(255,255,255,0.10);
        """ % TEXT_DIM)
        tl.addWidget(self.dev)

        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索功能…")
        self.search.setFixedWidth(210)
        self.search.textChanged.connect(self._on_search)
        tl.addWidget(self.search)

        up = QPushButton("检查更新")
        up.setCursor(Qt.PointingHandCursor)
        up.setStyleSheet("""
            QPushButton { background: rgba(255,255,255,0.07); color:#C9D4E6; border:none;
                border-radius:9px; font-size:11px; padding:5px 11px; }
            QPushButton:hover { background: rgba(91,157,255,0.22); color:#fff; }
        """)
        up.clicked.connect(self._check_update)
        tl.addWidget(up)

        for txt, fn in (("−", self.showMinimized), ("□", self._toggle_max), ("×", self.close)):
            b = QPushButton(txt)
            b.setFixedSize(26, 26)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet("""
                QPushButton { background: transparent; color: rgba(255,255,255,0.55);
                    border:none; border-radius:13px; font-size:13px; }
                QPushButton:hover { background: rgba(255,255,255,0.12); color:#fff; }
            """)
            b.clicked.connect(fn)
            tl.addWidget(b)
        outer.addWidget(top)

        # ---------- 主体
        body = QHBoxLayout()
        body.setContentsMargins(16, 4, 16, 14)
        body.setSpacing(12)

        # 左栏
        left = GlassPanel(radius=16, fill=14)
        left.setFixedWidth(226)
        ll = QVBoxLayout(left)
        ll.setContentsMargins(10, 12, 10, 12)
        ll.setSpacing(4)
        cap = QLabel("主菜单")
        cap.setStyleSheet("color:%s; font-size:10px; letter-spacing:2px; padding-left:8px;" % TEXT_DIM)
        ll.addWidget(cap)
        self.nav_box = QVBoxLayout()
        self.nav_box.setSpacing(2)
        ll.addLayout(self.nav_box)
        ll.addStretch(1)
        self.nav_buttons = []
        ll.addWidget(self._hint_label())
        self.about_btn = NavButton("关于 / 致谢")
        self.about_btn.clicked.connect(self._show_about)
        ll.addWidget(self.about_btn)
        body.addWidget(left)

        # 中栏
        mid = QVBoxLayout()
        mid.setSpacing(8)
        self.title = QLabel("")
        self.title.setStyleSheet("color:#FFFFFF; font-size:15px; font-weight:600;")
        self.sub = QLabel("")
        self.sub.setStyleSheet("color:%s; font-size:11px;" % TEXT_DIM)
        mid.addWidget(self.title)
        mid.addWidget(self.sub)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.cards = QWidget()
        self.card_box = QVBoxLayout(self.cards)
        self.card_box.setContentsMargins(0, 2, 4, 8)
        self.card_box.setSpacing(6)
        self.card_box.addStretch(1)
        self.scroll.setWidget(self.cards)

        self.stack = QStackedWidget()
        self.stack.addWidget(self.scroll)
        self.dev_host = QWidget()
        dv = QVBoxLayout(self.dev_host)
        dv.setContentsMargins(0, 0, 0, 0)
        self.dev_slot = dv
        self.dev_built = False
        self.stack.addWidget(self.dev_host)
        mid.addWidget(self.stack, 1)
        body.addLayout(mid, 1)

        # 右栏:日志
        right = QVBoxLayout()
        right.setSpacing(8)
        bar = QHBoxLayout()
        lg = QLabel("输出")
        lg.setStyleSheet("color:%s; font-size:10px; letter-spacing:2px;" % TEXT_DIM)
        bar.addWidget(lg)
        bar.addStretch(1)
        self.stop_btn = QPushButton("中止")
        self.stop_btn.setFixedSize(52, 24)
        self.stop_btn.setCursor(Qt.PointingHandCursor)
        self.stop_btn.setStyleSheet("""
            QPushButton { background: rgba(255,107,107,0.16); color:#FFB4B4; border:none;
                border-radius:8px; font-size:11px; }
            QPushButton:hover { background: rgba(255,107,107,0.28); }
            QPushButton:disabled { color: rgba(255,255,255,0.25); background: rgba(255,255,255,0.05); }
        """)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._kill)
        bar.addWidget(self.stop_btn)
        right.addLayout(bar)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setFixedWidth(392)
        f = QFont("Consolas", 9)
        self.log.setFont(f)
        self.log.setStyleSheet("QPlainTextEdit{background: rgba(0,0,0,0.34);"
                               "border:1px solid rgba(255,255,255,0.08); border-radius:14px;"
                               "color:#C3CDE0; padding:10px;}")
        right.addWidget(self.log, 1)
        body.addLayout(right)

        outer.addLayout(body, 1)
        self._fill_nav()

    def _hint_label(self):
        l = QLabel("引擎:AllToolBox 1.2.7ultra\nbin 未改动,仅替换菜单层")
        l.setStyleSheet("color:rgba(255,255,255,0.24); font-size:9px; padding-left:8px;")
        return l

    # -- 顶部五个分区
    def _fill_nav(self):
        for key, label in (("home", "首页"), ("lib", "功能库"),
                           ("res", "云端资源"), ("dev", "开发者平台")):
            b = NavButton(label)
            b.clicked.connect(lambda _=False, k=key: self._on_section(k))
            self.nav_box.addWidget(b)
            self.nav_buttons.append((key, b))
        self._on_section("home")

    def _on_section(self, key):
        self._mode = key
        for k, b in self.nav_buttons:
            b.setChecked(k == key)
        if key == "dev":
            self._open_dev()
            return
        self.stack.setCurrentIndex(0)
        if key == "home":
            self._render_home()
        elif key == "lib":
            self._render_library()
        elif key == "res":
            self._render_resources()

    def _clear_cards(self):
        while self.card_box.count() > 1:
            it = self.card_box.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

    def _add_card(self, title, sub, danger=False, fn=None, wide=False):
        c = Card(title, sub, danger, (lambda: fn()) if fn else None)
        if wide:
            c.setMinimumHeight(64)
        self.card_box.insertWidget(self.card_box.count() - 1, c)
        return c

    def _render_home(self):
        self._clear_cards()
        self.title.setText("Star All Tool Box")
        ok, part, miss = resources.summary()
        self.sub.setText("引擎资源 %d/%d 就位 · 未下载 %d 项" % (ok, len(resources.CATALOG), miss))
        self._add_card("一键安装最新 Star OS(离线包)",
                       "读线上清单 → 下载 full 包 → adb 推送到手表 → magisk 安装",
                       False, lambda: self._install_staros(False))
        self._add_card("安装最新 Star OS(在线包 400KB)",
                       "手表自己联网补资源,网络好时用这个更快",
                       False, lambda: self._install_staros(True))
        self._add_card("检查更新 / 版本信息",
                       "和模块同一套 update.json,正式 + 内测双通道取高者",
                       False, self._check_update)
        self._add_card("云端资源补全",
                       "%d 项未下载 —— bin 不全时在这里补齐" % miss,
                       False, lambda: self._on_section("res"))
        self._add_card("开发者平台",
                       "登录 / 上传模块 / 上传表盘 / 开发文档(原开发者平台整页)",
                       False, lambda: self._on_section("dev"))
        for o in self.data["menus"].get("main.json", []):
            if o["hidden"]:
                continue
            act = self.data["routes"].get("main.json", {}).get(o["value"], {})
            self._add_card(o["label"], runner.describe(act, "main.bat"),
                           any(w in o["label"].lower() for w in DANGER_WORDS),
                           lambda oo=o, aa=act: self._click_item(oo, aa))

    def _render_library(self):
        self._clear_cards()
        self.title.setText("功能库")
        total = sum(len([x for x in v if not x["hidden"]]) for v in self.data["menus"].values())
        self.sub.setText("%d 个菜单 · %d 个可用条目" % (len(self.data["menus"]), total))
        for name in sorted(self.data["menus"]):
            opts = [x for x in self.data["menus"][name] if not x["hidden"]]
            if not opts:
                continue
            src = self.data["sources"].get(name, "")
            self._add_card("%s  (%d 项)" % (name.replace(".json", ""), len(opts)),
                           "来源 %s · 点开查看全部条目" % (src or "—"),
                           False, lambda n=name: self.goto_menu(n))

    def _render_resources(self):
        self._clear_cards()
        ok, part, miss = resources.summary()
        self.title.setText("云端资源")
        self.sub.setText("%d 项就位 · %d 项未下载 · 来源 settings/link.txt(123pan WebDAV)" % (ok, miss))
        for key, fname, name, grp, xdir, move in resources.CATALOG:
            st, path, size = resources.local_state(key)
            where = xdir or move or "bin/"
            if st == "ok":
                mark, sub = "已就位", "%s · %.1f MB · %s" % (name, size / 1048576.0, where)
            elif st == "zip-only":
                mark, sub = "待安装", "%s · 已下载 %s,点一下解压到 %s" % (name, fname, where)
            else:
                mark, sub = "未下载", "%s · %s → %s" % (name, fname, where)
            title = "%s   %s" % (mark, grp)
            self._add_card(title, sub, False,
                           lambda k=key: self._download_res(k))

    def _download_res(self, key):
        key = key[0] if isinstance(key, (list, tuple)) else key
        _k, fname, name, _g, xdir, move = resources.BY_KEY[key]
        st, path, _s = resources.local_state(key)
        if st == "ok":
            self._log("[资源] %s 已就位" % name)
            return
        if st == "zip-only":
            self._log("[资源] 安装 %s" % fname)
            resources.run_async(lambda cb: resources.download(key, cb),
                                self._log,
                                lambda e: (self.show_error(e) if e else None,
                                           self._render_resources()))
            return
        if not self._confirm("下载资源 %s(约几十 MB)" % name):
            return
        self._log("")
        self._log("▶ 下载 %s (%s)" % (name, fname))

        def job(cb):
            resources.download(key, cb)

        def fin(err):
            if err:
                self.show_error(err)
            self._render_resources()

        resources.run_async(job, self._log, fin)

    def _download_many(self, keys, label):
        if not self._confirm("下载「%s」需要的 %d 个资源" % (label, len(keys))):
            return
        self._log("")
        self._log("▶ %s  ← %s" % (label, ", ".join(keys)))

        def job(cb):
            for k in keys:
                st = resources.local_state(k)[0]
                if st == "ok":
                    cb("[资源] %s 已就位,跳过" % resources.BY_KEY[k][2])
                    continue
                resources.download(k, cb)

        def fin(err):
            if err:
                self.show_error(err)
            self._render_resources()

        resources.run_async(job, self._log, fin)

    def _install_staros(self, online):
        if not self._confirm("安装最新版 Star OS 到已连接的手表"):
            return
        self._log("")
        self._log("▶ 安装 Star OS(%s)" % ("在线包" if online else "离线包"))

        def job(cb):
            if online:
                staros.install_online(cb)
            else:
                staros.install(cb)

        def fin(err):
            if err:
                self.show_error(err)
            else:
                self._log("[StarOS] 完成,建议重启手表")

        resources.run_async(job, self._log, fin)

    def _open_dev(self):
        self.stack.setCurrentIndex(1)
        if self.dev_built:
            return
        self.dev_built = True
        w = devpage.build(self.dev_host)
        self.dev_slot.addWidget(w)

    def _on_nav(self, value, label):
        act = self.data["routes"].get("main.json", {}).get(value)
        if act and act["kind"] == "goto":
            tgt = self._menu_of_label("main.bat", act["target"])
            if tgt:
                self.goto_menu(tgt)
                self._sync_nav(value)
                return
        if act:
            self._run(act, label)
        else:
            self._log("[未接入] %s —— 这一项在 bat 里是内置标签,暂无独立入口" % label)

    def _sync_nav(self, value):
        for v, b in self.nav_buttons:
            b.setChecked(v == value)

    def _menu_of_label(self, bat, label):
        secs = self.data.get("sections", {}).get(bat, {})
        return secs.get(str(label).lstrip(":").lower())

    def goto_menu(self, name, push_nav=False):
        if name not in self.data["menus"]:
            return
        self.stack.setCurrentIndex(0)
        self._cur_menu = name
        src = self.data["sources"].get(name, "")
        self.title.setText(os.path.splitext(name)[0])
        n = len([o for o in self.data["menus"][name] if not o["hidden"]])
        self.sub.setText("%d 个功能 · 来源 %s" % (n, src or "—"))
        while self.card_box.count() > 1:
            it = self.card_box.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        for o in self.data["menus"][name]:
            if o["hidden"]:
                continue
            act = self.data["routes"].get(name, {}).get(o["value"], {})
            kind = act.get("kind")
            if kind == "call":
                sub = "执行  %s" % act.get("target", "")
            elif kind == "goto":
                t = self._menu_of_label(src, act.get("target", ""))
                sub = "打开子菜单  %s" % (t or act.get("target"))
            else:
                sub = "未接入"
            danger = any(w in (o["label"] + sub).lower() for w in DANGER_WORDS)
            c = Card(o["label"], sub, danger, lambda oo=o, aa=act: self._click_item(oo, aa))
            self.card_box.insertWidget(self.card_box.count() - 1, c)

    def _click_item(self, opt, act):
        if self._cur_menu == "cloud.json":
            keys = resources.cloud_map().get(str(opt.get("value", "")))
            if keys:
                self._download_many(keys, opt.get("label", ""))
                return
        if act.get("kind") == "goto":
            t = self._menu_of_label(self.data["sources"].get(self._cur_menu, ""), act["target"])
            if t:
                self.goto_menu(t)
                return
        self._run(act, opt["label"], opt.get("value", ""))

    # -- 搜索
    def _on_search(self, text):
        text = text.strip().lower()
        if not text:
            self.goto_menu(self._cur_menu)
            return
        self.title.setText("搜索 “%s”" % text)
        self.sub.setText("跨 40 个菜单匹配")
        while self.card_box.count() > 1:
            it = self.card_box.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        hit = 0
        for m, opts in self.data["menus"].items():
            for o in opts:
                if o["hidden"] or text not in o["label"].lower():
                    continue
                act = self.data["routes"].get(m, {}).get(o["value"], {})
                if act.get("kind") not in ("call", "goto"):
                    continue
                hit += 1
                c = Card(o["label"], "%s · %s" % (os.path.splitext(m)[0],
                                                  act.get("target", "")),
                         any(w in o["label"].lower() for w in DANGER_WORDS),
                         lambda oo=o, aa=act: self._click_item(oo, aa))
                self.card_box.insertWidget(self.card_box.count() - 1, c)
        if not hit:
            l = QLabel("没有匹配的功能")
            l.setStyleSheet("color:%s; padding:12px;" % TEXT_DIM)
            self.card_box.insertWidget(self.card_box.count() - 1, l)

    # -- 执行
    def _run(self, act, label, value=""):
        src = self.data["sources"].get(self._cur_menu, "")
        line = runner.build(self._cur_menu, value, act, src)
        if not line:
            self._log("[未接入] %s —— 该条目的动作无法还原" % label)
            return
        if any(w in label.lower() for w in DANGER_WORDS):
            if not self._confirm(label):
                return
        runner.write_menutmp(value)
        self._log("")
        self._log("▶ %s" % label)
        self._log("  %s" % line)
        self._start_proc(line)

    def _confirm(self, label):
        box = QMessageBox(self)
        box.setWindowTitle("确认操作")
        box.setText("即将执行:%s\n\n涉及 Root / 刷机 / 抹除类操作,可能改变设备状态。" % label)
        box.setIcon(QMessageBox.Warning)
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        box.setDefaultButton(QMessageBox.No)
        box.setStyleSheet("""
            QMessageBox { background:#1B1E25; }
            QLabel { color:#E9EDF5; font-size:12px; }
            QPushButton { background:rgba(255,255,255,0.10); color:#E9EDF5;
                border:none; border-radius:8px; padding:6px 16px; }
            QPushButton:hover { background:rgba(255,255,255,0.18); }
        """)
        return box.exec_() == QMessageBox.Yes

    def _start_proc(self, line):
        if self._proc:
            self._kill()
        p = QProcess(self)
        p.setWorkingDirectory(BIN)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PATH", BIN + ";" + env.value("PATH", ""))
        env.insert("PYTHONIOENCODING", "gbk")
        p.setProcessEnvironment(env)
        p.setProcessChannelMode(QProcess.MergedChannels)
        p.readyReadStandardOutput.connect(lambda: self._drain(p))
        p.finished.connect(lambda c, s: self._done(c))
        p.errorOccurred.connect(lambda e: self._log("[启动失败] %s" % e))
        p.start("cmd", ["/c", line])
        self._proc = p
        self.stop_btn.setEnabled(True)

    def _drain(self, p):
        raw = bytes(p.readAllStandardOutput())
        txt = raw.decode("gbk", "replace")
        txt = ANSI.sub("", txt)
        for ln in txt.splitlines():
            ln = ln.rstrip()
            if ln:
                self._log(ln)

    def _done(self, code):
        self._log("■ 结束 (exit %d)" % code)
        self._proc = None
        self.stop_btn.setEnabled(False)
        self._poll_device()

    def _kill(self):
        if self._proc:
            self._proc.kill()
            self._proc = None
            self.stop_btn.setEnabled(False)
            self._log("■ 已中止")

    def _log(self, s):
        self.log.appendPlainText(s)
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())

    # -- 设备状态
    def _poll_device(self):
        p = QProcess(self)
        p.setWorkingDirectory(BIN)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PATH", BIN + ";" + env.value("PATH", ""))
        p.setProcessEnvironment(env)
        p.setProcessChannelMode(QProcess.MergedChannels)
        p.finished.connect(lambda c, s, pp=p: self._dev_done(pp))
        p.start("cmd", ["/c", "adb devices"])
        QTimer.singleShot(8000, self._poll_device)

    def _dev_done(self, p):
        t = bytes(p.readAllStandardOutput()).decode("gbk", "replace")
        lines = [l.strip() for l in t.splitlines() if l.strip()]
        dev = [l for l in lines[1:] if l.endswith("device")]
        if dev:
            self.dev.setText("已连接 · " + dev[0].split()[0])
            self.dev.setStyleSheet("color:%s; font-size:11px; padding:5px 11px;"
                                   "border-radius:11px; background: rgba(67,214,160,0.14);"
                                   "border:1px solid rgba(67,214,160,0.35);" % OK)
        else:
            self.dev.setText("未连接")
            self.dev.setStyleSheet("color:%s; font-size:11px; padding:5px 11px;"
                                   "border-radius:11px; background: rgba(255,255,255,0.07);"
                                   "border:1px solid rgba(255,255,255,0.10);" % TEXT_DIM)

    # -- 更新 / 关于 / 错误
    def _check_update(self):
        from threading import Thread
        self._log("正在检查更新…")

        def job():
            try:
                info = updater.latest(0)      # 0 = 永远取到线上最新,仅用于展示
                self._sig_info.emit(info or {})
            except StarError as e:
                self._sig_err.emit(e)
            except Exception as e:            # 兜底,绝不让异常冒到线程外
                self._sig_err.emit(StarError("E9000", str(e)))

        Thread(target=job, daemon=True).start()

    def _on_update_info(self, info):
        if not info:
            self._log("[E5004] 已是最新版本")
            return
        self._log("线上最新:%s (vc%s)" % (info.get("version"), info.get("versionCode")))
        box = QMessageBox(self)
        box.setWindowTitle("检查更新")
        box.setText("线上最新版本:%s (versionCode %s)\n通道:%s\n\n来源:%s"
                    % (info.get("version"), info.get("versionCode"),
                       info.get("_channel", "stable"), info.get("_source", "")))
        box.setInformativeText("更新日志:%s" % info.get("changelog", "—"))
        box.setStandardButtons(QMessageBox.Ok)
        box.setStyleSheet("QMessageBox{background:#1B1E25;} QLabel{color:#E9EDF5;font-size:12px;}"
                          "QPushButton{background:rgba(255,255,255,0.10);color:#E9EDF5;border:none;"
                          "border-radius:8px;padding:6px 16px;}")
        box.exec_()

    def _show_about(self):
        box = QMessageBox(self)
        box.setWindowTitle("关于 " + about_mod.APP_NAME)
        box.setTextFormat(Qt.RichText)
        txt = about_mod.about_text(device=self.dev.text()).replace("\n", "<br>")
        txt = txt.replace("——— 特别鸣谢 ———",
                          '<span style="color:#F5B254;font-weight:700;">——— 特别鸣谢 ———</span>')
        box.setText(txt)
        box.setStyleSheet("QMessageBox{background:#1B1E25;} QLabel{color:#E9EDF5;font-size:12px;}"
                          "QPushButton{background:rgba(255,255,255,0.10);color:#E9EDF5;border:none;"
                          "border-radius:8px;padding:6px 16px;}")
        box.exec_()

    def show_error(self, e):
        """所有错误都从这里出口:号码 + 中文标题 + 原因 + 建议。"""
        self._log(e.text())
        box = QMessageBox(self)
        box.setWindowTitle("出错了 · %s" % e.code)
        box.setText(e.info.title)
        box.setInformativeText("原因:%s\n\n建议:%s%s"
                               % (e.info.why, e.info.fix,
                                  ("\n\n详情:%s" % e.detail) if e.detail else ""))
        box.setIcon(QMessageBox.Warning)
        box.setStyleSheet("QMessageBox{background:#1B1E25;} QLabel{color:#E9EDF5;font-size:12px;}"
                          "QPushButton{background:rgba(255,255,255,0.10);color:#E9EDF5;border:none;"
                          "border-radius:8px;padding:6px 16px;}")
        box.exec_()

    # -- 窗口行为
    def _toggle_max(self):
        self.showNormal() if self.isMaximized() else self.showMaximized()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and e.pos().y() < 60:
            self._drag = e.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag and e.buttons() & Qt.LeftButton:
            self.move(e.globalPos() - self._drag)

    def mouseReleaseEvent(self, e):
        self._drag = None

    def paintEvent(self, e):
        glass.paint_root(self, 22)


def preflight():
    """启动前的三道检查,失败一律抛 StarError(带中文解释)。"""
    import ctypes
    if os.name != "nt":
        raise StarError("E0001")
    if not os.path.isdir(BIN):
        raise StarError("E0003", "缺少 " + BIN)
    if not os.path.isfile(os.path.join(BIN, "adb.exe")):
        raise StarError("E0003", "缺少 adb.exe")
    try:
        admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        admin = False
    if not admin:
        raise StarError("E0002")


def main():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei UI", 9))
    try:
        preflight()
    except StarError as e:
        box = QMessageBox()
        box.setWindowTitle("无法启动 · %s" % e.code)
        box.setText(e.info.title)
        box.setInformativeText("原因:%s\n\n建议:%s" % (e.info.why, e.info.fix))
        box.setIcon(QMessageBox.Critical)
        box.setStyleSheet("QMessageBox{background:#1B1E25;} QLabel{color:#E9EDF5;font-size:12px;}"
                          "QPushButton{background:rgba(255,255,255,0.10);color:#E9EDF5;border:none;"
                          "border-radius:8px;padding:6px 16px;}")
        box.exec_()
        sys.exit(2)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
