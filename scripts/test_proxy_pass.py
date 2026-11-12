# -*- coding: utf-8 -*-
"""测试代理批次刮削：jav321 / av-wiki（走代理）"""
import sys
import logging

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"F:\github\MyMovieDB\backend")
logging.basicConfig(level=logging.WARNING)

import enhanced_scraper as es  # noqa: E402
import config as cfg           # noqa: E402

CFG = es.EnhancedConfig(request_delay=0.4)

for sid in ["jav321", "av-wiki"]:
    s = [x for x in cfg.SCRAPER_SOURCES if x["id"] == sid][0]
    w = es.LegacyScraperWrapper(s, CFG)
    d = w.scrape("SNIS-800")
    if d:
        print(sid, "-> OK", str(d.get("title"))[:45])
    else:
        print(sid, "-> MISS")
