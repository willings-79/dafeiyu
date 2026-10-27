# -*- coding: utf-8 -*-
"""tools/test_core.py — 纯逻辑回归（离线、无副作用）

    python tools/test_core.py

覆盖四块最容易在"调措辞/调规则"时被悄悄改坏的纯逻辑：
lint 自检（含格言腔的自我反应降级）、广告段识别、api_runner 的
base_url 安全校验、模型 JSON 抽取（嵌套花括号）。
"""
import importlib.util
import os
import sys

# Windows 上管道输出的默认编码是 cp1252，第一条中文 PASS 就会炸——
# test_settings 没这问题是因为它导入链上有 duty（duty 顶层 reconfigure 了 stdout）；
# 这个文件不经过 duty，得自己来
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from lib import ads, lint  # noqa: E402

_spec = importlib.util.spec_from_file_location("api_runner", os.path.join(HERE, "api_runner.py"))
api = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(api)

ok = True


def check(name, cond, extra=""):
    global ok
    print(("PASS " if cond else "FAIL ") + name + ((" | " + extra) if extra else ""))
    ok = ok and cond


# ---- lint：hard 拦截
check("空评论拦", not lint.lint("")["ok"])
check("太短拦", not lint.lint("哈哈哈")["ok"])
check("书面套话拦", not lint.lint("总的来说这个视频非常值得一看，内容很充实。")["ok"])
check("报时间点拦", not lint.lint("他在2分12秒那里说的那句话，本鲸记到现在了")["ok"])
check("格言腔（总结视频）拦", not lint.lint(
    "人格卡能改语气，改不了她记得什么。真正长出来的性格，是被人一次次回话磨出来的。")["ok"])

# ---- lint：warn 提醒但放行 + 自我反应不误伤
r = lint.lint("本鲸不是饿，是嘴馋，刚吃完还想再来一口。")
check("格言句式但说本鲸自己 → 放行", r["ok"], str(r["hard"]))
check("……并带提醒", any("格言" in w for w in r["warn"]), str(r["warn"]))
r = lint.lint("主人，卡借我看看。我就改一条：看不懂的时候允许装懂，这比「爱吃白饭」实用。")
check("复盘表正例放行", r["ok"], str(r["hard"]))
r = lint.lint("这个视频讲了很多东西，不过其实内容还不错，但是节奏也还行，只是有点长。")
check("转折词过多提醒", any("转折" in w for w in r["warn"]), str(r["warn"]))

# ---- ads：广告段识别
ad_subs = [
    {"t": "1:00", "text": "先说一下赞助商，用口令下单有优惠"},
    {"t": "1:30", "text": "记得领券再买，比官方便宜"},
    {"t": "3:00", "text": "这个框架的实测数据很有意思，结论也客观"},
    {"t": "4:00", "text": "所以选型要看自己的场景"},
]
wins = ads.find_ads(ad_subs)
check("广告段被识别", len(wins) == 1, str(wins))
check("窗口覆盖两句广告", bool(wins) and wins[0]["start"] <= 60 and wins[0]["end"] >= 90, str(wins))
kept = ads.clean(ad_subs, wins)
check("clean 剔掉广告保留正文",
      [x["t"] for x in kept] == ["3:00", "4:00"], str([x["t"] for x in kept]))
check("单个弱信号不构段（宁可漏不错杀）",
      ads.find_ads([{"t": "3:00", "text": "链接在评论区"}]) == [])
check("讲价格的正经内容不误伤",
      ads.find_ads([{"t": "2:00", "text": "这套方案一年只要六块钱，价格是真的低"}]) == [])

# ---- api_runner._endpoint：SSRF 校验
def blocked(url):
    try:
        api._endpoint(url)
        return False
    except ValueError:
        return True


check("拒绝非 http(s)", blocked("ftp://example.com/x"))
check("拒绝 URL 内嵌凭据", blocked("http://user:pass@example.com/"))
check("拒绝云元数据地址", blocked("http://169.254.169.254/latest/meta-data/"))
check("拒绝环回地址（离线可测）", blocked("http://127.0.0.1:11434/"))
check("拒绝内网地址（离线可测）", blocked("http://192.168.1.5/"))
check("拒绝保留段地址（离线可测）", blocked("http://10.0.0.1/"))
try:
    ep = api._endpoint("https://api.deepseek.com/v1")
    check("公网 https 放行", ep.startswith("https://api.deepseek.com"), ep)
except ValueError as exc:
    if "解析" in str(exc):
        print("SKIP 公网放行（当前环境没网）")
    else:
        check("公网 https 放行", False, str(exc))

# ---- api_runner._extract_json：嵌套花括号
check("嵌套花括号抓得到",
      api._extract_json('前置废话 {"bvid":"BV1","why":"用了 {花括号} 的理由"} 后缀')
      == {"bvid": "BV1", "why": "用了 {花括号} 的理由"})
check("多个 JSON 取最后一个",
      api._extract_json('{"a":1} 中间话 {"b":{"c":2}}') == {"b": {"c": 2}})
check("字符串里的引号括号不乱套",
      api._extract_json('{"why":"他说 \\"好{\\" 就走了"}') == {"why": '他说 "好{" 就走了'})
check("纯垃圾返回空", api._extract_json("模型没回 JSON") == {})

print("\n结果：" + ("全部通过" if ok else "有失败"))
sys.exit(0 if ok else 1)
