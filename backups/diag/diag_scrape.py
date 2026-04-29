import sys
sys.path.insert(0, '.')
from database import get_db, check_and_fix_scrape_status, calculate_scrape_status

conn = get_db()
cur = conn.cursor()

# 查 Step-1 SQL 原始数量（只看非 Jellyfin + 非 complete 的）
cur.execute("""
    SELECT v.id, v.code, v.movie_id,
           m.scrape_status as old_status, m.source_type,
           m.title, m.release_date, m.maker, m.poster_path,
           m.actors
    FROM local_videos v
    LEFT JOIN movies m ON v.movie_id = m.id
    WHERE v.code IS NOT NULL AND v.code != ''
      AND (m.scrape_status IS NULL OR m.scrape_status != 'complete')
      AND (m.source_type IS NULL OR m.source_type != 'jellyfin')
    ORDER BY v.id
""")
rows = cur.fetchall()
print(f"Step-1 SQL 原始数量: {len(rows)}")

# 统计 Step-1 各状态分布
from collections import Counter
status_dist = Counter(r['old_status'] for r in rows)
print(f"Step-1 old_status 分布: {dict(status_dist)}")

# Step-2 Python 预检：逐个验证
passed = []
skipped = []
for r in rows:
    code = r['code']
    check = check_and_fix_scrape_status(code)
    if not check['exists']:
        passed.append(('no_movie', code))
    elif check['should_scrape']:
        passed.append((check['new_status'], code))
    else:
        skipped.append((check['new_status'], code, r['old_status']))

print(f"\n预检后 需刮削: {len(passed)}")
passed_dist = Counter(x[0] for x in passed)
print(f"  分布: {dict(passed_dist)}")

print(f"\n预检后 跳过（标志修正）: {len(skipped)}")
skipped_dist = Counter(x[0] for x in skipped)
print(f"  分布: {dict(skipped_dist)}")

# 展示被跳过原因
print("\n被跳过样例（前5个）:")
for s, code, old in skipped[:5]:
    print(f"  [{code}] old={old} new={s} → 跳过")

# 展示 passed 样例
print("\n需刮削样例（前10个）:")
for s, code in passed[:10]:
    print(f"  [{code}] → {s}")

# 查 Jellyfin 视频的 scrape_status 分布
print("\n=== Jellyfin 视频的 scrape_status ===")
cur.execute("""
    SELECT m.scrape_status, COUNT(*) as cnt
    FROM local_videos v
    JOIN movies m ON v.movie_id = m.id
    WHERE v.code IS NOT NULL AND v.code != ''
      AND m.source_type = 'jellyfin'
    GROUP BY m.scrape_status
""")
for row in cur.fetchall():
    print(f"  {row['scrape_status'] or 'NULL'}: {row['cnt']}")

conn.close()
