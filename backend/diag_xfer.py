"""诊断 X:\中转站 整理问题"""
import sys, re, json
sys.path.insert(0, 'F:/github/MyMovieDB/backend')
from organizer import _extract_code_with_suffix, scan_video_files
from pathlib import Path
import sqlite3

source = r"X:\中转站"
p = Path(source)
if not p.exists():
    print(f"路径不存在: {source}")
    sys.exit(1)

print(f"=== X:\\中转站 所有视频文件 ===\n")
files = list(p.rglob("*"))
videos = []
for f in files:
    if f.is_file() and f.suffix.lower() in {'.mp4', '.mkv', '.avi', '.wmv', '.mov', '.webm', '.m4v', '.ts'}:
        code, stype, dname = _extract_code_with_suffix(f.name)
        videos.append({
            "path": str(f),
            "name": f.name,
            "code": code,
            "suffix": stype,
        })

print(f"共 {len(videos)} 个视频文件\n")

# 统计
no_code = [v for v in videos if not v["code"]]
has_code = [v for v in videos if v["code"]]
print(f"番号识别成功: {len(has_code)} 个")
print(f"番号识别失败: {len(no_code)} 个\n")

if no_code:
    print("=== 无法识别的文件 ===")
    for v in no_code:
        print(f"  {v['name']}")
    print()

# 查询数据库中有多少能匹配
if has_code:
    conn = sqlite3.connect('F:/github/MyMovieDB/backend/data/movies.db')
    cur = conn.cursor()
    codes = list(set(v["code"] for v in has_code))
    placeholders = ",".join("?" * len(codes))
    cur.execute(f"SELECT code, title FROM movies WHERE code IN ({placeholders})", codes)
    found = {r[0]: r[1] for r in cur.fetchall()}
    conn.close()

    db_hit = [v for v in has_code if v["code"] in found]
    db_miss = [v for v in has_code if v["code"] not in found]

    print(f"=== 数据库匹配情况 ===")
    print(f"数据库有数据: {len(db_hit)} 个")
    print(f"数据库无数据: {len(db_miss)} 个")
    if db_miss:
        print("\n数据库中找不到的番号:")
        for v in db_miss[:20]:
            print(f"  {v['code']} <- {v['name']}")

    print("\n=== 示例：有数据的文件 ===")
    for v in db_hit[:5]:
        print(f"  {v['code']} ({found[v['code']]}) <- {v['name']}")
