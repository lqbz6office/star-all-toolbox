#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""关于页 —— 版本、致谢、诊断信息。

致谢分两栏:
  特别鸣谢  给对这个项目有决定性帮助的人(排第一)
  致谢      给上游作者与开源组件
"""

APP_NAME = "Star All Tool Box"
# 版本号只有一处来源:app/version.py。写两份必然对不上(关于页曾显示 0.1.0、
# 检查更新却显示 1.0.0),所以这里直接读。
try:                              # app/ 在 sys.path 里
    from version import APP_VC, APP_VERSION as APP_VER
except Exception:                 # 单独跑这个文件的兜底
    APP_VER, APP_VC = "1.0.0", 1

SPECIAL = [
    ("小公爵(xgj_236)", "特别鸣谢 —— AllToolBox 的作者,也是这个项目的引擎与全部流程的来源;"
                        "从命令行走向图形界面的过程中给了关键帮助"),
]

THANKS = [
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
