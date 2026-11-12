# -*- coding: utf-8 -*-
"""local_videos 行按盘符/源统计 存在性 """
import os, sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8")

con = sqlite3.connect(r"F:\github\MyMovieDB\data\movies.db")
cur = con.cursor()

stats = {}
for (p, sid) in cur.execute("SELECT path, source_id FROM local_videos"):
    pl = str(p)
    top = pl.split("\\")[0] if "\\" in pl else pl.split("/")[0]
    exists = os.path.exists(pl)
    s = stats.setdefault((top, sid), [0, 0, 0])
    s[0] += 1
    s[1] += 1 if exists else 0
    s[2] += 0 if exists else 1

print(f"{'前缀':<22}{'src':<5}{'总':>5}{'存在':>5}{'缺失':>5}")
for (top, sid), (total, ok, miss) in sorted(stats.items(), key=lambda kv: (kv[0][0], str(kv[0][1]))):
    print(f"{top:<22}{str(sid):<5}{total:>5}{ok:>5}{miss:>5}")
con.close()
