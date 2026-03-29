import sqlite3
from pathlib import Path

# 数据库路径
DB_PATH = Path("F:/github/MyMovieDB/data/movies.db")
BASE_DIR = Path("F:/github/MyMovieDB").resolve()

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# 检查有多少条记录使用相对路径
cursor.execute('SELECT COUNT(*) FROM movies WHERE poster_path LIKE "..%"')
relative_count = cursor.fetchone()[0]

cursor.execute('SELECT COUNT(*) FROM movies WHERE poster_path LIKE "F:%"')
absolute_count = cursor.fetchone()[0]

print(f'相对路径记录: {relative_count}')
print(f'绝对路径记录: {absolute_count}')

if relative_count > 0:
    # 修复相对路径为绝对路径
    old_prefix = f"..\\data\\covers\\"
    new_prefix = f"{BASE_DIR}\\data\\covers\\"
    
    cursor.execute('''
        UPDATE movies 
        SET poster_path = REPLACE(poster_path, ?, ?),
            fanart_path = REPLACE(fanart_path, ?, ?),
            thumb_path = REPLACE(thumb_path, ?, ?)
        WHERE poster_path LIKE "..%"
    ''', (old_prefix, new_prefix, old_prefix, new_prefix, old_prefix, new_prefix))
    
    updated = cursor.rowcount
    conn.commit()
    print(f'\n已修复 {updated} 条记录')
    
    # 验证修复结果
    cursor.execute('SELECT COUNT(*) FROM movies WHERE poster_path LIKE "..%"')
    remaining = cursor.fetchone()[0]
    print(f'剩余相对路径记录: {remaining}')

conn.close()
