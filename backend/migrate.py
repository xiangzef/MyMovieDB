"""
数据库迁移脚本
执行所有必要的数据库结构更新
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "movies.db"


def migrate():
    """执行数据库迁移"""
    if not DB_PATH.exists():
        print("[Migration] 数据库文件不存在，将自动创建")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("[Migration] 开始迁移...")
    
    # 1. movies 表增加 source 字段
    try:
        cursor.execute("ALTER TABLE movies ADD COLUMN source TEXT DEFAULT 'scraped'")
        print("[Migration] ✅ movies.source 字段添加成功")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e).lower():
            print("[Migration] ⏭️ movies.source 字段已存在，跳过")
        else:
            print(f"[Migration] ❌ 添加 movies.source 失败: {e}")
    
    # 2. movies 表增加 plot 字段
    try:
        cursor.execute("ALTER TABLE movies ADD COLUMN plot TEXT")
        print("[Migration] ✅ movies.plot 字段添加成功")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e).lower():
            print("[Migration] ⏭️ movies.plot 字段已存在，跳过")
        else:
            print(f"[Migration] ❌ 添加 movies.plot 失败: {e}")
    
    # 3. local_sources 表增加 is_jellyfin 字段
    try:
        cursor.execute("ALTER TABLE local_sources ADD COLUMN is_jellyfin INTEGER DEFAULT 0")
        print("[Migration] ✅ local_sources.is_jellyfin 字段添加成功")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e).lower():
            print("[Migration] ⏭️ local_sources.is_jellyfin 字段已存在，跳过")
        else:
            print(f"[Migration] ❌ 添加 local_sources.is_jellyfin 失败: {e}")
    
    # 4. 检查并添加 movies 表其他可能缺失的字段
    existing_columns = [col[1] for col in cursor.execute("PRAGMA table_info(movies)")]
    
    optional_columns = {
        "fanart_path": "ALTER TABLE movies ADD COLUMN fanart_path TEXT",
        "poster_path": "ALTER TABLE movies ADD COLUMN poster_path TEXT",
        "thumb_path": "ALTER TABLE movies ADD COLUMN thumb_path TEXT",
        "title_cn": "ALTER TABLE movies ADD COLUMN title_cn TEXT",
        "scrape_status": "ALTER TABLE movies ADD COLUMN scrape_status TEXT DEFAULT 'partial'",
        "scrape_source": "ALTER TABLE movies ADD COLUMN scrape_source TEXT",
    }
    
    for col_name, sql in optional_columns.items():
        if col_name not in existing_columns:
            try:
                cursor.execute(sql)
                print(f"[Migration] ✅ movies.{col_name} 字段添加成功")
            except sqlite3.OperationalError as e:
                if "duplicate column" not in str(e).lower():
                    print(f"[Migration] ❌ 添加 movies.{col_name} 失败: {e}")
    
    conn.commit()
    conn.close()
    
    print("[Migration] 迁移完成！")


if __name__ == "__main__":
    migrate()
