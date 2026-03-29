import sqlite3
from pathlib import Path

DB_PATH = Path("F:/github/MyMovieDB/data/movies.db")
COVERS_DIR = Path("F:/github/MyMovieDB/data/covers")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# 查询所有标记为 complete 的影片
cursor.execute("""
    SELECT id, code, title, scrape_status, poster_path, fanart_path, thumb_path, cover_url
    FROM movies
    WHERE scrape_status = 'complete'
""")
rows = cursor.fetchall()

print(f"标记为 'complete' 的影片数: {len(rows)}\n")

missing_cover = []
for row in rows:
    id, code, title, status, poster, fanart, thumb, cover_url = row
    
    # 检查封面文件是否存在
    poster_exists = poster and Path(poster).exists() if poster else False
    fanart_exists = fanart and Path(fanart).exists() if fanart else False
    
    if not poster_exists:
        missing_cover.append({
            'id': id,
            'code': code,
            'title': title[:30] if title else '',
            'poster_path': poster,
            'cover_url': cover_url
        })

print(f"缺少封面文件的影片数: {len(missing_cover)}\n")
print(f"{'ID':<6} {'番号':<12} {'标题':<35} {'cover_url'}")
print("-" * 120)
for item in missing_cover[:20]:  # 只显示前20条
    print(f"{item['id']:<6} {item['code']:<12} {item['title']:<35} {item['cover_url']}")

conn.close()

# 输出到文件供后续处理
if missing_cover:
    import json
    with open('missing_covers.json', 'w', encoding='utf-8') as f:
        json.dump(missing_cover, f, ensure_ascii=False, indent=2)
    print(f"\n完整列表已保存到: missing_covers.json")
