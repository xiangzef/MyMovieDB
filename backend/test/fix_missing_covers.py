"""
批量修复缺少封面的影片
- 重新下载封面
- 更新刮削状态
"""
import json
import sqlite3
import time
from pathlib import Path

from scraper import download_and_crop_cover, generate_nfo

# 配置
DB_PATH = Path("F:/github/MyMovieDB/data/movies.db")
COVERS_DIR = Path("F:/github/MyMovieDB/data/covers")

# 加载缺少封面的影片列表
with open('missing_covers.json', 'r', encoding='utf-8') as f:
    missing_covers = json.load(f)

print(f"需要修复的影片数: {len(missing_covers)}\n")

# 连接数据库
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

success_count = 0
fail_count = 0

for i, item in enumerate(missing_covers, 1):
    code = item['code']
    cover_url = item['cover_url']
    
    print(f"[{i}/{len(missing_covers)}] {code}: ", end='', flush=True)
    
    if not cover_url:
        print("无封面URL，跳过")
        fail_count += 1
        continue
    
    try:
        # 下载并裁切封面
        crop_paths = download_and_crop_cover(cover_url, code, COVERS_DIR)
        
        if crop_paths:
            # 更新数据库
            cursor.execute("""
                UPDATE movies 
                SET poster_path = ?, fanart_path = ?, thumb_path = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (crop_paths.get('poster'), crop_paths.get('fanart'), crop_paths.get('thumb'), item['id']))
            
            # 生成 NFO 文件
            cursor.execute("SELECT * FROM movies WHERE id = ?", (item['id'],))
            row = cursor.fetchone()
            if row:
                movie_data = dict(row)
                safe_code = code.replace(':', '_').replace('/', '_')
                nfo_path = Path(crop_paths.get('folder', COVERS_DIR / safe_code)) / f"{safe_code}.nfo"
                generate_nfo(movie_data, nfo_path)
            
            conn.commit()
            print("✅ 成功")
            success_count += 1
        else:
            print("❌ 下载失败")
            fail_count += 1
        
        # 避免请求过快
        time.sleep(0.5)
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        fail_count += 1

# 重新计算所有影片的刮削状态
print("\n重新计算刮削状态...")
cursor.execute("SELECT id FROM movies")
all_ids = [row[0] for row in cursor.fetchall()]

for movie_id in all_ids:
    cursor.execute("SELECT * FROM movies WHERE id = ?", (movie_id,))
    row = cursor.fetchone()
    if row:
        movie_data = dict(row)
        # 动态计算状态（会检查封面文件）
        from database import calculate_scrape_status
        status = calculate_scrape_status(movie_data)
        cursor.execute("UPDATE movies SET scrape_status = ? WHERE id = ?", (status, movie_id))

conn.commit()
conn.close()

print(f"\n修复完成！成功: {success_count}, 失败: {fail_count}")
