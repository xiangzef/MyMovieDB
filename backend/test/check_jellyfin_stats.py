#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3

db_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'movies.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 查看 Jellyfin 导入的影片数量
cursor.execute("SELECT COUNT(*) FROM movies WHERE source = 'jellyfin'")
print(f'Jellyfin 导入的影片数: {cursor.fetchone()[0]}')

# 查看 Jellyfin 目录
cursor.execute('SELECT id, path, video_count, is_jellyfin FROM local_sources')
print('\n所有目录:')
for row in cursor.fetchall():
    print(f'  ID={row[0]}, path={row[1]}, video_count={row[2]}, is_jellyfin={row[3]}')

conn.close()
