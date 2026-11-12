# -*- coding: utf-8 -*-
"""Z:\av 根目录收尾：字幕归位、空目录清理、eMule 垃圾清理"""
import os
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")
Z_ROOT = r"Z:\av"

# 1) SSPD-149 字幕归位（找到它的视频目录，按新视频名配字幕）
for f in os.listdir(Z_ROOT):
    if f.lower().endswith(".srt") and "SSPD-149" in f.upper():
        # 视频在 Z:\av\{演员}\SSPD-149\ 下
        for actor in os.listdir(Z_ROOT):
            d = os.path.join(Z_ROOT, actor, "SSPD-149")
            if os.path.isdir(d):
                vids = [x for x in os.listdir(d) if x.lower().endswith((".mp4", ".mkv", ".avi"))]
                if vids:
                    stem = os.path.splitext(vids[0])[0]
                    # 视频名 SSPD-149-LTX.mp4 -> 字幕 SSPD-149-LTX.zh.srt
                    dst = os.path.join(d, f"{stem}.zh.srt")
                    shutil.move(os.path.join(Z_ROOT, f), dst)
                    print(f"字幕归位: {f} -> {dst}")
                else:
                    shutil.copy2(os.path.join(Z_ROOT, f), os.path.join(d, f))
                    print(f"字幕归位(无视频名匹配): ", d)
                break

# 2) 空目录 / torrent 垃圾目录删除
for d in ("SDSI-004_LTX", "SOE-480-U", "[javdb.com]mide-599-uncensored.torrent"):
    p = os.path.join(Z_ROOT, d)
    if os.path.isdir(p):
        files_left = sum(len(fs) for _, _, fs in os.walk(p))
        if files_left == 0:
            os.rmdir(p)
            print(f"删除空目录: {d}")
        else:
            print(f"目录非空，保留: {d} ({files_left} 个文件)")

# 3) eMule 控制文件删除
n = 0
for f in os.listdir(Z_ROOT):
    if f.lower().endswith((".xltd", ".cfg", ".xlemule.cfg", ".emule.xltd")):
        os.remove(os.path.join(Z_ROOT, f))
        n += 1
        print(f"删除垃圾文件: {f}")
print(f"清理完成，共删 {n}")

print("\n根目录现状:")
for f in os.listdir(Z_ROOT):
    if os.path.isfile(os.path.join(Z_ROOT, f)):
        print("  ", f)
