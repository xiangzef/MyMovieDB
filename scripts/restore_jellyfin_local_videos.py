"""
重建 Jellyfin 影片的 local_videos 记录
根据 movies.source_type='jellyfin' 的记录，反向写入 local_videos

用法：python scripts/restore_jellyfin_local_videos.py
"""
import sys
sys.path.insert(0, 'backend')
from database import get_db
import os

def restore():
    db = get_db()
    cursor = db.cursor()

    # 查询所有 jellyfin 来源的 movies
    cursor.execute("""
        SELECT id, code, video_path FROM movies
        WHERE source_type = 'jellyfin' AND video_path IS NOT NULL AND video_path != ''
    """)
    movies = cursor.fetchall()
    print(f"找到 {len(movies)} 个 jellyfin movies 需要重建 local_videos")

    # 获取 jellyfin sources 的 source_id
    cursor.execute("SELECT id, path FROM local_sources WHERE is_jellyfin = 1")
    jellyfin_sources = {row['path']: row['id'] for row in cursor.fetchall()}
    print(f"Jellyfin sources: {jellyfin_sources}")
    print()

    inserted = 0
    skipped = 0
    errors = 0

    for m in movies:
        code = m['code']
        movie_id = m['id']
        video_path = m['video_path']

        if not video_path or not os.path.exists(video_path):
            skipped += 1
            continue

        # 确定 source_id
        video_dir = os.path.dirname(video_path)
        source_id = None
        for src_path, src_id in jellyfin_sources.items():
            if video_path.startswith(src_path):
                source_id = src_id
                break

        if source_id is None:
            # 查找是否有其他 source 匹配
            cursor.execute("SELECT id FROM local_sources WHERE ? LIKE path || '%'", (video_path,))
            row = cursor.fetchone()
            source_id = row['id'] if row else None

        # 插入 local_videos（path UNIQUE，重复则跳过）
        file_size = os.path.getsize(video_path) if os.path.exists(video_path) else 0
        name = os.path.basename(video_path)

        try:
            cursor.execute("""
                INSERT OR IGNORE INTO local_videos
                (source_id, name, path, code, movie_id, file_size, scraped, is_jellyfin)
                VALUES (?, ?, ?, ?, ?, ?, 1, 1)
            """, (source_id, name, video_path, code, movie_id, file_size))
            if cursor.rowcount > 0:
                inserted += 1
            else:
                skipped += 1
        except Exception as e:
            errors += 1
            print(f"  ❌ {code}: {e}")

        if (inserted + errors) % 100 == 0 and inserted > 0:
            print(f"  已处理 {inserted + errors}/{len(movies)}, 插入 {inserted}, 跳过 {skipped}, 错误 {errors}")

    db.commit()

    print(f"\n✅ 完成: 插入 {inserted}, 跳过 {skipped}, 错误 {errors}")

    # 验证结果
    cursor.execute("SELECT COUNT(*) FROM local_videos WHERE is_jellyfin = 1")
    print(f"  local_videos.is_jellyfin=1: {cursor.fetchone()[0]}")

    db.close()

if __name__ == "__main__":
    restore()