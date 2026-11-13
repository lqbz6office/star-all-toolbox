#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""液态玻璃视觉层 —— Windows 原生亚克力 + 自绘玻璃面板。

为什么不用贴图:模糊必须来自"桌面实际内容",贴图一闪就穿帮。
这里走 Windows 自己的合成器(SetWindowCompositionAttribute / DWM),
所以窗口背后是什么,玻璃里就透出什么,是活的。

参考的公开实现思路:
  * SetWindowCompositionAttribute 的 ACCENT_ENABLE_ACRYLICBLURBEHIND
    (Win10 1803+ 引入,Win11 继续可用)
  * Win11 的 DWMWA_WINDOW_CORNER_PREFERENCE 圆角
  * 玻璃拟态的分层:底色 alpha / 顶部高光 / 1px 描边 / 内阴影
"""
import ctypes
from ctypes import wintypes

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import (QColor, QLinearGradient, QPainter, QPainterPath,
                         QPen, QRadialGradient)
from PyQt5.QtWidgets import QWidget

IS_WIN = hasattr(ctypes, "windll")

# ---------------------------------------------------------------- 调色板
INK = QColor(23, 25, 31, 224)          # 玻璃底色(带 alpha,模糊才能透出来)
INK_SOFT = QColor(255, 255, 255, 14)   # 面板填充
LINE = QColor(255, 255, 255, 28)       # 描边
LINE_HI = QColor(255, 255, 255, 54)    # 顶部高光描边
TEXT = "#EDF0F6"
TEXT_DIM = "#9BA4B6"
ACCENT = "#5B9DFF"
OK = "#43D6A0"
WARN = "#F5B254"
DANGER = "#FF6B6B"


class _AccentPolicy(ctypes.Structure):
    _fields_ = [("AccentState", ctypes.c_int),
                ("AccentFlags", ctypes.c_int),
                ("GradientColor", ctypes.c_uint),
                ("AnimationId", ctypes.c_int)]


class _WinCompAttrData(ctypes.Structure):
    _fields_ = [("Attribute", ctypes.c_int),
                ("Data", ctypes.c_void_p),
                ("SizeOfData", ctypes.c_size_t)]


ACCENT_ENABLE_BLURBEHIND = 3
ACCENT_ENABLE_ACRYLICBLURBEHIND = 4
WCA_ACCENT_POLICY = 19


def apply_acrylic(hwnd, tint=(23, 25, 31), alpha=0x99):
    """把窗口背后变成磨砂玻璃。失败(老系统/非 Win)返回 False,上层退回纯色。"""
    if not IS_WIN or not hwnd:
        return False
    try:
        # GradientColor 是 AABBGGRR
        grad = (alpha << 24) | (tint[2] << 16) | (tint[1] << 8) | tint[0]
        for state in (ACCENT_ENABLE_ACRYLICBLURBEHIND, ACCENT_ENABLE_BLURBEHIND):
            policy = _AccentPolicy(state, 0x20 | 0x40 | 0x80, grad, 0)
            data = _WinCompAttrData(WCA_ACCENT_POLICY, ctypes.cast(
                ctypes.pointer(policy), ctypes.c_void_p),
                ctypes.sizeof(_AccentPolicy))
            res = ctypes.windll.user32.SetWindowCompositionAttribute(
                wintypes.HWND(int(hwnd)), ctypes.byref(data))
            if res:
                return True
    except Exception:
        pass
    return False


def apply_round_corners(hwnd, radius=2):
    """Win11 圆角偏好:1=圆角 2=更圆 3=直角。失败忽略。"""
    if not IS_WIN or not hwnd:
        return
    try:
        pref = ctypes.c_int(radius)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            wintypes.HWND(int(hwnd)), 33, ctypes.byref(pref), ctypes.sizeof(pref))
    except Exception:
        pass


def enable_shadow(hwnd):
    """给无边框窗口恢复系统投影(靠一个 1px 的 DWM 边框骗出来)。"""
    if not IS_WIN or not hwnd:
        return
    try:
        margins = ctypes.c_int * 4
        m = margins(-1, -1, -1, -1)
        ctypes.windll.dwmapi.DwmExtendFrameIntoClientArea(
            wintypes.HWND(int(hwnd)), ctypes.byref(m))
    except Exception:
        pass


# ---------------------------------------------------------------- 绘制
def glass_path(rect: QRectF, radius: float) -> QPainterPath:
    p = QPainterPath()
    p.addRoundedRect(rect, radius, radius)
    return p


def paint_glass(widget: QWidget, radius=18, tint=None, fill=18, border=True):
    """给任意 widget 画一层玻璃:底色 + 顶部高光 + 内阴影 + 描边。"""
    p = QPainter(widget)
    p.setRenderHints(QPainter.Antialiasing)
    r = QRectF(widget.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
    path = glass_path(r, radius)
    p.setClipPath(path)

    base = QColor(tint) if tint else QColor(255, 255, 255, fill)
    if not tint:
        base.setAlpha(fill)
    p.fillPath(path, base)

    # 顶部高光:模拟斜上方光源在玻璃表面的反射
    g = QLinearGradient(QPointF(r.topLeft()), QPointF(r.left(), r.bottom()))
    g.setColorAt(0.0, QColor(255, 255, 255, 42))
    g.setColorAt(0.35, QColor(255, 255, 255, 10))
    g.setColorAt(1.0, QColor(255, 255, 255, 0))
    p.fillPath(path, g)

    # 左上角那一小团镜面光斑(液态玻璃的"液"就在这)
    rg = QRadialGradient(QPointF(r.left() + r.width() * 0.18, r.top() - r.height() * 0.1),
                         r.width() * 0.75)
    rg.setColorAt(0.0, QColor(255, 255, 255, 34))
    rg.setColorAt(0.55, QColor(255, 255, 255, 6))
    rg.setColorAt(1.0, QColor(255, 255, 255, 0))
    p.fillPath(path, rg)
    p.setClipping(False)

    if border:
        p.setPen(QPen(LINE, 1))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
        # 上边缘一条更亮的细线,玻璃的"边"
        p.setPen(QPen(LINE_HI, 1))
        p.drawLine(QPointF(r.left() + radius * 0.6, r.top() + 0.5),
                   QPointF(r.right() - radius * 0.6, r.top() + 0.5))
    p.end()


class GlassPanel(QWidget):
    """一块玻璃面板。子控件照常往里加。"""

    def __init__(self, parent=None, radius=16, fill=16, tint=None):
        super().__init__(parent)
        self._radius = radius
        self._fill = fill
        self._tint = tint
        self.setAttribute(Qt.WA_StyledBackground, False)

    def paintEvent(self, e):
        paint_glass(self, self._radius, self._tint, self._fill)


def paint_root(widget: QWidget, radius=22):
    """整窗玻璃底。独立函数 —— 不要在子类里直接调用另一个类的 paintEvent,
    那样会踩 self._radius 这种"父类私有属性"的坑,异常在绘制期抛出会被
    PyQt5 直接 qFatal(进程无声退出)。"""
    p = QPainter(widget)
    p.setRenderHints(QPainter.Antialiasing)
    r = QRectF(widget.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
    path = glass_path(r, radius)
    p.setClipPath(path)
    p.fillPath(path, INK)

    g = QLinearGradient(QPointF(r.topLeft()), QPointF(r.bottomLeft()))
    g.setColorAt(0.0, QColor(255, 255, 255, 26))
    g.setColorAt(0.22, QColor(255, 255, 255, 6))
    g.setColorAt(1.0, QColor(0, 0, 0, 26))
    p.fillPath(path, g)
    p.setClipping(False)

    p.setPen(QPen(QColor(255, 255, 255, 46), 1))
    p.setBrush(Qt.NoBrush)
    p.drawPath(path)
    p.end()


class GlassRoot(QWidget):
    """主窗口的玻璃底:整窗一块大圆角玻璃。"""

    def __init__(self, parent=None, radius=22):
        super().__init__(parent)
        self._radius = radius

    def paintEvent(self, e):
        paint_root(self, self._radius)
