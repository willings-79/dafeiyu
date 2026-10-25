# -*- coding: utf-8 -*-
"""
lib/http_chrome.py — 用 Chrome 的 TLS 指纹发请求

为什么需要它：
    Python 的 urllib 用的是自己的 TLS 栈（HTTP/1.1 + 一套固定 cipher），
    B站 的风控（阿瓦隆）能直接看出来"这不是浏览器"。
    于是无论 cookie 多齐、参数多对，评论都会被标成 state=17（仅自己可见）。

    curl_cffi 会复刻真实 Chrome 的 TLS/JA3 + HTTP2 指纹，请求在服务端看来和浏览器一致。

只用在"写"接口上（发评论、回复、点赞投币），读接口继续走 urllib，省依赖。
"""

import json

try:
    from curl_cffi import requests as _creq

    HAVE_CFFI = True
except Exception:
    HAVE_CFFI = False    # 没装也先不慌：真正要用时 ensure_cffi() 会现场装一个


BASE = "https://api.bilibili.com"

HEADERS = {
    "Referer": "https://www.bilibili.com/",
    "Origin": "https://www.bilibili.com",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
}


def ensure_cffi():
    """curl_cffi 缺了就现场装一个（lib/deps.py）。装不上抛 RuntimeError，带手动命令。

    只在"用户正在等这个结果"的写请求里被调到，import 时不装——
    agent 一天跑几十次命令，不能每条命令都先去碰 pip。
    """
    global _creq, HAVE_CFFI
    if HAVE_CFFI:
        return
    from lib import deps
    ok, why = deps.ensure("curl_cffi")
    if not ok:
        raise RuntimeError("curl_cffi 自动安装失败（%s）" % why)
    from curl_cffi import requests as _r
    _creq = _r
    HAVE_CFFI = True


def post_form(path, params, cookie=None, impersonate="chrome", timeout=30, referer=None):
    """带浏览器指纹的表单 POST。失败时抛异常，调用方自己兜。"""
    ensure_cffi()
    headers = dict(HEADERS)
    if referer:
        headers["Referer"] = referer
    if cookie:
        headers["Cookie"] = cookie
    r = _creq.post(BASE + path, data=params, headers=headers,
                   impersonate=impersonate, timeout=timeout)
    return json.loads(r.text)


def get_json(path, params=None, cookie=None, impersonate="chrome", timeout=30):
    ensure_cffi()
    headers = dict(HEADERS)
    if cookie:
        headers["Cookie"] = cookie
    r = _creq.get(BASE + path, params=params or {}, headers=headers,
                  impersonate=impersonate, timeout=timeout)
    return json.loads(r.text)
