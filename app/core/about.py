#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""关于页 —— 版本、致谢、诊断信息。

致谢分两栏:
  特别鸣谢  给对这个项目有决定性帮助的人(排第一)
  致谢      给上游作者与开源组件
"""

APP_NAME = "Star All Tool Box"
APP_VER = "0.1.0"
APP_VC = 1

SPECIAL = [
    ("小公爵", "特别鸣谢 —— 在这个项目从命令行走向图形界面的过程中给出的关键帮助"),
]

THANKS = [
    ("xgj_236", "AllToolBox 原作者,本项目的引擎与流程来自他的 AllToolBox 1.2.7ultra"),
    ("Magisk / topjohnwu", "模块化与 boot 补丁方案"),
    ("scrcpy / Genymobile", "投屏组件"),
    ("aria2", "多线程下载引擎"),
    ("Qt / PyQt5", "界面框架"),
]

DISCLAIMER = (
    "本工具涉及 Root、刷机等高风险操作,可能造成设备无法开机、数据丢失、失去保修。\n"
    "所有操作由你自行决定并承担后果;请务必先备份,并确认机型与固件版本匹配。"
)


def about_text(toolbox_ver=None, engine_ver=None, device=None):
    lines = ["%s %s" % (APP_NAME, APP_VER), ""]
    if engine_ver:
        lines.append("引擎:AllToolBox %s" % engine_ver)
    if toolbox_ver:
        lines.append("外壳:%s" % toolbox_ver)
    if device:
        lines.append("设备:%s" % device)
    lines.append("")
    lines.append("——— 特别鸣谢 ———")
    for who, why in SPECIAL:
        lines.append("%s   %s" % (who, why))
    lines.append("")
    lines.append("——— 致谢 ———")
    for who, why in THANKS:
        lines.append("%s   %s" % (who, why))
    lines.append("")
    lines.append("——— 免责声明 ———")
    lines.append(DISCLAIMER)
    return "\n".join(lines)
