#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""更新器 —— 与 Star OS 模块**同一套逻辑**。

同一套的意思不是"长得像",而是:
  * 同样的清单格式(version / versionCode / zipUrl / changelog)
  * 同样的双通道(正式 / beta),取 versionCode 更高的那个
  * 同样的多镜像兜底:主域名优先,后面挂 GitHub raw / jsDelivr
  * 同样用 versionCode 比较,而不是字符串比版本号

清单示例:
    { "version": "3.0.4", "versionCode": 35,
      "zipUrl": "https://.../x.zip", "changelog": "https://.../changelog.md" }
"""
import hashlib
import json
import os
import ssl
import urllib.error
import urllib.request

from .errors import StarError

UA = "StarATB/0.1 (Windows)"

# 主域名在前,后面挂镜像兜底(和模块里 mirrorUrls 的顺序一致)
STABLE_URLS = [
    "https://staros.lqbz.dpdns.org/upd",
    "https://cdn.jsdelivr.net/gh/lqbz6office/star-os-assets@main/update.json",
    "https://raw.githubusercontent.com/lqbz6office/star-os-assets/main/update.json",
]
BETA_URLS = [
    "https://staros.lqbz.dpdns.org/beta",
    "https://cdn.jsdelivr.net/gh/lqbz6office/star-os-beta@main/update.json",
    "https://raw.githubusercontent.com/lqbz6office/star-os-beta/main/update.json",
]
# Star All Tool Box 自己的清单 —— 和手表模块那套 update.json 完全两码事
APP_URLS = [
    "https://staros.lqbz.dpdns.org/gh/lqbz6office/star-all-toolbox/main/version.json",
    "https://cdn.jsdelivr.net/gh/lqbz6office/star-all-toolbox@main/version.json",
    "https://raw.githubusercontent.com/lqbz6office/star-all-toolbox/main/version.json",
]


def _ctx():
    try:
        return ssl.create_default_context()
    except Exception:
        return None


def fetch(url, timeout=12):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ctx()) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        raise StarError("E2002", "%s -> HTTP %d" % (url, e.code))
    except urllib.error.URLError as e:
        raise StarError("E2001", "%s -> %s" % (url, e.reason))
    except Exception as e:
        raise StarError("E2001", "%s -> %s" % (url, e))


def urls_for(channel):
    return list(BETA_URLS if channel == "beta" else STABLE_URLS)


def read_app_manifest():
    """读 StarATB 自己的 version.json;全镜像都失败返回 None(不算错误)。"""
    for url in APP_URLS:
        try:
            raw = fetch(url, timeout=8)
            data = json.loads(raw.decode("utf-8", "replace"))
        except Exception:
            continue
        if isinstance(data, dict) and data.get("versionCode"):
            data["_source"] = url
            return data
    return None


def read_manifest(channel="stable"):
    """按镜像顺序试,第一个解析成功的就用;全失败抛 E2004。"""
    last = None
    for url in urls_for(channel):
        try:
            raw = fetch(url)
        except StarError as e:
            last = e
            continue
        try:
            data = json.loads(raw.decode("utf-8", "replace"))
        except Exception as e:
            last = StarError("E5001", "%s -> %s" % (url, e))
            continue
        if "version" not in data or "versionCode" not in data:
            last = StarError("E5002", url)
            continue
        data["_source"] = url
        data["_channel"] = channel
        return data
    raise last or StarError("E2004")


def latest(local_vc, allow_beta=True):
    """取两个通道里 versionCode 更高的那条;不比本地新就返回 None。"""
    cands = []
    try:
        cands.append(read_manifest("stable"))
    except StarError:
        if not allow_beta:
            raise
    if allow_beta:
        try:
            cands.append(read_manifest("beta"))
        except StarError:
            pass
    if not cands:
        raise StarError("E2004")
    best = max(cands, key=lambda d: int(d.get("versionCode") or 0))
    if int(best.get("versionCode") or 0) <= int(local_vc):
        return None
    return best


def download(url, dest, sha256=None, on_progress=None):
    """带进度与校验的下载;校验失败抛 E2003。"""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + ".part"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    h = hashlib.sha256()
    got = 0
    try:
        with urllib.request.urlopen(req, timeout=30, context=_ctx()) as r:
            total = int(r.headers.get("Content-Length") or 0)
            with open(tmp, "wb") as f:
                while True:
                    chunk = r.read(262144)
                    if not chunk:
                        break
                    f.write(chunk)
                    h.update(chunk)
                    got += len(chunk)
                    if on_progress:
                        on_progress(got, total)
    except StarError:
        raise
    except Exception as e:
        raise StarError("E2005", "%s -> %s" % (url, e))
    if sha256 and h.hexdigest().lower() != sha256.lower():
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise StarError("E2003", "期望 %s… 实际 %s…" % (sha256[:12], h.hexdigest()[:12]))
    os.replace(tmp, dest)
    return got
