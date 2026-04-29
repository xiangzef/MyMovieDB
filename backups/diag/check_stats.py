import sqlite3, sys
sys.path.insert(0, '.')
from database import get_db

conn = get_db()
cur = conn.cursor()

# 1. 全部有番号的本地视频
cur.execute("SELECT COUNT(*) FROM local_videos WHERE code IS NOT NULL AND code != ''")
total = cur.fetchone()[0]
print(f'总视频（含Jellyfin）: {total}')

# 2. 非Jellyfin来源的总数
cur.execute("""
    SELECT COUNT(*) FROM local_videos v
    LEFT JOIN movies m ON v.movie_id = m.id
    WHERE v.code IS NOT NULL AND v.code != ''
      AND (m.source_type IS NULL OR m.source_type != 'jellyfin')
""")
non_jf = cur.fetchone()[0]
print(f'非Jellyfin视频: {non_jf}')

# 3. 已刮削完整（非Jellyfin）
cur.execute("""
    SELECT COUNT(*) FROM local_videos v
    JOIN movies m ON v.movie_id = m.id
    WHERE v.code IS NOT NULL AND v.code != ''
      AND m.scrape_status = 'complete'
      AND (m.source_type IS NULL OR m.source_type != 'jellyfin')
""")
scraped = cur.fetchone()[0]
print(f'已刮削（complete+非Jellyfin）: {scraped}')

# 4. 待刮削
print(f'待刮削（推算 non_jf - scraped）: {non_jf - scraped}')

# 5. Jellyfin视频数
cur.execute("""
    SELECT COUNT(*) FROM local_videos v
    JOIN movies m ON v.movie_id = m.id
    WHERE v.code IS NOT NULL AND v.code != ''
      AND m.source_type = 'jellyfin'
""")
jellyfin = cur.fetchone()[0]
print(f'Jellyfin视频: {jellyfin}')

# 6. 验证
print(f'\n验证: total={total} vs scraped+待刮+jellyfin={scraped}+{non_jf-scraped}+{jellyfin} -> {total == scraped + (non_jf-scraped) + jellyfin}')

# 7. Jellyfin 来源目录
print('\n=== Jellyfin 来源目录 ===')
cur.execute("""
    SELECT s.path, COUNT(v.id) as cnt
    FROM local_sources s
    LEFT JOIN local_videos v ON v.source_id = s.id
    WHERE s.is_jellyfin = 1
    GROUP BY s.id, s.path
    ORDER BY cnt DESC
""")
for row in cur.fetchall():
    print(f'  [{row[1]}] {row[0]}')

# 8. 非Jellyfin来源目录
print('\n=== 非Jellyfin 来源目录 ===')
cur.execute("""
    SELECT s.path, COUNT(v.id) as cnt
    FROM local_sources s
    LEFT JOIN local_videos v ON v.source_id = s.id
    WHERE (s.is_jellyfin = 0 OR s.is_jellyfin IS NULL)
    GROUP BY s.id, s.path
    ORDER BY cnt DESC
""")
for row in cur.fetchall():
    print(f'  [{row[1]}] {row[0]}')

conn.close()
