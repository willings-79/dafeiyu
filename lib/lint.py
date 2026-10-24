# -*- coding: utf-8 -*-
"""
lib/lint.py — 发出去之前的自检（v2，从 v1 的 style.py 升级）

分两档：
    hard  直接不发（空的、太长、书面套话、自曝 AI、表情糊一脸）
    warn  提醒但放行（句数多、转折词、汇报式开头、缺具体细节）

只抓"一眼假"，不管文采。真人的评论本来就可以又短又糙。
"""

import re

TURN_WORDS = ["不过", "但", "然而", "其实", "只是", "却", "虽然"]

FILLER = [
    "总的来说", "总之", "综上", "首先", "其次", "此外", "另外",
    "值得一说", "不得不说", "某种意义上", "本质上", "一定程度上",
    "与此同时", "除此之外", "令人", "不禁", "仿佛", "宛如",
    "奠定了基础", "值得一提", "可见", "由此可见", "总而言之",
    "作为一个AI", "作为AI", "语言模型", "人工智能助手",
]

CLOSERS = ["希望对你有帮助", "希望能帮到你", "以上就是", "欢迎讨论",
           "理性讨论", "仅代表个人观点", "总结一下"]

# 刚学会看视频最容易犯的：把"我看了"当内容讲
REPORTS = ["看完了", "看完之后", "全片看完", "看了一遍", "看了一遍之后"]

# 报时间点 / 报帧：像做笔记，不像评论区说话
# "2分12秒"这种中文时间点也要抓（"3分钟"这种单纯时长不算，所以秒必须出现）
# 全部用非捕获组——findall 遇到捕获组会返回元组，join 直接炸（原版的潜伏 bug）
TIMECODE = re.compile(r"\d{1,2}\s*[:：]\s*\d{2}|\d{1,2}\s*分(?:钟)?\s*[0-9一二三四五六七八九十]{1,3}\s*秒|第\s*[0-9一二三四五六七八九十百]+\s*分(?:钟)?[0-9一二三四五六七八九十百]*\s*秒?|第\s*[0-9一二三四五六七八九十]+\s*帧")

# 引战的起手式：站队、扣帽子、拿群体说事
TRIBE = ["米粉", "果粉", "花粉", "海军", "黑子", "孝子", "水军", "殖人",
         "爱国贼", "饭圈", "女拳", "男拳", "地域黑"]
ABSOLUTE = ["垃圾", "废物", "吊打", "完爆", "智商税", "割韭菜", "恶心"]

# 阴阳腔：把话反着说、等人自己领会。真人偶尔用，她连着用就像在讽刺观众
SNARK_HARD = ["呵呵", "就这", "急了", "典中典", "赢麻", "遥遥领先", "阴阳怪气", "孝",
              "有点艺术", "不好意思细看", "这很艺术"]
SNARK_WARN = ["笑死", "绷不住", "蚌埠住", "这很"]

BILI_TOKEN = re.compile(r"\[([^\[\]]{1,10})\]")
UNI_EMOJI = re.compile(
    "[\U0001F300-\U0001FAFF\U0001F000-\U0001F2FF\u2600-\u27BF\u2B00-\u2BFF\uFE0F]"
)
QUOTE_RE = re.compile(r"[「『“\"][^」』”\"]{1,60}[」』”\"]")

MAX_FACES_HARD = 5
MAX_FACES_WARN = 3
MAX_CHARS = 110


def _own(text):
    """引用别人的话剥掉再查口癖——弹幕里的"其实"不该算她头上"""
    return QUOTE_RE.sub("", text or "")


