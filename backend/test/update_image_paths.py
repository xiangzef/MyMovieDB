"""更新数据库中已有影片的图片路径"""
import sqlite3
from pathlib import Path

conn = sqlite3.connect('F:/github/MyMovieDB/data/movies.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# 获取所有有封面目录的番号
covers_dir = Path('F:/github/MyMovieDB/data/covers')
updated = 0

for code_dir in covers_dir.iterdir():
    if not code_dir.is_dir():
        continue
    
    code = code_dir.name
    fanart_path = code_dir / f"{code}-fanart.jpg"
    poster_path = code_dir / f"{code}-poster.jpg"
    thumb_path = code_dir / f"{code}-thumb.jpg"
    
    if fanart_path.exists() or poster_path.exists():
        cursor.execute("""
            UPDATE movies 
            SET fanart_path = ?, poster_path = ?, thumb_path = ?
            WHERE code = ?
        """, (
            str(fanart_path) if fanart_path.exists() else None,
            str(poster_path) if poster_path.exists() else None,
            str(thumb_path) if thumb_path.exists() else None,
            code
        ))
        if cursor.rowcount > 0:
            print(f"✅ 更新 {code}")
            updated += 1
        else:
            print(f"⚠️ 数据库中未找到 {code}")

conn.commit()
conn.close()
print(f"\n共更新 {updated} 条记录")
