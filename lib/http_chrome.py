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
except Exception:  # 没装就退回普通请求，功能不中断
    HAVE_CFFI = False

BASE = "https://api.bilibili.com"

HEADERS = {
    "Referer": "https://www.bilibili.com/",
    "Origin": "https://www.bilibili.com",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
}


def post_form(path, params, cookie=None, impersonate="chrome", timeout=30, referer=None):
    """带浏览器指纹的表单 POST。失败时抛异常，调用方自己兜。"""
    if not HAVE_CFFI:
        raise RuntimeError("没装 curl_cffi")
    headers = dict(HEADERS)
    if referer:
        headers["Referer"] = referer
    if cookie:
        headers["Cookie"] = cookie
    r = _creq.post(BASE + path, data=params, headers=headers,
                   impersonate=impersonate, timeout=timeout)
    return json.loads(r.text)


def get_json(path, params=None, cookie=None, impersonate="chrome", timeout=30):
    if not HAVE_CFFI:
        raise RuntimeError("没装 curl_cffi")
    headers = dict(HEADERS)
    if cookie:
        headers["Cookie"] = cookie
    r = _creq.get(BASE + path, params=params or {}, headers=headers,
                  impersonate=impersonate, timeout=timeout)
    return json.loads(r.text)
