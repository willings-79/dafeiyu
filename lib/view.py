# -*- coding: utf-8 -*-
"""
lib/view.py — 给人看的视图层

state/ 下的产出是 .md：agent 读着方便，git 里也是干净纯文本，
但双击打开对人太不友好。这里把 .md 转成一页带样式的 HTML 拿默认浏览器打开，
**原文件一个字不动**——HTML 只是视图，不是数据。

渲染器是故意写小的：她产出的 md 格式有限（标题/列表/引用/粗体/行内码/链接/表格），
不追求通用，只求这几样渲染对。
"""

import html
import re
import tempfile
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_CSS = """
body{margin:0;background:#f6f7f9;color:#1c1f23;
     font:15px/1.75 system-ui,-apple-system,"Segoe UI","Microsoft YaHei",sans-serif}
main{max-width:720px;margin:0 auto;padding:36px 22px 80px}
h1{font-size:21px;border-bottom:2px solid #185fa5;padding-bottom:8px}
h2{font-size:17px;margin-top:30px}
h3{font-size:15px}
a{color:#185fa5}
blockquote{margin:10px 0;padding:6px 14px;border-left:3px solid #9cc3e8;
           background:#eef5fc;border-radius:0 8px 8px 0;color:#3a4a5c}
blockquote p{margin:4px 0}
code{background:#eceff3;border-radius:4px;padding:1px 5px;font-size:13px;
     font-family:Consolas,Menlo,monospace}
li{margin:3px 0}
table{border-collapse:collapse;margin:10px 0}
td,th{border:1px solid #d8dce2;padding:5px 12px;font-size:14px;text-align:left}
th{background:#eef5fc}
hr{border:0;border-top:1px solid #d8dce2;margin:26px 0}
footer{color:#8a94a0;font-size:12px;text-align:center;margin-top:40px}
"""

_INLINE = [
    (re.compile(r"`([^`]+)`"), r"<code>\1</code>"),
    (re.compile(r"\*\*([^*]+)\*\*"), r"<b>\1</b>"),
    (re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)"), r'<a href="\2">\1</a>'),
    (re.compile(r"~~([^~]+)~~"), r"<s>\1</s>"),
]


def _inline(s):
    for rx, rep in _INLINE:
        s = rx.sub(rep, s)
    return s


def md_to_html(src, title=""):
    """她那份受限的 markdown → HTML。先整体转义，再按行做块级、按规则做行内。"""
    out, i = [], 0
    lines = src.replace("\r\n", "\n").split("\n")
    list_open = quote_open = table_open = False

    def close():
        nonlocal list_open, quote_open, table_open
        if list_open:
            out.append("</ul>")
            list_open = False
        if quote_open:
            out.append("</blockquote>")
            quote_open = False
        if table_open:
            out.append("</table>")
            table_open = False

    for ln in lines:
        s = ln.rstrip()
        if s.startswith("|") and s.endswith("|") and s.count("|") >= 2:
            cells = [c.strip() for c in s.strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", c) for c in cells):   # 分隔行，跳过
                continue
            tag = "th" if not table_open else "td"
            if not table_open:
                close()
                out.append("<table>")
                table_open = True
            out.append("<tr>" + "".join("<%s>%s</%s>" % (tag, _inline(html.escape(c, quote=False)), tag)
                                        for c in cells) + "</tr>")
            continue
        if table_open:
            out.append("</table>")
            table_open = False
        if not s.strip():
            close()
            continue
        m = re.match(r"(#{1,4})\s+(.*)", s)
        if m:
            close()
            n = len(m.group(1))
            out.append("<h%d>%s</h%d>" % (n, _inline(html.escape(m.group(2), quote=False)), n))
            continue
        if s.strip() in ("---", "***"):
            close()
            out.append("<hr>")
            continue
        if s.lstrip().startswith("> "):
            if not quote_open:
                close()
                out.append("<blockquote>")
                quote_open = True
            out.append("<p>%s</p>" % _inline(html.escape(s.lstrip()[2:], quote=False)))
            continue
        if quote_open:
            out.append("</blockquote>")
            quote_open = False
        m = re.match(r"\s*[-*]\s+(.*)", s)
        if m:
            if not list_open:
                close()
                out.append("<ul>")
                list_open = True
            out.append("<li>%s</li>" % _inline(html.escape(m.group(1), quote=False)))
            continue
        m = re.match(r"\s*\d+[.、]\s+(.*)", s)
        if m:
            if not list_open:
                close()
                out.append("<ul>")
                list_open = True
            out.append("<li>%s</li>" % _inline(html.escape(m.group(1), quote=False)))
            continue
        close()
        out.append("<p>%s</p>" % _inline(html.escape(s, quote=False)))
    close()
    title = html.escape(title or "大肥鱼")
    return ("<!DOCTYPE html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>%s</title><style>%s</style></head><body><main>%s</main>"
            "<footer>由 dafeiyu 从 .md 生成的视图 · 数据原文件未改动</footer>"
            "</body></html>" % (title, _CSS, "\n".join(out)))


def open_md(path, title=""):
    """把一个 .md 转成临时 HTML 并用默认浏览器打开。返回打开的 URL。
    只许打开项目根内的文件——cmd_open 传来的路径可能拼了外部输入。"""
    src = Path(path).resolve()
    if ".." in src.parts or not src.is_relative_to(ROOT):
        raise ValueError("只许打开项目内的文件：%s" % src)
    doc = md_to_html(src.read_text(encoding="utf-8"), title or src.name)
    out_dir = Path(tempfile.gettempdir()) / "dafeiyu-view"
    out_dir.mkdir(exist_ok=True)
    dst = out_dir / (re.sub(r"[^\w.-]", "_", src.stem) + ".html")
    dst.write_text(doc, encoding="utf-8")
    url = "file:///" + str(dst).replace("\\", "/")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    return url
