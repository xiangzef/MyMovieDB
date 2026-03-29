"""
更新数据库中的封面路径
"""
import sqlite3
from pathlib import Path

DB_PATH = Path("F:/github/MyMovieDB/data/movies.db")
COVERS_DIR = Path("F:/github/MyMovieDB/data/covers")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# 获取所有影片
cursor.execute("SELECT id, code FROM movies")
movies = cursor.fetchall()

updated_count = 0
for id, code in movies:
    if not code:
        continue
    
    # 检查封面文件是否存在
    code_dir = COVERS_DIR / code
    poster_path = code_dir / f"{code}-poster.jpg"
    fanart_path = code_dir / f"{code}-fanart.jpg"
    thumb_path = code_dir / f"{code}-thumb.jpg"
    
    if poster_path.exists():
        # 更新数据库
        cursor.execute("""
            UPDATE movies 
            SET poster_path = ?, fanart_path = ?, thumb_path = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (str(poster_path), str(fanart_path) if fanart_path.exists() else None,
              str(thumb_path) if thumb_path.exists() else None, id))
        updated_count += 1

conn.commit()
print(f"已更新 {updated_count} 条记录的封面路径")

# 重新计算刮削状态
cursor.execute("SELECT id FROM movies")
all_ids = [row[0] for row in cursor.fetchall()]

from database import get_movie_by_id

for movie_id in all_ids:
    movie_data = get_movie_by_id(movie_id)
    if movie_data:
        from database import calculate_scrape_status
        status = calculate_scrape_status(movie_data)
        cursor.execute("UPDATE movies SET scrape_status = ? WHERE id = ?", (status, movie_id))

conn.commit()
conn.close()

print("已重新计算所有影片的刮削状态")
