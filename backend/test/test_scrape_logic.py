"""
测试刮削逻辑：验证重新刮削 partial 状态的影片
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "movies.db"

def test_scrape_logic():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("=" * 60)
    print("刮削逻辑测试")
    print("=" * 60)

    # 1. 统计本地视频状态
    print("\n【本地视频统计】")
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN scraped = 0 THEN 1 ELSE 0 END) as unscraped,
            SUM(CASE WHEN scraped = 1 THEN 1 ELSE 0 END) as scraped
        FROM local_videos
    """)
    row = cursor.fetchone()
    print(f"总视频数: {row['total']}")
    print(f"未刮削: {row['unscraped']}")
    print(f"已刮削: {row['scraped']}")

    # 2. 统计影片刮削状态
    print("\n【影片刮削状态】")
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN scrape_status = 'complete' THEN 1 ELSE 0 END) as complete,
            SUM(CASE WHEN scrape_status = 'partial' THEN 1 ELSE 0 END) as partial,
            SUM(CASE WHEN scrape_status = 'empty' THEN 1 ELSE 0 END) as empty
        FROM movies
    """)
    row = cursor.fetchone()
    print(f"总影片数: {row['total']}")
    print(f"完整刮削 (complete): {row['complete']}")
    print(f"部分刮削 (partial): {row['partial']}")
    print(f"仅番号 (empty): {row['empty']}")

    # 3. 模拟 get_unscraped_local_videos 查询
    print("\n【需要刮削的本地视频】")
    cursor.execute("""
        SELECT v.id, v.code, v.scraped, m.scrape_status, m.title
        FROM local_videos v
        LEFT JOIN movies m ON v.movie_id = m.id
        WHERE v.code IS NOT NULL AND v.code != ''
          AND (v.scraped = 0 OR m.scrape_status IS NULL OR m.scrape_status IN ('partial', 'empty'))
        ORDER BY v.id
        LIMIT 20
    """)
    rows = cursor.fetchall()
    
    print(f"查询结果（前20条）:")
    print(f"{'ID':<6} {'番号':<12} {'已刮削':<8} {'状态':<10} {'标题'}")
    print("-" * 60)
    for row in rows:
        title = (row['title'][:20] + '...') if row['title'] and len(row['title']) > 20 else (row['title'] or '')
        print(f"{row['id']:<6} {row['code']:<12} {row['scraped']:<8} {row['scrape_status'] or 'NULL':<10} {title}")

    # 4. 统计需要刮削的总数
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM local_videos v
        LEFT JOIN movies m ON v.movie_id = m.id
        WHERE v.code IS NOT NULL AND v.code != ''
          AND (v.scraped = 0 OR m.scrape_status IS NULL OR m.scrape_status IN ('partial', 'empty'))
    """)
    total_need_scrape = cursor.fetchone()['count']
    print(f"\n需要刮削的总数: {total_need_scrape}")

    # 5. 显示部分刮削的具体案例
    print("\n【部分刮削案例（需要重新刮削）】")
    cursor.execute("""
        SELECT v.code, m.title, m.scrape_status,
               m.actors IS NOT NULL as has_actors,
               m.maker IS NOT NULL as has_maker,
               m.release_date IS NOT NULL as has_date
        FROM local_videos v
        JOIN movies m ON v.movie_id = m.id
        WHERE m.scrape_status = 'partial'
        LIMIT 5
    """)
    rows = cursor.fetchall()
    if rows:
        for row in rows:
            print(f"  {row['code']}: {row['title'][:30]}")
            print(f"    演员={row['has_actors']}, 制作商={row['has_maker']}, 日期={row['has_date']}")
    else:
        print("  暂无部分刮削的影片")

    conn.close()

if __name__ == "__main__":
    test_scrape_logic()
