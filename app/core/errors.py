#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""错误码体系 —— 每一条错误都有号码、中文标题、原因、处置建议。

为什么不直接用异常信息:用户看的是"我该干什么",不是 traceback。
所有对外可见的错误都必须从这里取,禁止裸抛。
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Err:
    code: str
    title: str
    why: str
    fix: str


_TABLE = {
    # ---------------- 环境 0xxx
    "E0001": Err("E0001", "当前系统不受支持", "本工具依赖 Windows 的 adb 与批处理环境",
                 "请在 Windows 10/11 上运行"),
    "E0002": Err("E0002", "没有管理员权限", "刷机、驱动、端口占用都需要管理员身份",
                 "右键 → 以管理员身份运行"),
    "E0003": Err("E0003", "引擎目录不完整", "找不到 StarATB\\bin 或其中的 adb.exe",
                 "确认 bin 目录没有被移动、杀毒软件没有隔离文件"),
    "E0004": Err("E0004", "文件被占用", "另一个 adb / 工具箱进程正占用同一个文件",
                 "关闭其它工具箱窗口或任务管理器里结束 adb.exe 后重试"),
    "E0005": Err("E0005", "磁盘空间不足", "下载与解包至少需要 2GB 可用空间",
                 "清理磁盘后重试"),

    # ---------------- 设备 1xxx
    "E1001": Err("E1001", "没有检测到设备", "adb 列表为空,或手表没开 USB 调试",
                 "手表打开「开发者选项 → USB 调试」,换条数据线再插一次"),
    "E1002": Err("E1002", "设备未授权", "手表上没有点「允许」,或授权记录已失效",
                 "看手表屏幕点允许;不行就在开发者选项里撤销授权后重插"),
    "E1003": Err("E1003", "连接了多台设备", "同时插了多台手表,命令不知道发给谁",
                 "只保留一台设备"),
    "E1004": Err("E1004", "adb 无法启动", "adb.exe 缺失、被杀毒拦截或端口 5037 被占用",
                 "关闭占用 5037 端口的程序,或把 bin 目录加入杀毒白名单"),
    "E1005": Err("E1005", "设备连接超时", "线材接触不良、驱动异常,或手表进入休眠",
                 "换 USB 口 / 数据线,保持手表亮屏后再试"),
    "E1006": Err("E1006", "设备型号不在支持列表", "当前机型没有对应的分区表或 root 方案",
                 "先在「关于」里反馈机型与系统版本"),

    # ---------------- 网络 / 下载 2xxx
    "E2001": Err("E2001", "网络不可用", "无法解析或连接下载服务器",
                 "检查网络与代理设置"),
    "E2002": Err("E2002", "下载服务器返回错误", "服务器 4xx/5xx,或资源已被移除",
                 "换一个下载源,或稍后再试"),
    "E2003": Err("E2003", "下载文件校验失败", "文件在传输中被截断或被代理替换",
                 "删除 tmp 目录下同名文件后重新下载"),
    "E2004": Err("E2004", "所有下载源都失败了", "内置的多个镜像均不可达",
                 "挂代理,或在设置里手动指定镜像"),
    "E2005": Err("E2005", "下载中断", "网络波动或连接被重置",
                 "支持断点续传,直接重试即可"),

    # ---------------- 刷写 / Root 3xxx
    "E3001": Err("E3001", "该机型暂不支持一键 Root", "boot 分区结构与已知方案不匹配",
                 "改用「超级恢复」或联系作者补充机型"),
    "E3002": Err("E3002", "分区不匹配", "刷入的镜像与设备分区大小不一致",
                 "确认机型与固件版本后再刷,切勿强行继续"),
    "E3003": Err("E3003", "镜像文件损坏", "boot.img / userdata.img 校验失败",
                 "删除后重新下载,不要用断点未完成的文件"),
    "E3004": Err("E3004", "刷写失败", "fastboot / EDL 返回失败状态",
                 "保持连接不要拔线,重新进入对应模式再刷一次"),
    "E3005": Err("E3005", "Bootloader 未解锁", "设备拒绝写入分区",
                 "先完成解锁流程"),
    "E3006": Err("E3006", "Root 后系统未起来", "Magisk 补丁与当前固件冲突",
                 "进入恢复流程回滚,或改装稳定版 Magisk"),
    "E3007": Err("E3007", "EDL 模式未进入", "9008 端口没有出现",
                 "按住按键顺序重新进入,或检查驱动是否装好"),

    # ---------------- 模块 / 应用 4xxx
    "E4001": Err("E4001", "应用安装失败", "签名冲突、空间不足,或系统限制",
                 "先卸载旧版本,或确认包名是否被系统保护"),
    "E4002": Err("E4002", "应用卸载失败", "该应用是系统应用或正在运行",
                 "用「系统应用管理」的强制卸载路径"),
    "E4003": Err("E4003", "Magisk 模块不兼容", "模块的模板版本高于本机 Magisk",
                 "升级 Magisk 或改用兼容版本模块"),
    "E4004": Err("E4004", "设备未安装 Magisk", "所有模块操作都依赖 Magisk 环境",
                 "先执行「一键 Root」"),
    "E4005": Err("E4005", "模块安装后未生效", "模块已放入目录但没有启用",
                 "重启设备,或到 Magisk 里手动启用"),

    # ---------------- 更新 5xxx
    "E5001": Err("E5001", "更新清单解析失败", "服务器返回的不是合法 JSON",
                 "稍后重试;若持续失败,说明镜像被劫持,换官方源"),
    "E5002": Err("E5002", "清单版本信息异常", "缺少 version 或 versionCode 字段",
                 "联系作者修复发布产物"),
    "E5003": Err("E5003", "更新包不完整", "下载体积与清单声明不一致",
                 "删除后重新下载"),
    "E5004": Err("E5004", "已是最新版本", "当前 versionCode 不低于清单",
                 "无需操作"),

    # ---------------- 兜底 9xxx
    "E9000": Err("E9000", "未知错误", "未归类的异常,详情见日志",
                 "把日志面板内容反馈给作者"),
}


class StarError(Exception):
    """所有可预期错误都用它抛出,界面直接拿 code 查表显示。"""

    def __init__(self, code, detail="", cause=None):
        self.code = code
        self.info = _TABLE.get(code, _TABLE["E9000"])
        self.detail = detail
        self.cause = cause
        super().__init__("%s %s" % (self.code, self.info.title))

    def text(self, with_detail=True):
        parts = ["[%s] %s" % (self.code, self.info.title),
                 "原因:%s" % self.info.why,
                 "建议:%s" % self.info.fix]
        if with_detail and self.detail:
            parts.append("详情:%s" % self.detail)
        return "\n".join(parts)

    def one_line(self):
        return "[%s] %s —— %s" % (self.code, self.info.title, self.info.fix)


def lookup(code):
    return _TABLE.get(code, _TABLE["E9000"])


def guard():
    """把没预料到的异常统一折成 E9000,保证界面上永远是一句人话。"""
    import functools
    import traceback

    def deco(fn):
        @functools.wraps(fn)
        def wrap(*a, **kw):
            try:
                return fn(*a, **kw)
            except StarError:
                raise
            except Exception as e:
                raise StarError("E9000", "%s: %s" % (type(e).__name__, e),
                                cause=traceback.format_exc()) from e
        return wrap
    return deco
