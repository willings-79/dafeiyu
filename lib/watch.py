# -*- coding: utf-8 -*-
"""
lib/watch.py — 真的看一眼

把整片（30 分钟内）或分段（更长）下下来，均匀抽帧拼一张图。
她读这张图，才算"看过"。凭据落在 state/frames/<BV>.json。

    python -m lib.watch BV1xxx --frames 8
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "state", "frames")


def _run(cmd, timeout=300):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                       encoding="utf-8", errors="ignore")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def tools_ok():
    return bool(shutil.which("yt-dlp")) and bool(shutil.which("ffmpeg"))


def _pick_times(dur, frames, skip):
    """在"非广告"的区间里均匀取帧，而不是整片均匀——广告段一帧都不要"""
    segs, cur = [], 0
    for w in sorted(skip or [], key=lambda x: x.get("start", 0)):
        s, e = max(0, w.get("start", 0)), min(dur, w.get("end", 0))
        if s > cur:
            segs.append((cur, s))
        cur = max(cur, e)
    if cur < dur:
        segs.append((cur, dur))
    if not segs:
        segs = [(0, dur)]
    total = sum(b - a for a, b in segs) or dur or 1
    times = []
    for i in range(max(1, frames)):
        target = total * (i + 0.5) / max(1, frames)
        acc = 0
        for a, b in segs:
            if target <= acc + (b - a):
                times.append(a + (target - acc))
                break
            acc += b - a
        else:
            times.append(max(0.3, segs[-1][1] - 0.5))
    return [max(0.3, t) for t in times]


def grab(bvid, frames=8, force=False, skip=None):
    """返回 (grid 路径 or None, 说明)；skip 是要跳过的广告区间"""
    if not tools_ok():
        return None, "缺 yt-dlp / ffmpeg，看不了画面"
    os.makedirs(OUT, exist_ok=True)
    grid = os.path.join(OUT, "%s-grid.png" % bvid)
    meta_p = os.path.join(OUT, "%s.json" % bvid)
    if os.path.exists(grid) and os.path.exists(meta_p) and not force:
        return grid, "早就看过了"

    import lib.bili as bili
    try:
        dur = bili.meta(bvid)["duration"] or 0
    except Exception as exc:
        return None, "拿不到时长：%s" % exc

    clip = os.path.join(OUT, "%s-clip.mp4" % bvid)
    url = "https://www.bilibili.com/video/" + bvid

    full = 0 < dur <= 1800
    start = 0 if full else max(0, int(dur * 0.3))
    span = dur if full else 12

    ok = False
    last = ""
    for extra in (["-f", "bv*", "-S", "res:480"], ["-f", "bv*"]):
        for path in (clip, clip + ".part"):
            if os.path.exists(path):
                os.remove(path)
        dl = [] if full else ["--download-sections", "*%d-%d" % (start, start + 12)]
        cmd = (["yt-dlp", "-q", "--no-warnings", "--no-playlist",
                "-S", "res:360,+size"] + dl + ["-o", clip, url] + extra)
        code, out = _run(cmd)
        if code == 0 and os.path.exists(clip):
            ok = True
            break
        last = out.strip()[-200:]
    if not ok:
        return None, "下载失败：%s" % (last or "yt-dlp 没给出原因")

    cols = 4 if frames >= 8 else 2
    rows = (frames + cols - 1) // cols
    if full:
        times = _pick_times(span, frames, skip)
        sel = "+".join("between(t,%.2f,%.2f)" % (t, t + 0.2) for t in times)
        vf = "select='%s',scale=420:-1,tile=%dx%d" % (sel, cols, rows)
    else:
        interval = max(span / max(frames, 1), 0.5)
        vf = "fps=%s,scale=420:-1,tile=%dx%d" % (1.0 / interval, cols, rows)
    code, out = _run(["ffmpeg", "-y", "-loglevel", "error", "-i", clip,
                      "-vf", vf, "-frames:v", "1", grid])
    if code != 0 or not os.path.exists(grid):
        return None, "抽帧失败：%s" % (out.strip()[-160:] or "ffmpeg 报错")

    try:
        os.remove(clip)
    except OSError:
        pass

    extra = ("，跳过广告 %d 段" % len(skip)) if skip else ""
    with open(meta_p, "w", encoding="utf-8") as f:
        json.dump({"bvid": bvid, "at": time.strftime("%Y-%m-%d %H:%M:%S"),
                   "frames": frames, "duration": dur, "skip": skip or [],
                   "cover": ("全片 %d 秒均匀抽 %d 帧%s" % (dur, frames, extra) if full
                             else "%d-%d 秒（全片 %d 秒）" % (start, start + 12, dur))},
                  f, ensure_ascii=False, indent=2)
    return grid, ("全片 %d 秒抽 %d 帧%s" % (dur, frames, extra) if full
                  else "第 %d-%d 秒抽 %d 帧（全片 %d 秒）" % (start, start + 12, frames, dur))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bvid")
    ap.add_argument("--frames", type=int, default=8)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    p, why = grab(a.bvid, a.frames, a.force)
    print(p or "没看到", "|", why)
    return 0 if p else 1


if __name__ == "__main__":
    sys.exit(main())
