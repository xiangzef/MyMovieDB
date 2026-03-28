import sys
sys.path.insert(0, 'backend')
from database import get_db, cleanup_invalid_codes

# 先查看当前状态
conn = get_db()
cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) FROM local_videos")
before = cursor.fetchone()[0]
print(f"清理前记录数: {before}")

# 执行清理
deleted_count, deleted_names = cleanup_invalid_codes()
print(f"删除了: {deleted_count} 条记录")

# 查看清理后状态
cursor.execute("SELECT COUNT(*) FROM local_videos")
after = cursor.fetchone()[0]
print(f"清理后记录数: {after}")

if deleted_names:
    print("被删除的文件:")
    for name in deleted_names[:10]:
        print(f"  - {name}")
    if len(deleted_names) > 10:
        print(f"  ... 还有 {len(deleted_names) - 10} 个")

conn.close()
