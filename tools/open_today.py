# -*- coding: utf-8 -*-
"""tools/open_today.py — 双击用：在浏览器里打开《她的一天》。
还没写就弹个窗说明（pythonw 下没有控制台，弹窗是她唯一能说话的方式）。"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import duty  # noqa: E402
from lib import view  # noqa: E402

p = os.path.join(duty.STATE, "今天.md")
if not os.path.exists(p):
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            0, "她今天还没写《她的一天》。\n\n等值班跑完一轮（brief）再来，"
               "或者先在设置页跟她打个招呼。", "大肥鱼 · 她的一天", 0x40)
    except Exception:
        pass
    sys.exit(0)
view.open_md(p, title="她的一天")
