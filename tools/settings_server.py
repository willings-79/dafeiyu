# -*- coding: utf-8 -*-
"""
tools/settings_server.py — 大肥鱼的设置页（本机只读自己，不对外）

双击 `设置.bat` 会开这个：一个页面改完所有东西，保存即写回 config.local.json。

安全边界（从 v1 的坑里学来的）：
  · 只绑 127.0.0.1，不开放局域网
  · 每个请求要带本次启动生成的 token（写在地址里）
  · 校验 Origin，别的网页 post 不进来
  · 只能读写配置，不能发评论、不能删东西
"""

import json
import os
import secrets
import sys
import threading
import time
import urllib.parse
import webbrowser
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# pythonw / 无控制台启动时 sys.stdout 是 None，任何 print 都会抛异常直接退出——
# 表现就是"双击图标，什么都没发生"。所以先把输出接到文件。
_LOG_DIR = os.path.join(ROOT, "logs")
if sys.stdout is None or sys.stderr is None:
    try:
        os.makedirs(_LOG_DIR, exist_ok=True)
        _log = open(os.path.join(_LOG_DIR, "settings.log"), "a", encoding="utf-8", buffering=1)
    except Exception:
        _log = open(os.devnull, "w")
    sys.stdout = sys.stderr = _log
else:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def fatal(msg):
    """没有控制台的时候，错误要弹出来，不能悄悄死掉"""
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, msg, "大肥鱼 · 设置", 0x10)
    except Exception:
        pass
    try:
        sys.stderr.write("[fatal] %s\n" % msg)
    except Exception:
        pass

import lib.bili as bili  # noqa: E402
import duty              # noqa: E402

PORT = 8791
LAST_PING = time.time()
GRACE_SEC = int(os.environ.get("SETTINGS_GRACE", "240"))   # 启动后没人打开页面，最多等这么久
IDLE_SEC = int(os.environ.get("SETTINGS_IDLE", "120"))       # 页面关掉后多久自动退出
TOKEN = secrets.token_urlsafe(16)
STATE = os.path.join(ROOT, "state")


def cfg():
    c = duty.conf()          # 关键词/屏蔽词/预算的默认值全在 duty.conf 里（用作者原版兜底）
    b = c.setdefault("budget", {})
    for k, v in (("cap", 1), ("skip_prob", 0.22), ("quiet_prob", 0.10), ("interval_min", 45),
                 ("view_floor", 3000), ("view_ceil", 1500000), ("dur_min", 60),
                 ("dur_max", 1200), ("fresh_days", 14)):
        b.setdefault(k, v)
    c.setdefault("reply_cap", 3)
    c.setdefault("schedule", ["12:50", "22:20"])
    c.setdefault("schedule_driver", "api")
    return c


def _persona_name():
    try:
        import lib.persona as persona_mod
        pc = persona_mod.load()
        return (pc or {}).get("name") or ""
    except Exception:
        return ""


_LOGIN = {"key": None}


def _qr_svg(url):
    """qrcode 库不需要 Pillow 也能出矩阵，手工拼成 SVG 给页面渲染。"""
    try:
        from lib import deps
        deps.ensure("qrcode")            # 缺就现场装一次；装不上走降级（页面显示链接）
        import qrcode
    except Exception:
        return ""
    qr = qrcode.QRCode(border=2)
    qr.add_data(url)
    qr.make(fit=True)
    m = qr.get_matrix()
    n = len(m)
    rects = "".join('<rect x="%d" y="%d" width="1" height="1"/>'
                    % (x, y) for y, row in enumerate(m) for x, v in enumerate(row) if v)
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %(n)d %(n)d" '
            'shape-rendering="crispEdges" width="240" height="240">'
            '<rect width="%(n)d" height="%(n)d" fill="#fff"/>'
            '<g fill="#1c1f23">%(r)s</g></svg>' % {"n": n, "r": rects})


def snapshot():
    c = cfg()
    mood = {}
    try:
        mood = json.load(open(os.path.join(STATE, "mood.json"), encoding="utf-8"))
    except Exception:
        pass
    try:
        who = bili.whoami()
    except Exception as exc:
        who = {"login": False, "reason": str(exc)}
    try:
        g = duty.growth_state()
        me = {"level": g["level"], "xp": g["xp"], "traits": g["traits"],
              "mood_text": mood.get("mood_text") or "",
              "today": mood.get("roll") or ""}
    except Exception:
        me = {}
    return {
        "mode": c.get("mode", "dry"),
        "owner_nick": c.get("owner_nick") or "",
        "owner_mid": c.get("owner_mid") or "",
        "at_owner": bool(c.get("at_owner")),
        "keywords": c.get("keywords") or [],
        "negative_keywords": c.get("negative_keywords") or [],
        "budget": c.get("budget") or {},
        "reply_cap": c.get("reply_cap", 3),
        "learn": bool(c.get("learn_enabled", True)),
        "schedule": c.get("schedule", ["12:50", "22:20"]),
        "schedule_driver": c.get("schedule_driver", "api"),
        "account": {"login": who.get("login"), "uname": who.get("uname"),
                    "level": who.get("level"), "reason": who.get("reason")},
        "mood": {"roll": mood.get("roll"), "cap": mood.get("cap"), "acted": mood.get("acted")},
        "self": me,
        "dynamic_per_week": c.get("dynamic_per_week", 2),
        "persona_name": _persona_name(),
    }


