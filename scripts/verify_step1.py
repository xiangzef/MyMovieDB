# -*- coding: utf-8 -*-
"""验证 Step1 结果"""
import os, sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8")
con = sqlite3.connect(r"F:\github\MyMovieDB\data\movies.db")
cur = con.cursor()

print("local_videos 总数:", cur.execute("SELECT count(*) FROM local_videos").fetchone()[0])
print("local_sources:")
for r in cur.execute("SELECT id, path, enabled, video_count, is_jellyfin FROM local_sources"):
    print("  ", r)

rows = cur.execute("SELECT video_path FROM movies WHERE video_path IS NOT NULL AND video_path != ''").fetchall()
okv = sum(1 for (p,) in rows if os.path.exists(str(p)))
print(f"movies 有 video_path: {len(rows)}, 存在: {okv}")

for r in cur.execute("SELECT source_type, count(*) FROM movies GROUP BY source_type"):
    print("source_type:", r)
for r in cur.execute("SELECT jellyfin_status, count(*) FROM movies GROUP BY jellyfin_status"):
    print("jellyfin_status:", r)
for r in cur.execute("SELECT subtitle_type, count(*) FROM movies WHERE video_path != '' GROUP BY subtitle_type"):
    print("subtitle_type(有视频):", r)
con.close()
