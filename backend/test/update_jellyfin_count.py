#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3

db_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'movies.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 获取所有 Jellyfin 目录
cursor.execute('SELECT id, path FROM local_sources WHERE is_jellyfin = 1')
jellyfin_dirs = cursor.fetchall()

for source_id, dir_path in jellyfin_dirs:
    # 统计该目录下的影片数量（通过 poster_path 前缀匹配）
    cursor.execute('''
        SELECT COUNT(*) FROM movies 
        WHERE source = 'jellyfin' AND (poster_path LIKE ? OR fanart_path LIKE ?)
    ''', (dir_path + '%', dir_path + '%'))
    count = cursor.fetchone()[0]
    
    print(f'更新目录 {dir_path}: video_count = {count}')
    cursor.execute('UPDATE local_sources SET video_count = ? WHERE id = ?', (count, source_id))

conn.commit()

# 验证
cursor.execute('SELECT id, path, video_count, is_jellyfin FROM local_sources')
print('\n更新后所有目录:')
for row in cursor.fetchall():
    print(f'  ID={row[0]}, path={row[1]}, video_count={row[2]}, is_jellyfin={row[3]}')

conn.close()
