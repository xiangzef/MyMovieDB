# 清理 Jellyfin 视频源脚本
# 用途：删除 X:\jellyfin 和 Z:\影视库 的视频源记录及其本地视频，
#      然后重新用 Jellyfin 方式录入，避免被普通扫描覆盖
#
# 用法：python -c "exec(open('scripts/cleanup_jellyfin.py').read())"

import sys
sys.path.insert(0, 'backend')

from database import get_db
import os

def cleanup_and_reimport():
    db = get_db()

    # 要清理的 Jellyfin 目录
    jellyfin_paths = [
        r"X:\jellyfin",
        r"Z:\影视库",
    ]

    for path in jellyfin_paths:
        # 1. 查找 source
        source = db.get_local_source_by_path(path)
        if not source:
            print(f"⚠️  目录不存在: {path}")
            continue

        source_id = source['id']
        print(f"\n处理: {path} (id={source_id})")

        # 2. 删除 local_videos 记录（只删 is_jellyfin=1 的，避免误删普通目录视频）
        cursor = db.conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM local_videos WHERE source_id = ? AND is_jellyfin = 1",
            (source_id,)
        )
        lv_count = cursor.fetchone()[0]
        print(f"  将删除 {lv_count} 条 local_videos 记录 (is_jellyfin=1)")

        cursor.execute(
            "DELETE FROM local_videos WHERE source_id = ? AND is_jellyfin = 1",
            (source_id,)
        )
        db.conn.commit()
        print(f"  已删除 local_videos 记录")

        # 3. 删除 source 本身
        db.delete_local_source(source_id)
        print(f"  已删除视频源")

    print("\n✅ 清理完成")
    print("请到前端重新添加 Jellyfin 目录并执行 Jellyfin 扫描")

if __name__ == "__main__":
    cleanup_and_reimport()