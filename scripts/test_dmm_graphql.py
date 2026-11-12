# -*- coding: utf-8 -*-
"""单测 DMM GraphQL 移植版"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"F:\github\MyMovieDB\scripts")

from step2_offline_scrape import DmmGraphql, jav321_proxy  # noqa: E402

d = DmmGraphql()
md = d.scrape("SNIS-800")
if md:
    print("DMM OK")
    for k, v in md.items():
        print(f"  {k}: {str(v)[:70]}")
else:
    print("DMM MISS")

if not md:
    md2 = jav321_proxy("SNIS-800")
    if md2:
        print("jav321 OK")
        for k, v in md2.items():
            print(f"  {k}: {str(v)[:70]}")
