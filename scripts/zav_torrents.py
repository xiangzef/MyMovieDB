# -*- coding: utf-8 -*-
"""归拢 torrent 文件到 Z:\av\_torrents，删除空壳目录"""
import os
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")
Z_ROOT = r"Z:\av"
TB = os.path.join(Z_ROOT, "_torrents")
os.makedirs(TB, exist_ok=True)

for d in ("SDSI-004_LTX", "SOE-480-U", "[javdb.com]mide-599-uncensored.torrent"):
    p = os.path.join(Z_ROOT, d)
    if not os.path.isdir(p):
        continue
    for root, _dirs, fs in os.walk(p):
        for f in fs:
            src = os.path.join(root, f)
            dst = os.path.join(TB, f)
            if not os.path.exists(dst):
                shutil.move(src, dst)
                print(f"收拢: {src} -> {dst}")
    if not any(os.scandir(p)):
        os.rmdir(p)
        print(f"删除空目录: {d}")
    else:
        print(f"目录仍有内容，保留: {d}")
print("\n_torrents 内容:", os.listdir(TB))
