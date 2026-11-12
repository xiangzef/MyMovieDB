# -*- coding: utf-8 -*-
"""检查全部 Z:\\av 影片的 title 质量（空/等于番号/含非法字符）"""
import json
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"F:\github\MyMovieDB\backend")
import database as db  # noqa: E402

conn = db.get_db()
rows = conn.execute("""
    SELECT v.code, v.movie_id, m.title, m.title_jp, m.actors
    FROM local_videos v LEFT JOIN movies m ON v.movie_id=m.id
    WHERE v.source_id=14 ORDER BY v.code
""").fetchall()
conn.close()

bad = []
for r in rows:
    t = r["title_jp"] or r["title"] or ""
    if not t or t.strip().upper() == r["code"] or len(t.strip()) < 3:
        bad.append((r["code"], t, r["actors"]))
print(f"总 {len(rows)}，标题异常 {len(bad)}:")
for b in bad:
    print("  ", b)

INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
print("\n含非法字符的标题:")
for r in rows:
    t = r["title_jp"] or r["title"] or ""
    if INVALID.search(t):
        print(f"  [{r['code']}] {t[:70]}")
print("\n超长标题(>70):")
for r in rows:
    t = r["title_jp"] or r["title"] or ""
    if len(t) > 70:
        print(f"  [{r['code']}] len={len(t)} {t[:50]}...")
