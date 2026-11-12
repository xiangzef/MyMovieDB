# -*- coding: utf-8 -*-
"""临时脚本：检查 movies.db 的表结构与路径现状"""
import sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8")

DB = r"F:\github\MyMovieDB\data\movies.db"
con = sqlite3.connect(DB)
cur = con.cursor()

tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")]
print("TABLES:")
for t in tables:
    n = cur.execute(f"SELECT count(*) FROM [{t}]").fetchone()[0]
    print(f"  {t}: {n} rows")

# videos/local video 表结构
for t in tables:
    if "video" in t.lower() or "local" in t.lower() or "movie" in t.lower():
        cols = [r[1] for r in cur.execute(f"PRAGMA table_info([{t}])")]
        print(f"\n[{t}] columns: {cols}")

# 路径样例
try:
    rows = cur.execute("SELECT file_path FROM local_videos LIMIT 5").fetchall()
except Exception:
    rows = None
print("\nsample paths:")
if rows:
    for r in rows:
        print("  ", r[0])
con.close()
