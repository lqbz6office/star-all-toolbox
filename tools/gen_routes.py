#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""从 bat + menu/*.json 生成 GUI 路由表。

思路:每个 bat 里的 `menu.exe menu\\X.json` 之后紧跟若干
`if "%MENU%"=="K" ... call <脚本> / goto <标签>` —— 这就是「键 -> 动作」。
把这些抽出来, GUI 就能按菜单项直接执行, 不用再经过 menu.exe 的交互循环。
"""
import io
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
BIN = os.path.join(os.path.dirname(HERE), "StarATB", "bin")
OUT = os.path.join(os.path.dirname(HERE), "app", "routes.json")


def load_menu(path):
    """菜单 json 编码两种都有(大部分 UTF-8,cloud.json 等是 GBK),
    先按 UTF-8 试,出现替换符就退回 GBK —— 否则标签会整片乱码。"""
    raw = open(path, "rb").read()
    text = None
    for enc in ("utf-8-sig", "gbk", "gb18030"):
        try:
            t = raw.decode(enc)
        except UnicodeDecodeError:
            continue
        if "\ufffd" not in t:
            text = t
            break
        if text is None:
            text = t
    if text is None:
        text = raw.decode("utf-8", "replace")
    s = text
    s = re.sub(r"\}\s*\n\s*\{", "},\n{", s)     # 上游 json 允许缺逗号
    s = re.sub(r'"\s*\n\s*\{', '",\n{', s)
    s = re.sub(r",(\s*[\]\}])", r"\1", s)
    try:
        return json.loads(s)
    except Exception:
        return {"options": []}


def parse_bat(path):
    """返回 ({menu_json: {key: raw_action}}, {label: menu_json})。"""
    txt = io.open(path, encoding="gbk", errors="replace").read()
    lines = txt.splitlines()
    found = {}
    sections = {}
    cur = None
    label = None
    for ln in lines:
        m = re.match(r"^\s*:([\w\-]+)\s*$", ln)
        if m:
            label = m.group(1).lower()
            continue
        m = re.search(r"menu\.exe\s+\.?\\?menu\\([\w\-]+\.json)", ln, re.I)
        if m:
            cur = m.group(1)
            found.setdefault(cur, {})
            if label:
                sections.setdefault(label, cur)
            continue
        if cur is None:
            continue
        m = re.match(r'\s*if\s+(?:/i\s+)?"%MENU%"=="([^"]+)"\s*(.*)$', ln, re.I)
        if m:
            key, rest = m.group(1), m.group(2).strip()
            found[cur][key] = rest
    return found, sections


def action_of(rest):
    """把 bat 里的动作串归一化成 GUI 能执行/导航的形式。"""
    calls = re.findall(r"\bcall\s+([^\s&|]+)", rest, re.I)
    gotos = re.findall(r"\bgoto\s+([^\s&|]+)", rest, re.I)
    if calls:
        tgt = calls[-1]
        if tgt.lower().endswith((".bat", ".exe")):
            tgt = tgt[:-4] if tgt.lower().endswith(".bat") else tgt
        return {"kind": "call", "target": tgt, "raw": rest}
    if gotos:
        return {"kind": "goto", "target": gotos[-1], "raw": rest}
    return {"kind": "none", "target": "", "raw": rest}


def main():
    menus = {}
    for f in sorted(os.listdir(os.path.join(BIN, "menu"))):
        if not f.endswith(".json"):
            continue
        d = load_menu(os.path.join(BIN, "menu", f))
        opts = d.get("options") or []
        menus[f] = [{"value": o.get("value", ""), "label": o.get("label", ""),
                     "hidden": bool(o.get("hidden")), "trigger": o.get("trigger", "")}
                    for o in opts]

    routes = {}
    sources = {}
    all_sections = {}
    for f in sorted(os.listdir(BIN)):
        if not f.lower().endswith(".bat"):
            continue
        try:
            found, secs = parse_bat(os.path.join(BIN, f))
            all_sections[f] = secs
        except Exception as e:
            print("  跳过", f, e)
            continue
        for mj, table in found.items():
            if not table:
                continue
            routes.setdefault(mj, {})
            sources.setdefault(mj, f)
            for k, rest in table.items():
                if k not in routes[mj]:
                    routes[mj][k] = action_of(rest)

    data = {"menus": menus, "routes": routes, "sources": sources, "sections": all_sections}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(data, io.open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    n = sum(len(v) for v in menus.values())
    r = sum(len(v) for v in routes.values())
    print("菜单 %d 个 / 项 %d，路由 %d 条，来自 %d 个 bat" %
          (len(menus), n, r, len(set(sources.values()))))
    miss = [(m, o["label"]) for m, opts in menus.items() for o in opts
            if not o["hidden"] and o["value"] not in routes.get(m, {})]
    print("未覆盖项 %d 个，前 8 个：" % len(miss))
    for m, lb in miss[:8]:
        print("   %-22s %s" % (m, lb))


if __name__ == "__main__":
    main()
