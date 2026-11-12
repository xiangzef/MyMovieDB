# -*- coding: utf-8 -*-
"""测试 fanza(DMM) 直连刮削 SNIS-800 + 年龄 cookie 检查"""
import sys
import logging

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"F:\github\MyMovieDB\backend")
logging.basicConfig(level=logging.INFO)
import requests

# 直连模式（清掉代理 env）
for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
    import os
    os.environ.pop(k, None)

sess = requests.Session()
# 带 DMM 年龄确认 cookie
sess.cookies.set("age_check_done", "1", domain="www.dmm.co.jp")
r = sess.get("https://www.dmm.co.jp/mono/dvd/-/detail/=/cid=snis800/",
             headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"},
             timeout=20)
print("fanza direct + age cookie ->", r.status_code, len(r.content))
import re
t = re.sub(r"<[^>]+>", " ", r.text[:4000])
print(" ".join(t.split())[:300])

# 项目自己的 FanzaScraper
from scraper import FanzaScraper  # noqa: E402
fs = FanzaScraper(delay=0.5)
fs.session = sess  # 注入带年龄 cookie 的 session
d = fs.scrape("SNIS-800") if hasattr(fs, "scrape") else None
if d is None:
    try:
        d = fs.get_movie("SNIS-800")
    except Exception as e:
        print("FanzaScraper attr 查找失败:", e)
print("FanzaScraper ->", ("OK " + str(d.get("title"))[:50] + " cover=" + str(d.get("cover_url"))[:60]) if d else "MISS")
