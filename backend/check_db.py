import database as db

# 初始化数据库（创建表）
db.init_db()

# 检查表
conn = db.get_db()
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cursor.fetchall()]
print(f"数据库表: {tables}")
conn.close()