def save(body):
    c = cfg()
    changed = []

    mode = body.get("mode")
    if mode in ("dry", "live") and mode != c.get("mode"):
        c["mode"] = mode
        changed.append("模式 → " + ("真发" if mode == "live" else "只演练"))

    owner = (body.get("owner_input") or "").strip()
    if owner:
        mid = None
        if owner.isdigit():
            mid = owner
        else:
            import re
            m = re.search(r"(\d{3,})", owner)
            if m:
                mid = m.group(1)
        if not mid:
            return False, "没认出 UID，粘空间链接或者直接填数字 UID"
        try:
            who = bili.card(mid)
        except Exception as exc:
            return False, "查不到这个号：%s" % exc
        me = bili.whoami()
        if str(who["mid"]) == str(me.get("mid")):
            return False, "这是她自己那个号，@ 自己收不到通知"
        if str(c.get("owner_mid")) != str(who["mid"]):
            c["owner_mid"] = int(who["mid"])
            c["owner_nick"] = who["name"]
            c["at_owner"] = True
            changed.append("@ 对象 → " + who["name"])

    if body.get("at_owner") is not None:
        v = bool(body["at_owner"])
        if v != c.get("at_owner"):
            c["at_owner"] = v
            changed.append("评论里 @ 主人 → " + ("开" if v else "关"))

    if body.get("learn") is not None:
        v = bool(body["learn"])
        if v != bool(c.get("learn_enabled", True)):
            c["learn_enabled"] = v
            changed.append("学习开关 → " + ("开" if v else "关"))

    def lines(s):
        """一行一个。多行的时候不拆行内的顿号/逗号——"cos、cosplay" 是一个词，不是两个。"""
        raw = [x.strip() for x in (s or "").splitlines() if x.strip()]
        if len(raw) <= 1:
            one = (raw[0] if raw else "").replace("，", ",").replace("、", ",")
            raw = [x.strip() for x in one.split(",") if x.strip()]
        out = []
        for x in raw:
            if x not in out:
                out.append(x)
        return out

    if body.get("keywords_text") is not None:
        kws = lines(body["keywords_text"])
        if kws and kws != c.get("keywords"):
            c["keywords"] = kws
            changed.append("关键词 %d 个" % len(kws))
    if body.get("neg_text") is not None:
        negs = lines(body["neg_text"])
        if negs != c.get("negative_keywords"):
            c["negative_keywords"] = negs
            changed.append("屏蔽词 %d 个" % len(negs))

    b = c.setdefault("budget", {})
    rules = {"cap": (int, 1, 8), "interval_min": (int, 15, 360),
             "view_floor": (int, 0, 10000000), "dur_max": (int, 60, 7200),
             "skip_prob": (float, 0, 0.6), "quiet_prob": (float, 0, 0.5)}
    for k, (cast, lo, hi) in rules.items():
        v = body.get(k)
        if v is None or v == "":
            continue
        try:
            v = cast(float(v))
        except (TypeError, ValueError):
            continue
        v = max(lo, min(hi, v))
        if b.get(k) != v:
            b[k] = v
            changed.append("%s → %s" % (k, v))

    bili.save_conf(c)
    dw = body.get("dynamic_per_week")
    if dw not in (None, ""):
        try:
            dw = max(0, min(7, int(float(dw))))
            if c.get("dynamic_per_week") != dw:
                c["dynamic_per_week"] = dw
                changed.append("一周动态上限 → %d" % dw)
                bili.save_conf(c)
        except (TypeError, ValueError):
            pass
    rc = body.get("reply_cap")
    if rc not in (None, ""):
        try:
            rc = int(float(rc))
            rc = -1 if rc < 0 else min(12, rc)
            if c.get("reply_cap") != rc:
                c["reply_cap"] = rc
                changed.append("楼中楼上限 → %d" % rc)
                bili.save_conf(c)
        except (TypeError, ValueError):
            pass

    return True, ("改了：" + "；".join(changed)) if changed else "没有变化"


