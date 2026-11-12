# -*- coding: utf-8 -*-
"""检查 local_sources 与 local_videos 路径现状、movies 关联情况"""
import sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8")

DB = r"F:\github\MyMovieDB\data\movies.db"
con = sqlite3.connect(DB)
cur = con.cursor()

print("=== local_sources ===")
for r in cur.execute("SELECT id, path, name, enabled, video_count, last_scan_at, is_jellyfin FROM local_sources"):
    print(r)

print("\n=== local_videos 按 source 分组 ===")
for r in cur.execute("""SELECT s.id, s.path, COUNT(v.id)
                        FROM local_videos v LEFT JOIN local_sources s ON v.source_id=s.id
                        GROUP BY s.id"""):
    print(r)

print("\n=== local_videos path 前缀分布（取前 3 层） ===")
import collections
c = collections.Counter()
for (p,) in cur.execute("SELECT path FROM local_videos"):
    parts = str(p).replace("\\", "/").split("/")
    c["/".join(parts[:4])] += 1
for k, v in c.most_common(20):
    print(f"{v:5d}  {k}")

print("\n=== local_videos 刮削状态 ===")
for r in cur.execute("SELECT scraped, count(*) FROM local_videos GROUP BY scraped"):
    print(r)

print("\n=== local_videos.is_jellyfin ===")
for r in cur.execute("SELECT is_jellyfin, count(*) FROM local_videos GROUP BY is_jellyfin"):
    print(r)

print("\n=== movies.video_path 前缀分布 ===")
c2 = collections.Counter()
for (p,) in cur.execute("SELECT video_path FROM movies WHERE video_path IS NOT NULL AND video_path != ''"):
    parts = str(p).replace("\\", "/").split("/")
    c2["/".join(parts[:4])] += 1
for k, v in c2.most_common(20):
    print(f"{v:5d}  {k}")

print("\n=== movies 与 local_videos 关联情况 ===")
for r in cur.execute("""SELECT
    SUM(CASE WHEN video_path IS NULL OR video_path='' THEN 1 ELSE 0 END) AS no_video_path,
    SUM(CASE WHEN local_video_id IS NOT NULL THEN 1 ELSE 0 END) AS has_local_id,
    count(*) FROM movies"""):
    print(r)

print("\n=== movies.source_type ===")
for r in cur.execute("SELECT source_type, count(*) FROM movies GROUP BY source_type"):
    print(r)

print("\n=== video_path 不存在的文件抽查 ===")
import os
missing = 0
total = 0
samples = []
for (p,) in cur.execute("SELECT video_path FROM local_videos"):
    total += 1
    if not os.path.exists(str(p)):
        missing += 1
        if len(samples) < 8:
            samples.append(str(p))
print(f"local_videos: {total}, missing on disk: {missing}")
for s in samples:
    print("  miss:", s)
con.close()
