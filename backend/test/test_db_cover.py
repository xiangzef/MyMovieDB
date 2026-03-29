import sqlite3
from pathlib import Path

conn = sqlite3.connect('F:/github/MyMovieDB/data/movies.db')
cursor = conn.cursor()

# 检查 EBOD-869
cursor.execute('SELECT id, code, poster_path FROM movies WHERE code = "EBOD-869"')
row = cursor.fetchone()
if row:
    print(f'ID: {row[0]}, Code: {row[1]}')
    print(f'poster_path in DB: {row[2]}')
    
    # 检查文件是否存在
    if row[2]:
        print(f'File exists: {Path(row[2]).exists()}')
    
    # 检查实际文件
    covers_dir = Path('F:/github/MyMovieDB/data/covers')
    expected_path = covers_dir / 'EBOD-869' / 'EBOD-869-poster.jpg'
    print(f'Expected path: {expected_path}')
    print(f'Expected file exists: {expected_path.exists()}')

conn.close()
