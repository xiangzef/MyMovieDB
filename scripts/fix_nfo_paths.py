# -*- coding: utf-8 -*-
"""刷新 Z:\\av 下所有 NFO 的 fanart/thumb/filenameandpath 为当前实际路径"""
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
Z_ROOT = r"Z:\av"
VIDEO_EXT = (".mp4", ".mkv", ".avi", ".wmv", ".ts", ".mov", ".rmvb", ".m2ts")

n = 0
for root, _dirs, files in os.walk(Z_ROOT):
    for f in files:
        if not f.lower().endswith(".nfo"):
            continue
        base = os.path.splitext(f)[0]
        video = None
        for ext in VIDEO_EXT:
            cand = os.path.join(root, base + ext)
            if os.path.exists(cand):
                video = cand
                break
        if not video:
            continue
        p = os.path.join(root, f)
        with open(p, "r", encoding="utf-8", errors="ignore") as fh:
            text = fh.read()
        orig = text
        fanart = os.path.join(root, base + "-fanart.jpg")
        thumb = os.path.join(root, base + "-poster.jpg")
        if os.path.exists(fanart):
            text = re.sub(r"<fanart>.*?</fanart>", lambda m: f"<fanart>{fanart}</fanart>",
                          text, flags=re.S)
        if os.path.exists(thumb):
            text = re.sub(r"<thumb>.*?</thumb>", lambda m: f"<thumb>{thumb}</thumb>",
                          text, flags=re.S)
        text = re.sub(r"<filenameandpath>.*?</filenameandpath>",
                      lambda m: f"<filenameandpath>{video}</filenameandpath>",
                      text, flags=re.S)
        if text != orig:
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(text)
            n += 1
print(f"刷新 NFO 路径 {n} 个")
