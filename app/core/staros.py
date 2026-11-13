#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""一键安装最新版 Star OS(离线包)。

为什么要离线包:模块的 online 包(400KB)是"装的时候再去下载 200MB 资源",
手表那点网速和免费 CDN 速度加起来要好几分钟,而且中途断网就废。
离线包(full,203MB)把 payload 全打进去,adb 推过去一次装完,不依赖手表联网。

流程(和原版 instmodule.bat 的 magisk 分支一致,只是换成原生):
    清单 → 拼出 full.zip(网关 → GitHub → jsDelivr 三个来源轮着试)
    → 下载(tmp/staros/,带断点续传和百分比)
    → 校验(zip 里必须有 module.prop 和 META-INF)
    → adb push /sdcard/temp_module.zip
    → adb shell su -c 'magisk --install-module ...'
    → 收尾:删临时包,提示重启
"""
import io
import os
import re
import subprocess
import zipfile

from . import updater
from .errors import StarError

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BIN = os.path.join(ROOT, "StarATB", "bin")
ADB = os.path.join(BIN, "adb.exe")
TMP = os.path.join(ROOT, "tmp", "staros")
REPO = "lqbz6office/star-os-assets"


def plan(channel="stable"):
    """返回 {version, versionCode, name, urls[], size} —— 只读清单,不下载。"""
    info = updater.read_manifest(channel)
    ver = info.get("version")
    if not ver:
        raise StarError("E5001")
    name = "zz_star_os-%s-full.zip" % ver
    tag = "v" + ver
    urls = [
        "https://staros.lqbz.dpdns.org/rel/%s/%s/%s" % (REPO, tag, name),
        "https://github.com/%s/releases/download/%s/%s" % (REPO, tag, name),
        "https://hub.gitmirror.com/https://github.com/%s/releases/download/%s/%s"
        % (REPO, tag, name),
    ]
    return {"version": ver, "versionCode": info.get("versionCode"),
            "name": name, "urls": urls, "channel": channel,
            "online": info.get("zipUrl", "")}


def _env():
    e = dict(os.environ)
    e["PATH"] = BIN + os.pathsep + e.get("PATH", "")
    return e


def adb(*args, **kw):
    """跑 adb,返回 (rc, 输出)。超时给 60s。"""
    p = subprocess.Popen([ADB] + list(args), cwd=BIN, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, env=_env(),
                         creationflags=0x08000000 if os.name == "nt" else 0)
    try:
        out, _ = p.communicate(timeout=kw.get("timeout", 90))
    except subprocess.TimeoutExpired:
        p.kill()
        out, _ = p.communicate()
    return p.returncode, out.decode("gbk", "replace").strip()


def devices():
    rc, out = adb("devices")
    rows = []
    for ln in out.splitlines():
        ln = ln.strip()
        # adb 起服务时会往 stdout 打 "* daemon not running..." 这类提示,得跳过
        if not ln or ln.startswith("*") or ln.lower().startswith(("list of", "adb server")):
            continue
        parts = ln.split()
        if len(parts) >= 2:
            rows.append((parts[0], parts[1]))
    return rows


def ensure_device():
    rows = devices()
    if not rows:
        raise StarError("E1001")
    state = rows[0][1]
    if state != "device":
        raise StarError("E1002", "当前状态:" + state)
    return rows[0][0]


def server_version():
    """手表上模块的版本(读 /data/adb/modules/zz_star_os/module.prop)。"""
    rc, out = adb("shell", "su -c 'cat /data/adb/modules/zz_star_os/module.prop'")
    if rc != 0 or "version" not in out:
        return None
    m = re.search(r"^version=(.+)$", out, re.M)
    return m.group(1).strip() if m else None


def _download(url, dest, cb, total_hint=0):
    """带断点续传的下载,返回字节数。优先 aria2c(快),失败退回 urllib。"""
    if os.path.isfile(dest) and total_hint and os.path.getsize(dest) == total_hint:
        cb("[StarOS] 已有完整离线包,跳过下载")
        return total_hint
    size = os.path.getsize(dest) if os.path.isfile(dest) else 0
    cmd = [os.path.join(BIN, "progress.exe"), "aria2c.exe",
           "--conf-path=./settings/aria2c.conf",
           "--continue=true", "--auto-file-renaming=false",
           "--out=" + os.path.basename(dest),
           "--dir=" + os.path.dirname(dest), url]
    cb("[StarOS] 开始下载 %s" % os.path.basename(dest))
    env = _env()
    p = subprocess.Popen(cmd, cwd=os.path.dirname(dest), stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, env=env,
                         creationflags=0x08000000 if os.name == "nt" else 0)
    last = -1
    ansi = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")
    for raw in iter(p.stdout.readline, b""):
        line = ansi.sub("", raw.decode("gbk", "replace")).rstrip()
        m = re.search(r"\((\d{1,3})%\)", line)
        if m:
            pct = int(m.group(1))
            if pct // 5 != last // 5:
                last = pct
                cb("  下载 %d%%" % pct)
    p.wait()
    if p.returncode != 0 or not os.path.isfile(dest):
        raise StarError("E2003", "aria2c 退出码 %s" % p.returncode)
    cb("  下载完成 %s" % _size(os.path.getsize(dest)))
    return os.path.getsize(dest)


def _size(n):
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024 or u == "GB":
            return "%.1f%s" % (n, u)
        n /= 1024.0


def check_zip(path):
    try:
        z = zipfile.ZipFile(path)
        names = z.namelist()
    except Exception as e:
        raise StarError("E3001", str(e))
    need = ["module.prop", "META-INF/com/google/android/update-binary"]
    miss = [n for n in need if n not in names]
    if miss:
        raise StarError("E3002", "缺少 " + ", ".join(miss))
    prop = z.read("module.prop").decode("utf-8", "replace")
    ver = re.search(r"^version=(.+)$", prop, re.M)
    verc = re.search(r"^versionCode=(\d+)$", prop, re.M)
    return {"version": ver.group(1).strip() if ver else "?",
            "versionCode": int(verc.group(1)) if verc else 0,
            "files": len(names)}


def install(cb, channel="stable", reboot=False, force=False):
    """一条龙:查清单 → 下载 → 校验 → 推送安装。"""
    info = plan(channel)
    cb("[StarOS] 线上最新 %s (vc%s),通道 %s" % (info["version"], info["versionCode"], channel))
    dev = ensure_device()
    cb("[StarOS] 设备 %s 已连接" % dev)
    cur = server_version()
    if cur:
        cb("[StarOS] 设备当前版本 %s" % cur)
        if cur == info["version"] and not force:
            cb("[StarOS] 已是最新,无需安装(需要重装请在设置里开强制)")
            return {"skipped": True, "version": cur}
    os.makedirs(TMP, exist_ok=True)
    dest = os.path.join(TMP, info["name"])
    err = None
    for u in info["urls"]:
        try:
            cb("[StarOS] 来源:%s" % u.split("/")[2])
            _download(u, dest, cb)
            err = None
            break
        except StarError as e:
            err = e
            cb("[StarOS] 该来源失败(%s),换下一个" % e.info.title)
    if err:
        raise err
    meta = check_zip(dest)
    cb("[StarOS] 校验通过:%s (vc%s) %d 个文件" % (meta["version"], meta["versionCode"], meta["files"]))
    if meta["version"] != info["version"]:
        cb("[StarOS] 注意:包内版本 %s 与清单 %s 不一致" % (meta["version"], info["version"]))

    cb("[StarOS] 推送安装包到手表…")
    rc, out = adb("push", dest, "/sdcard/temp_module.zip", timeout=300)
    if rc != 0:
        raise StarError("E1004", out[-300:])
    cb("[StarOS] 调用 Magisk 安装…")
    rc, out = adb("shell", "su -c 'magisk --install-module /sdcard/temp_module.zip'; echo rc=$?",
                  timeout=600)
    cb(out[-1500:] if out else "")
    if "rc=0" not in out:
        raise StarError("E3004", out[-300:])
    adb("shell", "rm -f /sdcard/temp_module.zip")
    cb("[StarOS] 安装完成,模块已写入 /data/adb/modules/zz_star_os")
    if reboot:
        cb("[StarOS] 重启设备…")
        adb("reboot")
    return {"version": meta["version"], "versionCode": meta["versionCode"]}


def install_online(cb, channel="stable"):
    """online 包(400KB):手表自己联网补资源,适合网络好的时候。"""
    info = plan(channel)
    dev = ensure_device()
    cb("[StarOS] 设备 %s,准备 online 包 %s" % (dev, info["version"]))
    os.makedirs(TMP, exist_ok=True)
    url = info["online"]
    name = url.rsplit("/", 1)[-1] or ("zz_star_os-%s-online.zip" % info["version"])
    dest = os.path.join(TMP, name)
    _download(url, dest, cb)
    meta = check_zip(dest)
    rc, out = adb("push", dest, "/sdcard/temp_module.zip", timeout=180)
    if rc != 0:
        raise StarError("E1004", out[-300:])
    rc, out = adb("shell", "su -c 'magisk --install-module /sdcard/temp_module.zip'; echo rc=$?",
                  timeout=300)
    cb(out[-1200:])
    if "rc=0" not in out:
        raise StarError("E3004", out[-300:])
    return {"version": meta["version"]}
