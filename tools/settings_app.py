# -*- coding: utf-8 -*-
"""tools/settings_app.py — 原生桌面窗口版设置（tkinter）。
双击 `大肥鱼设置（原生版）.vbs` 打开。功能与 settings_server.py 对齐。"""

import json
import os
import sys
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import lib.bili as bili          # noqa: E402
import lib.persona as persona    # noqa: E402
import duty                      # noqa: E402

try:                              # 高 DPI 感知：不开这个，Win 缩放下全是糊的
    from ctypes import windll
    windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        windll.user32.SetProcessDPIAware()
    except Exception:
        pass

BG, CARD, LINE = "#eef1f6", "#ffffff", "#dfe4ec"
ACCENT, ACCENT_DK = "#185fa5", "#124a85"
TXT, DIM, OK, WARN = "#1c1f23", "#6b7280", "#0f6e56", "#a32d2d"
FONT = ("Microsoft YaHei UI", 10)
FONT_B = ("Microsoft YaHei UI", 10, "bold")
FONT_T = ("Microsoft YaHei UI", 15, "bold")
FONT_S = ("Microsoft YaHei UI", 9)


def btn(parent, text, cmd, primary=True):
    return tk.Button(parent, text=text, command=cmd, font=FONT, relief="flat",
                     cursor="hand2", padx=16, pady=6,
                     bg=ACCENT if primary else CARD, fg="white" if primary else TXT,
                     activebackground=ACCENT_DK if primary else "#e8edf4",
                     activeforeground="white" if primary else TXT,
                     highlightthickness=0, bd=0)


def card(parent):
    f = tk.Frame(parent, bg=CARD, highlightbackground=LINE, highlightthickness=1)
    inner = tk.Frame(f, bg=CARD)
    inner.pack(fill="both", expand=True, padx=16, pady=12)
    return f, inner


def lbl(parent, text, color=TXT, bold=False, size=10):
    return tk.Label(parent, text=text, bg=parent["bg"], fg=color, anchor="w",
                    justify="left", font=("Microsoft YaHei UI", size, "bold") if bold else FONT)


def load_conf():
    c = duty.conf()
    c.setdefault("reply_cap", 3)
    c.setdefault("learn_enabled", True)
    c.setdefault("dynamic_per_week", 2)
    c.setdefault("schedule", ["12:50", "22:20"])
    c.setdefault("schedule_driver", "api")
    return c


def schtasks(*args):
    """schtasks 在中文 Windows 上输出 GBK，按 UTF-8 解码会直接炸（实测）"""
    return subprocess.run(["schtasks", *args], capture_output=True, text=True,
                          encoding="gbk", errors="ignore")


