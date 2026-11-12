# -*- coding: utf-8 -*-
"""Z:\av 番号与库内已有数据的重叠检查"""
import os, re, sys, sqlite3
sys.stdout.reconfigure(encoding="utf-8")

CODE_PATTERN = re.compile(r'([A-Z]{2,6})-(\d{2,5})')
def extract(fn):
    m = CODE_PATTERN.search(fn.upper())
    return f"{m.group(1)}-{m.group(2)}" if m else None

zroot = r"Z:\av"
codes = set()
for root, dirs, ff in os.walk(zroot):
    for f in ff:
        if f.lower().endswith((".mp4", ".mkv", ".avi", ".wmv", ".ts", ".iso", ".rmvb", ".mov", ".m2ts")):
            c = extract(os.path.splitext(f)[0])
            if c:
                codes.add(c)
print(f"Z:\\av 可提取番号 {len(codes)} 个")

con = sqlite3.connect(r"F:\github\MyMovieDB\data\movies.db")
cur = con.cursor()
movie_codes = {r[0] for r in cur.execute("SELECT code FROM movies")}
lv_codes = {r[0] for r in cur.execute("SELECT code FROM local_videos")}

exist_m = codes & movie_codes
exist_lv = codes & lv_codes
print(f"已在 movies 表: {len(exist_m)}")
print(f"已在 local_videos 表(new): {len(exist_lv)}")
print("重叠样例:", sorted(exist_m)[:30])
print("\n新增番号:", len(codes - movie_codes))
con.close()
