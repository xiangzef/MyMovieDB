import sqlite3

conn = sqlite3.connect('F:/github/MyMovieDB/data/movies.db')
cursor = conn.cursor()

# 先查看要删除的记录
cursor.execute("SELECT id, code, name, path FROM local_videos WHERE code IS NULL OR code = ''")
rows = cursor.fetchall()
print(f"=== 将要删除 {len(rows)} 条无番号记录 ===")
for row in rows:
    print(f"ID: {row[0]}, Code: {row[1]}, Name: {row[2]}")

print()

# 删除无番号的记录
cursor.execute("DELETE FROM local_videos WHERE code IS NULL OR code = ''")
deleted = cursor.rowcount
conn.commit()

print(f"已删除 {deleted} 条记录")

# 验证
cursor.execute("SELECT COUNT(*) FROM local_videos WHERE code IS NULL OR code = ''")
remaining = cursor.fetchone()[0]
print(f"剩余无番号记录: {remaining}")

conn.close()
