import sys
sys.path.insert(0, '.')
from database import get_db, calculate_scrape_status
from collections import Counter

conn = get_db()
cur = conn.cursor()

# Jellyfin 视频的 scrape_status 重新核算
cur.execute("""
    SELECT m.id, m.code, m.title, m.scrape_status, m.source_type,
           m.release_date, m.maker, m.poster_path, m.actors
    FROM local_videos v
    JOIN movies m ON v.movie_id = m.id
    WHERE v.code IS NOT NULL AND v.code != ''
      AND m.source_type = 'jellyfin'
    LIMIT 10
""")
rows = cur.fetchall()
print(f"=== Jellyfin 视频样本（前10）===")
for r in rows:
    data = dict(r)
    calc = calculate_scrape_status(data)
    print(f"  [{r['code']}] 存={r['scrape_status']} 重算={calc} | title={str(r['title'])[:15]} maker={str(r['maker'])[:10]} poster={str(r['poster_path'])[:30]}")

# Jellyfin 目录中非视频文件
print("\n=== Jellyfin 目录结构分析 ===")
import os, glob

# X:\jellyfin
jellyfin_paths = [r[0] for r in conn.execute("SELECT path FROM local_sources WHERE is_jellyfin = 1").fetchall()]
for path in jellyfin_paths:
    print(f"\n目录: {path}")
    if not os.path.exists(path):
        print("  (路径不存在)")
        continue
    items = os.listdir(path)
    video_exts = {'.mp4', '.mkv', '.avi', '.wmv', '.mov', '.webm', '.m4v'}
    files = {}
    for item in items:
        full = os.path.join(path, item)
        if os.path.isdir(full):
            sub = os.listdir(full)
            sub_videos = [f for f in sub if os.path.splitext(f.lower())[1] in video_exts]
            sub_other = [f for f in sub if os.path.splitext(f.lower())[1] not in video_exts]
            if sub_other:
                print(f"  📁 {item}/ ({len(sub_videos)} 视频, {len(sub_other)} 非视频)")
                # 列出非视频文件
                for f in sub_other[:10]:
                    print(f"     - {f}")
                if len(sub_other) > 10:
                    print(f"     ... 还有 {len(sub_other)-10} 个")
        else:
            ext = os.path.splitext(item.lower())[1]
            cat = '视频' if ext in video_exts else '非视频'
            if cat == '非视频':
                print(f"  📄 {item} ({ext})")

# Z:\影视库 jellyfin
z_path = r"Z:\影视库"
print(f"\n=== Z:\\影视库 Jellyfin ===")
if os.path.exists(z_path):
    for item in os.listdir(z_path)[:10]:
        full = os.path.join(z_path, item)
        if os.path.isdir(full):
            files = os.listdir(full)
            video_exts = {'.mp4', '.mkv', '.avi', '.wmv', '.mov', '.webm', '.m4v'}
            videos = [f for f in files if os.path.splitext(f.lower())[1] in video_exts]
            other = [f for f in files if os.path.splitext(f.lower())[1] not in video_exts]
            print(f"  📁 {item}/ ({len(videos)} 视频, {len(other)} 非视频)")
            if other:
                for f in other[:5]:
                    print(f"     - {f}")
                if len(other) > 5:
                    print(f"     ... 还有 {len(other)-5} 个")
        else:
            print(f"  📄 {item}")
else:
    print("  路径不存在")

conn.close()
