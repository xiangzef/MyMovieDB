# -*- coding: utf-8 -*-
"""修复 Step3 前置数据：
  SNIS-091/110 -> 宇都宮しをん（r18dev Shion Utsunomiya 的日文原名）
  SNIS-166     -> 临时佚名（老垃圾记录，等 DMM 恢复后再补真数据）
"""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"F:\github\MyMovieDB\backend")
import database as db  # noqa: E402

conn = db.get_db()
conn.execute("UPDATE movies SET actors=? WHERE code IN ('SNIS-091','SNIS-110')",
             (json.dumps(["宇都宮しをん"], ensure_ascii=False),))
n = conn.execute("UPDATE movies SET actors=? WHERE code='SNIS-166'",
                 (json.dumps(["佚名"], ensure_ascii=False),))
conn.commit()
for code in ("SNIS-091", "SNIS-110", "SNIS-166"):
    r = conn.execute("SELECT id, actors FROM movies WHERE code=?", (code,)).fetchone()
    print(code, r["id"], r["actors"])
conn.close()
