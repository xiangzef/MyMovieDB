# -*- coding: utf-8 -*-
"""刷新 movies.jellyfin_status + 添加 Z:\av 本地源"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = r"F:\github\MyMovieDB"
sys.path.insert(0, ROOT + r"\backend")
import database as db  # noqa: E402

con = db.get_db()
cur = con.cursor()
rows = cur.execute(
    "SELECT id, video_path FROM movies WHERE source_type='jellyfin' "
    "AND video_path IS NOT NULL AND video_path != ''"
).fetchall()
n_done, n_partial, n_broken = 0, 0, 0
for mid, p in rows:
    if not os.path.exists(str(p)):
        cur.execute("UPDATE movies SET jellyfin_status='broken' WHERE id=?", (mid,))
        n_broken += 1
        continue
    folder = os.path.dirname(str(p))
    has_poster = any(("poster" in f.lower() or "cover" in f.lower())
                     for f in os.listdir(folder))
    cur.execute("UPDATE movies SET jellyfin_status=? WHERE id=?",
                ("complete" if has_poster else "partial", mid))
    n_done += 1 if has_poster else 0
    n_partial += 0 if has_poster else 1
con.commit()
print("jellyfin_status -> complete:", n_done, "partial:", n_partial, "broken:", n_broken)
con.close()

# 添加 Z:\av 源（若不存在）
existing = {r[0] for r in con_r.execute("SELECT path FROM local_sources")} if False else None
con2 = db.get_db()
existing = {r[0] for r in con2.execute("SELECT path FROM local_sources")}
if r"Z:\av" not in existing:
    sid = db.create_local_source(r"Z:\av", "AV 收件箱")
    print("新建 local_source id =", sid)
else:
    print("Z:\\av 源已存在")
con2.close()
