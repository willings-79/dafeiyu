# -*- coding: utf-8 -*-
"""
lib/bili.py — B站读写（v2）

和 v1 的区别只有一条：**凭证永远自动带上**。
    cookie = bili.cookie_header()   # 从 config.local.json 读，不再依赖环境变量

提供：
    whoami()                 登录态 / mid / uname / level
    search(kw, page)         关键词搜视频（wbi 签名）
    ranking() / popular()    榜单（探索位）
    meta(bvid)               详情
    subtitle(bvid, cid)      字幕（自动带 cookie）
    comments(aid, top)       热评
    danmaku(cid, pages)      弹幕
    reply_add(aid, text, at) 发评论（可 @ 人，带 at_name_to_mid）
    reply_del(aid, rpid)     撤回自己的评论
"""

import gzip
import hashlib
import html
import json
import os
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONF = os.path.join(ROOT, "config.local.json")
COOLDOWN = os.path.join(ROOT, "state", ".cooldown.json")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

HEADERS = {
    "User-Agent": UA,
    "Referer": "https://www.bilibili.com/",
    "Origin": "https://www.bilibili.com",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Accept-Encoding": "gzip",
    "sec-ch-ua": '"Chromium";v="126", "Not;A=Brand";v="24"',
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
}

MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
    33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
    61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
    36, 20, 34, 44, 52,
]

_cache = {"keys": None, "at": 0}
_SSL_CTX = None


def ssl_context():
    """固定用 certifi 的 CA 包（pip 装依赖时自带）：不依赖系统证书环境——
    中文 Windows 上 Python 的默认证书路径常被代理/杀软/SSL_CERT_FILE 弄坏，
    表现就是 CERTIFICATE_VERIFY_FAILED（pip 能装包、urllib 全挂）。"""
    global _SSL_CTX
    if _SSL_CTX is None:
        try:
            import certifi
            _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
        except Exception:
            _SSL_CTX = ssl.create_default_context()
    return _SSL_CTX


# 全部请求走这个 opener：证书固定 certifi，不随系统证书环境漂移
_OPENER = urllib.request.build_opener(
    urllib.request.HTTPSHandler(context=ssl_context()))


# ---------------------------------------------------------------- 配置

