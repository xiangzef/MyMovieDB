#!/usr/bin/env python
# -*- coding: utf-8 -*-
import jellyfin

result = jellyfin.scan_jellyfin_directory(r'X:\影视库')
print(f'扫描结果: {len(result)} 个影片')
for i, r in enumerate(result):
    print(f'{i+1}. {r["code"]} - {r["video_path"]}')
