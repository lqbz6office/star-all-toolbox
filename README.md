# Star All Tool Box

小天才手表工具箱 **AllToolBox** 的图形外壳。引擎还是作者 xgj_236 那一套（1.4.6.705），
只把命令行菜单换成了液态玻璃界面，并且把几个高频流程用 Python 原生重写了。

> 引擎版权归原作者。本仓库只包含外壳代码，不含 `StarATB/bin`（体积大、且属于作者）。

## 三个不套壳的地方

| 原版 | 这里 |
|---|---|
| `menu.exe` 画命令行菜单，选中项写 `menutmp.txt` | 自绘界面；菜单树来自 `app/routes.json`（49 个菜单 / 358 个条目） |
| `cloud.bat` 用 `for %%i in (%menu)` 分发下载 | `core/resources.py` 直接读 `cloud_toolbox.txt` / `cloud_other.txt`，按里面的解压目标下载 |
| Star OS 升级要去官网手动下载再刷 | `core/staros.py` 读线上清单 → 下离线包 → adb 推送 → `magisk --install-module` |

## 功能

### 首页
- **一键安装最新 Star OS（离线包）**：读 `staros.lqbz.dpdns.org/upd` 清单，下载 `full.zip`（约 200MB），
  `adb push` 到 `/sdcard/temp_module.zip`，`su -c 'magisk --install-module'` 安装，可选自动重启；
  三个下载源轮着试（自建网关 → GitHub → 镜像），带断点续传和百分比。
- **安装在线包**：400KB，手表自己联网补资源。
- **检查更新**：与 Star OS 模块同一套 `update.json`，正式 / 内测双通道取 `versionCode` 高者。
- **云端资源补全**、**开发者平台**、主菜单全部条目。

### 功能库
49 个菜单全量可进入，358 个条目按 `call` / `goto` / 动态菜单三种策略执行
（详见 `app/core/runner.py` 的文件头注释）。

### 云端资源
27 项资源的状态一目了然（已就位 / 待安装 / 未下载），点一下就走引擎自带的
`progress.exe + aria2c`，解压用 `7z.exe`，解压目标严格按 `cloud_*.txt` 里的声明。

### 开发者平台
`Star OS 开发者平台`整页嵌入（登录 / 上传模块 / 上传表盘 / 开发文档 / AI 教程 / 关于），
不是重写，是直接把它的 `centralWidget` 接进来。

## 目录

```
app/
  main.py          外壳：顶栏 / 导航 / 卡片 / 日志 / 执行
  glass.py         液态玻璃绘制（Windows Acrylic + 自绘高光）
  devpage.py       开发者平台嵌入
  routes.json      菜单树 + 键→动作 + 标签→子菜单（由 tools/gen_routes.py 生成）
  core/
    errors.py      错误码体系（E0xxx 环境 / E1xxx 设备 / E2xxx 下载 / E3xxx 刷写 / E5xxx 更新）
    updater.py     update.json 双通道 + 多镜像
    resources.py   云端资源下载/解压
    staros.py      Star OS 一键安装
    runner.py      bat 执行策略
    about.py       关于 / 致谢
tools/
  gen_routes.py    从 bin/menu/*.json + *.bat 生成 routes.json
StarATB/           引擎（需自备，见下）
```

## 运行

需要：Windows 10+、管理员权限（引擎里的 adb / 刷写工具要求）、Python 3.9+ 与 PyQt5。

```bash
pip install PyQt5
# 把 AllToolBox 的 bin 放到 StarATB/bin（双击 启动.bat 会自动提权）
双击 启动.bat
```

`启动.bat` 会先检查管理员权限，没有就自己弹 UAC 重新启动。

## 关于引擎版本

`StarATB/bin` 需要 **AllToolBox 1.4.6.705** 或更新版本。1.2.7 也能跑，但资源清单是写在
bat 里的，`core/resources.py` 有兜底清单；1.4.6 起清单抽到了 `cloud_toolbox.txt` /
`cloud_other.txt`，改资源不用改代码。

## 致谢

- **小公爵** —— 特别鸣谢
- **xgj_236** —— AllToolBox 原作者，本项目的引擎与流程全部来自他的工作
- Magisk / topjohnwu、scrcpy、aria2、7-Zip、Qt/PyQt5