PAGE = r"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>大肥鱼 · 设置</title>
<style>
:root{--bg:#f6f7f9;--card:#fff;--line:#e6e8eb;--txt:#1c1f23;--dim:#6b7280;--accent:#185fa5;--warn:#a32d2d}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--txt);font:14px/1.65 system-ui,-apple-system,"Segoe UI","Microsoft YaHei",sans-serif}
.wrap{max-width:820px;margin:0 auto;padding:28px 20px 80px}
h1{font-size:19px;font-weight:600;margin:0 0 4px}
.sub{color:var(--dim);font-size:13px;margin-bottom:20px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px 20px;margin-bottom:14px}
.card h2{font-size:14px;font-weight:600;margin:0 0 14px}
.row{display:flex;gap:14px;align-items:flex-start;flex-wrap:wrap}
.row>.item{flex:1;min-width:150px}
.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px 14px;margin-bottom:12px}
.grid>.item{min-width:0}
.grid label{display:block;min-height:44px}
.hint{font-size:12px;color:var(--dim);margin-top:6px}
label{display:block;font-size:12px;color:var(--dim);margin-bottom:5px}
input[type=text],input[type=number],textarea{width:100%;padding:8px 10px;border:1px solid var(--line);border-radius:8px;font:inherit;background:#fff;color:var(--txt)}
textarea{min-height:76px;resize:vertical;line-height:1.6}
.modes{display:flex;gap:10px;margin-top:2px}
.mode{flex:1;border:1px solid var(--line);border-radius:10px;padding:10px 12px;cursor:pointer;background:#fff}
.mode.on{border-color:var(--accent);background:#eef5fc}
.mode b{display:block;font-weight:600;font-size:13px}
.mode span{font-size:12px;color:var(--dim)}
.btn{display:inline-block;padding:9px 18px;border-radius:8px;border:1px solid var(--line);background:#fff;cursor:pointer;font:inherit}
.btn.primary{background:var(--accent);color:#fff;border-color:var(--accent)}
.btn:disabled{opacity:.5;cursor:default}
.foot{position:fixed;left:0;right:0;bottom:0;background:rgba(246,247,249,.96);border-top:1px solid var(--line);padding:10px 20px;display:flex;gap:10px;align-items:center;justify-content:center}
.msg{color:var(--dim);font-size:13px;min-height:20px}
.msg.ok{color:#0f6e56}.msg.err{color:var(--warn)}
.kv{display:flex;gap:18px;flex-wrap:wrap;font-size:13px;color:var(--dim)}
.kv b{color:var(--txt);font-weight:500}
.hint{font-size:12px;color:var(--dim);margin-top:6px}
.tag{display:inline-block;background:#eef5fc;color:#185fa5;border-radius:6px;padding:1px 7px;font-size:12px;margin-left:6px}
</style></head><body>
<div class="wrap">
<h1>大肥鱼 · 设置</h1>
<div class="sub">改完点保存，下一轮生效。本轮已经在跑的不会变。</div>

<div class="card">
  <h2>账号</h2>
  <div style="display:flex;gap:18px;align-items:flex-start;flex-wrap:wrap">
    <div id="qrBox" style="min-width:240px;text-align:center;display:none">
      <div id="qrImg"></div>
      <div class="hint" id="qrMsg"></div>
    </div>
    <div style="flex:1;min-width:220px">
      <div style="display:flex;gap:10px;flex-wrap:wrap">
        <button class="btn primary" onclick="startLogin()">扫码登录（把小号交给她）</button>
        <button class="btn" onclick="doLogout()">收回账号</button>
      </div>
      <div class="hint" id="accMsg"></div>
    </div>
  </div>
</div>

<div class="card">
  <h2>她现在是谁</h2>
  <div class="kv" id="who">读取中…</div>
</div>

<div class="card">
  <h2>跟她说</h2>
  <textarea id="sayText" placeholder="留一句话。她下次醒来会先看这里。"></textarea>
  <div style="margin-top:8px;display:flex;gap:10px;align-items:center;flex-wrap:wrap">
    <button class="btn primary" onclick="sayIt()">发给她</button>
    <span class="msg" id="sayMsg"></span>
  </div>
  <div class="hint">下一班时间看你给 agent 设的定时任务。想让她立刻回，就去 agent 会话里说一句"看留言"。</div>
  <div id="chatList" style="margin-top:12px;font-size:13px;line-height:1.7"></div>
</div>

<div class="card">
  <h2>人物性格</h2>
  <div class="kv" id="pNow">读取中…</div>
  <div id="drop" style="margin-top:10px;border:2px dashed var(--line);border-radius:10px;padding:14px;text-align:center;color:var(--dim);cursor:pointer">
    把性格 <b>.json</b> 拖到这里，或点击选文件
    <div class="hint">不拖就是默认的大肥鱼。换成你自己的角色，就没有大肥鱼的 CC 协议约束。改完下一轮生效。</div>
    <input type="file" id="pfile" accept=".json,application/json" style="display:none">
  </div>
</div>

<div class="card">
  <h2>说话方式</h2>
  <div class="modes">
    <div class="mode" id="m-dry" onclick="setMode('dry')"><b>只演练</b><span>照常逛、照常写，但不发出去</span></div>
    <div class="mode" id="m-live" onclick="setMode('live')"><b>真发</b><span>用这个号发评论，开头 @ 你</span></div>
  </div>
  <div class="hint" id="modeHint"></div>
  <div class="row" style="margin-top:10px;align-items:center">
    <div class="item" style="max-width:260px"><label>跟评论区同类学说话</label>
      <select id="learn" style="width:100%;padding:8px 10px;border:1px solid var(--line);border-radius:8px;font:inherit"><option value="1">开</option><option value="0">关</option></select></div>
    <div class="item" style="flex:2"><label>&nbsp;</label>
      <div class="hint">关了之后她只按人设和 persona.md 说话，不再收集别人的说法。</div></div>
  </div>
</div>

<div class="card">
  <h2>@ 谁</h2>
  <div class="row">
    <div class="item" style="flex:2">
      <label>主号空间链接或 UID（不是她自己的号）</label>
      <input type="text" id="owner" placeholder="https://space.bilibili.com/123456">
    </div>
    <div class="item">
      <label>允许 @ 主人（她只在觉得好玩时用）</label>
      <select id="atOwner" style="width:100%;padding:8px 10px;border:1px solid var(--line);border-radius:8px;font:inherit"><option value="1">允许</option><option value="0">一律不 @</option></select>
    </div>
  </div>
  <div class="hint" id="ownerNow"></div>
</div>

<div class="card">
  <h2>刷什么</h2>
  <div class="row">
    <div class="item">
      <label>关注的方向（一行一个，同义词用 | 隔开）</label>
      <textarea id="keywords" placeholder="大模型|LLM&#10;大肥鱼|鲸鱼娘&#10;智能体|Agent"></textarea>
      <div class="hint">关键词是"方向"，不要求标题里有：命中标题、简介、分区或视频标签都算。</div>
    </div>
    <div class="item">
      <label>屏蔽词（标题或标签里出现就不碰）</label>
      <textarea id="neg"></textarea>
    </div>
  </div>
</div>

<div class="card">
  <h2>说多少</h2>
  <div class="grid">
    <div class="item"><label>每天最多几条（1-8）</label><input type="number" id="cap" min="1" max="8" step="1"></div>
    <div class="item"><label>楼中楼上限（-1=不限量）</label><input type="number" id="replyCap" min="-1" max="12" step="1"></div>
    <div class="item"><label>一周动态上限（0-7）</label><input type="number" id="dynamicWeek" min="0" max="7" step="1"></div>
    <div class="item"><label>间隔下限（分钟）</label><input type="number" id="interval" min="15" max="360" step="5"></div>
    <div class="item"><label>播放量下限</label><input type="number" id="viewFloor" min="0" step="1000"></div>
    <div class="item"><label>时长上限（秒）</label><input type="number" id="durMax" min="60" step="30"></div>
  </div>
  <div class="grid" style="grid-template-columns:1fr 1fr">
    <div class="item"><label>今天不想看的概率：<b id="skipVal"></b></label><input type="range" id="skip" min="0" max="60" step="1" style="width:100%"></div>
    <div class="item"><label>只看不说的概率：<b id="quietVal"></b></label><input type="range" id="quiet" min="0" max="50" step="1" style="width:100%"></div>
  </div>
</div>

<div class="card">
  <h2>作息时间（到点她自动值班）</h2>
  <div id="schedChips" style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px"></div>
  <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
    <select id="schedH" style="padding:8px;border:1px solid var(--line);border-radius:8px;font:inherit"></select>
    <span>时</span>
    <select id="schedM" style="padding:8px;border:1px solid var(--line);border-radius:8px;font:inherit"></select>
    <span>分</span>
    <button class="btn" onclick="addSched()">＋添加</button>
    <button class="btn primary" onclick="applySched()">应用到系统定时任务</button>
  </div>
  <div class="row" style="margin-top:8px;align-items:center">
    <div class="item" style="max-width:260px"><label>由谁值班</label>
      <select id="driver" style="width:100%;padding:8px 10px;border:1px solid var(--line);border-radius:8px;font:inherit">
        <option value="api">API 直连（config 里填好 api 块）</option>
        <option value="claude">Claude Code</option>
        <option value="zcode">ZCode</option>
        <option value="opencode">OpenCode</option>
        <option value="codex">Codex CLI</option>
        <option value="gemini">Gemini CLI</option>
        <option value="workbuddy">WorkBuddy（在她的面板里配时间）</option>
      </select></div>
    <div class="item"><label>&nbsp;</label>
      <div class="hint">到点在后台跑一轮（无窗口）。</div></div>
  </div>
  <div class="hint" id="schedMsg"></div>
</div>
</div>

<div class="foot">
  <button class="btn primary" id="save" onclick="save()">保存</button>
  <button class="btn" onclick="openToday()">打开她的一天</button>
  <button class="btn" onclick="openPosts()">她说过的话</button>
  <button class="btn" onclick="quitPage()">关掉设置页</button>
  <span class="msg" id="msg"></span>
</div>

<script>
const T = new URLSearchParams(location.search).get('t') || '';
let mode = 'dry';
const $ = id => document.getElementById(id);

function setMode(m){
  mode = m;
  $('m-dry').classList.toggle('on', m === 'dry');
  $('m-live').classList.toggle('on', m === 'live');
  $('modeHint').textContent = m === 'live'
    ? '真发模式：她会在评论区署你的名。发出去可以撤回，但已经有人可能看到了。'
    : '只演练：她照常逛、照常写、照常写日记，评论只进账本不出去。';
}

function fill(d){
  setMode(d.mode || 'dry');
  $('keywords').value = (d.keywords || []).join('\n');
  $('neg').value = (d.negative_keywords || []).join('\n');
  const b = d.budget || {};
  $('cap').value = b.cap ?? 1;
  $('replyCap').value = d.reply_cap ?? 3;
  $('dynamicWeek').value = d.dynamic_per_week ?? 2;
  $('interval').value = b.interval_min ?? 45;
  $('viewFloor').value = b.view_floor ?? 3000;
  $('durMax').value = b.dur_max ?? 1200;
  $('skip').value = Math.round((b.skip_prob ?? 0.22) * 100);
  $('quiet').value = Math.round((b.quiet_prob ?? 0.10) * 100);
  $('skipVal').textContent = $('skip').value + '%';
  $('quietVal').textContent = $('quiet').value + '%';
  const pn = d.persona_name;
  $('pNow').innerHTML = pn ? ('当前：<b>' + esc(pn) + '</b> · 来源 persona.local.json（没拖过就是默认大肥鱼）') : '性格卡没加载到，先用写法教材顶上。';
  $('atOwner').value = d.at_owner ? '1' : '0';
  $('learn').value = d.learn ? '1' : '0';
  schedTimes = d.schedule || [];
  $('driver').value = d.schedule_driver || 'api';
  renderSched();
  $('ownerNow').textContent = d.owner_nick
    ? ('现在可以 @：' + d.owner_nick + '（UID ' + d.owner_mid + '）· 默认不加，她只在觉得好玩时 @ 你，一天最多一次')
    : '还没配 @ 对象——就算加了 --at 也不会通知到任何人。';
  const a = d.account || {};
  $('who').innerHTML = a.login
    ? '<span>账号 <b>' + a.uname + '</b></span><span>等级 <b>Lv' + (a.level ?? '?') + '</b></span>'
      + '<span>今天 <b>' + ({skip:'不想看',quiet:'只看不说',woke:'想出门'}[d.mood?.roll] || '还没定') + '</b></span>'
      + '<span>模式 <b>' + (d.mode === 'live' ? '真发' : '只演练') + '</b></span>'
      + (d.self && d.self.level
          ? '<span>成长 <b>Lv' + d.self.level + '</b>（' + (d.self.xp % 40) + '/40）</span>'
            + '<span>今天 <b>' + ({skip:'不想看',quiet:'只想看',woke:'想出门'}[d.self.today] || '还没定') + '</b></span>'
            + (d.self.mood_text ? '<span>心情 <b>' + esc(d.self.mood_text) + '</b></span>' : '')
          : '')
    : '<span style="color:#a32d2d">没登录：' + (a.reason || '') + '</span>';
}

fetch('/api/config?t=' + encodeURIComponent(T)).then(r => r.json()).then(fill);

$('skip').oninput = e => $('skipVal').textContent = e.target.value + '%';
$('quiet').oninput = e => $('quietVal').textContent = e.target.value + '%';

function say(text, ok){
  const m = $('msg');
  m.textContent = text;
  m.className = 'msg ' + (ok === false ? 'err' : 'ok');
  setTimeout(() => { m.textContent = ''; m.className = 'msg'; }, 5000);
}

function save(){
  const body = {
    mode: mode,
    owner_input: $('owner').value.trim(),
    at_owner: $('atOwner').value === '1',
    learn: $('learn').value === '1',
    keywords_text: $('keywords').value,
    neg_text: $('neg').value,
    cap: $('cap').value,
    reply_cap: $('replyCap').value,
    dynamic_per_week: $('dynamicWeek').value,
    interval_min: $('interval').value,
    view_floor: $('viewFloor').value,
    dur_max: $('durMax').value,
    skip_prob: Number($('skip').value) / 100,
    quiet_prob: Number($('quiet').value) / 100
  };
  $('save').disabled = true;
  fetch('/api/config?t=' + encodeURIComponent(T), {
    method: 'POST',
    headers: {'Content-Type': 'application/json', 'X-Token': T},
    body: JSON.stringify(body)
  }).then(r => r.json()).then(d => {
    $('save').disabled = false;
    say(d.msg, d.ok);
    if (d.ok) fetch('/api/config?t=' + encodeURIComponent(T)).then(r => r.json()).then(fill);
  }).catch(e => { $('save').disabled = false; say('保存失败：' + e, false); });
}

setInterval(function(){
  fetch('/api/ping?t=' + encodeURIComponent(T)).catch(function(){});
}, 15000);

function quitPage(){
  fetch('/api/bye?t=' + encodeURIComponent(T), {method:'POST', headers:{'X-Token':T}})
    .catch(function(){})
    .then(function(){
      window.close();
      setTimeout(function(){
        document.body.innerHTML = '<div class="wrap"><h1>关掉了</h1>'
          + '<div class="sub">进程已经退出，这个窗口也关掉就行。</div></div>';
      }, 300);
    });
}

function openPosts(){
  fetch('/api/open-posts?t=' + encodeURIComponent(T), {method:'POST', headers:{'X-Token':T}})
    .then(r => r.json()).then(d => say(d.msg, d.ok));
}

function openToday(){
  fetch('/api/open-today?t=' + encodeURIComponent(T), {method:'POST', headers:{'X-Token':T}})
    .then(r => r.json()).then(d => say(d.msg, d.ok));
}

function esc(s){
  return String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
}

function loadChat(){
  fetch('/api/chat?t=' + encodeURIComponent(T)).then(r => r.json()).then(d => {
    const rows = (d.history || []).slice(-6);
    $('chatList').innerHTML = rows.length
      ? rows.map(r => '<div style="margin:3px 0"><span style="color:' + (r.role === 'her' ? '#185fa5' : '#6b7280') + '">'
          + (r.role === 'her' ? '她' : '你') + '：</span>' + esc(r.text) + '</div>').join('')
      : '<span style="color:#6b7280">还没说过话。</span>';
  });
}

function sayIt(){
  const t = $('sayText').value.trim();
  if (!t) { say('说点什么', false); return; }
  fetch('/api/say?t=' + encodeURIComponent(T), {
    method: 'POST',
    headers: {'Content-Type': 'application/json', 'X-Token': T},
    body: JSON.stringify({text: t})
  }).then(r => r.json()).then(d => {
    if (d.ok) { $('sayText').value = ''; }
    say(d.msg, d.ok);
    loadChat();
  }).catch(e => say('没发出去：' + e, false));
}

let pollTimer = null;

function startLogin(){
  $('qrBox').style.display = 'block';
  $('qrImg').innerHTML = '';
  $('qrMsg').textContent = '生成二维码…';
  fetch('/api/login/qr?t=' + encodeURIComponent(T)).then(r=>r.json()).then(d=>{
    if(!d.ok){ $('qrMsg').textContent = d.msg || '生成失败'; return; }
    $('qrImg').innerHTML = d.svg;
    $('qrMsg').textContent = '用 B站 App（登录着小号的那个）扫，然后在手机上点「确认登录」。';
    if(pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(pollLogin, 2000);
  }).catch(e=>{ $('qrMsg').textContent = '生成失败：' + e; });
}

function pollLogin(){
  fetch('/api/login/poll?t=' + encodeURIComponent(T)).then(r=>r.json()).then(d=>{
    if(d.state === 'ok'){
      clearInterval(pollTimer); pollTimer = null;
      $('qrMsg').textContent = d.msg || '登录成功';
      if(d.login) setTimeout(function(){ location.reload(); }, 1500);
    } else if(d.state === 'expired'){
      clearInterval(pollTimer); pollTimer = null;
      $('qrMsg').textContent = d.msg || '二维码过期了，点「扫码登录」再来一次。';
      $('qrMsg').style.color = 'var(--warn)';
    }
  }).catch(function(){});
}

function doLogout(){
  if(!confirm('确定收回账号？她立刻就够不着这个号了（日记和账本会留在本地）。')) return;
  fetch('/api/logout?t=' + encodeURIComponent(T), {method:'POST', headers:{'X-Token':T}})
    .then(r=>r.json()).then(d=>{ $('accMsg').textContent = d.msg; setTimeout(function(){ location.reload(); }, 1200); })
    .catch(e=>{ $('accMsg').textContent = '失败：' + e; });
}

const drop = $('drop'), pf = $('pfile');
if (drop) {
  drop.onclick = function(){ pf.click(); };
  pf.onchange = function(){ if (pf.files[0]) importPersona(pf.files[0]); };
  drop.ondragover = function(e){ e.preventDefault(); drop.style.borderColor = 'var(--accent)'; };
  drop.ondragleave = function(){ drop.style.borderColor = 'var(--line)'; };
  drop.ondrop = function(e){ e.preventDefault(); drop.style.borderColor = 'var(--line)';
    if (e.dataTransfer.files[0]) importPersona(e.dataTransfer.files[0]); };
}
function importPersona(f){
  const rd = new FileReader();
  rd.onload = function(){
    fetch('/api/persona-import?t=' + encodeURIComponent(T), {method:'POST',
      headers:{'Content-Type':'application/json','X-Token':T}, body: JSON.stringify({json: rd.result})})
      .then(r=>r.json()).then(d=>{ say(d.msg, d.ok); if(d.ok) setTimeout(function(){ location.reload(); }, 1200); })
      .catch(e=>say('导入失败：' + e, false));
  };
  rd.readAsText(f, 'utf-8');
}

let schedTimes = [];
function renderSched(){
  $('schedChips').innerHTML = schedTimes.length
    ? schedTimes.map(function(t){
        return '<span style="background:#eef5fc;color:#185fa5;border-radius:8px;padding:4px 10px;font-size:13px">'
          + t + ' <a href="javascript:void(0)" onclick="delSched(\'' + t + '\')" style="color:#a32d2d;text-decoration:none">×</a></span>';
      }).join(' ')
    : '<span style="color:var(--dim)">还没有值班时间——选好时分点「＋添加」。</span>';
}
function delSched(t){ schedTimes = schedTimes.filter(function(x){return x !== t;}); renderSched(); }
function addSched(){
  const h = $('schedH').value, m = $('schedM').value, t = h + ':' + m;
  if (schedTimes.indexOf(t) < 0) schedTimes.push(t);
  schedTimes.sort();
  renderSched();
}
(function initSched(){
  const h = $('schedH'), m = $('schedM');
  for (let i = 0; i < 24; i++) h.add(new Option((i<10?'0':'')+i, (i<10?'0':'')+i));
  for (let i = 0; i < 60; i += 5) m.add(new Option((i<10?'0':'')+i, (i<10?'0':'')+i));
  h.value = '12'; m.value = '50';
})();

function applySched(){
  if(!schedTimes.length){ say('先添加至少一个值班时间', false); return; }
  fetch('/api/schedule?t=' + encodeURIComponent(T), {method:'POST',
    headers:{'Content-Type':'application/json','X-Token':T},
    body: JSON.stringify({times: schedTimes, driver: $('driver').value})})
    .then(r=>r.json()).then(d=>say(d.msg, d.ok)).catch(e=>say('失败：' + e, false));
}

loadChat();

</script>
</body></html>"""


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authed(self, q):
        origin = self.headers.get("Origin") or ""
        if origin and origin not in ("http://127.0.0.1:%d" % PORT, "http://localhost:%d" % PORT):
            return False
        t = (q.get("t") or [""])[0] or self.headers.get("X-Token") or ""
        return t == TOKEN

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception:
            return {}

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        if u.path in ("/", "/index.html"):
            if not self._authed(q):
                return self._json({"error": "bad token"}, 403)
            body = PAGE.replace("__TOKEN__", TOKEN).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store, max-age=0")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if u.path == "/api/config":
            if not self._authed(q):
                return self._json({"ok": False, "msg": "token 不对"}, 403)
            return self._json(snapshot())
        if u.path == "/api/ping":
            global LAST_PING
            if not self._authed(q):
                return self._json({"ok": False}, 403)
            LAST_PING = time.time()
            return self._json({"ok": True})
        if u.path == "/api/chat":
            if not self._authed(q):
                return self._json({"ok": False, "msg": "token 不对"}, 403)
            return self._json({"history": duty.chat_history(30),
                               "unread": len(duty.chat_unread())})
        if u.path == "/api/login/qr":
            if not self._authed(q):
                return self._json({"ok": False, "msg": "token 不对"}, 403)
            try:
                url, key = bili.qr_generate()
            except Exception as exc:
                return self._json({"ok": False, "msg": "生成二维码失败：%s" % exc})
            _LOGIN["key"] = key
            return self._json({"ok": True, "svg": _qr_svg(url)})
        if u.path == "/api/login/poll":
            if not self._authed(q):
                return self._json({"ok": False, "msg": "token 不对"}, 403)
            if not _LOGIN.get("key"):
                return self._json({"ok": True, "state": "idle", "msg": "先点扫码登录"})
            state, cookies, msg = bili.qr_poll(_LOGIN["key"])
            d = {"ok": True, "state": state, "msg": msg}
            if state == "ok":
                who = duty._save_login(cookies)
                d["login"] = bool(who.get("login"))
                d["uname"] = who.get("uname")
                d["msg"] = ("她是 %s 了。模式还是 dry，确认语气后再切真发。"
                            % (who.get("uname") or "这个号")) if who.get("login") \
                    else "凭证拿到了但登录态没认出来，再扫一次"
                _LOGIN["key"] = None
            return self._json(d)
        return self._json({"error": "not found"}, 404)

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        body = self._body()          # 先读干净，再判权限：不然客户端会看到连接被掐断
        if not self._authed(q):
            return self._json({"ok": False, "msg": "token 不对"}, 403)
        if u.path == "/api/config":
            ok, msg = save(body)
            return self._json({"ok": ok, "msg": msg})
        if u.path == "/api/bye":
            if not self._authed(q):
                return self._json({"ok": False, "msg": "token 不对"}, 403)
            self._json({"ok": True, "msg": "退出"})
            threading.Timer(0.5, lambda: os._exit(0)).start()
            return
        if u.path == "/api/logout":
            c = bili.load_conf()
            cleared = [k for k in ("SESSDATA", "bili_jct", "COOKIE_RAW", "DedeUserID",
                                   "bili_ticket", "bili_ticket_expires") if c.pop(k, None)]
            bili.save_conf(c)
            return self._json({"ok": True, "cleared": cleared,
                               "msg": ("凭证清掉了，她够不着这个号了" if cleared
                                       else "本来就没有登录态") + "；想删干净她的记忆就删 state/ 目录。"})
        if u.path == "/api/persona-import":
            try:
                import lib.persona as persona_mod
                d = json.loads(body.get("json") or "{}")
                if not str(d.get("name") or "").strip():
                    return self._json({"ok": False, "msg": "这张 json 里没有 name 字段，不像性格卡"})
                persona_mod.save(d)
                return self._json({"ok": True, "msg": "性格已换成「%s」，下一轮生效" % d["name"]})
            except Exception as exc:
                return self._json({"ok": False, "msg": "导入失败：%s" % exc})
        if u.path == "/api/schedule":
            times = [t for t in (body.get("times") or [])
                     if re.match(r"^\d{1,2}:\d{2}$", str(t))]
            driver = body.get("driver") or "api"
            if not times:
                return self._json({"ok": False, "msg": "时间一行一个，如 12:50"})
            c = bili.load_conf()
            c["schedule"] = times
            c["schedule_driver"] = driver
            bili.save_conf(c)
            import subprocess
            def st(args):
                # schtasks 在中文 Windows 上输出 GBK，按 UTF-8 解码会直接炸
                return subprocess.run(["schtasks"] + args, capture_output=True, text=True,
                                      encoding="gbk", errors="ignore")
            q = st(["/Query", "/FO", "CSV"])
            old = {ln.split(",")[0].strip('"') for ln in (q.stdout or "").splitlines()
                   if ln.startswith('"dafeiyu-')}
            if driver == "workbuddy":
                for name in sorted(old):
                    st(["/Delete", "/TN", name, "/F"])
                return self._json({"ok": True, "msg":
                    ("WorkBuddy 的定时在她的自动化面板里配：时间按 %s 设（每天），"
                     "提示词用 automation-prompt.txt 原文；系统里残留的 dafeiyu 定时任务已清理"
                     % "、".join(times))})
            vbs = os.path.join(ROOT, "tools", "windows", "duty.vbs")
            tr = 'wscript.exe "%s" %s' % (vbs, driver)
            q = st(["/Query", "/FO", "CSV"])
            old = {ln.split(",")[0].strip('"') for ln in (q.stdout or "").splitlines()
                   if ln.startswith('"dafeiyu-')}
            want = {"dafeiyu-%s" % t.replace(":", "") for t in times}
            outm = []
            for name in sorted(old - want):
                st(["/Delete", "/TN", name, "/F"])
                outm.append("已删除 " + name)
            for t in times:
                h, m = t.split(":")
                r = st(["/Create", "/F", "/TN", "dafeiyu-%s" % t.replace(":", ""),
                        "/SC", "DAILY", "/ST", "%02d:%s" % (int(h) % 24, m), "/TR", tr])
                outm.append(("已排 %s" % t) if r.returncode == 0
                            else ("%s 失败：%s" % (t, ((r.stderr or r.stdout) or "").strip()[-60:])))
            return self._json({"ok": True, "msg": " ".join(outm) or "没有变化"})
        if u.path == "/api/say":
            text = (body.get("text") or "").strip()
            if not text:
                return self._json({"ok": False, "msg": "说点什么"})
            if len(text) > 500:
                return self._json({"ok": False, "msg": "一次 500 字以内"})
            duty.chat_append("user", text)
            return self._json({"ok": True, "msg": "留言存好了，她下一次醒来会看到"})
        if u.path == "/api/open-posts":
            try:
                duty.render_posts()
            except Exception:
                pass
            p = os.path.join(STATE, "她说过的话.md")
            if not os.path.exists(p):
                return self._json({"ok": False, "msg": "账本里还没有评论"})
            try:
                from lib import view
                view.open_md(p, title="她说过的话")
                return self._json({"ok": True, "msg": "浏览器里打开了"})
            except Exception as exc:
                return self._json({"ok": False, "msg": str(exc)})
        if u.path == "/api/open-today":
            p = os.path.join(STATE, "今天.md")
            if not os.path.exists(p):
                return self._json({"ok": False, "msg": "她今天还没写（等下一轮跑完）"})
            try:
                from lib import view
                view.open_md(p, title="她的一天")
            except Exception as exc:
                return self._json({"ok": False, "msg": "打不开：%s" % exc})
            return self._json({"ok": True, "msg": "浏览器里打开了《她的一天》"})
        if u.path == "/api/quit":
            self._json({"ok": True, "msg": "关了"})
            threading.Thread(target=lambda: (time.sleep(0.3), os._exit(0)), daemon=True).start()
            return
        return self._json({"error": "not found"}, 404)


def _already_running():
    """双击第二次的时候，别再起一个服务，直接把已经开着的那个页面调出来"""
    try:
        with open(os.path.join(STATE, ".settings_url"), encoding="utf-8") as f:
            url = f.read().strip()
        u = urllib.parse.urlparse(url)
        if not u.port:
            return None
        from http.client import HTTPConnection
        c = HTTPConnection(u.hostname or "127.0.0.1", u.port, timeout=1.5)
        c.request("GET", u.path + ("?" + u.query if u.query else ""))
        r = c.getresponse()
        r.read()
        c.close()
        return url if r.status == 200 else None
    except Exception:
        return None


def _say(msg):
    """pythonw 没有控制台时 sys.stdout 可能是 None，print 会炸，这里吞掉"""
    try:
        print(msg, flush=True)
    except Exception:
        pass


CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def _run_quiet(cmd):
    """在 pythonw 里调 netstat/taskkill，不加这个标志就会闪一下黑框"""
    import subprocess
    try:
        return subprocess.run(cmd, capture_output=True, text=True, errors="ignore",
                              creationflags=CREATE_NO_WINDOW)
    except Exception:
        return None


def _kill_port_owner(lo, hi):
    """把占着 8791 附近的旧设置页关掉——不关的话新代码永远没机会跑起来"""
    killed = []
    r = _run_quiet(["netstat", "-ano"])
    if not r:
        return killed
    out = r.stdout or ""
    pids = set()
    for line in out.splitlines():
        if "LISTENING" not in line:
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        addr = parts[1]
        try:
            port = int(addr.rsplit(":", 1)[1])
        except Exception:
            continue
        if lo <= port <= hi:
            pids.add(parts[-1])
    for pid in pids:
        if not pid.isdigit() or int(pid) == os.getpid():
            continue
        # 只杀自己家的旧实例：命令行里必须是本文件自己的绝对路径。
        # 只认 settings_server 子串还是太宽——别个项目同名脚本照样会中招。
        # 确认不了就不杀：端口被占就走下一个（main 里本来就会顺延），
        # 杀错别人的进程没法补救，宁可多占一个端口。
        ours = os.path.abspath(__file__).lower()
        rr = _run_quiet(["powershell", "-NoProfile", "-Command",
                         "(Get-CimInstance Win32_Process -Filter 'ProcessId=%s').CommandLine" % pid])
        if rr is None or rr.returncode != 0:
            continue
        if ours not in (rr.stdout or "").lower():
            continue
        _run_quiet(["taskkill", "/PID", pid, "/F"])
        killed.append(pid)
    if killed:
        time.sleep(0.8)
    return killed


def _watchdog():
    """页面关掉就自己退：没人心跳超过 IDLE_SEC 秒，进程收工"""
    started = time.time()
    while True:
        time.sleep(5)
        now = time.time()
        if LAST_PING < started:
            if now - started > GRACE_SEC:
                _say("没人打开页面，退出")
                os._exit(0)
        elif now - LAST_PING > IDLE_SEC:
            _say("页面关掉了，退出")
            os._exit(0)


def main():
    global PORT
    base = PORT
    _say("\n[%s] 启动设置页" % time.strftime("%Y-%m-%d %H:%M:%S"))

    # 默认先清掉旧实例：不重启的话，双击打开的永远是上一次的页面
    if os.environ.get("SETTINGS_REUSE") != "1":
        killed = _kill_port_owner(base, base + 5)
        if killed:
            _say("关掉了旧实例：%s" % ", ".join(killed))

    old = _already_running()
    if old:
        _say("已经开着一个了：%s" % old)
        if not os.environ.get("SETTINGS_NO_OPEN"):
            webbrowser.open(old)
        return

    for p in range(base, base + 6):
        PORT = p
        try:
            httpd = ThreadingHTTPServer(("127.0.0.1", p), Handler)
        except OSError:
            continue
        url = "http://127.0.0.1:%d/?t=%s" % (p, TOKEN)
        try:
            os.makedirs(STATE, exist_ok=True)
            with open(os.path.join(STATE, ".settings_url"), "w", encoding="utf-8") as f:
                f.write(url + "\n")
        except Exception:
            pass
        _say("设置页：%s" % url)
        if not os.environ.get("SETTINGS_NO_OPEN"):
            threading.Timer(0.6, lambda: webbrowser.open(url)).start()
        threading.Thread(target=_watchdog, daemon=True).start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
        return
    fatal("%d-%d 端口都被占用了。\n\n关掉别的设置页窗口再试，或者重启电脑。" % (base, base + 5))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        tb = traceback.format_exc()
        try:
            sys.stderr.write(tb)
            sys.stderr.flush()
        except Exception:
            pass
        last = [x for x in tb.strip().splitlines() if x.strip()][-1]
        fatal("设置页起不来：\n\n%s\n\n详情看 logs\\settings.log" % last)
