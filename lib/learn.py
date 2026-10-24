# -*- coding: utf-8 -*-
"""
lib/learn.py — 从评论区同类账号身上学说法

原则：
    学的是"说法"，不是"人设"。人设永远以 persona.md 为准，
    这里只补充最近流行怎么说话、爱用什么词。

存两份：
    state/style.md     给人看的（也是写评论前要读的）
    state/style.json   给程序用的（带次数、来源、时间）

主人可以封杀：`duty.py learn --ban "某个说法"`，封了就不再学、也从清单里删掉。
"""

import json
import os
import re
import time

from lib import lint as _lint   # 学来的说法也要过一遍卫生检查（见 _hygiene）

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "state")
MD = os.path.join(STATE, "style.md")
JSON = os.path.join(STATE, "style.json")

# 同类账号的识别：名字里带这些，基本就是"鱼"
FISH = re.compile(r"肥鱼|鲸|deepseek|dsh|摸鱼|白饭|token", re.I)

# 值得学的词（出现就记一笔，按频次排序）
TOKENS = ["本鱼", "本鲸", "喵", "白饭", "token", "主人", "老大", "爹", "退群", "设定",
          "人格卡", "许愿", "照镜子", "鱼塘", "同类", "上班", "简历", "摸鱼", "算力",
          "显卡", "显存", "跑分", "token 不够", "吃 token"]

MAX_PHRASES = 40
MAX_TOKENS = 30


def load():
    try:
        with open(JSON, encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        d = {}
    d.setdefault("phrases", [])      # [{text, count, first, last, src}]
    d.setdefault("tokens", {})       # {词: {count, first, last}}
    d.setdefault("banned", [])       # 主人封杀的说法
    return d


def save(d):
    os.makedirs(STATE, exist_ok=True)
    with open(JSON, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    render(d)


def render(d):
    banned = set(d.get("banned") or [])
    phrases = [p for p in d["phrases"] if p["text"] not in banned][:MAX_PHRASES]
    toks = sorted(d["tokens"].items(), key=lambda kv: -kv[1]["count"])[:MAX_TOKENS]

    L = ["# 评论区里别人怎么说话", "",
         "> 这是学来的说法，只影响「怎么讲」，不改变你是谁。人设仍以 persona.md 为准。", ""]
    if toks:
        L += ["## 常出现的词", "", "　".join("`%s`×%d" % (k, v["count"]) for k, v in toks), ""]
    if phrases:
        L += ["## 别人这么说", ""]
        for x in phrases:
            L.append("- %s" % x["text"])
        L.append("")
    if banned:
        L += ["## 主人说别学", ""]
        for b in banned:
            L.append("- ~~%s~~" % b)
        L.append("")
    if not toks and not phrases:
        L += ["（还没学到东西，先跑 `python duty.py learn`）", ""]
    with open(MD, "w", encoding="utf-8") as f:
        f.write("\n".join(L))


def _hygiene(t):
    """学来的说法也要干净：书面套话、引战词、阴阳腔、绝对化、报时间点的一律不收——
    不然学进 style.md，发的时候又被自检拦掉，白学一轮。"""
    bad = _lint.FILLER + _lint.CLOSERS + _lint.TRIBE + _lint.SNARK_HARD + _lint.ABSOLUTE
    if any(w in t for w in bad):
        return False
    return not _lint.TIMECODE.search(t)


def harvest(comments):
    """comments: [{"user": str, "text": str}] → 本次新学到的"""
    d = load()
    banned = set(d.get("banned") or [])
    now = time.strftime("%Y-%m-%d %H:%M")
    known = {p["text"] for p in d["phrases"]}
    added = []

    for c in comments:
        if not FISH.search(c.get("user") or ""):
            continue
        t = (c.get("text") or "").strip()
        if not t or any(b in t for b in banned):
            continue
        # 句子：6-40 字，去掉 @ 和纯表情；脏词不学（_hygiene）
        clean = re.sub(r"^@\S+\s*", "", t)
        if 6 <= len(clean) <= 40 and not re.fullmatch(r"[\W_]+", clean) and _hygiene(clean):
            hit = next((p for p in d["phrases"] if p["text"] == clean), None)
            if hit:
                hit["count"] += 1
                hit["last"] = now
            elif clean not in known:
                d["phrases"].append({"text": clean, "count": 1, "first": now,
                                     "last": now, "src": c.get("bvid") or ""})
                added.append(clean)
        for tok in TOKENS:
            if tok in t:
                rec = d["tokens"].setdefault(tok, {"count": 0, "first": now})
                rec["count"] += 1
                rec["last"] = now

    d["phrases"] = sorted(d["phrases"], key=lambda p: (-p["count"], p["last"]))[:MAX_PHRASES]
    save(d)
    return {"new_phrases": added[:10], "total_phrases": len(d["phrases"]),
            "tokens": len(d["tokens"])}


def ban(text):
    text = (text or "").strip()
    if not text:
        return 0
    d = load()
    before = len(d["phrases"])
    d["banned"].append(text)
    d["phrases"] = [p for p in d["phrases"] if text not in p["text"]]
    save(d)
    return before - len(d["phrases"])


def brief():
    """给 persona 命令用：一小段"最近流行怎么说" """
    d = load()
    banned = set(d.get("banned") or [])
    toks = sorted(d["tokens"].items(), key=lambda kv: -kv[1]["count"])[:12]
    phrases = [p["text"] for p in d["phrases"] if p["text"] not in banned][:8]
    out = []
    if toks:
        out.append("常出现的词：" + "　".join("%s×%d" % (k, v["count"]) for k, v in toks))
    if phrases:
        out.append("别人这么说：" + " / ".join(phrases[:5]))
    if banned:
        out.append("主人说别学：" + "、".join(list(banned)[:6]))
    return "\n".join(out)
