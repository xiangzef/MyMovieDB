# -*- coding: utf-8 -*-
"""总审计：Z:\av 整理后的库状态"""
import json
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"F:\github\MyMovieDB\backend")
import database as db  # noqa: E402

conn = db.get_db()
cur = conn.cursor()

print("=== local_sources ===")
for r in cur.execute("SELECT * FROM local_sources"):
    print("  ", tuple(r))

print("\n=== local_videos 按源 ===")
for r in cur.execute("SELECT source_id, is_jellyfin, count(*) FROM local_videos GROUP BY source_id, is_jellyfin"):
    print("  ", tuple(r))

print("\n=== local_videos source 14 状态 ===")
for r in cur.execute("""SELECT scraped, is_jellyfin, count(*),
                        SUM(CASE WHEN movie_id IS NOT NULL THEN 1 ELSE 0 END)
                        FROM local_videos WHERE source_id=14 GROUP BY scraped, is_jellyfin"""):
    print("   scraped/is_jellyfin:", tuple(r[:3]), "| 有movie:", r[3])

print("\n=== source 14 视频路径存在性 ===")
n_ok = n_miss = 0
for (p,) in cur.execute("SELECT path FROM local_videos WHERE source_id=14"):
    if os.path.exists(str(p)):
        n_ok += 1
    else:
        n_miss += 1
print(f"   存在 {n_ok} / 缺失 {n_miss}")

print("\n=== movies（视频路径指向 Z:\\\\av）状态 ===")
for r in cur.execute("""SELECT source_type, jellyfin_status, count(*) FROM movies
                        WHERE video_path LIKE 'Z:\\av%'
                        GROUP BY source_type, jellyfin_status"""):
    print("  ", tuple(r))

print("\n=== 有 video_path 的 movies 磁盘有效性 ===")
n_ok = n_miss = 0
for (p,) in cur.execute("SELECT video_path FROM movies WHERE video_path IS NOT NULL AND video_path != ''"):
    if os.path.exists(str(p)):
        n_ok += 1
    else:
        n_miss += 1
print(f"   有效 {n_ok} / 失效 {n_miss}")

print("\n=== jellyfin_status 分布 ===")
for r in cur.execute("SELECT jellyfin_status, count(*) FROM movies GROUP BY jellyfin_status"):
    print("  ", tuple(r))

print("\n=== <tag>LTX 注入检查（Z:\\\\av NFO 抽样） ===")
root = Path(r"Z:\av")
nfos = list(root.glob(r"*/*/*.nfo"))
ltx_cnt = sum(1 for n in nfos if "LTX" in n.read_text(encoding="utf-8", errors="ignore"))
print(f"   NFO 数 {len(nfos)}，含 LTX 标签 {ltx_cnt}")

print("\n=== 视频文件名 LTX 后缀 ===")
n_v = n_name = 0
for v in root.glob(r"*/*/*.m*4"):
    pass
import re
n_name = 0
for p in root.glob(r"*/*/*"):
    if p.suffix.lower() in (".mp4", ".mkv", ".avi", ".wmv"):
        n_v += 1
        if "-LTX" in p.stem.upper():
            n_name += 1
print(f"   视频 {n_v} 个，文件名带 -LTX 的 {n_name} 个")
conn.close()