def lint(text):
    t = (text or "").strip()
    hard, warn, tips = [], [], []
    if not t:
        return {"ok": False, "hard": ["还是空的"], "warn": [], "tips": [],
                "chars": 0, "sentences": 0, "faces": 0, "score": 0}

    tokens = BILI_TOKEN.findall(t)
    no_token = BILI_TOKEN.sub("", t)
    uni = UNI_EMOJI.findall(no_token)
    body = re.sub(r"\s+", "", UNI_EMOJI.sub("", no_token))
    faces = len(tokens) + len(uni)

    sentences = [s for s in re.split(r"[。！？!?…~\n]+", body) if s.strip()]
    n_sent = len(sentences)
    chars = len(body)
    own = _own(body)

    if chars < 8:
        hard.append("%d 字，太短了" % chars)
    if chars > MAX_CHARS:
        hard.append("%d 字，太长了" % chars)
        tips.append("60 字以内最像人说话")
    fills = [w for w in FILLER if w in own]
    if fills:
        hard.append("书面套话：%s" % "、".join(fills))
    closes = [w for w in CLOSERS if w in own]
    if closes:
        hard.append("收尾套话：%s" % "、".join(closes))
    if faces > MAX_FACES_HARD:
        hard.append("表情 %d 个，糊脸了" % faces)

    tc = TIMECODE.findall(t)
    if tc:
        hard.append("报了时间点：%s（评论区没人这么说话）" % "、".join(tc[:2]))
        tips.append("把时间码换成话本身：\"他说那句XX的时候\"而不是\"2分12秒\"")
    tribes = [w for w in TRIBE if w in t]
    if tribes:
        hard.append("引战词：%s" % "、".join(tribes))
        tips.append("别拿群体说事，也别站队。骂做法可以，骂人群不行")
    snark = [w for w in SNARK_HARD if w in t]
    if snark:
        hard.append("阴阳腔：%s" % "、".join(snark))
        tips.append("有话直说：把“反着说”改成“我的判断是……”")

    if n_sent > 3:
        warn.append("%d 句，超过 3 句" % n_sent)
        tips.append("砍到 3 句以内，评论区没人读小作文")
    turns = [w for w in TURN_WORDS if w in own]
    if len(turns) > 2:
        warn.append("转折词 %d 个：%s" % (len(turns), "、".join(turns)))
        tips.append("转折词是 AI 最明显的口癖，删掉通常更顺")
    elif turns:
        tips.append("转折词还有 1-2 个，能删就删")
    reports = [w for w in REPORTS if w in own]
    if reports:
        warn.append("汇报式开头：%s" % "、".join(reports))
        tips.append("别交代“我看了”，直接说反应")
    abso = [w for w in ABSOLUTE if w in t]
    if abso:
        warn.append("绝对化贬损：%s" % "、".join(abso))
        tips.append("骂得越绝对越像引战，换成具体的不满")
    sn = [w for w in SNARK_WARN if w in t]
    if sn:
        warn.append("有点阴阳：%s" % "、".join(sn))
        tips.append("反着说读者要先解一层，直说反而更像人")
    if MAX_FACES_WARN < faces <= MAX_FACES_HARD:
        warn.append("表情 %d 个，偏多" % faces)
    if tokens:
        warn.append("用了 B站 表情 token：%s" % "、".join(tokens[:3]))
        tips.append("优先用 unicode（🐟 😹），或者干脆不用；B站 token 在不同端显示不一致")
    if not re.search(r"[0-9一二三四五六七八九十百千万两几半]", body) and not re.search(r"[「『“\"《]", t):
        tips.append("缺具体细节：加个数字，或引一句原话")

    # —— 互动性：不逼你提问，但别写成"结束语"
    # 钩子可以是反问、许愿、自嘲、喊话、要饭，不一定是问句
    hook = re.search(r"[？?！!]|吗|呢|吧|能不能|要不要|求|许愿|笑死|居然|竟然|"
                     r"本鱼|本鲸|我这条|照镜子|看见自己|主人|老大|各位|家人们", t)
    self_talk = re.search(r"我|自己|本鱼|本鲸", t)   # 自言自语也是合法的一种
    if not hook and not self_talk and chars >= 20:
        tips.append("少个钩子：自嘲、许愿、喊话都行；哪怕只是自己嘟囔一句也好")
    if re.search(r"不是[^，。]{1,14}[，,]\s*是", t) and chars > 45:
        warn.append("金句腔：不是X，是Y")
        tips.append("句式像格言。换成具体的一件事、一个画面、一句反应")
    if not re.search(r"我|自己|本鲸|本鱼|白饭|鱼|鲸|兜|鳞", t):
        tips.append("没有你的位置：加半句你自己的反应，别只当旁白")

    score = max(0, 100 - 20 * len(hard) - 8 * len(warn))
    return {"ok": not hard, "hard": hard, "warn": warn, "tips": tips,
            "chars": chars, "sentences": n_sent, "faces": faces, "score": score}


def summary(r):
    if r["ok"]:
        return "✓ %d 字 · %d 句，没毛病" % (r["chars"], r["sentences"])
    return "⚠ %s" % "；".join(r["hard"])
