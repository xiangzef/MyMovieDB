"""
封面修复工具 - 统一修复封面路径、重新生成缩略图
合并自: fix_cover_paths.py, update_db_covers.py, update_image_paths.py
"""
import sqlite3
import sys
from pathlib import Path
from argparse import ArgumentParser

sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = Path(__file__).parent.parent.parent / "data" / "movies.db"
COVERS_DIR = DB_PATH.parent / "covers"
BASE_DIR = DB_PATH.parent.parent


def fix_relative_paths():
    """修复相对路径为绝对路径"""
    print("\n" + "="*60)
    print("🔧 修复相对路径")
    print("="*60)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 检查相对路径数量
    cursor.execute('SELECT COUNT(*) FROM movies WHERE poster_path LIKE "..%"')
    relative_count = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM movies WHERE poster_path LIKE "F:%"')
    absolute_count = cursor.fetchone()[0]
    
    print(f"📊 相对路径记录: {relative_count}")
    print(f"📊 绝对路径记录: {absolute_count}")
    
    if relative_count == 0:
        print("✅ 没有需要修复的相对路径")
        conn.close()
        return
    
    # 修复相对路径
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
    
    # 验证修复结果
    cursor.execute('SELECT COUNT(*) FROM movies WHERE poster_path LIKE "..%"')
    remaining = cursor.fetchone()[0]
    conn.close()
    
    print(f"\n✅ 已修复 {updated} 条记录")
    print(f"📊 剩余相对路径记录: {remaining}")


def update_cover_paths():
    """根据封面文件更新数据库路径"""
    print("\n" + "="*60)
    print("🔄 更新数据库封面路径")
    print("="*60)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 获取所有封面目录
    if not COVERS_DIR.exists():
        print("❌ 封面目录不存在")
        conn.close()
        return
    
    updated = 0
    for code_dir in COVERS_DIR.iterdir():
        if not code_dir.is_dir():
            continue
        
        code = code_dir.name
        fanart_path = code_dir / f"{code}-fanart.jpg"
        poster_path = code_dir / f"{code}-poster.jpg"
        thumb_path = code_dir / f"{code}-thumb.jpg"
        
        if fanart_path.exists() or poster_path.exists():
            cursor.execute('''
                UPDATE movies 
                SET fanart_path = ?, poster_path = ?, thumb_path = ?, updated_at = CURRENT_TIMESTAMP
                WHERE code = ?
            ''', (
                str(fanart_path) if fanart_path.exists() else None,
                str(poster_path) if poster_path.exists() else None,
                str(thumb_path) if thumb_path.exists() else None,
                code
            ))
            if cursor.rowcount > 0:
                print(f"✅ 更新 {code}")
                updated += 1
            else:
                print(f"⚠️  数据库中未找到 {code}")
    
    conn.commit()
    conn.close()
    print(f"\n📊 共更新 {updated} 条记录")


def recalculate_status():
    """重新计算所有影片的刮削状态"""
    print("\n" + "="*60)
    print("🔄 重新计算刮削状态")
    print("="*60)
    
    # 添加 backend 到 path
    sys.path.insert(0, str(DB_PATH.parent.parent / "backend"))
    from database import get_movie_by_id, calculate_scrape_status
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM movies")
    all_ids = [row[0] for row in cursor.fetchall()]
    
    complete_count = 0
    partial_count = 0
    
    for movie_id in all_ids:
        movie_data = get_movie_by_id(movie_id)
        if movie_data:
            status = calculate_scrape_status(movie_data)
            cursor.execute("UPDATE movies SET scrape_status = ? WHERE id = ?", (status, movie_id))
            if status == 'complete':
                complete_count += 1
            else:
                partial_count += 1
    
    conn.commit()
    conn.close()
    
    print(f"✅ 完整: {complete_count} 部")
    print(f"⚠️  不完整: {partial_count} 部")


if __name__ == "__main__":
    parser = ArgumentParser(description="封面修复工具")
    parser.add_argument('command', choices=['paths', 'update', 'status', 'all'],
                       help='修复命令: paths(修复相对路径), update(更新路径), status(重算状态), all(全部执行)')
    
    args = parser.parse_args()
    
    if args.command == 'paths':
        fix_relative_paths()
    elif args.command == 'update':
        update_cover_paths()
    elif args.command == 'status':
        recalculate_status()
    elif args.command == 'all':
        fix_relative_paths()
        update_cover_paths()
        recalculate_status()
