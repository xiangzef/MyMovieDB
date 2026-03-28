import sys
sys.path.insert(0, 'backend')
from database import get_db

conn = get_db()
cursor = conn.cursor()

# 查看所有记录
print("=== local_videos 表内容 ===")
cursor.execute("SELECT id, name, code FROM local_videos")
rows = cursor.fetchall()
print(f"总数: {len(rows)}")
for r in rows:
    print(f"ID={r[0]}, name={r[1]}, code={r[2]}")

conn.close()
