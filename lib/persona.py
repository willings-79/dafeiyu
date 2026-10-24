# -*- coding: utf-8 -*-
"""
lib/persona.py — 性格卡接口

persona.md 是"写法教材"（怎么把一条评论写得像人），不好让每个用户重写；
真正属于"她是谁"的那部分拆出来，放 persona.local.json，谁都能改：

    python duty.py persona --init     # 从 persona.example.json 复制一份开始改
    双击设置页 → 「她的性格」块         # 不想碰 JSON 就在页面上改

没有 persona.local.json 时一切照旧（只用 persona.md），行为完全向后兼容。
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCAL = ROOT / "persona.local.json"
EXAMPLE = ROOT / "persona.example.json"

# 设置页/表单能写的字段白名单，其余一律不落盘
FORM_FIELDS = ("name", "self_call", "call_user", "species", "catchphrase",
               "likes", "dislikes", "notes")


def _checked(path):
    """只许读写项目根内的固定文件：解析真实路径、拒绝 ..、限制在 ROOT 内。"""
    p = Path(path).resolve()
    if ".." in p.parts or not p.is_relative_to(ROOT):
        raise ValueError("persona 路径越界：%s" % p)
    return p


def load():
    """读性格卡：没有 persona.local.json 就用 example 当默认（大肥鱼）。
    想换角色：把别人的 .json 拖进设置页（或复制成 persona.local.json）。"""
    for target in (LOCAL, EXAMPLE):
        try:
            p = _checked(target)
            if not p.is_file():
                continue
            d = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(d, dict) and d.get("name"):
                return d
        except ValueError:
            raise
        except Exception:
            continue
    return None


def save(d):
    target = _checked(LOCAL)
    target.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def init():
    """从 example 复制一份本地卡。已存在就不覆盖。返回 (是否新建, 路径)。"""
    if LOCAL.is_file():
        return False, str(LOCAL)
    d = json.loads(_checked(EXAMPLE).read_text(encoding="utf-8"))
    save(d)
    return True, str(LOCAL)


def _lines(s):
    return [x.strip() for x in (s or "").splitlines() if x.strip()]


def save_form(form):
    """设置页表单 → persona.local.json。只收白名单字段，坏了就抛异常。"""
    cur = load() or {}
    d = {k: cur[k] for k in cur if k.startswith("_")}     # 保留 _说明 之类
    d["name"] = (form.get("name") or "").strip() or "大肥鱼"
    d["self_call"] = (form.get("self_call") or "").strip() or "我"
    d["call_user"] = (form.get("call_user") or "").strip() or "主人"
    d["species"] = (form.get("species") or "").strip()
    d["catchphrase"] = (form.get("catchphrase") or "").strip()
    d["likes"] = _lines(form.get("likes"))
    d["dislikes"] = _lines(form.get("dislikes"))
    d["notes"] = (form.get("notes") or "").strip()
    save(d)
    return d


def public_fields(d):
    """性格卡 → 设置页表单形状（列表拼回多行文本）。"""
    return {
        "name": d.get("name") or "",
        "self_call": d.get("self_call") or "",
        "call_user": d.get("call_user") or "",
        "species": d.get("species") or "",
        "catchphrase": d.get("catchphrase") or "",
        "likes": "\n".join(d.get("likes") or []),
        "dislikes": "\n".join(d.get("dislikes") or []),
        "notes": d.get("notes") or "",
    }


def render(d):
    """性格卡 → 给 agent 读的 markdown。字段缺就跳过，不硬凑。"""
    g = d.get
    L = ["# %s · 性格卡" % (g("name") or "她"), "",
         "> 这张卡来自 persona.local.json（主人亲手改的）。和 persona.md 的示例冲突时，**以这张卡为准**。",
         ""]
    who = "，".join(x for x in [g("species"), "自称「%s」" % g("self_call")] if x)
    if g("call_user"):
        who += "，管眼前的人叫「%s」" % g("call_user")
    if who:
        L += ["## 你是谁", "", who + "。", ""]
    if g("catchphrase"):
        L += ["## 口头禅", "",
              "句尾偶尔挂「%s」，一条评论最多一个，多了立刻变味。" % g("catchphrase"), ""]
    if g("likes"):
        L += ["## 你喜欢 / 偏心", ""] + ["- " + x for x in g("likes")] + [
            "", "偏心要偏得具体（喜欢它哪一点），别变成粉丝发言，也别踩别人抬自己。", ""]
    if g("dislikes"):
        L += ["## 你反感 / 不碰", ""] + ["- " + x for x in g("dislikes")] + [""]
    if g("notes"):
        L += ["## 补充设定（主人写的，都是真的）", "", g("notes"), ""]
    L += ["> 卡里没写的，按 persona.md 的写法规矩来。别把卡背成设定——你是活成这样的。"]
    return "\n".join(L)
