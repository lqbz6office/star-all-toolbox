#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Star All Tool Box —— 液态玻璃外壳。

底下的引擎(2.8G 的 bin/)一个字没改,还是原来那套 bat;
这里只是把 menu.exe 那层命令行菜单换成图形界面:
左边是主菜单,中间是当前菜单的条目,下面是执行日志。

危险动作(Root / 刷机 / 抹机 / EDL)二次确认。
"""
import io
import json
import os
import re
import sys
import time
import traceback

from PyQt5.QtCore import QPoint, QProcess, QProcessEnvironment, QSize, Qt, QTimer
from PyQt5.QtGui import QColor, QFont, QFontMetrics, QIcon, QPainter, QPixmap
from PyQt5.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel,
                             QLineEdit, QMenu, QMessageBox, QPlainTextEdit,
                             QPushButton, QScrollArea, QSizePolicy, QStackedWidget,
                             QVBoxLayout, QWidget)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import glass
import devpage
from core import about as about_mod
from core import resources, runner, staros
from core.errors import StarError
from glass import (ACCENT, DANGER, GlassPanel, OK, TEXT, TEXT_DIM, WARN,
                   apply_acrylic, apply_round_corners, enable_shadow)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BIN = os.path.join(ROOT, "StarATB", "bin")
ROUTES = os.path.join(HERE, "routes.json")

# ---- 启动留痕:pythonw 没有控制台,出错必须落盘 + 弹框,否则就是"一闪而过"
LOGDIR = os.path.join(ROOT, "logs")
BOOTLOG = os.path.join(LOGDIR, "boot.log")
FLAG = os.path.join(LOGDIR, "started.flag")
RUNBAT = os.path.join(LOGDIR, "_run.bat")
# menu.exe 替身与界面之间传话用的两个文件(见 menu_shim.py)
GUI_DIR = os.path.join(BIN, "_gui")
MENU_REQ = os.path.join(GUI_DIR, "req.txt")
MENU_ANS = os.path.join(GUI_DIR, "ans.txt")
GEOM = os.path.join(ROOT, "ui.json")
ADMIN = False
_T0 = time.perf_counter()   # 本模块开始导入的时刻,用来算启动耗时


def _log(msg):
    try:
        if not os.path.isdir(LOGDIR):
            os.makedirs(LOGDIR)
        with open(BOOTLOG, "a", encoding="utf-8") as f:
            f.write("[%s.%03d] %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"),
                                        int(time.time() * 1000) % 1000, msg))
    except Exception:
        pass


def _die(title, why, tb_text=""):
    """画出错误框并退出 —— 保证不会静默消失。"""
    _log("DIE %s | %s\n%s" % (title, why, tb_text))
    try:
        box = QMessageBox()
        box.setWindowTitle("Star All Tool Box · 启动失败")
        box.setText(title)
        box.setInformativeText("原因:%s\n\n日志:%s" % (why, BOOTLOG))
        if tb_text:
            box.setDetailedText(tb_text[-2000:])
        box.setIcon(QMessageBox.Critical)
        box.setStyleSheet("QMessageBox{background:#1B1E25;} QLabel{color:#E9EDF5;font-size:12px;}"
                          "QPushButton{background:rgba(255,255,255,0.10);color:#E9EDF5;border:none;"
                          "border-radius:8px;padding:6px 16px;}")
        box.exec_()
    except Exception:
        pass
    sys.exit(9)


DANGER_WORDS = ("root", "刷", "edl", "9008", "抹", "格式化", "清空", "解bl",
                "twrp", "recovery", "降级", "wipe", "erase", "patch")
ANSI = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]|\x1b\][^\x07]*\x07")

# 引擎向导的三类信号(实测 menu.exe 的原始输出,见 2026-11-13 日志):
#   "  1. 是\r\n  2. 否\r\n选择: "   ← 选项行 + 无换行的「选择: 」
#   "请按任意键继续..."              ← pause,要敲回车
_OPT_LINE = re.compile(r"^(\d{1,3})[.、)]\s*(\S.*)$")
_LOOKS_PROMPT = re.compile(r"(选择|請選擇|请输入|請輸入)\s*[:：]?\s*$")
_ANYKEY = re.compile(r"(按任意键|按任意鍵|press any key)")


def _dec(b):
    """bat 打 GBK、progress.exe 打 UTF-8,同一股流里混着。逐行试,别整体猜。"""
    for enc in ("utf-8", "gbk"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    return b.decode("gbk", "replace")


# ---------------------------------------------------------------- 中文名表
# 引擎的菜单名是 A11 / appset / backup_9008 这种 bat 文件名,条目来源是 xxx.bat。
# 直接摊给用户就是"谁看得懂",这里一律换成人话:中文标题 + 一句话说明。
MENU_CN = {
    "main.json": ("主菜单", "一键 Root、进 RTOS、开 cmd、常用功能"),
    "commonly.json": ("常用功能", "一键 OTA、刷 TWRP、备份恢复、投屏"),
    "settings.json": ("工具箱设置", "快速启动、版本信息、重装驱动、强制更新"),
    "root.json": ("一键 Root(按机型)", "选型号后走完整 Root 流程"),
    "root-SDK25.json": ("Root · 老系统(SDK25)", "BOOT 方案或 Recovery 方案"),
    "scripttool.json": ("脚本工具", "型号对照表、导入 root 文件、读手表信息"),
    "scripttool-patchboot.json": ("修补 boot", "SDK27 / SDK25 / 狐狸面具"),
    "root_setting_mode.json": ("Root 后预装优化", "启用或跳过预装优化"),
    "root_setting_i3.json": ("Root 桌面版本", "130510 / 146000(Z12) / 123910"),
    "root_setting_lsp.json": ("Root 后预装框架", "预装 XP 框架或 LSP 框架"),
    "root_setting_root_manage.json": ("Root 面具类型", "普通面具或狐狸面具"),
    "root_setting_rootpro.json": ("Root 预装优化 · 增强", "启用或跳过"),
    "ota.json": ("离线 OTA 升级(按机型)", "选型号后拉 OTA 包升级"),
    "ota_mode.json": ("OTA 升级方式", "云服务拉取 / 手动选包 / 9008 进 QMMI"),
    "pashtwrp.json": ("推送 TWRP(按机型)", "把 TWRP 推到手表"),
    "rebtwrp.json": ("重启到 TWRP(按机型)", "重启并进入 TWRP"),
    "rebootpro.json": ("重启 / 进特殊模式", "系统、fastboot、recovery、9008、临时 TWRP"),
    "rebootpro_edl.json": ("进 9008(EDL)方式", "按版本高低选引导方式"),
    "qmmi.json": ("进 QMMI(按机型)", "进高通 QMMI 模式"),
    "super_rec_mode.json": ("超级恢复方式", "自动下载超级恢复 / 手动选包"),
    "miscre.json": ("Recovery 工具(按机型)", "按型号选 recovery 相关操作"),
    "nd03ver.json": ("ND03 固件版本", "281 / 302 Root 固件"),
    "A11.json": ("Android 11 机型选择", "Z10 / Z11(含少年版)"),
    "menu.json": ("机型选择", "按型号进入下一步"),
    "backup.json": ("备份与恢复", "相册、9008 分区、adb 分区"),
    "backup_9008.json": ("9008 分区备份(按机型)", "选型号后备份/恢复分区"),
    "backup_DCIM.json": ("相册备份选项", "启用或跳过备份相册"),
    "appset.json": ("应用管理", "安装、卸载、设置微信 QQ 自启"),
    "userinstapp.json": ("安装 APK", "单个 / 多个 / 整个文件夹"),
    "unapp.json": ("卸载应用", "查看包名后卸载"),
    "magisk.json": ("Magisk 模块管理", "刷入、列出、卸载模块"),
    "setmagisk-in.json": ("安装 Magisk 模块", "官方接口 / sh 模拟 / 强制安装"),
    "setmagisk-un.json": ("卸载 Magisk 模块", "标记卸载或直接删目录"),
    "modulestore.json": ("模块商店", "列出、搜索、关于"),
    "modulestore-list.json": ("模块商店 · 模块列表", "全部 / 开机动画 / 表盘 / 工具 / 字体"),
    "modulestore-search.json": ("模块商店 · 搜索", "按关键字搜模块"),
    "modulestore-about.json": ("模块商店 · 关于", "更新日志、捐赠、鸣谢"),
    "modulestore-other.json": ("模块商店 · 其他", "公告、帮助、作者排行"),
    "scrcpy-ui.json": ("投屏参数(scrcpy)", "控制、息屏、录音、录制等开关"),
    "wifiadb.json": ("无线 ADB", "连接 / 配对 / 有线转无线 / 关闭"),
    "debug.json": ("调试选项", "色卡、使用状态"),
    "rtos.json": ("RTOS 专区", "USB 当 U 盘、装应用、导出应用"),
    "rtos-at_tool.json": ("RTOS · AT 指令", "公用指令 / 私有指令"),
    "rtos-at_public.json": ("RTOS · 通用 AT 指令", "运营商、信号、附着状态"),
    "rtos-at_private.json": ("RTOS · 小天才私有 AT", "绑定号、机型、版本、电量"),
    "cloud.json": ("云端资源下载", "各机型 root 包、TWRP、驱动"),
    "isv3.json": ("确认(是/否)", "让脚本自己问的确认"),
    "yesno.json": ("确认(是/否)", "让脚本自己问的确认"),
    "run_cmd.json": ("确认(是/否)", "让脚本自己问的确认"),
}

# 功能库分组:顺序即展示顺序,没列进去的归到「其他」
LIB_GROUPS = [
    ("一键与常用", ["main.json", "commonly.json", "settings.json"]),
    ("Root 与权限", ["root.json", "root-SDK25.json", "scripttool.json",
                 "scripttool-patchboot.json", "root_setting_mode.json",
                 "root_setting_i3.json", "root_setting_lsp.json",
                 "root_setting_root_manage.json", "root_setting_rootpro.json"]),
    ("刷机 · 恢复", ["ota.json", "ota_mode.json", "pashtwrp.json", "rebtwrp.json",
                 "rebootpro.json", "rebootpro_edl.json", "qmmi.json",
                 "super_rec_mode.json", "miscre.json", "nd03ver.json",
                 "A11.json", "menu.json"]),
    ("备份", ["backup.json", "backup_9008.json", "backup_DCIM.json"]),
    ("应用", ["appset.json", "userinstapp.json", "unapp.json"]),
    ("模块", ["magisk.json", "setmagisk-in.json", "setmagisk-un.json",
            "modulestore.json", "modulestore-list.json", "modulestore-search.json",
            "modulestore-about.json", "modulestore-other.json"]),
    ("投屏 · 调试", ["scrcpy-ui.json", "wifiadb.json", "debug.json"]),
    ("RTOS 专区", ["rtos.json", "rtos-at_tool.json", "rtos-at_public.json",
                "rtos-at_private.json"]),
    ("云端资源", ["cloud.json"]),
    ("确认类", ["isv3.json", "yesno.json", "run_cmd.json"]),
]

# 云端资源的中文名(引擎清单里只有文件名)
RES_CN = {
    "userdata": ("系统分区镜像 userdata", "Root 必刷的精简 userdata 分区"),
    "systemui": ("系统 UI 补丁", "改状态栏 / 界面的 systemui 补丁"),
    "xtcpatch": ("核心破解补丁", "去掉签名校验的核心补丁"),
    "apks": ("预装 APK 合集", "Root 后一并装进去的应用"),
    "rootproapks": ("Root 增强 APK", "Root 后常用的工具集"),
    "twrp": ("TWRP 超级恢复", "刷机 / 救砖用的 recovery"),
    "drivers": ("Windows 驱动包", "9008 和 adb 驱动,电脑认不到设备先装它"),
    "xp": ("XP / LSP 框架组件", "XP 框架运行需要的文件"),
}

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

        # 高度按字体真实高度算(不是写死 58):系统缩放 125%/150% 时字号被放大,
        # 写死的高度会让标题钻进副标题、两行叠在一起看不清。
        need = max(t.sizeHint().height() + s.sizeHint().height() + 8,
                   arrow.sizeHint().height() + 10, 58)
        self.setFixedHeight(need)

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
        # 窗口别写死 1120×720:1366×768 的笔记本上会顶满屏幕,而且缩放后看着"巨大"。
        # 取屏幕可用区的 86%,再压到 1000×660 以内,居中。
        scr = QApplication.desktop().availableGeometry()
        w = max(880, min(1000, int(scr.width() * 0.86)))
        h = max(600, min(660, int(scr.height() * 0.86)))
        try:                                   # 记住上次窗口大小
            g = json.load(open(GEOM, encoding="utf-8"))
            w = max(820, min(int(g.get("w") or w), scr.width() - 40))
            h = max(540, min(int(g.get("h") or h), scr.height() - 40))
        except Exception:
            pass
        self.resize(w, h)
        self.move(scr.x() + (scr.width() - w) // 2, scr.y() + (scr.height() - h) // 2)
        self.setMinimumSize(820, 540)
        self.setMouseTracking(True)
        self._r_edge = None
        self._r_geo = None
        self._r_pos = None

        self._drag = None
        self._proc = None
        # 引擎向导状态:menu.exe 会把选项打成「  1. xxx」再打「选择: 」然后阻塞等 stdin。
        # 我们把它解析成按钮(见 _feed_menu_line),点一下就把按键写回管道。
        self._carry_raw = b""      # 未等到换行的半行(选择提示就是没有换行的)
        self._opts = []            # 当前菜单的 [(序号, 文字)]
        self._menu_on = False      # 是否已经把这个菜单做成按钮
        self._last_token = ""      # 已处理的向导请求号,防止同一菜单反复弹
        self._last_req_mtime = 0.0
        self._choice_token = ""
        from PyQt5.QtCore import QObject, pyqtSignal

        class _Sig(QObject):
            info = pyqtSignal(object)
            err = pyqtSignal(object)
            # ⚠ 后台线程只准 emit,绝不准直接碰控件(碰了 Qt 直接 qFatal,连 traceback 都没有)
            line = pyqtSignal(str)
            after = pyqtSignal(object)

        self._sigs = _Sig()
        self._sigs.info.connect(self._on_update_info)
        self._sigs.err.connect(self.show_error)
        self._sigs.line.connect(self._log)
        self._sigs.after.connect(self._after_bg)
        self._sig_info = self._sigs.info
        self._sig_err = self._sigs.err
        self._sig_line = self._sigs.line
        self._mode = "home"
        self._cur_menu = "main.json"
        self.data = json.load(open(ROUTES, encoding="utf-8"))
        self._build()
        if not ADMIN:
            self._limited()
        QTimer.singleShot(60, self._native)

    # -- 受限模式提示条(非管理员)
    def _limited(self):
        bar = QWidget()
        bar.setStyleSheet("background: rgba(255,176,64,0.16); border-radius:8px;")
        row = QHBoxLayout(bar)
        row.setContentsMargins(12, 7, 8, 7)
        row.setSpacing(10)
        t = QLabel("受限模式:当前没有管理员权限,刷写 / 驱动 / 端口占用类功能会失败")
        t.setStyleSheet("color:%s; font-size:11px;" % WARN)
        row.addWidget(t, 1)
        btn = QPushButton("以管理员身份重启")
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedHeight(24)
        btn.setStyleSheet("QPushButton{background:rgba(255,255,255,0.14);color:#E9EDF5;"
                          "border:none;border-radius:7px;padding:0 12px;font-size:11px;}"
                          "QPushButton:hover{background:rgba(255,255,255,0.24);}")
        btn.clicked.connect(self._elevate_restart)
        row.addWidget(btn)
        self.mid.insertWidget(self.mid.indexOf(self.title) + 2, bar)
        self._log("⚠ 受限模式:非管理员。需要刷机 / Root / 提权操作时,请点上面的「以管理员身份重启」。")

    def _elevate_restart(self):
        try:
            import ctypes
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, '"%s"' % os.path.join(HERE, "main.py"),
                ROOT, 1)
        except Exception as e:
            self.show_error(StarError("E0002", str(e)))
            return
        self.close()
        QTimer.singleShot(200, QApplication.instance().quit)

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
        up.clicked.connect(self._update_menu)
        self.up_btn = up
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
        self.mid = mid
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

        # 引擎向导的「选择」区 —— 引擎弹选项时这里长出按钮,不用再手打数字
        self.choice_host = QWidget()
        self.choice_host.setFixedWidth(330)
        self.choice_lay = QVBoxLayout(self.choice_host)
        self.choice_lay.setContentsMargins(0, 0, 0, 0)
        self.choice_lay.setSpacing(6)
        self.choice_host.setVisible(False)
        right.addWidget(self.choice_host)
        # 每 120ms 看一眼引擎有没有新菜单要问 —— 替身阻塞等我们写答案
        self._menu_timer = QTimer(self)
        self._menu_timer.setInterval(120)
        self._menu_timer.timeout.connect(self._poll_menu_req)
        self._menu_timer.start()

        self.stdin = QLineEdit()
        self.stdin.setPlaceholderText("输入给命令的内容,回车发送…")
        self.stdin.setFixedWidth(330)
        self.stdin.returnPressed.connect(self._send_stdin)
        self.stdin.setEnabled(False)
        self.stdin.setStyleSheet("""
            QLineEdit { background: rgba(255,255,255,0.05); color:#C3CDE0;
                border:1px solid rgba(255,255,255,0.08); border-radius:10px;
                padding:6px 10px; font-size:11px; }
            QLineEdit:disabled { color: rgba(255,255,255,0.25); }
        """)
        right.addWidget(self.stdin)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setFixedWidth(330)
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
        # 版本别写死:换引擎后忘了改就一直在左下角显示旧版本(用户已经看到过一次)
        l = QLabel("引擎:AllToolBox %s\nbin 未改动,仅替换菜单层" % resources.engine_version())
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
        # 首屏渲染放到窗口画出来之后:22 张卡片建一次要 0.7s,
        # 放在这之前会把"窗口出现"整体拖慢(实测 3.3s → 1.4s)。
        self.title.setText("Star All Tool Box")
        self.sub.setText("正在加载…")
        QTimer.singleShot(30, lambda: self._on_section("home"))

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
        # ⚠ 必须 setParent(None)+hide:只 takeAt 的话旧卡片虽然不在布局里,
        #   但仍然是 cards 的子控件,会留在原位继续重绘 —— 新卡片叠上去就成了「两层字叠印」。
        #   deleteLater 要等下一轮事件循环,下载输出很密时能卡住好几秒。
        while self.card_box.count() > 1:
            it = self.card_box.takeAt(0)
            w = it.widget()
            if w:
                w.hide()
                w.setParent(None)
                w.deleteLater()

    def _add_card(self, title, sub, danger=False, fn=None, wide=False):
        c = Card(title, sub, danger, (lambda: fn()) if fn else None)
        if wide:
            c.setFixedHeight(max(c.height(), 64))
        self.card_box.insertWidget(self.card_box.count() - 1, c)
        c.show()          # 清空卡片后立即重建时,不显式 show 会闪一帧空白
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
        self._add_card("检查工具更新(StarATB 本体)",
                       "查这个工具箱自己的新版本 —— 和手表模块的版本是两回事",
                       False, self._check_app_update)
        self._add_card("查看 Star OS 模块版本",
                       "看手表模块线上最新版(3.0.4 这种),和模块里那套 update.json 一致",
                       False, self._check_update)
        self._add_card("云端资源补全",
                       "%d 项未下载 —— bin 不全时在这里补齐" % miss,
                       False, lambda: self._on_section("res"))
        self._add_card("开发者平台",
                       "登录 / 上传模块 / 上传表盘 / 开发文档(原开发者平台整页)",
                       False, lambda: self._on_section("dev"))
        # 1.4.6 新增:Root 安装选项 / 修补 boot / 超级恢复 / 运行命令
        for menu, title, sub in (
            ("root_setting_mode.json", "Root 安装选项",
             "桌面版本 / XP 或 LSP 框架 / 面具类型 / root 后预装优化"),
            ("scripttool-patchboot.json", "修补 boot",
             "SDK25 / SDK27 / SDK27 狐狸面具,内置 patch_boot.exe"),
            ("super_rec_mode.json", "超级恢复",
             "自动下载固件包,或手动选择固件/超级恢复镜像"),
            ("run_cmd.json", "运行命令",
             "把手表当 shell 用,命令直接透传(带 adb 环境)"),
        ):
            if menu in self.data["menus"]:
                self._add_card("新 · " + title, sub, False,
                               lambda m=menu: self.goto_menu(m))
        for o in self.data["menus"].get("main.json", []):
            if o["hidden"]:
                continue
            act = self.data["routes"].get("main.json", {}).get(o["value"], {})
            self._add_card(o["label"], runner.describe(act, "main.bat"),
                           any(w in o["label"].lower() for w in DANGER_WORDS),
                           lambda oo=o, aa=act: self._click_item(oo, aa))

    def _add_section(self, text):
        l = QLabel(text)
        l.setStyleSheet("color:%s; font-size:10px; letter-spacing:3px;"
                        "padding:10px 4px 2px 4px;" % TEXT_DIM)
        self.card_box.insertWidget(self.card_box.count() - 1, l)
        l.show()

    def _render_library(self):
        self._clear_cards()
        self.title.setText("功能库")
        total = sum(len([x for x in v if not x["hidden"]]) for v in self.data["menus"].values())
        self.sub.setText("%d 个功能菜单 · 共 %d 个操作,按类别排好;点进去就是具体命令"
                         % (len(self.data["menus"]), total))
        done = set()

        def one(name):
            opts = [x for x in self.data["menus"].get(name, []) if not x["hidden"]]
            if not opts:
                return
            title, desc = MENU_CN.get(name, (name.replace(".json", ""), "共 %d 项" % len(opts)))
            self._add_card(title, "%s · %d 项" % (desc, len(opts)), False,
                           lambda n=name: self.goto_menu(n))
            done.add(name)

        for gname, names in LIB_GROUPS:
            hit = [n for n in names if n in self.data["menus"]]
            if not hit:
                continue
            self._add_section(gname)
            for n in hit:
                one(n)
        rest = [n for n in sorted(self.data["menus"]) if n not in done]
        if rest:
            self._add_section("其他")
            for n in rest:
                one(n)

    def _render_resources(self):
        self._clear_cards()
        ok, part, miss = resources.summary()
        self.title.setText("云端资源")
        self.sub.setText("%d 项已就位 · %d 项还没下 · 从 cdn.alltoolbox.app 下载,"
                         "自动放到引擎要的位置" % (ok, miss))
        order = {"Root 组件": 0, "资源": 1}
        last = None
        for key, fname, name, grp, xdir, move in sorted(
                resources.CATALOG, key=lambda c: (order.get(c[3], 9), c[0])):
            st, path, size = resources.local_state(key)
            cn, why = RES_CN.get(key, (None, None))
            if not cn:
                if re.match(r"^[A-Z]{1,3}\d{2}[A-Z]?$", key):
                    cn, why = "机型 %s 刷机包" % key, "这个型号的固件 / 资源包"
                else:
                    cn, why = name, "引擎要的资源文件"
            g = {"Root 组件": "Root 必需组件",
                 "资源": "刷机 · 机型资源"}.get(grp, grp or "其他")
            if g != last:
                self._add_section(g)
                last = g
            if st == "ok":
                tail = "已就位 · %.1f MB" % (size / 1048576.0)
            elif st == "zip-only":
                tail = "已下载,点一下解压安装"
            else:
                tail = "未下载 · 点一下开始下载"
            self._add_card(cn, "%s · %s" % (why, tail), False,
                           lambda k=key: self._download_res(k))

    # ---- 后台任务:所有界面操作一律排队回主线程 ----
    def _bg(self, job, after=None):
        """在工作线程跑 job(cb):cb 是安全的行回调,收尾(after)也回主线程执行。

        ⚠ 这是唯一允许的跨线程方式。直接在线程里 appendPlainText / 加卡片,
          PyQt5 会 qFatal 秒退(无 traceback、boot.log 里什么都留不下)。
        """
        def fin(err):
            if err:
                self._sig_err.emit(err)
            if after:
                self._sigs.after.emit(after)

        resources.run_async(job, self._sig_line.emit, fin)

    def _after_bg(self, what):
        if what == "res":
            self._render_resources()
        elif what == "home":
            self._on_section("home")
        elif what == "refresh":
            self._on_section(self._mode)

    def _download_res(self, key):
        key = key[0] if isinstance(key, (list, tuple)) else key
        _k, fname, name, _g, xdir, move = resources.BY_KEY[key]
        st, path, _s = resources.local_state(key)
        if st == "ok":
            self._log("[资源] %s 已就位" % name)
            return
        if st == "zip-only":
            # 包已经在本地:只搬/解压,绝不重下(以前这里又走 download,几十 MB 白下)
            self._bg(lambda cb: resources.install_zip(key, cb), "res")
            return
        if not self._confirm("下载资源 %s(约几十 MB)" % name):
            return
        self._log("")
        self._log("▶ 下载 %s (%s)" % (name, fname))

        def job(cb):
            resources.download(key, cb)

        self._bg(job, "res")

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
                if st == "zip-only":
                    resources.install_zip(k, cb)
                    continue
                resources.download(k, cb)

        self._bg(job, "res")

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
            cb("[StarOS] 完成,建议重启手表")

        self._bg(job, "home")

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
        self._clear_cards()
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
        self._clear_cards()
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
        l.show()

    # -- 执行
    def _run(self, act, label, value=""):
        src = self.data["sources"].get(self._cur_menu, "")
        line = runner.build(self._cur_menu, value, act, src)
        if not line:
            self._log("[不可直连] %s —— 这一项属于上层流程里的子步骤,"
                      "请从对应父菜单进入" % label)
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
        # ⚠⚠ 不能把带引号的一整行直接丢给 cmd /c:QProcess 会再套一层引号,
        #   cmd 对 \" 的解析历来错乱,实测报「文件名、目录名或卷标语法不正确」。
        #   落一个临时 bat 再执行,彻底绕开转义。
        try:
            if not os.path.isdir(LOGDIR):
                os.makedirs(LOGDIR)
            with open(RUNBAT, "w", encoding="gbk", errors="replace",
                      newline="\r\n") as f:
                f.write("@echo off\n")
                # ⚠⚠ 必须开延迟展开:引擎里 link.bat 用 !filename! 拼 URL,
                #   原来是靠 双击运行.exe 那边开的;我们直接调子脚本时没开,
                #   URL 就变成 https://cdn.alltoolbox.app/!userdata! ⇒ aria2 退出码 3(资源未找到)。
                f.write("setlocal EnableDelayedExpansion\n")
                f.write(line + "\n")
        except Exception as e:
            self._log("[E9000] 无法生成临时脚本:%s" % e)
            return
        p = QProcess(self)
        p.setWorkingDirectory(BIN)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PATH", BIN + ";" + env.value("PATH", ""))
        env.insert("PYTHONIOENCODING", "gbk")
        env.insert("STARATB_MENU_GUI", "1")   # 让 menu.exe 替身走界面通道
        p.setProcessEnvironment(env)
        p.setProcessChannelMode(QProcess.MergedChannels)
        p.readyReadStandardOutput.connect(lambda: self._drain(p))
        p.finished.connect(lambda c, s: self._done(c))
        p.errorOccurred.connect(lambda e: self._log("[启动失败] %s" % e))
        # 换任务 ⇒ 上一个向导的候选/按钮全部作废
        self._opts = []
        self._carry_raw = b""
        self._last_token = ""
        self._last_req_mtime = 0.0
        self._choice_token = ""
        self._hide_choices()
        try:
            os.makedirs(GUI_DIR, exist_ok=True)
            for f in (MENU_REQ, MENU_ANS):
                if os.path.exists(f):
                    os.remove(f)
        except Exception:
            pass
        p.start("cmd", ["/c", RUNBAT])
        self._proc = p
        self.stop_btn.setEnabled(True)
        self.stdin.setEnabled(True)
        self.stdin.setFocus()

    def _drain(self, p):
        # 引擎里 bat 是 GBK 编码、progress.exe 输出的是 UTF-8,同一股流里混着来。
        # 按行各自判断编码,才不会出现「姝 e 漆锷犳祰」这种火星文。
        raw = self._carry_raw + bytes(p.readAllStandardOutput())
        blines = re.split(rb"\r\n|\n|\r", raw)
        self._carry_raw = blines.pop() if blines else b""
        for bline in blines:
            if not bline.strip():
                continue
            ln = _dec(bline).rstrip()
            ln = ANSI.sub("", ln).rstrip()
            if ln:
                self._log(ln)
                self._feed_menu_line(ln)
        # menu.exe 打「选择: 」时**不带换行**,所以这一行永远留在 carry 里等不到 \r\n。
        # 不主动看它,按钮就永远出不来 —— 这就是「点了没反应」的真正原因。
        tail = self._carry_raw.strip()
        if tail:
            ln = ANSI.sub("", _dec(self._carry_raw)).strip()
            if _LOOKS_PROMPT.search(ln):
                self._log(ln)
                self._carry_raw = b""
                self._feed_menu_line(ln)

    # -- 把引擎的文本菜单变成按钮 ----------------------------------------
    def _feed_menu_line(self, ln):
        s = ln.strip()
        m = _OPT_LINE.match(s)
        if m:
            num, label = m.group(1), m.group(2).strip()
            for i, (n0, l0) in enumerate(self._opts):
                if n0 == num:
                    if l0 != label:        # 同一序号换了文字 ⇒ 是另一个菜单,重来
                        self._opts = [(num, label)]
                    return
            self._opts.append((num, label))
            return
        if not s:
            return
        if _ANYKEY.search(s):
            # 原版这里是「请按任意键继续」,要敲一下回车 —— 自动敲,并留一行记录
            self._send_raw("")
            return
        if _LOOKS_PROMPT.search(s):
            if self._opts:
                self._show_choices(s, list(self._opts))
            else:
                # 没有选项的输入提示(如「请输入机型」)⇒ 直接把焦点给输入框
                self._hint_stdin(s)
            return

    def _hint_stdin(self, prompt):
        if not self._proc:
            return
        self.stdin.setEnabled(True)
        self.stdin.setFocus()
        self.stdin.setPlaceholderText(prompt[:24])

    def _show_choices(self, prompt, opts, mode="num", token=""):
        """opts: [(key, label)]。mode=num 走 stdin 敲数字,mode=val 写给 menu.exe 替身。"""
        if not self._proc:
            return
        self._menu_on = True
        self._opts = []
        self._choice_token = token
        while self.choice_lay.count():
            it = self.choice_lay.takeAt(0)
            w = it.widget()
            if w:
                w.hide()
                w.setParent(None)
                w.deleteLater()
        head = QLabel(prompt.rstrip(": ：") or "请选择")
        head.setStyleSheet("color:#FFD08A; font-size:11px; padding-left:2px;")
        head.setWordWrap(True)
        self.choice_lay.addWidget(head)
        for i, (key, label) in enumerate(opts, 1):
            b = QPushButton(("%d   %s" % (i, label)) if mode != "num" else ("%s   %s" % (key, label)))
            b.setCursor(Qt.PointingHandCursor)
            b.setToolTip(label)
            b.setStyleSheet("""
                QPushButton { background: rgba(120,170,255,0.16); color:#DCE6FA; border:none;
                    border-radius:9px; padding:8px 11px; font-size:11px; text-align:left; }
                QPushButton:hover { background: rgba(120,170,255,0.34); }
                QPushButton:pressed { background: rgba(120,170,255,0.5); }
            """)
            b.clicked.connect(lambda _=False, k=key: self._pick(k, mode))
            self.choice_lay.addWidget(b)
        self.choice_host.setVisible(True)
        self.stdin.setPlaceholderText("也可以直接输入后回车…")

    def _pick(self, key, mode="num"):
        self._hide_choices()
        if mode == "val":
            self._answer_menu(key)
        else:
            self._send_raw(str(key))

    def _answer_menu(self, value):
        """把选择写给 menu.exe 替身(它阻塞在 _gui\\req.txt 对应的答案上)。"""
        if not self._choice_token:
            self._send_raw(str(value))
            return
        try:
            tmp = MENU_ANS + ".tmp"
            with open(tmp, "w", encoding="utf-8", newline="\n") as f:
                f.write("%s\n%s\n" % (self._choice_token, value))
            os.replace(tmp, MENU_ANS)
            self._log("→ 选择 %s" % value)
        except Exception as e:
            self._log("[回传失败] %s" % e)

    def _poll_menu_req(self):
        """menu.exe 替身把选项写进 _gui\\req.txt,这里读出来做成按钮。"""
        if not self._proc:
            return
        try:
            mtime = os.path.getmtime(MENU_REQ)
        except OSError:
            return
        if mtime == self._last_req_mtime:
            return
        try:
            lines = io.open(MENU_REQ, encoding="utf-8", errors="replace").read().split("\n")
        except Exception:
            return
        if len(lines) < 3:
            return
        token, title = lines[0].strip(), lines[1].strip()
        if token == self._last_token:
            return
        self._last_req_mtime = mtime
        self._last_token = token
        opts = []
        for ln in lines[2:]:
            if not ln.strip():
                continue
            v, _, lb = ln.partition("\t")
            opts.append((v, lb or v))
        if title == "__PAUSE__":
            # 引擎的 pause.exe:显示一个「继续」,0.4 秒后自动点掉(相当于原版敲任意键)
            self._show_choices("继续", opts, "val", token)
            QTimer.singleShot(400, lambda t=token: self._auto_continue(t))
            return
        if opts:
            self._show_choices(title or "请选择", opts, "val", token)

    def _auto_continue(self, token):
        if self._choice_token == token and self._proc:
            self._pick("ok", "val")

    def _hide_choices(self):
        self._menu_on = False
        self.choice_host.setVisible(False)
        while self.choice_lay.count():
            it = self.choice_lay.takeAt(0)
            w = it.widget()
            if w:
                w.hide()
                w.setParent(None)
                w.deleteLater()

    def _send_raw(self, text):
        if not self._proc:
            return
        try:
            self._proc.write((text + "\r\n").encode("gbk", "replace"))
        except Exception as e:
            self._log("[发送失败] %s" % e)
            return
        self._log("→ " + (text if text else "(回车)"))

    def _done(self, code):
        self._log("■ 结束 (exit %d)" % code)
        self._proc = None
        self._opts = []
        self._carry_raw = b""
        self._hide_choices()
        self.stop_btn.setEnabled(False)
        self.stdin.setEnabled(False)
        self._poll_device()

    def _kill(self):
        if self._proc:
            self._proc.kill()
            self._proc = None
            self.stop_btn.setEnabled(False)
            self.stdin.setEnabled(False)
            self._opts = []
            self._carry_raw = b""
            self._hide_choices()
            self._log("■ 已中止")

    def _send_stdin(self):
        if not self._proc:
            return
        text = self.stdin.text()
        self.stdin.clear()
        self._send_raw(text)

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
    def _update_menu(self):
        """顶栏「检查更新」:以前这里**直接查手表模块**的 update.json,
        所以在工具里看到 3.0.4/vc35,很容易以为查的是工具自己。
        现在给两个入口,谁也别猜。
        """
        m = QMenu(self)
        m.setStyleSheet("QMenu{background:#1B1E25;border:1px solid rgba(255,255,255,0.12);"
                        "border-radius:8px;padding:6px;}"
                        "QMenu::item{color:#E9EDF5;padding:7px 24px;border-radius:6px;"
                        "font-size:12px;}"
                        "QMenu::item:selected{background:rgba(91,157,255,0.28);color:#fff;}")
        a1 = m.addAction("检查工具更新(StarATB 本体)")
        a2 = m.addAction("查看 Star OS 模块版本")
        pos = self.up_btn.mapToGlobal(QPoint(0, self.up_btn.height() + 4))
        act = m.exec_(pos)
        if act == a1:
            self._check_app_update()
        elif act == a2:
            self._check_update()

    def _check_app_update(self):
        """查 StarATB 自己 —— 以前这里查的是手表模块的 update.json,容易误会。"""
        from threading import Thread
        import version
        self._log("正在检查 StarATB 本体更新(当前 v%s / vc%d)…"
                  % (version.APP_VERSION, version.APP_VC))
        local = (version.APP_VERSION, version.APP_VC)

        def job():
            try:
                from core import updater
                self._sig_info.emit({"_kind": "app", "online": updater.read_app_manifest(),
                                     "local": local})
            except StarError as e:
                self._sig_err.emit(e)
            except Exception as e:
                self._sig_err.emit(StarError("E9000", str(e)))

        Thread(target=job, daemon=True).start()

    def _show_app_update(self, d):
        import version
        lv, lvc = d["local"]
        on = d.get("online") or {}
        ov = on.get("version")
        ovc = int(on.get("versionCode") or 0)
        self._log("本体:当前 v%s · 线上 %s" % (lv, ("v%s (vc%d)" % (ov, ovc)) if ov else "查不到"))
        box = QMessageBox(self)
        box.setWindowTitle("StarATB 本体更新")
        if not ov:
            box.setText("当前版本:v%s (vc%d)" % (lv, lvc))
            box.setInformativeText("查不到线上清单 —— 仓库里还没有 version.json,或者网络不通。\n"
                                   "这不影响使用。")
        elif ovc > lvc:
            box.setText("有新版本:v%s (vc%d) → v%s (vc%d)" % (lv, lvc, ov, ovc))
            box.setInformativeText("%s\n\n下载:%s"
                                   % (on.get("notes", ""),
                                      on.get("url") or "仓库 Releases 页"))
        else:
            box.setText("已是最新:v%s (vc%d)" % (lv, lvc))
            box.setInformativeText("线上也是 v%s (vc%d)。" % (ov, ovc))
        box.setIcon(QMessageBox.Information)
        box.setStyleSheet("QMessageBox{background:#1B1E25;} QLabel{color:#E9EDF5;font-size:12px;}"
                          "QPushButton{background:rgba(255,255,255,0.10);color:#E9EDF5;border:none;"
                          "border-radius:8px;padding:6px 16px;}")
        box.exec_()

    def _check_update(self):
        from threading import Thread
        self._log("正在检查更新…")

        def job():
            try:
                from core import updater   # 延迟导入:urllib+email 要 0.4s,启动时用不到
                info = updater.latest(0)      # 0 = 永远取到线上最新,仅用于展示
                self._sig_info.emit(info or {})
            except StarError as e:
                self._sig_err.emit(e)
            except Exception as e:            # 兜底,绝不让异常冒到线程外
                self._sig_err.emit(StarError("E9000", str(e)))

        Thread(target=job, daemon=True).start()

    def _on_update_info(self, info):
        if isinstance(info, dict) and info.get("_kind") == "app":
            return self._show_app_update(info)
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

    def closeEvent(self, e):
        # ⚠ 关窗时先收掉子进程:QProcess 活着被析构会 qFatal,进程无声退出(exit 127)
        try:
            if self._proc:
                self._proc.kill()
                self._proc.waitForFinished(2000)
        except Exception:
            pass
        super(MainWindow, self).closeEvent(e)

    def _edge_at(self, pos):
        e = 9
        x, y = pos.x(), pos.y()
        w, h = self.width(), self.height()
        left, right, top, bot = x <= e, x >= w - e, y <= e, y >= h - e
        if top and left:
            return "tl"
        if top and right:
            return "tr"
        if bot and left:
            return "bl"
        if bot and right:
            return "br"
        if left:
            return "l"
        if right:
            return "r"
        if top:
            return "t"
        if bot:
            return "b"
        return None

    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        edge = self._edge_at(e.pos())
        if edge:
            self._r_edge = edge
            self._r_geo = self.geometry()
            self._r_pos = e.globalPos()
            return
        if e.pos().y() < 60:
            self._drag = e.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._r_edge:
            d = e.globalPos() - self._r_pos
            g = self._r_geo
            x, y, w, h = g.x(), g.y(), g.width(), g.height()
            mw, mh = self.minimumWidth(), self.minimumHeight()
            if "l" in self._r_edge:
                nw = max(mw, w - d.x())
                x, w = x + (w - nw), nw
            if "r" in self._r_edge:
                w = max(mw, w + d.x())
            if "t" in self._r_edge:
                nh = max(mh, h - d.y())
                y, h = y + (h - nh), nh
            if "b" in self._r_edge:
                h = max(mh, h + d.y())
            self.setGeometry(x, y, w, h)
            return
        if self._drag and e.buttons() & Qt.LeftButton:
            self.move(e.globalPos() - self._drag)
            return
        cur = {"tl": Qt.SizeFDiagCursor, "br": Qt.SizeFDiagCursor,
               "tr": Qt.SizeBDiagCursor, "bl": Qt.SizeBDiagCursor,
               "l": Qt.SizeHorCursor, "r": Qt.SizeHorCursor,
               "t": Qt.SizeVerCursor, "b": Qt.SizeVerCursor}.get(self._edge_at(e.pos()))
        self.setCursor(cur or Qt.ArrowCursor)

    def mouseReleaseEvent(self, e):
        if self._r_edge:
            self._r_edge = None
            self._save_geo()
        self._drag = None

    def _save_geo(self):
        try:
            with open(GEOM, "w", encoding="utf-8") as f:
                json.dump({"w": self.width(), "h": self.height()}, f)
        except Exception:
            pass

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
    # 非管理员不再直接退出(之前正是这条让窗口"一闪而过"),
    # 改成受限模式:主界面照常打开,顶栏挂一条提示,刷写类动作再拦截。
    return admin


def _single_instance_gate(app):
    """只允许一个窗口。已有实例就把它的窗口抬到前面,然后本进程退出。

    ⚠ 用户双击两次(或上次没关干净)时,两个一模一样的窗口叠在一起,
      看起来就像「文字两层叠印」——比任何排版 bug 都更容易被当成界面坏了。
    返回 (is_first, server)。
    """
    try:
        from PyQt5.QtNetwork import QLocalServer, QLocalSocket
    except Exception:
        return True, None
    key = "StarATB-single"
    sock = QLocalSocket()
    sock.connectToServer(key)
    if sock.waitForConnected(150):
        sock.write(b"show")
        sock.flush()
        sock.waitForBytesWritten(300)
        sock.disconnectFromServer()
        _log("已有实例在运行,已叫它到前台,本进程退出")
        return False, None
    QLocalServer.removeServer(key)
    srv = QLocalServer()
    srv.listen(key)
    _log("单实例锁已建立")
    return True, srv


def main():
    global ADMIN
    _log("---- 启动 pid=%s argv=%s" % (os.getpid(), sys.argv))

    def _hook(t, v, tb):
        txt = "".join(traceback.format_exception(t, v, tb))
        _log("未捕获异常:\n" + txt)
        _die("程序内部出错了(E9000)", "%s: %s" % (t.__name__, v), txt)
        os._exit(9)

    sys.excepthook = _hook

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei UI", 9))
    _log("Qt 已起,版本 %s" % app.applicationVersion() or "-")

    first, srv = _single_instance_gate(app)
    if not first:
        # 已有实例:照样告诉启动器「这次启动被正常处理了」,不然 bat 会白等 20 秒再报错
        try:
            with open(FLAG, "w", encoding="utf-8") as f:
                f.write("already-running")
        except Exception:
            pass
        return

    try:
        ADMIN = bool(preflight())
    except StarError as e:
        _die("%s · %s" % (e.code, e.info.title), "%s\n建议:%s" % (e.info.why, e.info.fix))
    _log("preflight ok, admin=%s" % ADMIN)
    w = MainWindow()
    w.show()
    _log("窗口已显示(自本模块导入起 %.2fs)" % (time.perf_counter() - _T0))

    if srv is not None:
        def on_conn():
            while srv.hasPendingConnections():
                c = srv.nextPendingConnection()
                if c:
                    c.waitForReadyRead(100)
                    c.readAll()
                    c.disconnectFromServer()
                w.showNormal()
                w.raise_()
                w.activateWindow()

        srv.newConnection.connect(on_conn)

    try:
        with open(FLAG, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
    except Exception:
        pass
    sys.exit(app.exec_())



if __name__ == "__main__":
    main()
