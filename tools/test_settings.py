# -*- coding: utf-8 -*-
"""tools/test_settings.py — 设置页回归测试（不开浏览器、不改配置）

    python tools/test_settings.py
"""

import importlib.util
import json
import os
import socket
import sys
import tempfile
import threading
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

spec = importlib.util.spec_from_file_location("settings_server", os.path.join(HERE, "settings_server.py"))
srv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(srv)

from http.server import ThreadingHTTPServer  # noqa: E402

# 用临时端口跑测试，别跟正在用的设置页抢 8791
_s = socket.socket()
_s.bind(("127.0.0.1", 0))
FREE_PORT = _s.getsockname()[1]
_s.close()
srv.PORT = FREE_PORT
# 聊天写到临时目录，别把测试留言混进她真正的对话里
srv.duty.CHAT = tempfile.mkdtemp(prefix="feiyu-chat-")
# 性格卡同样隔离：下面要测"导入一张卡再删掉"，
# 不隔离的话会先覆盖、再删掉用户真正的 persona.local.json。
# 注意只能指到项目根之内——persona._checked() 会拒绝根外的路径（这是它该有的警惕）
import lib.persona as _persona  # noqa: E402
from pathlib import Path as _Path  # noqa: E402
os.makedirs(os.path.join(ROOT, "state"), exist_ok=True)
_persona.LOCAL = _Path(os.path.join(ROOT, "state", "feiyu-test-persona.local.json"))
if _persona.LOCAL.exists():
    _persona.LOCAL.unlink()

BASE = "http://127.0.0.1:%d" % FREE_PORT
T = srv.TOKEN


def call(path, method="GET", body=None, token=True, origin=None):
    url = BASE + path + (("&" if "?" in path else "?") + "t=" + T if token else "")
    req = urllib.request.Request(url, method=method,
                                 data=json.dumps(body).encode() if body is not None else None)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("X-Token", T)
    if origin:
        req.add_header("Origin", origin)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")


def main():
    httpd = ThreadingHTTPServer(("127.0.0.1", srv.PORT), srv.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    ok = True

    def check(name, cond, extra=""):
        nonlocal ok
        print(("PASS " if cond else "FAIL ") + name + (" | " + extra if extra else ""))
        ok = ok and cond

    code, body = call("/", token=False)
    check("没 token 打不开页面", code == 403, str(code))

    code, body = call("/")
    check("带 token 打开页面", code == 200 and "大肥鱼 · 设置" in body, str(code))

    code, body = call("/api/config")
    d = json.loads(body)
    check("配置能读", code == 200 and "budget" in d, "keys=" + ",".join(sorted(d)[:5]))

    cur = dict(mode=d["mode"], owner_input="", at_owner=d["at_owner"],
               keywords_text="\n".join(d["keywords"]),
               neg_text="\n".join(d["negative_keywords"]), reply_cap=d.get("reply_cap"),
               cap=d["budget"].get("cap"), interval_min=d["budget"].get("interval_min"),
               view_floor=d["budget"].get("view_floor"), dur_max=d["budget"].get("dur_max"),
               skip_prob=d["budget"].get("skip_prob"), quiet_prob=d["budget"].get("quiet_prob"))
    code, body = call("/api/config", "POST", cur, origin=BASE)
    r = json.loads(body)
    check("原样保存不改配置", code == 200 and r["ok"] and "没有变化" in r["msg"], r["msg"])

    code, body = call("/api/config", "POST", cur, token=False)
    check("没 token 不能保存", code == 403, str(code))

    code, body = call("/api/config", "POST", cur, origin="https://evil.example")
    check("外站 origin 被拒", code == 403, str(code))

    code, body = call("/api/config", "POST", dict(cur, owner_input="abc"))
    r = json.loads(body)
    check("乱填 owner 被拒", code == 200 and not r["ok"], r["msg"])

    # 先把 cap 拉回 1，保证下面的越界测试有起点
    call("/api/config", "POST", dict(cur, cap=1))
    code, body = call("/api/config", "POST", dict(cur, cap=99))
    r = json.loads(body)
    check("cap 超范围被夹到 8", code == 200 and r["ok"] and "cap → 8" in r["msg"], r["msg"])

    code, body = call("/api/config", "POST", dict(cur, reply_cap=99))
    r = json.loads(body)
    check("楼中楼上限被夹到 12", code == 200 and r["ok"] and "12" in r["msg"], r["msg"])

    # 还原成测试前的样子——别把用户设的上限改回 1（之前就是这里把她设的值冲掉了）
    call("/api/config", "POST", dict(cur))

    code, body = call("/api/say", "POST", {"text": "自检留言"}, origin=BASE)
    r = json.loads(body)
    check("留言能存", code == 200 and r["ok"], r["msg"])

    code, body = call("/api/ping")
    r = json.loads(body)
    check("心跳能打", code == 200 and r["ok"], "ok")

    code, body = call("/api/chat")
    d = json.loads(body)
    check("聊天记录能读", code == 200 and any(x.get("text") == "自检留言" for x in d["history"]),
          "条数=%d" % len(d.get("history") or []))

    code, body = call("/api/persona-import", "POST", {"json": json.dumps({
        "name": "测试鱼", "self_call": "本测", "call_user": "铲屎官",
        "species": "测试用的鱼", "catchphrase": "汪", "likes": ["a", "b"], "notes": "n"},
        ensure_ascii=False)}, origin=BASE)
    r = json.loads(body)
    check("性格卡 json 能导入", code == 200 and r["ok"] and "测试鱼" in r["msg"], r["msg"])
    import lib.persona as _pm
    pc = _pm.load()
    check("导入后读得回且能渲染", bool(pc) and pc.get("name") == "测试鱼"
          and "本测" in _pm.render(pc), "name=%s" % (pc or {}).get("name"))
    try:
        _pm.LOCAL.unlink()      # 测试产物清掉，别给用户留一张"测试鱼"
    except OSError:
        pass

    code, body = call("/api/open-today", "POST")
    print("info 打开她的一天：", body[:80])

    httpd.shutdown()
    print("\n结果：" + ("全部通过" if ok else "有失败"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
