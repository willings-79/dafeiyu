# -*- coding: utf-8 -*-
"""lib/deps.py — 缺哪个小包就现场装哪个

只管"用户正在等结果"那一刻要用的包：
    qrcode    → 扫码登录画二维码
    PIL       → login --png 把二维码存成图片
    curl_cffi → 发评论走 Chrome 指纹

两条铁律：
    - 只在用户主动触发的动作里调（login / post），绝不在 import 时装。
      agent 一天跑几十次命令，不能每条命令都先去碰 pip。
    - 装不上就把原因和手动命令原样交回去，绝不静默糊弄。

不归这里管的：certifi（缺了会退回系统证书库，README 有说明）、
yt-dlp / ffmpeg（系统级工具，用户自己装）。
"""

import importlib
import importlib.util
import subprocess
import sys

# 白名单：能装的包写死在这里。mod 只来自本仓库代码里的字面量调用，
# 不接收任何外部输入；mod 只决定走哪个分支，本身不进命令行。
_PACKAGES = {
    "qrcode":    {"pip": "qrcode",    "why": "扫码登录画二维码"},
    "curl_cffi": {"pip": "curl_cffi", "why": "发评论走 Chrome 指纹"},
    "PIL":       {"pip": "pillow",    "why": "把二维码存成图片"},
}


def _pip_run(mod, timeout):
    """现场跑一次 pip install。命令行是写死的字面量，包名不经过任何变量拼接。"""
    if mod == "qrcode":
        return subprocess.run(
            [sys.executable, "-m", "pip", "install",
             "--disable-pip-version-check", "qrcode"],
            capture_output=True, timeout=timeout)
    if mod == "curl_cffi":
        return subprocess.run(
            [sys.executable, "-m", "pip", "install",
             "--disable-pip-version-check", "curl_cffi"],
            capture_output=True, timeout=timeout)
    if mod == "PIL":
        return subprocess.run(
            [sys.executable, "-m", "pip", "install",
             "--disable-pip-version-check", "pillow"],
            capture_output=True, timeout=timeout)
    return None


def _say(msg):
    # pythonw 起的窗口程序里 sys.stderr 是 None，print 会炸，先看一眼
    try:
        if sys.stderr is not None:
            print(msg, file=sys.stderr)
    except Exception:
        pass


def has(mod):
    try:
        return importlib.util.find_spec(mod) is not None
    except Exception:
        return False


def ensure(mod, timeout=300):
    """mod 缺就现场装一个。返回 (True, "") 或 (False, 人类可读的原因)。"""
    if mod not in _PACKAGES:
        return False, "不认识这个包：%s（不在自动安装白名单里）" % mod
    pip_name = _PACKAGES[mod]["pip"]
    if has(mod):
        return True, ""
    _say("[deps] %s 还没装（%s），第一次用，帮你装一下（十几秒，以后不用再装）…"
         % (pip_name, _PACKAGES[mod]["why"]))
    try:
        r = _pip_run(mod, timeout)
    except Exception as exc:
        return False, "pip 没跑起来：%s" % exc
    if r is None:
        return False, "不认识这个包：%s（不在自动安装白名单里）" % mod
    if r.returncode != 0:
        blob = r.stderr or r.stdout or b""
        text = ""
        for enc in ("utf-8", "gbk"):          # zh-CN Windows 的 pip 输出是 GBK
            try:
                text = blob.decode(enc)
                break
            except UnicodeDecodeError:
                pass
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        tail = "\n".join(lines[-3:]) if lines else ""
        return False, ("pip 退出码 %d%s\n手动装一下：%s -m pip install %s"
                       % (r.returncode, ("\n" + tail) if tail else "",
                          sys.executable, pip_name))
    importlib.invalidate_caches()
    if not has(mod):
        return False, ("装完了还是找不到 %s——可能装进了别的 Python。\n"
                       "手动跑：%s -m pip install %s" % (mod, sys.executable, pip_name))
    _say("[deps] %s 装好了，继续。" % pip_name)
    return True, ""
