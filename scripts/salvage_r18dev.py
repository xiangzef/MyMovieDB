# -*- coding: utf-8 -*-
"""补刮 11 个失败番号：r18.dev 直连（peach 的有码主源）"""
import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"F:\github\MyMovieDB\backend")

import requests

FAIL = ["ADN-151", "AVOP-004", "RBD-916", "SNIS-027", "SNIS-091",
        "SNIS-110", "SOE-646", "SSPD-142", "SSPD-144", "SSPD-157", "TEK-089"]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def r18dev(code):
    parts = code.split("-")
    letters, number = parts[0], parts[1]
    sess = requests.Session()
    sess.trust_env = False
    # dvd_id 形式: dvd_id=snis00127 / combined=snis00127
    cid = f"{letters.lower()}{int(number):05d}"
    for url in (f"https://r18.dev/videos/vod/movies/detail/-/dvd_id={cid}/json",
                f"https://r18.dev/videos/vod/movies/detail/-/combined={cid}/json"):
        try:
            r = sess.get(url, headers={"User-Agent": UA}, timeout=20)
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            print("  err", type(e).__name__, url)
    return None


results = {}
for code in FAIL:
    d = r18dev(code)
    if d and isinstance(d, dict) and d.get("content_id"):
        results[code] = d
        print(f"[{code}] OK  {d.get('title','')[:50]}  actors={[a.get('name') for a in d.get('actresses',[])][:3]}")
    else:
        print(f"[{code}] MISS")
    time.sleep(1.5)

out = Path(r"F:\github\MyMovieDB\data\r18dev_salvage.json")
out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nr18dev 命中 {len(results)}/{len(FAIL)}，原始 JSON 已存 {out}")
