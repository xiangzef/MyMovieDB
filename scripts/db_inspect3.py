# -*- coding: utf-8 -*-
"""检查 local_videos 路径是否仍存在于磁盘 + movies video_path 有效性"""
import sqlite3, os, collections, sys
sys.stdout.reconfigure(encoding="utf-8")

DB = r"F:\github\MyMovieDB\data\movies.db"
con = sqlite3.connect(DB)
cur = con.cursor()

print("=== local_videos 文件存在性 ===")
ok, missing = 0, 0
miss_samples = []
prefix_stat = collections.defaultdict(lambda: [0, 0])
for (p, src) in cur.execute("SELECT path, source_id FROM local_videos"):
    e = os.path.exists(str(p))
    parts = str(p).replace("\\", "/").split("/")
    key = "/".join(parts[:3]) or str(p)
    prefix_stat[key][0 if e else 1] += 1
    if e:
        ok += 1
    else:
        missing += 1
        if len(miss_samples) < 10:
            miss_samples.append(f"(src={src}) {p}")
print(f"exists: {ok}, missing: {missing}")
for s in miss_samples:
    print("  miss:", s)

print("\n=== 覆盖率检查: 前缀目录 (部分展示) ===")
for k, v in list(prefix_stat.items())[:5]:
    print(f"  {k} ok={v[0]} miss={v[1]}")
bad = [(k, v) for k, v in prefix_stat.items() if v[1] > 0]
print(f"前缀中有缺失的: {len(bad)} / {len(prefix_stat)}")
for k, v in bad[:15]:
    print(f"  {k} ok={v[0]} miss={v[1]}")

print("\n=== movies.video_path 存在性 ===")
ok2, miss2, nonempty = 0, 0, 0
miss2_samples = []
for (p,) in cur.execute("SELECT video_path FROM movies WHERE video_path IS NOT NULL AND video_path != ''"):
    nonempty += 1
    if os.path.exists(str(p)):
        ok2 += 1
    else:
        miss2 += 1
        if len(miss2_samples) < 10:
            miss2_samples.append(str(p))
print(f"nonempty: {nonempty}, exists: {ok2}, missing: {miss2}")
for s in miss2_samples:
    print("  miss:", s)

print("\n=== X:\\jellyfin 磁盘现状 ===")
xroot = r"X:\jellyfin"
actor_dirs = [d for d in os.listdir(xroot) if os.path.isdir(os.path.join(xroot, d))]
print("演员目录数:", len(actor_dirs))
cnt = 0
for d in actor_dirs[:5]:
    sub = os.listdir(os.path.join(xroot, d))
    print(" ", d, "->", sub[:3])

# 统计 X:\jellyfin 下所有视频文件数
vids = 0
for root, dirs, files in os.walk(xroot):
    for f in files:
        if f.lower().endswith((".mp4", ".mkv", ".avi", ".wmv", ".ts", ".iso", ".rmvb", ".mov", ".m2ts")):
            vids += 1
print("X:\\jellyfin 下视频文件数:", vids)

print("\n=== Z:\\av 磁盘现状 ===")
zroot = r"Z:\av"
try:
    z_all = os.listdir(zroot)
except Exception as e:
    z_all = []
    print("无法访问 Z:\\av:", e)
dirs = [d for d in z_all if os.path.isdir(os.path.join(zroot, d))]
files, vidsz = [], 0
for d in z_all:
    fp = os.path.join(zroot, d)
    if os.path.isdir(fp):
        pass
for f in z_all:
    if f.lower().endswith((".mp4", ".mkv", ".avi", ".wmv", ".ts", ".iso", ".rmvb", ".mov", ".m2ts")):
        vidsz += 1
subdirs_vids = collections.Counter()
for d in dirs:
    dp = os.path.join(zroot, d)
    for root, dd, ff in os.walk(dp):
        for f in ff:
            if f.lower().endswith((".mp4", ".mkv", ".avi", ".wmv", ".ts", ".iso", ".rmvb", ".mov", ".m2ts")):
                vidsz += 1
                subdirs_vids[d] += 1
print("Z:\\av 顶层条目:", len(z_all), "目录:", len(dirs), "视频文件总数:", vidsz)
print("顶层文件数:", sum(1 for f in z_all if os.path.isfile(os.path.join(zroot, f))))
for d, n in subdirs_vids.most_common(15):
    print(f"  子目录 {d}: {n} 个视频")
con.close()
