# -*- coding: utf-8 -*-
"""
lib/ads.py — 找出视频里插播的广告段

UP 主大多会在中段口播一段商单：优惠、领券、下单、链接在评论区。
这些内容不该被当成"视频内容"去评论——她要是引用广告词，比说套话还尴尬。

做法很土但够用：给每条字幕打分，把 150 秒内累积到 3 分的连续区间标成广告段。
"""

STRONG = ["赞助", "广告", "恰饭", "商单", "推广", "领券", "优惠券", "优惠码", "折扣码",
          "下单", "口令", "直播间", "会员购", "秒杀", "返现", "福利", "限时", "立减",
          "买一送一", "专属链接", "购物车", "小黄车", "官方旗舰店", "预约", "优惠", "折扣"]
# 这些词在正经内容里也常见（讲价格、开箱评测），只能当辅证，不能单独定罪
WEAK = ["链接", "购买", "抽奖", "送礼"]

GAP = 150        # 一"段"广告最多跨多久
NEED_STRONG = 2  # 至少要两个"硬信号"
NEED_TOTAL = 3   # 加权分到多少才算广告
PAD_HEAD = 3     # 前后各留一点余量
PAD_TAIL = 8


def _sec(t):
    try:
        parts = [int(x) for x in str(t).split(":")]
    except Exception:
        return None
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    return None


def score(text):
    strong = 0
    weak = 0
    for w in STRONG:
        if w in text:
            strong += 1
    for w in WEAK:
        if w in text:
            weak += 1
    return strong, weak


def find_ads(subs, gap=GAP, need_strong=NEED_STRONG, need_total=NEED_TOTAL):
    """subs: [{"t": "m:ss", "text": ...}]  →  [{"start":秒, "end":秒, "score":n, "why":[...]}]"""
    hits = []
    for x in subs or []:
        t = _sec(x.get("t"))
        if t is None:
            continue
        s, w = score(x.get("text") or "")
        if s or w:
            hits.append((t, s, w, x.get("text") or ""))

    windows = []
    i = 0
    while i < len(hits):
        j = i
        ts = tw = 0
        words = []
        while j < len(hits) and hits[j][0] - hits[i][0] <= gap:
            ts += hits[j][1]
            tw += hits[j][2]
            for w in STRONG + WEAK:
                if w in hits[j][3] and w not in words:
                    words.append(w)
            j += 1
        if ts >= need_strong and ts + tw * 0.5 >= need_total:
            windows.append({"start": max(0, hits[i][0] - PAD_HEAD),
                            "end": hits[j - 1][0] + PAD_TAIL,
                            "score": ts + tw, "why": words[:6]})
            i = j
        else:
            i += 1

    merged = []
    for w in windows:
        if merged and w["start"] <= merged[-1]["end"]:
            merged[-1]["end"] = max(merged[-1]["end"], w["end"])
            merged[-1]["score"] += w["score"]
            for x in w["why"]:
                if x not in merged[-1]["why"]:
                    merged[-1]["why"].append(x)
        else:
            merged.append(w)
    return merged


def in_ads(t, windows):
    return any(w["start"] <= t <= w["end"] for w in windows)


def clean(subs, windows):
    """把广告段里的字幕剔掉，剩下的才是"内容" """
    keep = [x for x in (subs or []) if not in_ads(_sec(x.get("t")) or 0, windows)]
    return keep


def label(sec):
    m, s = divmod(int(sec), 60)
    return "%d:%02d" % (m, s)
