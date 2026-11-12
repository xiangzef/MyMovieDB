# -*- coding: utf-8 -*-
"""检查 5 个手工命名文件在库中的状态 + 当前整理目录内容结构"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"F:\github\MyMovieDB\backend")
import database as db  # noqa: E402

CODES = ["ADN-151", "AVOP-004", "RBD-916", "SNIS-027", "SSNI-473"]
conn = db.get_db()
for code in CODES:
    lv = conn.execute("SELECT id, path, scraped, movie_id FROM local_videos WHERE code=?",
                      (code,)).fetchall()
    mv = conn.execute("SELECT id, title, title_jp, actors, video_path, organized_path FROM movies WHERE code=?",
                      (code,)).fetchall()
    print(f"=== {code} ===")
    for r in lv:
        print("  lv:", tuple(r))
    for r in mv:
        print("  movie:", tuple(r))
conn.close()

print("\n=== 样例整理目录内容 ===")
import glob
for d in sorted(glob.glob(r"Z:\av\松下紗栄子\*"))[:3]:
    print(d)
    for f in os.listdir(d):
        print("   ", f)
