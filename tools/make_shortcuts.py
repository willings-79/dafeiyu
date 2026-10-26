# -*- coding: utf-8 -*-
r"""tools/make_shortcuts.py — 一次性把桌面图标建好（仅 Windows）。

    py -3 tools\make_shortcuts.py

建出两个双击即用的图标（鲸鱼娘 icon，无黑窗口）：
  大肥鱼 · 设置    扫码登录 / 捏性格 / 调额度 / 切真发演练
  大肥鱼 · 她的一天 浏览器里看她今天干了什么
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DESKTOP = os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")), "Desktop")
ICO = os.path.join(ROOT, "assets", "icon.ico")

PYW = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
if not os.path.exists(PYW):
    PYW = sys.executable      # 没有 pythonw（精简发行版）就退回 python.exe，会有窗口但能用

# 桌面两个 + 项目文件夹里两个：文件夹里的双击入口也要鲸鱼图标
SHORTCUTS = [
    (os.path.join(DESKTOP, "大肥鱼 · 设置.lnk"),
     os.path.join(ROOT, "tools", "settings_server.py")),
    (os.path.join(DESKTOP, "大肥鱼 · 她的一天.lnk"),
     os.path.join(ROOT, "tools", "open_today.py")),
    (os.path.join(ROOT, "大肥鱼设置.lnk"),
     os.path.join(ROOT, "tools", "settings_server.py")),
    (os.path.join(ROOT, "她的一天.lnk"),
     os.path.join(ROOT, "tools", "open_today.py")),
]


def main():
    if os.name != "nt":
        print("Only Windows needs .lnk shortcuts; on macOS/Linux run the scripts directly.")
        return 0
    if not os.path.exists(ICO):
        print("icon not found: %s" % ICO)
        return 1
    cmds = []

    def _ps(s):
        # PowerShell 单引号串里 ' 要写成 ''——路径里带单引号的人也存在
        return s.replace("'", "''")

    for name, target in SHORTCUTS:
        lnk = os.path.join(DESKTOP, name)
        cmds.append(
            "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%s');"
            "$s.TargetPath='%s';$s.Arguments='\"%s\"';$s.WorkingDirectory='%s';"
            "$s.IconLocation='%s,0';$s.Save()"
            % (_ps(lnk), _ps(PYW), _ps(target), _ps(ROOT), _ps(ICO)))
    r = subprocess.run(["powershell", "-NoProfile", "-Command", "; ".join(cmds)],
                       capture_output=True, text=True)
    ok = True
    for name, _ in SHORTCUTS:
        made = os.path.exists(os.path.join(DESKTOP, name))
        ok = ok and made
        print(("created: " if made else "FAILED : ") + name)
    if not ok and r.stderr:
        print(r.stderr.strip()[-400:])
    print("\n以后日常就是双击桌面图标。值班定时任务见 docs/AGENT-PROTOCOL.md。")
    print("注意：快捷方式记的是绝对路径——以后把文件夹挪了位置，回来重跑一遍这个脚本就好。")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
