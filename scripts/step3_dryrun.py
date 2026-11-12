# -*- coding: utf-8 -*-
"""Step3 dry-run：检查演员目录名分布 + DMM 网络状态 + 加上 DJB/RBD 之类测试"""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"F:\github\MyMovieDB\backend")
sys.path.insert(0, r"F:\github\MyMovieDB\scripts")

import database as db              # noqa: E402
from step3_organize_ltx import pick_actor, sanitize   # noqa: E402

conn = db.get_db()
rows = conn.execute("""
    SELECT v.code, v.name, v.scraped, m.id AS mid, m.actors
    FROM local_videos v LEFT JOIN movies m ON v.movie_id = m.id
    WHERE v.source_id = 14
""").fetchall()
conn.close()

actors = {}
for r in rows:
    a = pick_actor(r["actors"]) if r["mid"] else "(未刮削)"
    actors.setdefault(a, []).append(r["code"])

for a, codes in sorted(actors.items(), key=lambda kv: -len(kv[1])):
    print(f"{a}: {len(codes)} 部")
    print("   ", ", ".join(sorted(codes)[:12]), "..." if len(codes) > 12 else "")
