"""临时迁移脚本"""
import sqlite3
from pathlib import Path

DB_PATH = Path("F:/github/MyMovieDB/data/movies.db")

print(f"数据库路径: {DB_PATH}")
print(f"数据库存在: {DB_PATH.exists()}")

if DB_PATH.exists():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 添加 source 字段
    try:
        cursor.execute("ALTER TABLE movies ADD COLUMN source TEXT DEFAULT 'scraped'")
        print("✅ movies.source 字段添加成功")
    except Exception as e:
        if "duplicate column" in str(e).lower():
            print("⏭️ movies.source 字段已存在")
        else:
            print(f"❌ {e}")
    
    # 添加 plot 字段
    try:
        cursor.execute("ALTER TABLE movies ADD COLUMN plot TEXT")
        print("✅ movies.plot 字段添加成功")
    except Exception as e:
        if "duplicate column" in str(e).lower():
            print("⏭️ movies.plot 字段已存在")
        else:
            print(f"❌ {e}")
    
    # 添加 is_jellyfin 字段到 local_sources
    try:
        cursor.execute("ALTER TABLE local_sources ADD COLUMN is_jellyfin INTEGER DEFAULT 0")
        print("✅ local_sources.is_jellyfin 字段添加成功")
    except Exception as e:
        if "duplicate column" in str(e).lower():
            print("⏭️ local_sources.is_jellyfin 字段已存在")
        else:
            print(f"❌ {e}")
    
    conn.commit()
    conn.close()
    print("迁移完成！")
else:
    print("数据库不存在，将在首次启动时自动创建")
