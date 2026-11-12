# -*- coding: utf-8 -*-
"""重命名后总验证：目录结构、每部资产完整性、DB 一致性"""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"F:\github\MyMovieDB\backend")
import database as db  # noqa: E402

Z_ROOT = r"Z:\av"
vid_exts = (".mp4", ".mkv", ".avi", ".wmv", ".ts", ".mov", ".rmvb", ".m2ts")

print("=== Z:\\av 顶层 ===")
root_files = [f for f in os.listdir(Z_ROOT) if os.path.isfile(os.path.join(Z_ROOT, f))]
print("  根目录文件:", root_files if root_files else "无")

actors = sorted([d for d in os.listdir(Z_ROOT) if os.path.isdir(os.path.join(Z_ROOT, d))])
print("\n=== 女优目录 ===")
total_folders = 0
problems = []
for a in actors:
    if a == "_torrents":
        continue
    subs = [d for d in os.listdir(os.path.join(Z_ROOT, a))
            if os.path.isdir(os.path.join(Z_ROOT, a, d))]
    total_folders += len(subs)
    print(f"  {a}: {len(subs)} 部")
    for s in subs:
        d = os.path.join(Z_ROOT, a, s)
        files = os.listdir(d)
        has_video = any(f.lower().endswith(vid_exts) and f.startswith(s) for f in files)
        has_nfo = any(f == s + ".nfo" for f in files)
        has_poster = any(f == s + "-poster.jpg" for f in files)
        has_fanart = any(f == s + "-fanart.jpg" for f in files)
        if not (has_video and has_nfo):
            problems.append((a, s, "缺视频或NFO", [f for f in files]))
        elif not (has_poster or has_fanart):
            problems.append((a, s, "缺图", [f for f in files]))
print(f"\n总计影片目录: {total_folders}")
print(f"结构问题: {len(problems)}")
for p in problems[:20]:
    print("  ", p[0], "|", p[1], "|", p[2])

print("\n=== DB 一致性 ===")
conn = db.get_db()
rows = conn.execute("""
    SELECT v.code, v.path, v.is_jellyfin, m.video_path, m.organized_path, m.actors
    FROM local_videos v JOIN movies m ON v.movie_id=m.id
    WHERE v.source_id=14
""").fetchall()
bad_path = bad_dir = 0
for r in rows:
    if not os.path.exists(str(r["path"])):
        bad_path += 1
    if not r["organized_path"] or not os.path.isdir(str(r["organized_path"])):
        bad_dir += 1
print(f"  记录 {len(rows)}；path 失效 {bad_path}；organized_path 失效 {bad_dir}")

print("\n=== 英文名残留检查（DB actors） ===")
import re
for r in conn.execute("""SELECT code, actors FROM movies WHERE id IN
                         (SELECT movie_id FROM local_videos WHERE source_id=14)"""):
    acts = r["actors"] or ""
    if re.search(r"[A-Za-z]{3}", acts) and not any(k in acts for k in ("LTX",)):
        print("  ", r["code"], acts)

print("\n=== 女优分布（DB） ===")
from collections import Counter
c = Counter()
for r in conn.execute("""SELECT actors FROM movies WHERE id IN
                         (SELECT movie_id FROM local_videos WHERE source_id=14)"""):
    try:
        a = json.loads(r["actors"])[0]
    except Exception:
        a = "?"
    c[a] += 1
for k, v in c.most_common():
    print(f"  {k}: {v}")

print("\n=== 字幕/额外文件 ===")
for root, _d, fs in os.walk(Z_ROOT):
    for f in fs:
        if f.lower().endswith((".srt", ".ass")):
            print("  ", os.path.join(root, f))
conn.close()
