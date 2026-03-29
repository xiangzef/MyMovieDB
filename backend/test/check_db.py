"""
数据库检查工具 - 统一检查封面路径、刮削状态、影片完整性
合并自: check_images.py, check_status.py, test_db_cover.py
"""
import sqlite3
import sys
from pathlib import Path
from argparse import ArgumentParser

sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = Path(__file__).parent.parent.parent / "data" / "movies.db"


def check_images(limit=10):
    """检查数据库中的封面路径字段"""
    print("\n" + "="*60)
    print(f"📊 检查封面路径字段（前 {limit} 条）")
    print("="*60)
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT code, title, fanart_path, poster_path, thumb_path, cover_url 
        FROM movies 
        ORDER BY updated_at DESC 
        LIMIT ?
    ''', (limit,))
    
    rows = cursor.fetchall()
    for row in rows:
        code = row['code']
        title = (row['title'] or '')[:30]
        fanart = row['fanart_path']
        poster = row['poster_path']
        thumb = row['thumb_path']
        cover = row['cover_url']
        
        print(f"\n🎬 {code} - {title}")
        print(f"  fanart: {'✅' if fanart else '❌'} {fanart[:50] if fanart else None}")
        print(f"  poster: {'✅' if poster else '❌'} {poster[:50] if poster else None}")
        print(f"  thumb: {'✅' if thumb else '❌'} {thumb[:50] if thumb else None}")
        print(f"  cover_url: {'✅' if cover else '❌'} {cover[:50] if cover else None}")
    
    conn.close()


def check_status(limit=20):
    """检查刮削状态为 complete 的影片详情"""
    print("\n" + "="*60)
    print(f"🔍 检查刮削状态（前 {limit} 条 complete）")
    print("="*60)
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT code, title, cover_url, actors, maker, release_date, scrape_status, poster_path
        FROM movies
        WHERE scrape_status = 'complete'
        ORDER BY updated_at DESC
        LIMIT ?
    ''', (limit,))
    
    rows = cursor.fetchall()
    issues = []
    
    for row in rows:
        code = row['code']
        title = (row['title'] or '')[:30]
        has_cover = bool(row['cover_url'] or row['poster_path'])
        has_actors = bool(row['actors'])
        has_maker = bool(row['maker'])
        has_date = bool(row['release_date'])
        status = row['scrape_status']
        
        issue_list = []
        if not has_cover:
            issue_list.append('无封面')
        if not has_actors:
            issue_list.append('无演员')
        if not has_maker:
            issue_list.append('无制作商')
        if not has_date:
            issue_list.append('无日期')
        
        status_icon = '✅' if not issue_list else '⚠️'
        print(f"{status_icon} {code}: {title}")
        if issue_list:
            print(f"   ⚠️  缺失: {', '.join(issue_list)}")
            issues.append(code)
    
    conn.close()
    
    print(f"\n📊 统计: 完整 {len(rows) - len(issues)} 部，不完整 {len(issues)} 部")
    if issues:
        print(f"⚠️  不完整番号: {', '.join(issues[:10])}")


def check_code(code):
    """检查特定番号的封面路径和文件存在性"""
    print("\n" + "="*60)
    print(f"🔎 检查番号: {code}")
    print("="*60)
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, code, title, poster_path, fanart_path, thumb_path, cover_url
        FROM movies 
        WHERE code = ?
    ''', (code,))
    
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        print(f"❌ 数据库中未找到 {code}")
        return
    
    print(f"🎬 ID: {row['id']}, Code: {row['code']}")
    print(f"📝 Title: {row['title']}")
    
    covers_dir = DB_PATH.parent / "covers" / code
    
    # 检查 poster
    poster_db = row['poster_path']
    poster_file = covers_dir / f"{code}-poster.jpg"
    print(f"\n📌 Poster:")
    print(f"  数据库路径: {poster_db}")
    print(f"  文件存在: {'✅' if poster_db and Path(poster_db).exists() else '❌'}")
    print(f"  预期路径: {poster_file}")
    print(f"  预期文件存在: {'✅' if poster_file.exists() else '❌'}")
    
    # 检查 fanart
    fanart_db = row['fanart_path']
    fanart_file = covers_dir / f"{code}-fanart.jpg"
    print(f"\n🖼️  Fanart:")
    print(f"  数据库路径: {fanart_db}")
    print(f"  文件存在: {'✅' if fanart_db and Path(fanart_db).exists() else '❌'}")
    print(f"  预期路径: {fanart_file}")
    print(f"  预期文件存在: {'✅' if fanart_file.exists() else '❌'}")
    
    # 检查 thumb
    thumb_db = row['thumb_path']
    thumb_file = covers_dir / f"{code}-thumb.jpg"
    print(f"\n🔲 Thumb:")
    print(f"  数据库路径: {thumb_db}")
    print(f"  文件存在: {'✅' if thumb_db and Path(thumb_db).exists() else '❌'}")
    print(f"  预期路径: {thumb_file}")
    print(f"  预期文件存在: {'✅' if thumb_file.exists() else '❌'}")


def check_missing_covers():
    """检查标记为 complete 但缺少封面文件的影片"""
    print("\n" + "="*60)
    print("🔍 检查缺少封面的 complete 影片")
    print("="*60)
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, code, title, scrape_status, poster_path, fanart_path, thumb_path, cover_url
        FROM movies
        WHERE scrape_status = 'complete'
    ''')
    
    rows = cursor.fetchall()
    conn.close()
    
    issues = []
    for row in rows:
        code = row['code']
        poster_path = row['poster_path']
        
        # 检查 poster 文件是否存在
        if poster_path and not Path(poster_path).exists():
            issues.append({
                'code': code,
                'title': row['title'],
                'poster_path': poster_path
            })
    
    if issues:
        print(f"⚠️  发现 {len(issues)} 部影片缺少封面文件:")
        for item in issues[:20]:
            print(f"  - {item['code']}: {item['poster_path'][:60]}")
    else:
        print("✅ 所有 complete 影片都有封面文件")


if __name__ == "__main__":
    parser = ArgumentParser(description="数据库检查工具")
    parser.add_argument('command', choices=['images', 'status', 'code', 'missing'],
                       help='检查命令: images(封面路径), status(刮削状态), code(特定番号), missing(缺失封面)')
    parser.add_argument('--limit', type=int, default=10, help='显示数量限制')
    parser.add_argument('--code', type=str, help='特定番号')
    
    args = parser.parse_args()
    
    if args.command == 'images':
        check_images(args.limit)
    elif args.command == 'status':
        check_status(args.limit)
    elif args.command == 'code':
        if not args.code:
            print("❌ 请使用 --code 参数指定番号")
            sys.exit(1)
        check_code(args.code)
    elif args.command == 'missing':
        check_missing_covers()
