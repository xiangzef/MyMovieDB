#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""清理错误路径的 Jellyfin 目录记录"""
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'movies.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 删除错误路径的记录
cursor.execute("DELETE FROM local_sources WHERE path = 'X:\\\\影视库'")
conn.commit()
print(f'删除了 {cursor.rowcount} 条记录')

# 验证
cursor.execute('SELECT id, path, is_jellyfin FROM local_sources ORDER BY id')
for row in cursor.fetchall():
    print(f'ID={row[0]}, path={row[1]}, is_jellyfin={row[2]}')
conn.close()