class ScrollFrame(tk.Frame):
    """能滚动的容器：内容超出窗口高度时出滚动条 + 滚轮，窗口拉大就自动贴合。"""

    def __init__(self, parent):
        super().__init__(parent, bg=BG)
        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0, bd=0)
        vsb = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=BG)
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.bind("<Configure>", self._on_resize)
        self.canvas.configure(yscrollcommand=vsb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        for w in (self.canvas, self.inner):
            w.bind("<Enter>", lambda e: self.canvas.bind_all(
                "<MouseWheel>", lambda ev: self.canvas.yview_scroll(int(-ev.delta / 120), "units")))
            w.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

    def _on_resize(self, e):
        """内容不足一屏时也把内容区撑到可视高度——白卡不许在半截露灰底"""
        self.canvas.itemconfigure(self._win, width=e.width,
                                  height=max(e.height, self.inner.winfo_reqheight()))
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("大肥鱼 · 设置")
        try:                              # 不设这个，任务栏永远按 python.exe 分组显示默认图标
            from ctypes import windll
            windll.shell32.SetCurrentProcessExplicitAppUserModelID("dafeiyu.settings.app.1")
        except Exception:
            pass
        try:
            self.iconbitmap(os.path.join(ROOT, "assets", "icon.ico"))
        except Exception:
            pass
        self.configure(bg=BG)
        self.geometry("680x780")
        self.minsize(620, 720)
        self._center()

        head = tk.Frame(self, bg=ACCENT)
        head.pack(fill="x")
        tk.Label(head, text="🐟 大肥鱼 · 设置", bg=ACCENT, fg="white",
                 font=FONT_T).pack(anchor="w", padx=22, pady=(14, 0))
        tk.Label(head, text="她住在这个配置里。改完即存，下一轮值班生效。",
                 bg=ACCENT, fg="#cfe2f5", font=FONT_S).pack(anchor="w", padx=22, pady=(0, 12))

        bar = tk.Frame(self, bg=CARD, highlightbackground=LINE, highlightthickness=1)
        bar.pack(fill="x", padx=14)
        self.container = tk.Frame(self, bg=BG)
        self.container.pack(fill="both", expand=True, padx=14, pady=(12, 14))
        self.tab_labels, self.scrolls, self.cards = [], [], []
        for i, name in enumerate(("账号", "性格", "偏好", "作息")):
            l = tk.Label(bar, text=name, bg=CARD, fg=DIM, font=FONT,
                         padx=22, pady=10, cursor="hand2")
            l.pack(side="left")
            l.bind("<Button-1>", lambda e, i=i: self.select_tab(i))
            self.tab_labels.append(l)
            sf = ScrollFrame(self.container)
            self.scrolls.append(sf)
            outer, inner = card(sf.inner)
            outer.pack(fill="both", expand=True)
            self.cards.append(outer)
        self._build_account(self.cards[0].winfo_children()[0])
        self._build_persona(self.cards[1].winfo_children()[0])
        self._build_pref(self.cards[2].winfo_children()[0])
        self._build_sched(self.cards[3].winfo_children()[0])
        self.select_tab(0)
        self.after(200, self._refresh_status)

    def select_tab(self, idx):
        for i, (l, sf) in enumerate(zip(self.tab_labels, self.scrolls)):
            if i == idx:
                l.config(fg=ACCENT, font=FONT_B)
                sf.pack(fill="both", expand=True)
            else:
                l.config(fg=DIM, font=FONT)
                sf.pack_forget()

    def _center(self):
        self.update_idletasks()
        w, h = 680, 780
        x = (self.winfo_screenwidth() - w) // 2
        y = max(0, (self.winfo_screenheight() - h) // 3)
        self.geometry("%dx%d+%d+%d" % (w, h, x, y))

    # ---------------- 账号 ----------------
    def _build_account(self, f):
        self.acc_lbl = lbl(f, "读取中…", bold=True, size=11)
        self.acc_lbl.pack(fill="x")
        self.acc_sub = lbl(f, "", color=DIM)
        self.acc_sub.pack(fill="x", pady=(2, 8))
        row = tk.Frame(f, bg=CARD)
        row.pack(anchor="w", pady=(0, 8))
        btn(row, "扫码登录（把小号交给她）", self.start_login).pack(side="left", padx=(0, 8))
        btn(row, "收回账号", self.logout, primary=False).pack(side="left")
        self.qr = tk.Canvas(f, width=260, height=260, bg="white",
                            highlightthickness=1, highlightbackground=LINE)
        self.qr.pack(pady=2)
        self.qr_msg = lbl(f, "点上面按钮生成二维码，用 B站 App（小号）扫。", color=DIM)
        self.qr_msg.pack(pady=(6, 0))

    def _set_status(self, text, sub="", color=TXT):
        self.acc_lbl.config(text=text, fg=color)
        self.acc_sub.config(text=sub)

    def _refresh_status(self):
        c = load_conf()
        try:
            who = bili.whoami()
        except Exception as exc:
            who = {"login": False, "reason": str(exc)}
        if who.get("login"):
            mode = c.get("mode")
            self._set_status("账号：%s（Lv%s）" % (who.get("uname"), who.get("level") or "?"),
                             "模式：%s%s" % ("真发" if mode == "live" else "只演练（dry）",
                                            "　● 真发中" if mode == "live" else ""),
                             OK if mode == "live" else TXT)
        else:
            self._set_status("还没登录", "点「扫码登录」，用 B站 App（小号）扫一下即可", WARN)

    def start_login(self):
        try:
            from lib import deps
            self.qr_msg.config(text="第一次扫码，先装画二维码的小包（十几秒，只此一次）…", fg=DIM)
            self.update_idletasks()
            ok, why = deps.ensure("qrcode")
            if not ok:
                messagebox.showerror("大肥鱼", "qrcode 自动安装失败：%s" % why)
                return
            url, key = bili.qr_generate()
        except Exception as exc:
            messagebox.showerror("大肥鱼", "生成二维码失败：%s" % exc)
            return
        self._qr_key = key
        import qrcode
        qr = qrcode.QRCode(border=1)
        qr.add_data(url)
        qr.make(fit=True)
        m = qr.get_matrix()
        n = len(m)
        px = max(2, 260 // n)            # 自适应：模块尺寸随版本缩，保证整码画进画布
        off = (260 - n * px) // 2
        cv = self.qr
        cv.delete("all")
        for y, row in enumerate(m):
            for x, v in enumerate(row):
                if v:
                    cv.create_rectangle(off + x * px, off + y * px,
                                        off + (x + 1) * px, off + (y + 1) * px,
                                        fill=TXT, width=0)
        self.qr_msg.config(text="用 B站 App 扫，然后手机上点「确认登录」…", fg=DIM)
        self._poll_login()

    def _poll_login(self):
        if not self._qr_key:
            return
        state, cookies, msg = bili.qr_poll(self._qr_key)
        if state == "ok":
            self._qr_key = None
            who = duty._save_login(cookies)
            if who.get("login"):
                self.qr_msg.config(text="她是 %s 了。模式还是 dry。" % who.get("uname"), fg=OK)
                self._refresh_status()
            else:
                self.qr_msg.config(text="凭证拿到了但登录态没认出来，再扫一次", fg=WARN)
            return
        if state == "expired":
            self._qr_key = None
            self.qr_msg.config(text=msg or "二维码过期了，再点一次「扫码登录」。", fg=WARN)
            return
        if state == "scanned":
            self.qr_msg.config(text="扫上了，手机上点确认…", fg=ACCENT)
        self.after(2000, self._poll_login)

    def logout(self):
        if not messagebox.askyesno("大肥鱼", "确定收回账号？她立刻够不着这个号。"):
            return
        c = load_conf()
        cleared = [k for k in ("SESSDATA", "bili_jct", "COOKIE_RAW", "DedeUserID",
                               "bili_ticket", "bili_ticket_expires") if c.pop(k, None)]
        bili.save_conf(c)
        self._refresh_status()
        messagebox.showinfo("大肥鱼", ("清掉了：%s" % "、".join(cleared)) if cleared else "本来没登录")

    # ---------------- 性格 ----------------
    def _build_persona(self, f):
        self.p_lbl = lbl(f, "", bold=True, size=11)
        self.p_lbl.pack(fill="x")
        self.p_sub = lbl(f, "不导入就是默认的大肥鱼。换成自己的角色就没有大肥鱼的 CC 协议约束。\n"
                            "写法规矩在 persona.md，不用动。", color=DIM)
        self.p_sub.pack(fill="x", pady=(2, 10))
        row = tk.Frame(f, bg=CARD)
        row.pack(anchor="w")
        btn(row, "导入性格 .json", self.import_persona).pack(side="left", padx=(0, 8))
        btn(row, "恢复默认（大肥鱼）", self.reset_persona, primary=False).pack(side="left")
        self._refresh_persona()

    def _refresh_persona(self):
        pc = persona.load()
        self.p_lbl.config(text="当前性格：%s" % ((pc or {}).get("name") or "（未加载）"))

    def import_persona(self):
        p = filedialog.askopenfilename(filetypes=[("性格卡 json", "*.json")])
        if not p:
            return
        try:
            d = json.loads(open(p, encoding="utf-8").read())
            if not str(d.get("name") or "").strip():
                raise ValueError("没有 name 字段")
            persona.save(d)
        except Exception as exc:
            messagebox.showerror("大肥鱼", "导入失败：%s" % exc)
            return
        self._refresh_persona()
        messagebox.showinfo("大肥鱼", "性格已换成「%s」，下一轮生效。" % d["name"])

    def reset_persona(self):
        try:
            persona.LOCAL.unlink()
        except OSError:
            pass
        self._refresh_persona()

    # ---------------- 偏好 ----------------
    def _build_pref(self, f):
        c = load_conf()
        self.vars = {}
        grid = tk.Frame(f, bg=CARD)
        grid.pack(fill="x")
        for col in range(3):
            grid.columnconfigure(col, weight=1, uniform="pref")

        def num(row, col, label, key, default, budget=False):
            tk.Label(grid, text=label, bg=CARD, fg=DIM, font=FONT_S).grid(
                row=row, column=col, sticky="w")
            cur = (c.get("budget") or {}).get(key, default) if budget else c.get(key, default)
            v = tk.StringVar(value=str(cur))
            e = tk.Entry(grid, textvariable=v, relief="flat", bd=0, font=FONT,
                         highlightthickness=1, highlightbackground=LINE,
                         highlightcolor=ACCENT, insertbackground=TXT)
            e.grid(row=row + 1, column=col, sticky="ew", pady=(3, 14), ipady=4, padx=(0, 12))
            self.vars[key] = v

        num(0, 0, "每天最多几条", "cap", 1, budget=True)
        num(0, 1, "楼中楼上限(-1不限)", "reply_cap", 3)
        num(0, 2, "一周动态上限", "dynamic_per_week", 2)
        num(2, 0, "两条间隔（分钟）", "interval_min", 45, budget=True)
        num(2, 1, "播放量下限", "view_floor", 3000, budget=True)
        num(2, 2, "时长上限（秒）", "dur_max", 1200, budget=True)
        num(4, 0, "每天班次数", "shifts_per_day", 2)
        num(4, 1, "不想出门概率", "skip_prob", 0.22, budget=True)
        num(4, 2, "只看不说概率", "quiet_prob", 0.10, budget=True)

        tk.Frame(f, bg=LINE, height=1).pack(fill="x", pady=2)
        tk.Label(f, text="说话方式", bg=CARD, fg=DIM, font=FONT_S).pack(anchor="w", pady=(8, 4))
        self.mode_v = tk.StringVar(value=c.get("mode", "dry"))
        mrow = tk.Frame(f, bg=CARD)
        mrow.pack(anchor="w")
        self.mode_pills = {}
        self.mode_hint = tk.Label(f, bg=CARD, fg=DIM, font=FONT_S, anchor="w")
        for txt, val in (("只演练", "dry"), ("真发", "live")):
            b = tk.Button(mrow, text=txt, font=FONT, relief="flat", cursor="hand2",
                          padx=22, pady=4, bd=0, highlightthickness=0,
                          command=lambda v=val: self._set_mode(v))
            b.pack(side="left", padx=(0, 8))
            self.mode_pills[val] = b
        self._paint_mode()
        self.mode_hint.pack(anchor="w", pady=(6, 0))

        lrow = tk.Frame(f, bg=CARD)
        lrow.pack(anchor="w", pady=(12, 0))
        tk.Label(lrow, text="跟评论区同类学说话", bg=CARD, font=FONT).pack(side="left")
        self.learn_v = tk.BooleanVar(value=duty.learning_on(c))
        self.learn_btn = tk.Button(lrow, font=FONT_S, relief="flat", cursor="hand2",
                                   bd=0, highlightthickness=0, padx=14, pady=2,
                                   command=self._toggle_learn)
        self.learn_btn.pack(side="left", padx=12)
        self._paint_learn()

        self.at_owner_v = tk.BooleanVar(value=bool(c.get("at_owner", True)))
        arow = tk.Frame(f, bg=CARD)
        arow.pack(anchor="w", pady=(10, 0))
        tk.Label(arow, text="评论里 @ 主人", bg=CARD, font=FONT).pack(side="left")
        tk.Checkbutton(arow, variable=self.at_owner_v, bg=CARD, font=FONT_S,
                       activebackground=CARD, highlightthickness=0).pack(side="left", padx=12)

        tk.Label(f, text="关键词（一行一个）", bg=CARD, fg=DIM, font=FONT_S).pack(anchor="w", pady=(14, 2))
        self.kw = tk.Text(f, height=4, relief="flat", bd=0, font=FONT,
                          highlightthickness=1, highlightbackground=LINE,
                          highlightcolor=ACCENT)
        self.kw.insert("1.0", "\n".join(c.get("keywords") or []))
        self.kw.pack(fill="x", ipady=4)
        tk.Label(f, text="屏蔽词（一行一个）", bg=CARD, fg=DIM, font=FONT_S).pack(anchor="w", pady=(12, 2))
        self.neg = tk.Text(f, height=4, relief="flat", bd=0, font=FONT,
                           highlightthickness=1, highlightbackground=LINE,
                           highlightcolor=ACCENT)
        self.neg.insert("1.0", "\n".join(c.get("negative_keywords") or []))
        self.neg.pack(fill="x", ipady=4)
        btn(f, "保存偏好", self.save_pref).pack(anchor="w", pady=(14, 0))

    def _set_mode(self, v):
        self.mode_v.set(v)
        self._paint_mode()

    def _paint_mode(self):
        for val, b in self.mode_pills.items():
            on = self.mode_v.get() == val
            b.config(bg=ACCENT if on else "#eef1f6", fg="white" if on else DIM,
                     activebackground=ACCENT_DK if on else "#e2e8f0",
                     activeforeground="white" if on else DIM)
        if self.mode_v.get() == "live":
            self.mode_hint.config(text="● 真发：评论会真的发出去，别人能看到", fg=WARN)
        else:
            self.mode_hint.config(text="只演练：照常逛照常写，但一条都不会发出去", fg=DIM)

    def _toggle_learn(self):
        self.learn_v.set(not self.learn_v.get())
        self._paint_learn()

    def _paint_learn(self):
        on = self.learn_v.get()
        self.learn_btn.config(text="开" if on else "关",
                              bg="#e2f3ec" if on else "#f2f3f5",
                              fg=OK if on else DIM)

    def save_pref(self):
        c = load_conf()
        try:
            b = c.setdefault("budget", {})
            # 夹取范围与网页版完全一致——两个入口不许有两种行为
            b["cap"] = max(1, min(30, int(self.vars["cap"].get())))
            new_iv = max(15, min(360, int(self.vars["interval_min"].get())))
            if b.get("interval_min") != new_iv:
                b["interval_min"] = new_iv
                if "interval_sec" in b:
                    b.pop("interval_sec", None)  # 真的改了分钟才清秒级覆盖；只改别的项不碰它
            b["view_floor"] = max(0, min(10000000, int(self.vars["view_floor"].get())))
            b["dur_max"] = max(60, min(7200, int(self.vars["dur_max"].get())))
            rc = int(self.vars["reply_cap"].get())
            c["reply_cap"] = -1 if rc < 0 else min(100, rc)
            c["dynamic_per_week"] = max(0, min(7, int(self.vars["dynamic_per_week"].get())))
            c["shifts_per_day"] = max(1, min(8, int(self.vars["shifts_per_day"].get())))
            # 心情概率：网页版单顶 0.6/0.5，合计超 0.9 会吃掉"想出门"——这里夹单顶并留提示
            b["skip_prob"] = max(0.0, min(0.6, float(self.vars["skip_prob"].get())))
            b["quiet_prob"] = max(0.0, min(0.5, float(self.vars["quiet_prob"].get())))
        except (KeyError, ValueError):
            messagebox.showerror("大肥鱼", "数字项里填的不是数字")
            return
        c["mode"] = self.mode_v.get()
        c["learn"] = self.learn_v.get()          # 和网页版/文档统一用 learn，旧 learn_enabled 只读不写
        c["at_owner"] = bool(self.at_owner_v.get())
        c["keywords"] = [x.strip() for x in self.kw.get("1.0", "end").splitlines() if x.strip()]
        c["negative_keywords"] = [x.strip() for x in self.neg.get("1.0", "end").splitlines() if x.strip()]
        bili.save_conf(c)
        # 输入框回填成真正存进去的值——夹取过了就让用户看见，别让他以为存的是 99
        for k, v in (("cap", b["cap"]), ("interval_min", b["interval_min"]),
                     ("view_floor", b["view_floor"]), ("dur_max", b["dur_max"]),
                     ("reply_cap", c["reply_cap"]),
                     ("dynamic_per_week", c["dynamic_per_week"]),
                     ("shifts_per_day", c["shifts_per_day"]),
                     ("skip_prob", b["skip_prob"]), ("quiet_prob", b["quiet_prob"])):
            self.vars[k].set(str(v))
        self._refresh_status()
        messagebox.showinfo("大肥鱼", "偏好已保存，下一轮生效。")

    # ---------------- 作息 ----------------
    def _build_sched(self, f):
        c = load_conf()
        self.sched = sorted(c.get("schedule") or [])
        tk.Label(f, text="已排的时间（选中后可删除）", bg=CARD, fg=DIM, font=FONT_S).pack(anchor="w")
        self.sched_list = tk.Listbox(f, height=4, relief="solid", bd=1, font=FONT,
                                     selectbackground="#e8eef7", activestyle="none")
        self.sched_list.pack(fill="x", pady=(2, 8))
        self._render_sched()
        row = tk.Frame(f, bg=CARD)
        row.pack(anchor="w")
        self.sh = ttk.Combobox(row, width=4, values=["%02d" % i for i in range(24)],
                               state="readonly", font=FONT)
        self.sm = ttk.Combobox(row, width=4, values=["%02d" % i for i in range(0, 60, 5)],
                               state="readonly", font=FONT)
        self.sh.set("12")
        self.sm.set("50")
        tk.Label(row, text="时", bg=CARD, font=FONT).pack(side="left")
        self.sh.pack(side="left", padx=3)
        tk.Label(row, text="分", bg=CARD, font=FONT).pack(side="left")
        self.sm.pack(side="left", padx=3)
        btn(row, "＋添加", self.add_sched, primary=False).pack(side="left", padx=6)
        btn(row, "－删除选中", self.del_sched, primary=False).pack(side="left")
        tk.Label(f, text="由谁值班（api 需先在 config 填 api 块）", bg=CARD, fg=DIM,
                 font=FONT_S).pack(anchor="w", pady=(10, 0))
        self.driver = ttk.Combobox(f, width=42, state="readonly", font=FONT, values=[
            "api", "claude", "zcode", "opencode", "codex", "gemini", "workbuddy"])
        self.driver.set(c.get("schedule_driver") or "api")
        self.driver.pack(anchor="w", pady=(2, 8))
        btn(f, "应用到系统定时任务", self.apply_sched).pack(anchor="w")
        lbl(f, "到点在后台跑一轮（无窗口）。删除时间后应用即从系统里移除。", color=DIM).pack(anchor="w", pady=(8, 0))

    def _render_sched(self):
        self.sched_list.delete(0, "end")
        for t in sorted(self.sched):
            self.sched_list.insert("end", "⏰ " + t)

    def add_sched(self):
        t = "%s:%s" % (self.sh.get(), self.sm.get())
        if t not in self.sched:
            self.sched.append(t)
        self._render_sched()

    def del_sched(self):
        sel = self.sched_list.curselection()
        if sel:
            del self.sched[sel[0]]
        self._render_sched()

    def apply_sched(self):
        if not self.sched:
            messagebox.showinfo("大肥鱼", "先添加至少一个时间")
            return
        c = load_conf()
        c["schedule"] = sorted(self.sched)
        c["schedule_driver"] = self.driver.get()
        bili.save_conf(c)
        if self.driver.get() == "workbuddy":
            self._clear_tasks()
            messagebox.showinfo(
                "大肥鱼",
                "WorkBuddy 的定时在她的自动化面板里配：\n\n"
                "· 时间按 %s 设（每天）\n"
                "· 提示词用 automation-prompt.txt 原文\n"
                "· 工作目录选 dafeiyu 项目根\n\n（系统里残留的 dafeiyu 定时任务已清理）"
                % "、".join(sorted(self.sched)))
            return
        tr = 'wscript.exe "%s" %s' % (os.path.join(ROOT, "tools", "windows", "duty.vbs"),
                                      self.driver.get())
        q = schtasks("/Query", "/FO", "CSV")
        old = {ln.split(",")[0].strip('"') for ln in (q.stdout or "").splitlines()
               if ln.startswith('"dafeiyu-')}
        want = {"dafeiyu-%s" % t.replace(":", "") for t in self.sched}
        msgs = []
        for name in sorted(old - want):
            schtasks("/Delete", "/TN", name, "/F")
            msgs.append("删 " + name)
        for t in sorted(self.sched):
            h, m = t.split(":")
            r = schtasks("/Create", "/F", "/TN", "dafeiyu-%s" % t.replace(":", ""),
                         "/SC", "DAILY", "/ST", "%02d:%s" % (int(h) % 24, m), "/TR", tr)
            msgs.append(("已排 %s" % t) if r.returncode == 0 else ("%s 失败" % t))
        self._refresh_status()
        messagebox.showinfo("大肥鱼", " ".join(msgs) or "没有变化")

    def _clear_tasks(self):
        q = schtasks("/Query", "/FO", "CSV")
        for ln in (q.stdout or "").splitlines():
            if ln.startswith('"dafeiyu-'):
                schtasks("/Delete", "/TN", ln.split(",")[0].strip('"'), "/F")


if __name__ == "__main__":
    App().mainloop()
