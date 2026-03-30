#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""手动添加 Jellyfin 目录"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database as db

# 使用原始字符串
dirs = [r'X:\影视库', r'Y:\影视库']
for d in dirs:
    result = db.mark_source_as_jellyfin(d)
    print(f'添加目录 {d}: {result}')

# 验证
sources = db.get_local_sources_with_jellyfin()
print('\n当前所有目录:')
for s in sources:
    print(f'  ID={s["id"]}, path={s["path"]}, is_jellyfin={s.get("is_jellyfin", 0)}')
