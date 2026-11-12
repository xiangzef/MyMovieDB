# -*- coding: utf-8 -*-
"""Step 2: 批量刮削驱动 — 消费 /local-sources/scrape SSE 流，记录日志"""
import json
import sys

import requests

sys.stdout.reconfigure(encoding="utf-8")
URL = "http://localhost:8000/local-sources/scrape"

with requests.post(URL, stream=True, timeout=3600) as r:
    r.raise_for_status()
    for line in r.iter_lines(decode_unicode=True):
        if not line:
            continue
        print(line, flush=True)
        if line.startswith("event: done") or '"type": "done"' in line:
            break
print("[driver] done.")
