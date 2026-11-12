# -*- coding: utf-8 -*-
"""检查 SNIS-166 / SNIS-091 的 actors 字段与 DMM 可用性"""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"F:\github\MyMovieDB\backend")
import database as db                          # noqa: E402
from step3_organize_ltx import pick_actor      # noqa: E402
from step2_offline_scrape import DmmGraphql    # noqa: E402

conn = db.get_db()
for code in ("SNIS-166", "SNIS-091", "SNIS-110"):
    r = conn.execute("""
        SELECT m.id, m.actors, m.actors_male, m.scrape_source, m.title
        FROM local_videos v JOIN movies m ON v.movie_id=m.id
        WHERE v.source_id=14 AND v.code=?
    """, (code,)).fetchone()
    print(code, "| mid:", r["id"], "| scrape_source:", r["scrape_source"])
    print("   actors repr:", repr(r["actors"]), "| male:", repr(r["actors_male"]))
    print("   title:", str(r["title"])[:50])
    print("   pick_actor ->", pick_actor(r["actors"]))
conn.close()

d = DmmGraphql()
for code, cid in (("SNIS-166", "snis00166"), ("SNIS-091", "snis00091")):
    try:
        item = d.content(cid)
        if item:
            acts = [a["name"] for a in item.get("actresses") or [] if isinstance(a, dict) and a.get("name")]
            print(f"DMM {code}: {item.get('title','')[:40]} actors={acts}")
        else:
            print(f"DMM {code}: MISS")
    except Exception as e:
        print(f"DMM {code}: {type(e).__name__}")
