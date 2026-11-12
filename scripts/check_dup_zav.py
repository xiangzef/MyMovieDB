# -*- coding: utf-8 -*-
"""Z:\av 内番号在 X:\jellyfin 是否存在副本"""
import sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8")
con = sqlite3.connect(r"F:\github\MyMovieDB\data\movies.db")
cur = con.cursor()
rows = cur.execute("""
    SELECT a.code, a.path, b.path
    FROM local_videos a
    JOIN local_videos b ON a.code = b.code AND a.id != b.id
    WHERE a.source_id = 14 AND b.source_id = 10
""").fetchall()
print(f"Z:\\av 与 X:\\jellyfin 重复番号: {len(rows)}")
for code, za, xj in rows:
    print(f"  [{code}]\n    Z: {za}\n    X: {xj}")
con.close()
