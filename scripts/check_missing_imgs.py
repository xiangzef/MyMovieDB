# -*- coding: utf-8 -*-
"""检查缺图 33 部的 movies 图片路径与 cover_url 状态"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"F:\github\MyMovieDB\backend")
import database as db  # noqa: E402

conn = db.get_db()
rows = conn.execute("""
    SELECT v.code, m.id AS mid, m.fanart_path, m.poster_path, m.cover_url
    FROM local_videos v JOIN movies m ON v.movie_id=m.id
    WHERE v.source_id=14
""").fetchall()
conn.close()

missing = []
for r in rows:
    fa_ok = r["fanart_path"] and os.path.exists(str(r["fanart_path"]))
    po_ok = r["poster_path"] and os.path.exists(str(r["poster_path"]))
    if not (fa_ok or po_ok):
        missing.append((r["code"], r["mid"], r["fanart_path"], (r["cover_url"] or "")[:60]))

print(f"缺图（fanart/poster 均无有效本地文件）: {len(missing)}")
for code, mid, fa, cu in missing:
    print(f"  [{code}] mid={mid}\n    fanart={fa}\n    cover_url={cu}")
