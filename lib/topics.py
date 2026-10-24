# -*- coding: utf-8 -*-
"""
lib/topics.py — 关键词当"方向"用，不当"标题必须包含"

两件事：
1) 同义词扩展：关键词写「大模型」，也能匹配 LLM / 基座模型 / 模型 这些标签
2) 标签匹配：B站 视频有 tag，比标题可靠得多（标题爱玩梗，标签是 UP 自己打的）

关键词本身也支持分组写法：`大模型|LLM|基座模型`，竖线分隔，任一命中即可。
"""

import re

SYN = {
    "ai": ["人工智能", "aigc", "机器学习", "深度学习", "ai应用"],
    "人工智能": ["ai", "aigc", "机器学习"],
    "aigc": ["ai", "生成式"],
    "大模型": ["llm", "基座模型", "语言模型", "模型", "大语言模型"],
    "llm": ["大模型", "语言模型"],
    "deepseek": ["深度求索", "dsk", "鲸鱼娘", "深度求索"],
    "智能体": ["agent", "ai agent", "agents", "智能代理"],
    "agent": ["智能体", "agents"],
    "开源": ["open source", "opensource", "github", "开源项目"],
    "机器人": ["具身智能", "embodied", "robot", "机械臂"],
    "具身智能": ["机器人", "embodied"],
    "科普": ["原理", "涨知识", "讲解"],
    "dsh": ["deepseek harness", "harness"],
    "大肥鱼": ["鲸鱼娘", "deepseek娘", "肥鱼"],
    "编程": ["代码", "coding", "程序"],
    "claude": ["anthropic", "克劳德"],
    "算力": ["gpu", "显卡", "芯片"],
    "开源项目": ["开源", "github", "open source"],
    "教程": ["教学", "手把手", "保姆级"],
    "测评": ["评测", "实测", "横评"],
    "模型": ["大模型", "llm"],
}


def groups(kw):
    """关键词可以写成 `大模型|LLM` 这种分组"""
    parts = re.split(r"[|｜]", kw or "")
    return [p.strip() for p in parts if p.strip()]


def variants(kw):
    out = []
    for g in groups(kw):
        out.append(g)
        out.extend(SYN.get(g.lower(), []))
    seen, res = set(), []
    for w in out:
        w = w.strip()
        if w and w.lower() not in seen:
            seen.add(w.lower())
            res.append(w)
    return res


def _has(hay, word):
    w = word.lower()
    if not w:
        return False
    # 英文短词用边界，避免 ai 命中 said / brain
    if re.fullmatch(r"[a-z0-9 .\-]{1,20}", w):
        return re.search(r"(?<![a-z0-9])" + re.escape(w) + r"(?![a-z0-9])", hay) is not None
    return w in hay


def match(hay, keywords):
    """hay 里命中了哪些方向，返回 [(关键词, 命中的词)]"""
    hay = (hay or "").lower()
    hits = []
    for kw in keywords:
        for v in variants(kw):
            if _has(hay, v):
                hits.append((kw, v))
                break
    return hits