def load_conf():
    try:
        with open(CONF, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_conf(c):
    # 原子写：这文件里存着 SESSDATA，写一半崩溃/断电 = "莫名其妙没登录了"
    from pathlib import Path
    conf = Path(CONF)
    tmp = conf.with_name(conf.name + ".tmp")
    tmp.write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(str(tmp), str(conf))
    try:
        os.chmod(conf, 0o600)
    except Exception:
        pass


def cookie_header(conf=None):
    c = conf if conf is not None else load_conf()
    # 有浏览器原样 Cookie 就整串照发——buvid_fp / _uuid / b_lsid 这些
    # 是 JS 算出来的，自己拼不出来，缺一个就像"不是同一个浏览器"
    if c.get("COOKIE_RAW"):
        raw = c["COOKIE_RAW"]
        for k in ("SESSDATA", "bili_jct"):
            if c.get(k) and ("%s=" % k) not in raw:
                raw += "; %s=%s" % (k, c[k])
        return raw
    parts = []
    for k in ("SESSDATA", "bili_jct", "buvid3", "buvid4", "bili_ticket",
              "DedeUserID", "b_nut"):
        if c.get(k):
            parts.append("%s=%s" % (k, c[k]))
    return "; ".join(parts) if parts else None


# ---------------------------------------------------------------- 网络

def cooldown_left():
    try:
        with open(COOLDOWN, encoding="utf-8") as f:
            d = json.load(f)
        return max(0, int(d.get("until", 0) - time.time())), d.get("reason", "")
    except Exception:
        return 0, ""


def set_cooldown(minutes, reason):
    os.makedirs(os.path.dirname(COOLDOWN), exist_ok=True)
    with open(COOLDOWN, "w", encoding="utf-8") as f:
        json.dump({"until": time.time() + minutes * 60, "reason": reason,
                   "since": time.strftime("%Y-%m-%d %H:%M:%S")}, f, ensure_ascii=False)
    print("  [风控] %s —— 停手 %d 分钟，不重试" % (reason, minutes))


def _request(url, cookie=None, data=None):
    req = urllib.request.Request(url, headers=dict(HEADERS), data=data)
    if cookie:
        req.add_header("Cookie", cookie)
    if data is not None:
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with _OPENER.open(req, timeout=25) as r:
            raw = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
    except urllib.error.HTTPError as exc:
        if exc.code in (412, 429):
            set_cooldown(120, "HTTP %d" % exc.code)
        raise
    return json.loads(raw.decode("utf-8", "ignore"))


def get(path, params=None, cookie=None):
    url = "https://api.bilibili.com" + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    return _request(url, cookie=cookie or cookie_header())


def post_form(path, params, cookie=None):
    body = urllib.parse.urlencode(params).encode()
    return _request("https://api.bilibili.com" + path, cookie=cookie or cookie_header(), data=body)


# ---------------------------------------------------------------- wbi

def _mixin(orig):
    return "".join(orig[i] for i in MIXIN_KEY_ENC_TAB)[:32]


def get_keys(force=False):
    now = time.time()
    if not force and _cache["keys"] and now - _cache["at"] < 1800:
        return _cache["keys"]
    d = get("/x/web-interface/nav")
    img = (d.get("data") or {}).get("wbi_img") or {}
    if not img.get("img_url"):
        raise RuntimeError("拿不到 wbi 密钥：%s" % (d.get("message") or d.get("code")))
    i = img["img_url"].rsplit("/", 1)[-1].split(".")[0]
    s = img["sub_url"].rsplit("/", 1)[-1].split(".")[0]
    _cache.update(keys=(i, s), at=now)
    return i, s


def sign(params):
    i, s = get_keys()
    mixin = _mixin(i + s)
    p = dict(params)
    p["wts"] = int(time.time())
    clean = {k: "".join(ch for ch in str(v) if ch not in "!'()*") for k, v in p.items()}
    q = urllib.parse.urlencode(sorted(clean.items()))
    clean["w_rid"] = hashlib.md5((q + mixin).encode()).hexdigest()
    return clean


# ---------------------------------------------------------------- 账号

def whoami():
    d = get("/x/web-interface/nav")
    data = d.get("data") or {}
    return {
        "login": bool(data.get("isLogin")),
        "mid": data.get("mid"),
        "uname": data.get("uname"),
        "level": (data.get("level_info") or {}).get("current_level"),
        "reason": None if data.get("isLogin") else (d.get("message") or "没登录"),
    }


def card(mid):
    """按 mid 查昵称，用来配"要 @ 的那个人"（主人主号）"""
    d = get("/x/web-interface/card", {"mid": mid})
    if d.get("code") != 0:
        raise RuntimeError("card code=%s %s" % (d.get("code"), d.get("message")))
    c = (d.get("data") or {}).get("card") or {}
    return {"mid": c.get("mid"), "name": c.get("name")}


# ---------------------------------------------------------------- 候选

def _clean(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def _secs(dur):
    """"12:34" / "1:02:03" -> 秒"""
    if isinstance(dur, (int, float)):
        return int(dur)
    parts = [p for p in str(dur).split(":") if p.strip().isdigit()]
    total = 0
    for p in parts:
        total = total * 60 + int(p)
    return total


def search(kw, page=1):
    """关键词搜视频。返回精简条目列表（title 已去 <em>）"""
    p = sign({"search_type": "video", "keyword": kw, "page": page, "page_size": 20})
    d = get("/x/web-interface/wbi/search/type", p)
    if d.get("code") != 0:
        raise RuntimeError("search code=%s %s" % (d.get("code"), d.get("message")))
    out = []
    for x in ((d.get("data") or {}).get("result") or []):
        if not x.get("bvid"):
            continue
        out.append({
            "bvid": x["bvid"],
            "title": _clean(x.get("title")),
            "owner": _clean(x.get("author")),
            "mid": x.get("mid"),
            "view": x.get("play") or 0,
            "reply": x.get("video_review") or 0,
            "duration": _secs(x.get("duration")),
            "pubdate": x.get("pubdate") or 0,
            "desc": _clean(x.get("description")),
            "src": "search:" + kw,
        })
    return out


def ranking(limit=60):
    p = sign({"rid": 0, "type": "all"})
    d = get("/x/web-interface/ranking/v2", p)
    out = []
    for x in (((d.get("data") or {}).get("list")) or [])[:limit]:
        st = x.get("stat") or {}
        out.append({
            "bvid": x.get("bvid"), "title": _clean(x.get("title")),
            "owner": ((x.get("owner") or {}).get("name")), "mid": (x.get("owner") or {}).get("mid"),
            "view": st.get("view") or 0, "reply": st.get("reply") or 0,
            "duration": x.get("duration") or 0, "pubdate": x.get("pubdate") or 0,
            "desc": _clean(x.get("desc")), "src": "ranking",
        })
    return [x for x in out if x["bvid"]]


def following_videos(pages=2):
    """已关注 UP 的视频动态。一次请求拿关注流，不逐个 UP 打空间接口。

    只取 DYNAMIC_TYPE_AV（投稿转发的视频卡片），返回精简条目。
    翻页靠接口给的 offset；重复 offset 或空页就停。
    """
    out, seen, offset = [], set(), ""
    for pn in range(1, max(1, pages) + 1):
        p = {"type": "video", "page": pn}
        if offset:
            p["offset"] = offset
        d = get("/x/polymer/web-dynamic/v1/feed/all", p)
        if d.get("code") != 0:
            if pn == 1:
                raise RuntimeError("following code=%s %s" % (d.get("code"), d.get("message")))
            break
        data = d.get("data") or {}
        items = data.get("items") or []
        if not items:
            break
        for x in items:
            if x.get("type") != "DYNAMIC_TYPE_AV":
                continue
            mods = x.get("modules") or {}
            ar = (((mods.get("module_dynamic") or {}).get("major") or {})
                  .get("archive") or {})
            au = mods.get("module_author") or {}
            bvid = ar.get("bvid")
            if not bvid or bvid in seen:
                continue
            st = ar.get("stat") or {}
            try:
                view = int(st.get("play") or 0)
            except (TypeError, ValueError):
                view = 0
            try:
                pub_ts = int(au.get("pub_ts") or 0)
            except (TypeError, ValueError):
                pub_ts = 0
            seen.add(bvid)
            out.append({
                "bvid": bvid,
                "title": _clean(ar.get("title")),
                "owner": _clean(au.get("name")),
                "mid": au.get("mid"),
                "view": view,
                "reply": 0,
                "duration": _secs(ar.get("duration_text")),
                "pubdate": pub_ts,
                "desc": _clean(ar.get("desc")),
                "cover": ar.get("cover") or "",
                "src": "following",
                "why": "关注了 %s" % _clean(au.get("name") or "的 UP"),
            })
        nxt = str(data.get("offset") or "")
        if not nxt or nxt == offset:
            break
        offset = nxt
    return out


def popular(pages=2):
    out = []
    for pn in range(1, pages + 1):
        d = get("/x/web-interface/popular", {"ps": 20, "pn": pn})
        for x in ((d.get("data") or {}).get("list") or []):
            st = x.get("stat") or {}
            out.append({
                "bvid": x.get("bvid"), "title": _clean(x.get("title")),
                "owner": ((x.get("owner") or {}).get("name")), "mid": (x.get("owner") or {}).get("mid"),
                "view": st.get("view") or 0, "reply": st.get("reply") or 0,
                "duration": x.get("duration") or 0, "pubdate": x.get("pubdate") or 0,
                "desc": _clean(x.get("desc")), "src": "popular",
            })
    return [x for x in out if x["bvid"]]


# ---------------------------------------------------------------- 详情

def meta(bvid):
    d = get("/x/web-interface/view", {"bvid": bvid})
    if d.get("code") != 0:
        raise RuntimeError("view code=%s %s" % (d.get("code"), d.get("message")))
    data = d.get("data") or {}
    rights = data.get("rights") or {}
    pay = bool(data.get("is_upower_exclusive") or data.get("is_upower_play")
               or rights.get("pay") == 1 or rights.get("ugc_pay") == 1)
    return {
        "bvid": data.get("bvid"), "aid": data.get("aid"), "cid": data.get("cid"),
        "title": data.get("title"), "desc": (data.get("desc") or "").strip(),
        "owner": (data.get("owner") or {}).get("name"),
        "owner_mid": (data.get("owner") or {}).get("mid"),
        "tname": data.get("tname"), "duration": data.get("duration") or 0,
        "pubdate": data.get("pubdate") or 0,
        "pay": pay,
        "exclusive": bool(data.get("is_upower_exclusive")),
        "stat": data.get("stat") or {},
        "pages": data.get("pages") or [],
    }


def subtitle(bvid, cid, aid=None):
    """字幕。凭证自动带上——v1 就是漏了这一步，43 份素材全空。

    两个坑：① 不带签名的 /x/player/v2 常常只回一条空壳（subtitle_url 是空串）；
    ② 同一个视频会给好几条中文轨，长度差一倍。所以走 wbi 签名接口，
    再把中文轨都拉一遍，取最长的那份。
    """
    tracks = []
    for attempt in range(3):
        p = {"bvid": bvid, "cid": cid}
        if aid:
            p["aid"] = aid
        d = get("/x/player/wbi/v2", sign(p))
        if d.get("code") != 0:
            d = get("/x/player/v2", p)
        subs = ((d.get("data") or {}).get("subtitle") or {}).get("subtitles") or []
        tracks = [s for s in subs if s.get("subtitle_url")]
        if tracks:
            break
        time.sleep(0.8)
    if not tracks:
        return []

    zh = [s for s in tracks
          if "zh" in str(s.get("lan", "")) or "中文" in str(s.get("lan_doc", ""))]
    best = []
    for s in (zh or tracks)[:3]:
        url = s.get("subtitle_url") or ""
        if url.startswith("//"):
            url = "https:" + url
        try:
            body = _request(url, cookie=cookie_header()).get("body") or []
        except Exception:
            continue
        lines = [{"t": mmss(int(x["from"] * 1000)), "text": (x.get("content") or "").strip()}
                 for x in body if x.get("content")]
        if len(lines) > len(best):
            best = lines
    return best


def comments(aid, top=8):
    pool, seen, pn = [], set(), 1
    while len(pool) < top and pn <= 3:
        d = get("/x/v2/reply", {"type": 1, "oid": aid, "sort": 2, "ps": 20, "pn": pn})
        data = d.get("data") or {}
        for key in ("top_replies", "replies"):
            for r in (data.get(key) or []):
                if r.get("rpid") not in seen:
                    seen.add(r.get("rpid"))
                    pool.append(r)
        if not (data.get("replies") or []):
            break
        pn += 1
    pool.sort(key=lambda r: r.get("like", 0), reverse=True)
    return [{
        "user": (r.get("member") or {}).get("uname"),
        "text": ((r.get("content") or {}).get("message") or "").strip(),
        "like": r.get("like", 0),
        "replies": r.get("rcount", 0),
    } for r in pool[:top]]


# ---- 弹幕：protobuf 最小解析，不引依赖 ----

def _varint(buf, i):
    shift, val = 0, 0
    while True:
        b = buf[i]
        i += 1
        val |= (b & 0x7F) << shift
        if not (b & 0x80):
            return val, i
        shift += 7


def _fields(buf):
    i, n, out = 0, len(buf), []
    while i < n:
        key, i = _varint(buf, i)
        fno, wt = key >> 3, key & 7
        if wt == 0:
            v, i = _varint(buf, i)
            out.append((fno, wt, v))
        elif wt == 2:
            ln, i = _varint(buf, i)
            out.append((fno, wt, buf[i:i + ln]))
            i += ln
        elif wt == 5:
            out.append((fno, wt, buf[i:i + 4]))
            i += 4
        elif wt == 1:
            out.append((fno, wt, buf[i:i + 8]))
            i += 8
        else:
            break
    return out


def danmaku(cid, pages=2):
    items = []
    for seg in range(1, pages + 1):
        url = "https://api.bilibili.com/x/v2/dm/web/seg.so?type=1&oid=%s&segment_index=%d" % (cid, seg)
        try:
            req = urllib.request.Request(url, headers=dict(HEADERS, Cookie=cookie_header() or ""))
            with _OPENER.open(req, timeout=25) as r:
                buf = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    buf = gzip.decompress(buf)
        except urllib.error.HTTPError as exc:
            if exc.code in (412, 429):
                set_cooldown(120, "弹幕 HTTP %d" % exc.code)
            continue
        except Exception:
            continue
        for fno, wt, val in _fields(buf):
            if fno != 1 or wt != 2:
                continue
            progress, text = 0, ""
            for f2, w2, v2 in _fields(val):
                if f2 == 2 and w2 == 0:
                    progress = v2
                elif f2 == 7 and w2 == 2:
                    text = v2.decode("utf-8", "ignore")
            if text and 1 < len(text) <= 40 and not re.fullmatch(r"[\d\s\.\-+*/=]+", text):
                items.append({"t": mmss(progress), "text": text.strip()})
    return items


def mmss(ms):
    s = int(ms) // 1000
    return "%d:%02d" % (s // 60, s % 60)


# ---------------------------------------------------------------- 写

def upload_image(path):
    """把图传到 B站 图床，返回 {img_src,img_width,img_height,img_size}。

    坑：字段名是 file_up（不是 file），biz=new_dyn，category=daily，三个都得是表单字段。
    """
    c = load_conf()
    if not c.get("SESSDATA") or not c.get("bili_jct"):
        return False, "缺 SESSDATA / bili_jct", None
    if not os.path.exists(path):
        return False, "图片不存在：%s" % path, None
    raw = open(path, "rb").read()
    if len(raw) > 20 * 1024 * 1024:
        return False, "图太大了（>20MB）", None
    ext = os.path.splitext(path)[1].lower()
    mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".gif": "image/gif", ".webp": "image/webp"}.get(ext)
    if not mime:
        return False, "只支持 jpg/png/gif/webp", None

    boundary = "----feiyu" + uuid.uuid4().hex
    parts = []
    parts.append(("--%s\r\nContent-Disposition: form-data; name=\"file_up\"; filename=\"c%s\"\r\n"
                  "Content-Type: %s\r\n\r\n" % (boundary, ext, mime)).encode() + raw + b"\r\n")
    for k, v in (("biz", "new_dyn"), ("category", "daily"), ("csrf", c["bili_jct"])):
        parts.append(("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n"
                      % (boundary, k, v)).encode())
    parts.append(("--%s--\r\n" % boundary).encode())

    url = "https://api.bilibili.com/x/dynamic/feed/draw/upload_bfs"
    req = urllib.request.Request(url, data=b"".join(parts), headers={
        "User-Agent": HEADERS["User-Agent"], "Referer": "https://www.bilibili.com/",
        "Cookie": cookie_header() or "",
        "Content-Type": "multipart/form-data; boundary=%s" % boundary})
    try:
        with _OPENER.open(req, timeout=60) as r:
            d = json.loads(r.read().decode("utf-8", "ignore"))
    except Exception as exc:
        return False, "上传失败：%s" % exc, None
    if d.get("code") != 0:
        return False, "上传被拒：%s（code=%s）" % (d.get("message"), d.get("code")), None
    data = d.get("data") or {}
    if not data.get("image_url"):
        return False, "上传返回空 url", None
    return True, "ok", {"img_src": data["image_url"],
                        "img_width": data.get("image_width") or 0,
                        "img_height": data.get("image_height") or 0,
                        "img_size": data.get("img_size") or 0}


def tags(bvid):
    """视频标签。比标题靠谱：标题玩梗，标签是 UP 自己打的"""
    try:
        d = get("/x/tag/archive/tags", {"bvid": bvid})
    except Exception:
        return []
    return [t.get("tag_name") for t in (d.get("data") or []) if t.get("tag_name")]



def ensure_fingerprint(force=False):
    """把浏览器该有、脚本常常缺的字段补齐：buvid3/4、DedeUserID、bili_ticket。

    阿瓦隆很看这个——只有 SESSDATA + bili_jct 的请求，在它眼里就是"裸脚本"。
    返回补了哪些字段（空表示本来就齐）。
    """
    import hmac
    c = load_conf()
    added = []

    if force or not c.get("buvid3") or not c.get("buvid4"):
        try:
            d = get("/x/frontend/finger/spi", {})
            data = d.get("data") or {}
            if data.get("b_3"):
                c["buvid3"] = data["b_3"]
                c.setdefault("b_nut", int(time.time()))
                added.append("buvid3")
            if data.get("b_4"):
                c["buvid4"] = data["b_4"]
                added.append("buvid4")
        except Exception:
            pass

    if force or not c.get("DedeUserID"):
        try:
            d = get("/x/web-interface/nav", {})
            mid = (d.get("data") or {}).get("mid")
            if mid:
                c["DedeUserID"] = mid
                added.append("DedeUserID")
        except Exception:
            pass

    exp = int(c.get("bili_ticket_expires") or 0)
    if force or not c.get("bili_ticket") or exp < time.time() + 3600:
        try:
            ts = int(time.time())
            sign = hmac.new(b"XgwSnGZ1p", ("ts%d" % ts).encode(), hashlib.sha256).hexdigest()
            # 关键：这个接口的参数必须放 query，放表单体里会报 "empty ts field null"
            q = urllib.parse.urlencode({"key_id": "ec02", "hexsign": sign,
                                        "context[ts]": ts, "csrf": c.get("bili_jct", "")})
            url = ("https://api.bilibili.com/bapis/bilibili.api.ticket.v1.Ticket/"
                   "GenWebTicket?" + q)
            req = urllib.request.Request(url, data=b"", method="POST", headers={
                "User-Agent": HEADERS["User-Agent"],
                "Referer": "https://www.bilibili.com/",
                "Cookie": cookie_header(c) or ""})
            with _OPENER.open(req, timeout=20) as r:
                d = json.loads(r.read().decode("utf-8", "ignore"))
            data = d.get("data") or {}
            tk = data.get("ticket")
            if tk:
                c["bili_ticket"] = tk
                c["bili_ticket_expires"] = ts + int(data.get("ttl") or 259200)
                added.append("bili_ticket")
        except Exception:
            pass

    if added:
        save_conf(c)
    return added


def react(aid, like=None, coin=0):
    """点赞 / 投币。like=None 表示不动；coin=0/1/2。返回 (ok, msg)"""
    c = load_conf()
    if not c.get("bili_jct"):
        return False, "缺 bili_jct"
    msgs = []
    if like is not None:
        try:
            d = post_form("/x/web-interface/archive/like",
                          {"aid": aid, "like": 1 if like else 0, "csrf": c["bili_jct"]})
            if d.get("code") == 65006:
                msgs.append("早就赞过了")
            elif d.get("code") != 0:
                return False, "点赞失败：%s（%s）" % (d.get("message"), d.get("code"))
            else:
                msgs.append("赞了" if like else "取消赞")
        except Exception as exc:
            return False, "点赞请求失败：%s" % exc
    if coin:
        try:
            d = post_form("/x/web-interface/coin/add",
                          {"aid": aid, "multiply": int(coin), "select_like": 1,
                           "csrf": c["bili_jct"]})
            if d.get("code") != 0:
                if d.get("code") == 34005:
                    return True, "、".join(msgs + ["硬币不够了"])
                return False, "投币失败：%s（%s）" % (d.get("message"), d.get("code"))
            msgs.append("投了 %d 个币" % int(coin))
        except Exception as exc:
            return False, "投币请求失败：%s" % exc
    return True, "、".join(msgs) or "什么都没做"


def post_dynamic(text):
    """发一条纯文字动态。返回 (ok, msg, dynamic_id)"""
    c = load_conf()
    if not c.get("bili_jct"):
        return False, "缺 bili_jct", None
    if not (text or "").strip():
        return False, "动态是空的", None
    p = {"dynamic_id": 0, "type": 4, "rid": 0, "content": text.strip(),
         "csrf": c["bili_jct"], "csrf_token": c["bili_jct"]}
    body = urllib.parse.urlencode(p).encode()
    req = urllib.request.Request(
        "https://api.vc.bilibili.com/dynamic_svr/v1/dynamic_svr/create", data=body,
        headers={"User-Agent": HEADERS["User-Agent"], "Referer": "https://www.bilibili.com/",
                 "Cookie": cookie_header() or "",
                 "Content-Type": "application/x-www-form-urlencoded"})
    try:
        with _OPENER.open(req, timeout=30) as r:
            d = json.loads(r.read().decode("utf-8", "ignore"))
    except Exception as exc:
        return False, "请求失败：%s" % exc, None
    if d.get("code") != 0:
        return False, "code=%s %s" % (d.get("code"), d.get("message")), None
    data = d.get("data") or {}
    return True, "发了", data.get("dynamic_id_str") or data.get("dynamic_id")


def own_dynamics(mid, limit=5):
    d = get("/x/polymer/web-dynamic/v1/feed/space", {"host_mid": mid, "offset": ""})
    items = ((d.get("data") or {}).get("items") or [])[:limit]
    return [{"id": (i.get("id_str") or ""), "type": i.get("type"),
             "text": (((i.get("modules") or {}).get("module_dynamic") or {}).get("desc") or {}).get("text")}
            for i in items]


def reply_add(aid, text, at_name=None, at_mid=None, root=None, parent=None, pictures=None,
              bvid=None):
    """发一条视频评论。at_name/at_mid 都给时，@ 才会真的通知到人。
    root/parent 给上就是楼中楼回复（parent 是被回的那条）。"""
    c = load_conf()
    if not c.get("SESSDATA") or not c.get("bili_jct"):
        return False, "缺 SESSDATA / bili_jct", None
    if not (text or "").strip():
        return False, "评论是空的", None
    if len(text) > 1000:
        return False, "超过 1000 字", None
    left, why = cooldown_left()
    if left > 0:
        return False, "冷却中（%s），还有 %d 分钟" % (why, left // 60 + 1), None

    p = {"oid": aid, "type": 1, "message": text, "plat": 1, "csrf": c["bili_jct"],
         "gaia_source": "main_web"}
    if root:
        p["root"] = root
        p["parent"] = parent or root
    if at_name and at_mid:
        p["at_name_to_mid"] = json.dumps({at_name: at_mid}, ensure_ascii=False)
    if pictures:
        p["pictures"] = json.dumps(pictures, ensure_ascii=False)
        p["gaia_source"] = "main_web"
        p["has_vote_option"] = "true"

    # 评论接口本身不需要 WBI 签名。浏览器不带 w_rid/wts；之前把签名拼在 query 里，
    # 但签名是对 body 算的，查询串只有 w_rid/wts 属于"不完整签名"，反而更像异常客户端。
    path = "/x/v2/reply/add"
    try:
        # 只用 Chrome TLS 指纹发。curl_cffi 缺了会现场装一次（lib/deps.py），
        # 装不上才明确失败；绝不静默退回 urllib——那样接口会返回成功，
        # 评论却被阿瓦隆隐藏，看起来像"发了却没人看得见"。
        from lib import http_chrome
        http_chrome.ensure_cffi()
        ref = ("https://www.bilibili.com/video/%s" % bvid) if bvid else None
        d = http_chrome.post_form(path, p, cookie=cookie_header(), referer=ref)
    except Exception as exc:
        return False, "Chrome 指纹通道失败：%s" % exc, None

    if d.get("code") == 0:
        data = d.get("data") or {}
        rpid = data.get("rpid_str") or data.get("rpid")
        return True, "已发出", rpid
    code = d.get("code")
    if code in (-101, -111):
        return False, "凭证失效（%s），重新扫码/复制 SESSDATA" % code, None
    if code in (-352, -412, -429, -509):
        set_cooldown(120, "发评论 code=%s" % code)
        return False, "被风控（%s），停手两小时" % code, None
    if code == 12045:
        return False, "这条视频要购买/充电才能评论，换一条", None
    if code == 12002:
        return False, "这条评论区关了，换一条", None
    return False, "code=%s %s" % (code, d.get("message")), None


def reply_del(aid, rpid):
    c = load_conf()
    if not c.get("bili_jct"):
        return False, "缺 bili_jct"
    try:
        d = post_form("/x/v2/reply/del", {"oid": aid, "type": 1, "rpid": rpid,
                                          "csrf": c["bili_jct"]})
    except Exception as exc:
        return False, "请求失败：%s" % exc
    return (d.get("code") == 0), ("已撤回" if d.get("code") == 0
                                  else "code=%s %s" % (d.get("code"), d.get("message")))


# ---------------------------------------------------------------- 扫码登录

def qr_generate():
    """生成登录二维码。返回 (qr_url, qrcode_key)。不需要登录态。
    坑：路径是连字符 passport-login；驼峰 passportLogin 的老接口已 404。"""
    d = _request("https://passport.bilibili.com/x/passport-login/web/qrcode/generate")
    if d.get("code") != 0:
        raise RuntimeError("生成二维码失败：code=%s %s" % (d.get("code"), d.get("message")))
    data = d.get("data") or {}
    return data.get("url"), data.get("qrcode_key")


def _exchange_ticket(url):
    """新版扫码：poll 成功只给 ticket，GET 一次 crossDomain 才真正发凭证。
    不跟重定向，凭证从第一跳的 Set-Cookie 或 JSON 体里抠。"""
    class _NoRedir(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    op = urllib.request.build_opener(_NoRedir,
                                     urllib.request.HTTPSHandler(context=ssl_context()))
    cookies = {}
    try:
        try:
            r = op.open(urllib.request.Request(url, headers=dict(HEADERS)), timeout=15)
        except urllib.error.HTTPError as exc:
            r = exc                      # 302 也是答案：凭证就挂在这一跳的 Set-Cookie 上
        for h in (r.headers.get_all("Set-Cookie") or []):
            k, _, v = h.split(";")[0].partition("=")
            if k.strip() in ("SESSDATA", "bili_jct", "DedeUserID") and v:
                cookies[k.strip()] = v.strip()
        try:
            body = r.read().decode("utf-8", "ignore")
        except Exception:
            body = ""
        if body.strip().startswith("{"):
            d = (json.loads(body) or {}).get("data") or {}
            for c in ((d.get("cookie_info") or {}).get("cookies") or (d.get("cookies") or [])):
                if c.get("name") in ("SESSDATA", "bili_jct", "DedeUserID") and c.get("value"):
                    cookies.setdefault(c["name"], c["value"])
    except Exception:
        pass
    return cookies


def _extract_cookies(data):
    """从扫码成功响应里抠凭证。三处都找：
    ① data.url 的 query 参数（老结构 crossDomain）
    ② data.cookie_info.cookies 列表（新结构，scan-web 流程）
    ③ url 整体 unquote 后再找一遍（有的返回整个 query 被编码）"""
    cookies = {}
    raw = data.get("url") or ""
    q = urllib.parse.parse_qs(urllib.parse.urlparse(raw).query)
    cookies.update({k: q[k][0] for k in ("SESSDATA", "bili_jct", "DedeUserID") if k in q})
    if not cookies.get("SESSDATA"):
        for c in ((data.get("cookie_info") or {}).get("cookies") or []):
            if c.get("name") in ("SESSDATA", "bili_jct", "DedeUserID") and c.get("value"):
                cookies[c["name"]] = c["value"]
    if not cookies.get("SESSDATA") and raw:
        try:
            qq = urllib.parse.parse_qs(urllib.parse.unquote(raw))
            cookies.update({k: qq[k][0] for k in ("SESSDATA", "bili_jct", "DedeUserID") if k in qq})
        except Exception:
            pass
    return cookies


def qr_poll(qrcode_key):
    """查一次扫码状态。返回 (state, cookies, msg)。
    state: wait=没扫 / scanned=扫了没确认 / ok=成功 / expired=过期。
    ok 时 cookies 里带 SESSDATA / bili_jct / DedeUserID（B站 直接给全，不用抠浏览器）。
    坑：现在的 poll 外层 code 恒为 0，真实状态在 data.code 里（86101/86090/86038/0）。"""
    url = ("https://passport.bilibili.com/x/passport-login/web/qrcode/poll?"
           + urllib.parse.urlencode({"qrcode_key": qrcode_key}))
    d = _request(url)
    data = d.get("data") or {}
    code = data.get("code")
    if code is None:
        code = d.get("code")               # 老结构：状态直接在外层
    if code == 0:
        cookies = _extract_cookies(data)
        if not cookies.get("SESSDATA") and data.get("url"):
            cookies = _exchange_ticket(data["url"]) or {}
        if not cookies.get("SESSDATA"):
            try:
                from pathlib import Path
                dbg = Path(__file__).resolve().parent.parent / "state" / ".qr_debug.json"
                dbg.parent.mkdir(parents=True, exist_ok=True)
                dbg.write_text(json.dumps({"at": time.strftime("%Y-%m-%d %H:%M:%S"),
                                           "raw": data}, ensure_ascii=False, indent=2),
                               encoding="utf-8")
            except Exception:
                pass
            keys = ",".join(sorted((data or {}).keys())) or "（响应是空的）"
            return "expired", {}, ("B站 返回了登录成功，但没在响应里找到 SESSDATA"
                                   "（data 字段：%s；原始响应已存 state/.qr_debug.json，发给维护者即可）" % keys)
        return "ok", cookies, "登录成功"
    if code == 86090:
        return "scanned", {}, "扫上了，在手机上点确认"
    if code == 86038:
        return "expired", {}, "二维码过期了"
    return "wait", {}, "等扫码…"
