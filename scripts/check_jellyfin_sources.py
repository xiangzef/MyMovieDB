# 查看 Jellyfin 视频源状态脚本
# 用法：python scripts/check_jellyfin_sources.py

import sys
sys.path.insert(0, 'backend')

from database import get_db
import os

def check_jellyfin_sources():
    db = get_db()
    cursor = db.conn.cursor()

    print("=" * 60)
    print("Jellyfin 视频源状态检查")
    print("=" * 60)

    # 查找所有 is_jellyfin=1 的 source
    cursor.execute("""
        SELECT id, path, name, video_count, last_scan_at, is_jellyfin
        FROM local_sources
        WHERE is_jellyfin = 1
        ORDER BY id
    """)
    sources = cursor.fetchall()

    if not sources:
        print("\n⚠️  没有找到任何 Jellyfin 视频源 (is_jellyfin=1)")
    else:
        print(f"\n找到 {len(sources)} 个 Jellyfin 视频源:")
        for s in sources:
            print(f"  id={s[0]}, path={s[1]}, name={s[2]}, video_count={s[3]}, last_scan={s[4]}")

    # 统计 local_videos 中 is_jellyfin=1 的数量
    cursor.execute("SELECT COUNT(*) FROM local_videos WHERE is_jellyfin = 1")
    lv_jellyfin_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM local_videos")
    lv_total_count = cursor.fetchone()[0]

    print(f"\nlocal_videos 统计:")
    print(f"  is_jellyfin=1: {lv_jellyfin_count}")
    print(f"  is_jellyfin=0: {lv_total_count - lv_jellyfin_count}")
    print(f"  总计: {lv_total_count}")

    # 统计 movies 中 source_type='jellyfin' 的数量
    cursor.execute("SELECT COUNT(*) FROM movies WHERE source_type = 'jellyfin'")
    movies_jellyfin = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM movies WHERE source_type = 'web'")
    movies_web = cursor.fetchone()[0]

    print(f"\nmovies 统计:")
    print(f"  source_type='jellyfin': {movies_jellyfin}")
    print(f"  source_type='web': {movies_web}")

    # 统计 is_jellyfin IS NULL 的孤立记录
    cursor.execute("SELECT COUNT(*) FROM local_videos WHERE is_jellyfin IS NULL")
    lv_null = cursor.fetchone()[0]
    print(f"\nlocal_videos.is_jellyfin IS NULL: {lv_null} (需要修复)")

    # 列出所有 local_sources
    print("\n" + "=" * 60)
    print("所有视频源:")
    cursor.execute("""
        SELECT id, path, name, video_count, last_scan_at, is_jellyfin
        FROM local_sources
        ORDER BY id
    """)
    all_sources = cursor.fetchall()
    for s in all_sources:
        print(f"  [{s[0]}] {s[1]}")
        print(f"      name={s[2]}, video_count={s[3]}, last_scan={s[4]}, is_jellyfin={s[5]}")

if __name__ == "__main__":
    check_jellyfin_sources()