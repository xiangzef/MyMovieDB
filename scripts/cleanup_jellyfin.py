# 清理 Jellyfin 视频源脚本
# 用途：删除 X:\jellyfin 和 Z:\影视库 的视频源记录及其本地视频，
#      然后重新用 Jellyfin 方式录入，避免被普通扫描覆盖
#
# 用法：python -c "exec(open('scripts/cleanup_jellyfin.py').read())"

import sys
sys.path.insert(0, 'backend')
from database import get_db, delete_local_source, get_local_source_by_id

def cleanup_and_reimport():
    # 要清理的 Jellyfin 目录
    jellyfin_paths = [
        r"X:\jellyfin",
        r"Z:\影视库",
    ]

    db = get_db()
    cursor = db.cursor()

    for path in jellyfin_paths:
        # 1. 查找 source（用 get_local_source_by_id 先查所有再匹配 path）
        cursor.execute("SELECT id, path, name, is_jellyfin FROM local_sources WHERE path = ?", (path,))
        row = cursor.fetchone()
        if not row:
            print(f"⚠️  目录不存在: {path}")
            continue

        source_id = row[0]
        print(f"\n处理: {path} (id={source_id})")

        # 2. 统计要删除的 local_videos
        cursor.execute(
            "SELECT COUNT(*) FROM local_videos WHERE source_id = ?",
            (source_id,)
        )
        lv_count = cursor.fetchone()[0]
        print(f"  将删除 {lv_count} 条 local_videos 记录")

        # 3. 删除 source（delete_local_source 会级联删除关联视频）
        success = delete_local_source(source_id)
        if success:
            print(f"  ✅ 已删除视频源 id={source_id}")
        else:
            print(f"  ❌ 删除失败")

    # 4. 清理 movies 表中被普通扫描覆盖的 Jellyfin 记录
    print("\n" + "=" * 50)
    print("清理 movies 表中的 Jellyfin 记录...")
    cursor.execute("SELECT COUNT(*) FROM movies WHERE source_type = 'jellyfin'")
    jellyfin_movie_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM movies")
    total_movie_count = cursor.fetchone()[0]
    print(f"  movies.source_type='jellyfin': {jellyfin_movie_count} 条")
    print(f"  movies 总计: {total_movie_count} 条")

    confirm = input(f"\n⚠️  确定删除所有 source_type='jellyfin' 的 movies 记录吗？(y/N): ")
    if confirm.lower() == 'y':
        cursor.execute("DELETE FROM movies WHERE source_type = 'jellyfin'")
        db.commit()
        print(f"  ✅ 已删除 {jellyfin_movie_count} 条 movies 记录")
    else:
        print(f"  ❌ 已取消")

    print("\n✅ 清理完成")
    print("请到前端重新添加 Jellyfin 目录并执行 Jellyfin 扫描")
    db.close()

if __name__ == "__main__":
    cleanup_and_reimport()