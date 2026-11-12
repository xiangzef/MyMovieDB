# -*- coding: utf-8 -*-
"""统计 post_dmm_recovery 成果：33 部补图实际成功几个"""
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"F:\github\MyMovieDB\backend")
import database as db  # noqa: E402

MISSING = ['SNIS-896', 'SSIS-338', 'SSNI-644', 'SSNI-780', 'IPX-493', 'SNIS-070',
           'SNIS-205', 'SNIS-539', 'SNIS-623', 'SNIS-692', 'SNIS-752', 'SNIS-918',
           'SNIS-939', 'SSIS-037', 'SSIS-088', 'SSIS-124', 'SSIS-241', 'SSIS-541',
           'SSNI-344', 'SSNI-452', 'SSNI-542', 'SSNI-618', 'SSNI-674', 'SSNI-700',
           'SSNI-727', 'SSNI-730', 'SSNI-802', 'SSNI-865', 'SSNI-888', 'SSNI-916',
           'SSNI-939', 'SOE-480', 'SSPD-149']

conn = db.get_db()
ok, fail = [], []
for code in MISSING:
    r = conn.execute("SELECT id, fanart_path FROM movies WHERE code=?", (code,)).fetchone()
    if r and r["fanart_path"] and os.path.exists(str(r["fanart_path"])):
        ok.append(code)
    else:
        fail.append(code)
conn.close()
print(f"补图成功 {len(ok)}/33:", ok)
print(f"仍缺 {len(fail)}:", fail)

# 顺带验证 r18dev 7 部的 title/cover 现状
R18 = {"SNIS-091": 2456, "SNIS-110": 2457, "SOE-646": 2458,
       "SSPD-142": 2459, "SSPD-144": 2460, "SSPD-157": 2461, "TEK-089": 2462}
conn = db.get_db()
print("\nr18dev 7 部现状:")
for code, mid in R18.items():
    r = conn.execute("SELECT title, fanart_path FROM movies WHERE id=?", (mid,)).fetchone()
    cover_ok = r["fanart_path"] and os.path.exists(str(r["fanart_path"]))
    print(f"  [{code}] {str(r['title'])[:38]} | cover={'有' if cover_ok else '缺'}")
conn.close()
