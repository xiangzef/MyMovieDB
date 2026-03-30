#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试 Jellyfin 导入逻辑"""
import sys
sys.path.insert(0, '.')

import database as db
from jellyfin import scan_jellyfin_directory

# 初始化所有数据库表
db.init_all_tables()

# 扫描目录
results = scan_jellyfin_directory(r'Y:\影视库')

print(f"\n找到 {len(results)} 个影片")
for item in results:
    print(f"\n{'='*60}")
    print(f"番号: {item['code']}")
    print(f"视频: {item['video_path']}")
    print(f"NFO: {item.get('nfo_path')}")
    print(f"封面: {item.get('poster_file')}")
    print(f"背景: {item.get('fanart_file')}")
    print(f"缩略图: {item.get('thumb_file')}")
    print(f"元数据: {item['metadata']}")
    
    # 测试导入
    print(f"\n尝试导入数据库...")
    try:
        movie_id = db.import_jellyfin_movie(
            code=item['code'],
            metadata=item['metadata'],
            video_path=item['video_path'],
            poster_file=item.get('poster_file'),
            fanart_file=item.get('fanart_file'),
            thumb_file=item.get('thumb_file'),
        )
        print(f"导入结果: movie_id={movie_id}")
        
        if movie_id == -1:
            print("❌ 导入失败")
        elif movie_id == 0:
            print("⏭️ 已存在，跳过")
        else:
            print(f"✅ 导入成功，ID={movie_id}")
    except Exception as e:
        print(f"❌ 导入异常: {e}")
        import traceback
        traceback.print_exc()
