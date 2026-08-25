# 重建 Jellyfin 视频源并导入所有影片
# 用法：python scripts/rebuild_jellyfin_sources.py

import sys
sys.path.insert(0, 'backend')
from database import get_db, create_local_source, import_jellyfin_movie
from jellyfin import scan_jellyfin_directory

def rebuild():
    jellyfin_dirs = [
        r"X:\jellyfin",
        r"Z:\影视库",
    ]

    db = get_db()
    cursor = db.cursor()
    total_imported = 0

    for directory in jellyfin_dirs:
        print(f"\n{'='*50}")
        print(f"处理: {directory}")

        # 1. 创建 source（标记 is_jellyfin=1）
        cursor.execute(
            "INSERT INTO local_sources (path, is_jellyfin, enabled, video_count) VALUES (?, 1, 1, 0)",
            (directory,)
        )
        db.commit()
        source_id = cursor.lastrowid
        print(f"  创建视频源 id={source_id}")

        # 2. 扫描 Jellyfin 目录
        print(f"  开始扫描...")
        t0 = __import__('time').time()
        results = scan_jellyfin_directory(directory)
        print(f"  扫描完成: {len(results)} 个影片 in {time.time()-t0:.1f}s")

        # 3. 导入每个影片
        imported = 0
        skipped = 0
        errors = 0
        for i, item in enumerate(results):
            try:
                movie_id = import_jellyfin_movie(
                    code=item['code'],
                    metadata=item['metadata'],
                    video_path=item['video_path'],
                    poster_file=item.get('poster_file'),
                    fanart_file=item.get('fanart_file'),
                    thumb_file=item.get('thumb_file'),
                )
                if movie_id > 0:
                    imported += 1
                else:
                    skipped += 1
            except Exception as e:
                errors += 1
                print(f"  ❌ {item['code']}: {e}")

            if (i + 1) % 100 == 0:
                print(f"    进度: {i+1}/{len(results)}")

        # 4. 更新 source 计数
        cursor.execute(
            "UPDATE local_sources SET video_count = ? WHERE id = ?",
            (imported, source_id)
        )
        db.commit()

        print(f"  ✅ 导入完成: imported={imported}, skipped={skipped}, errors={errors}")
        total_imported += imported

    # 5. 同步 is_jellyfin 到 local_videos
    print(f"\n同步 local_videos.is_jellyfin...")
    cursor.execute("""
        UPDATE local_videos SET is_jellyfin = 1
        WHERE source_id IN (SELECT id FROM local_sources WHERE is_jellyfin = 1)
    """)
    db.commit()
    print(f"  更新了 {cursor.rowcount} 条记录")

    # 6. 同步 movies.source_type
    print(f"\n同步 movies.source_type...")
    cursor.execute("""
        UPDATE movies SET source_type = 'jellyfin'
        WHERE source_type != 'jellyfin'
        AND code IN (
            SELECT code FROM local_videos WHERE is_jellyfin = 1 AND code IS NOT NULL
        )
    """)
    db.commit()
    print(f"  更新了 {cursor.rowcount} 条记录")

    print(f"\n{'='*50}")
    print(f"✅ 总计导入: {total_imported} 个影片")
    db.close()

if __name__ == "__main__":
    import time
    rebuild()