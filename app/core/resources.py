#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""云端资源层 —— 复刻 AllToolBox 1.4.6 的下载逻辑,原生实现。

原版逻辑(全部读自 bin 里的脚本,不是猜的):

    settings/link.txt      ← 资源站基址(1.4.6 起是 https://cdn.alltoolbox.app/)
    cloud_toolbox.txt      ← 「文件 -> 目标路径」清单(Root 组件,放到 tmp/)
    cloud_other.txt        ← 「名字 文件 解压到<目录>」清单(TWRP/驱动/各机型)
    link.bat               ← 资源短名 → 文件名
    curltool.bat           ← progress.exe aria2c.exe --conf-path=./settings/aria2c.conf
    curltool.bat           ← 还把 aria2 的 1~32 号退出码翻译成中文提示(1.4.6 新增)
    7z.exe x <file> -o<dir> -aoa
    settings/dirs_conf.txt ← 需要预先存在的目录列表

1.2.7 的清单是硬编码在 bat 里的,1.4.6 抽成了两个 txt —— 所以我们**直接读这两个 txt**,
以后作者加资源也不用改代码。1.2.7 的清单作为兜底保留。
"""
import io
import os
import re
import subprocess
import threading

from .errors import StarError

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BIN = os.path.join(ROOT, "StarATB", "bin")
LINK_TXT = os.path.join(BIN, "settings", "link.txt")
TOOLBOX_TXT = os.path.join(BIN, "cloud_toolbox.txt")
OTHER_TXT = os.path.join(BIN, "cloud_other.txt")
DIRS_TXT = os.path.join(BIN, "settings", "dirs_conf.txt")

# curltool.bat 里的 aria2 退出码表(1.4.6 才有,照抄)
ARIA2_CODES = {
    1: "发生未知错误", 2: "发生超时", 3: "未找到资源", 4: "文件未找到次数超限",
    5: "下载速度低于下限而中止", 6: "发生网络问题", 7: "存在未完成的下载",
    8: "远程服务器不支持断点续传", 9: "磁盘空间不足", 10: "分片长度与控制文件不一致",
    11: "正在下载相同的文件", 13: "文件已存在", 14: "重命名文件失败",
    15: "无法打开已存在的文件", 16: "无法创建或截断文件", 17: "文件 I/O 错误",
    18: "无法创建目录", 19: "域名解析失败", 20: "连接失败",
    22: "HTTP 响应头异常", 23: "重定向过多", 24: "HTTP 认证失败",
}

# 1.2.7 的兜底清单(新版的 txt 缺失时用)
FALLBACK = [
    ("userdata.img", "Root 组件", "tmp", "userdata 镜像"),
    ("apks.zip", "Root 组件", "", "预装 apks"),
    ("systemui.zip", "Root 组件", "tmp", "系统 UI 补丁"),
    ("xtcpatch.zip", "Root 组件", "tmp", "核心破解补丁"),
    ("rootproapks.zip", "Root 组件", "", "Root 增强 apk"),
    ("twrp.zip", "刷机", "EDL", "TWRP / 超级恢复"),
    ("drivers.zip", "刷机", "", "Windows 驱动包"),
    ("xp.zip", "XP 框架", "tmp", "XP 框架组件"),
]


def _read(path):
    try:
        return io.open(path, encoding="gbk", errors="replace").read()
    except Exception:
        return ""


def _norm(p):
    """把 .\\tmp\\ 这种相对路径换成相对 bin 的干净路径。"""
    p = (p or "").strip().strip('"').replace("/", "\\")
    p = p.lstrip(".\\").rstrip("\\")
    return p


def _parse_file(path, group):
    """解析 cloud_*.txt → [(key, 文件名, 显示名, 解压目录, 移动目标, 说明)]"""
    rows = []
    for ln in _read(path).splitlines():
        ln = ln.strip()
        if not ln or "->" not in ln and "解压到" not in ln:
            continue
        m = re.match(r"^(\S+)\s+(\S+\.(?:zip|img))\s*(.*)$", ln, re.I)
        if not m:
            m2 = re.match(r"^(\S+\.(?:zip|img))\s*(.*)$", ln, re.I)
            if not m2:
                continue
            name, rest = m2.group(1), m2.group(2)
            label = m2.group(1)
        else:
            label, name, rest = m.group(1), m.group(2), m.group(3)
        rest = rest.strip()
        if not rest.startswith("->"):
            rest = rest.split("->", 1)[-1].strip()
        else:
            rest = rest[2:].strip()
        rest = rest.replace("解压到", "").strip()
        key = os.path.splitext(name)[0]
        if name.lower().endswith(".img"):
            # 镜像一律是「搬到某处」
            rows.append((key, name, label, "", _norm(rest) or name, group))
            continue
        last = _norm(rest)
        if last.lower().endswith(".zip"):
            rows.append((key, name, label, "", last, group))       # 只挪位置
        else:
            rows.append((key, name, label, last, "", group))       # 解压到目录
    return rows


def _build_catalog():
    rows = []
    rows += _parse_file(TOOLBOX_TXT, "Root 组件")
    rows += _parse_file(OTHER_TXT, "资源")
    if not rows:
        rows = [(os.path.splitext(f)[0], f, os.path.splitext(f)[0], d, "", g)
                for f, g, d, _n in FALLBACK]
    seen, out = set(), []
    for key, name, label, xdir, move, group in rows:
        if key.lower() in seen:
            continue
        seen.add(key.lower())
        out.append((key, name, label, group, xdir, move))
    return out


CATALOG = _build_catalog()          # [(key, 文件名, 显示名, 分组, 解压目录, 移动目标)]
BY_KEY = {c[0]: c for c in CATALOG}


def base_url():
    for ln in _read(LINK_TXT).splitlines():
        ln = ln.strip()
        if ln.startswith("http"):
            return ln if ln.endswith("/") else ln + "/"
    raise StarError("E2001", LINK_TXT)


def url_of(key):
    if key not in BY_KEY:
        raise StarError("E9000", "未知资源 " + str(key))
    return base_url() + BY_KEY[key][1]


def target_of(key):
    """资源最终该落在哪(用于"是否已就位"判断)。"""
    _k, fname, _l, _g, xdir, move = BY_KEY[key]
    if move:
        return os.path.join(BIN, move)
    if xdir:
        return os.path.join(BIN, xdir)
    return os.path.join(BIN, os.path.splitext(fname)[0])


def local_state(key):
    """'ok' 就位 / 'zip-only' 只有包 / 'missing' 没有。"""
    _k, fname, _l, _g, xdir, move = BY_KEY[key]
    zpath = os.path.join(BIN, fname)
    tgt = target_of(key)
    if move:
        if os.path.isfile(tgt):
            return "ok", tgt, os.path.getsize(tgt)
        if os.path.isfile(zpath):
            return "zip-only", zpath, os.path.getsize(zpath)
        return "missing", "", 0
    if os.path.isdir(tgt) and os.listdir(tgt):
        return "ok", tgt, _du(tgt)
    if os.path.isfile(zpath):
        return "zip-only", zpath, os.path.getsize(zpath)
    return "missing", "", 0


def _du(path):
    total = 0
    for base, _d, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(base, f))
            except OSError:
                pass
    return total


def summary():
    rows = [local_state(c[0])[0] for c in CATALOG]
    return rows.count("ok"), rows.count("zip-only"), rows.count("missing")


def ensure_dirs(cb=None):
    """create the dirs listed in settings/dirs_conf.txt (原版启动时会建)."""
    made = []
    for ln in _read(DIRS_TXT).splitlines():
        rel = _norm(ln)
        if not rel:
            continue
        p = os.path.join(BIN, rel)
        if not os.path.isdir(p):
            try:
                os.makedirs(p, exist_ok=True)
                made.append(rel)
            except Exception:
                pass
    if made and cb:
        cb("[资源] 已创建目录: " + ", ".join(made))
    return made


# ------------------------------------------------------------------ 执行
ANSI = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")


def _dec(raw):
    """引擎里两套编码并存:bat 输出是 GBK,progress.exe 的进度条是 UTF-8。
    先按 UTF-8 严格解,失败再退回 GBK —— 不然进度条会全变乱码。"""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("gbk", "replace")


def _popen(cmd, cb):
    """逐行/逐段回调。⚠ progress.exe 的进度条用 \r 刷新,不按 \n 换行,
    只 readline 会一直卡到进程结束 —— 所以按 \r 和 \n 都切。"""
    env = dict(os.environ)
    env["PATH"] = BIN + os.pathsep + env.get("PATH", "")
    p = subprocess.Popen(cmd, cwd=BIN, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, env=env,
                         creationflags=0x08000000 if os.name == "nt" else 0)
    buf = b""
    while True:
        chunk = p.stdout.read(4096)
        if not chunk:
            break
        buf += chunk
        parts = re.split(rb"[\r\n]", buf)
        buf = parts.pop()
        for raw in parts:
            line = ANSI.sub("", _dec(raw)).strip()
            if line and cb:
                cb(line)
    if buf.strip() and cb:
        cb(ANSI.sub("", _dec(buf)).strip())
    p.wait()
    return p.returncode


def download(key, cb=None, extract=True):
    fname, name = BY_KEY[key][1], BY_KEY[key][2]
    _k, _f, _l, _g, xdir, move = BY_KEY[key]
    url = base_url() + fname
    ensure_dirs()
    if cb:
        cb("[资源] 开始下载 %s (%s)" % (name, fname))
    rc = _popen([os.path.join(BIN, "progress.exe"), "aria2c.exe",
                 "--conf-path=./settings/aria2c.conf", url], cb)
    if rc != 0:
        raise StarError("E2003", "%s:%s(aria2 退出码 %s)" %
                        (name, ARIA2_CODES.get(rc, "未知错误"), rc))
    zpath = os.path.join(BIN, fname)
    if not os.path.isfile(zpath):
        raise StarError("E2004", name)

    if extract:
        if move and not move.lower().endswith(".zip"):
            dest = os.path.join(BIN, move)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            if os.path.abspath(dest) != os.path.abspath(zpath):
                os.replace(zpath, dest)
            if cb:
                cb("[资源] %s → %s" % (fname, move))
        elif xdir is not None and not move:
            out_dir = os.path.join(BIN, xdir) if xdir else BIN
            os.makedirs(out_dir, exist_ok=True)
            if cb:
                cb("[资源] 解压 %s → %s" % (fname, xdir or "bin/"))
            rc = _popen([os.path.join(BIN, "7z.exe"), "x", fname,
                         "-o" + out_dir, "-aoa", "-bsp1"], cb)
            if rc != 0:
                raise StarError("E2005", "%s(7z 退出码 %s)" % (name, rc))
        mark(fname)
    if cb:
        cb("[资源] %s 就绪" % name)
    return zpath


def mark(fname):
    """写 settings/resversion.txt,和原版 resvertool set 等价。"""
    try:
        path = os.path.join(BIN, "settings", "resversion.txt")
        cur = {}
        if os.path.isfile(path):
            for ln in _read(path).splitlines():
                if "=" in ln:
                    a, b = ln.split("=", 1)
                    cur[a.strip()] = b.strip()
        cur[fname] = "999999"
        with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
            for a, b in cur.items():
                fh.write("%s=%s\n" % (a, b))
    except Exception:
        pass


def run_async(fn, cb, done=None):
    def wrapper():
        try:
            fn(cb)
            done and done(None)
        except StarError as e:
            done and done(e)
        except Exception as e:
            done and done(StarError("E9000", str(e)))
    t = threading.Thread(target=wrapper, daemon=True)
    t.start()
    return t

# --------------------------------------------------- cloud.bat 的值 → 资源
def link_map():
    """link.bat 里的 短名 → 文件名(Z1=I16.zip)。"""
    txt = _read(os.path.join(BIN, "link.bat"))
    out = {}
    for short, fname in re.findall(r'set\s+"([\w\-]+)=(\S+\.(?:zip|img))"', txt, re.I):
        out[short.lower()] = fname
    return out


def _key_of_link(name, lmap):
    """把 link.bat 的短名/文件名统一成 CATALOG 的 key。"""
    if name in BY_KEY:
        return name
    fname = lmap.get(name.lower(), "")
    if fname:
        stem = os.path.splitext(fname)[0]
        for k, c in BY_KEY.items():
            if c[1].lower() == fname.lower() or k.lower() == stem.lower():
                return k
    return None


def cloud_map():
    """解析 cloud.bat:菜单值 → [资源 key]。

    cloud.bat 的写法是
        for %%i in (%menu) do ( if %%i==1 ( call :toolbox ) ... )
        :toolbox ... call :userdata / call :apks ...
        :Z1 ... call link Z1 url
    它自己会 `del menutmp.txt` 再调 menu.exe,所以"写菜单值"这条路对它无效 ——
    只能把映射抽出来,直接调我们自己的下载器。段可以嵌套,所以递归展开。
    """
    txt = _read(os.path.join(BIN, "cloud.bat"))
    if not txt:
        return {}
    lmap = link_map()
    sec_keys, sec_calls = {}, {}
    cur = None
    for ln in txt.splitlines():
        m = re.match(r"^:([\w\-]+)\s*$", ln.strip())
        if m:
            cur = m.group(1).lower()
            sec_keys.setdefault(cur, [])
            sec_calls.setdefault(cur, [])
            continue
        if cur is None:
            continue
        for k in re.findall(r"call\s+link\s+([\w\-]+)\s+url", ln, re.I):
            k = _key_of_link(k, lmap) or k
            if k in BY_KEY and k not in sec_keys[cur]:
                sec_keys[cur].append(k)
        for lb in re.findall(r"call\s+:([\w\-]+)", ln, re.I):
            if lb.lower() not in sec_calls[cur]:
                sec_calls[cur].append(lb.lower())

    def expand(label, depth=0, seen=None):
        seen = seen or set()
        if label in seen or depth > 4:
            return []
        seen.add(label)
        keys = list(sec_keys.get(label, []))
        for sub in sec_calls.get(label, []):
            for k in expand(sub, depth + 1, seen):
                if k not in keys:
                    keys.append(k)
        return keys

    out = {}
    for val, body in re.findall(r"if\s+%%i==(\d+)\s*\(([\s\S]*?)\)\s*else", txt + "\nelse"):
        labels = re.findall(r"call\s+:([\w\-]+)", body, re.I)
        keys = []
        for lb in labels:
            for k in expand(lb.lower()):
                if k not in keys:
                    keys.append(k)
        if keys:
            out[val] = keys
    return out
