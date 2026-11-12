# -*- coding: utf-8 -*-
"""测试单源离线刮削：av-wiki/javsee(直连), jav321(代理)"""
import sys
import logging

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"F:\github\MyMovieDB\backend")
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")

os_env_proxy = False  # 本脚本：直连模式

import enhanced_scraper as es  # noqa: E402
import config as cfg           # noqa: E402

CODE = "SSIS-338"
CFG = es.EnhancedConfig(request_delay=0.4, parallel_timeout=60)

def src(sid: str):
    return next(s for s in cfg.SCRAPER_SOURCES if s["id"] == sid)

for sid in ["av-wiki", "javsee", "jav321"]:
    w = es.LegacyScraperWrapper(src(sid), CFG)
    data = w.scrape(CODE)
    if data:
        print(f"[{sid}] OK  code={data.get('code')} title={str(data.get('title'))[:50]} "
              f"cover={str(data.get('cover_url'))[:60]} actors={data.get('actors')}")
    else:
        print(f"[{sid}] MISS")
