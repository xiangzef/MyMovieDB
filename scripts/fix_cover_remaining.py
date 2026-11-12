# -*- coding: utf-8 -*-
"""给缺图影片补封面：DMM GraphQL 拿 cover_url，多图床 × 直连/代理重试"""
import json
import os
import re
import sys
import time
from io import BytesIO
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = r"F:\github\MyMovieDB"
sys.path.insert(0, ROOT + r"\backend")
sys.path.insert(0, ROOT + r"\scripts")
for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
    os.environ.pop(k, None)

import requests  # noqa: E402
from PIL import Image  # noqa: E402
import database as db  # noqa: E402
from step2_offline_scrape import DmmGraphql   # noqa: E402
import enhanced_scraper as es_mod  # noqa: E402
es_mod.translate_to_chinese = lambda *a, **k: None

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
PROXY = {"http": "http://127.0.0.1:7897", "https": "http://127.0.0.1:7897"}


def dmm_scrape_any(code, tries=6):
    for t in range(tries):
        proxied = t % 2 == 1
        try:
            obj = DmmGraphql.__new__(DmmGraphql)
            obj.sess = requests.Session()
            if proxied:
                obj.sess.proxies = PROXY
            else:
                obj.sess.trust_env = False
            return obj.scrape(code)
        except Exception:
            time.sleep(3 + 2 * t)
    return None


def fetch(url, tries=3):
    for t in range(tries):
        try:
            kw = {"trust_env": False} if t % 2 == 0 else {"proxies": PROXY}
            r = requests.get(url, timeout=30, headers={
                "User-Agent": UA, "Referer": "https://www.dmm.co.jp/"}, **kw)
            if r.status_code == 200 and len(r.content) > 8000:
                return r.content
        except Exception:
            pass
        time.sleep(2 + 2 * t)
    return None


def cid_of(code):
    letters, number = code.split("-")[0], code.split("-")[1]
    return f"{letters.lower()}{int(number):05d}"


def save_into_folder(folder, base, data):
    img = Image.open(BytesIO(data)).convert("RGB")
    w, h = img.size
    fanart = os.path.join(folder, base + "-fanart.jpg")
    img.save(fanart, quality=92)
    pw = int(h * 2 / 3)
    poster_img = img.crop((w - pw, 0, w, h)) if pw < w else img
    poster = os.path.join(folder, base + "-poster.jpg")
    poster_img.resize((1000, 1500), Image.Resampling.LANCZOS).save(poster, quality=92)
    thumb = os.path.join(folder, base + "-thumb.jpg")
    poster_img.resize((300, 450), Image.Resampling.LANCZOS).save(thumb, quality=90)
    return fanart, poster, thumb


conn = db.get_db()
rows = conn.execute("""
    SELECT v.id AS vid, v.code, m.id AS mid, m.organized_path, m.actors
    FROM local_videos v JOIN movies m ON v.movie_id=m.id
    WHERE v.source_id=14
""").fetchall()

todo = []
for r in rows:
    d = str(r["organized_path"] or "")
    base = os.path.basename(d)
    if not os.path.isdir(d):
        continue
    if os.path.exists(os.path.join(d, base + "-fanart.jpg")) or \
       os.path.exists(os.path.join(d, base + "-poster.jpg")):
        continue
    todo.append((r, d, base))
print(f"缺图影片: {len(todo)}", flush=True)

ok = 0
for i, (r, d, base) in enumerate(todo, 1):
    code = r["code"]
    print(f"[{i}/{len(todo)}] {code}", flush=True)
    cover = None
    md = dmm_scrape_any(code)
    if md and md.get("cover_url"):
        cover = md["cover_url"]
        print(f"    DMM: {cover[:70]}", flush=True)
    if not cover:
        cid = cid_of(code)
        cover = f"https://awsimgsrc.dmm.co.jp/pics_dig/digital/video/{cid}/{cid}pl.jpg"
        print(f"    推测图床: {cover}", flush=True)

    data = fetch(cover)
    if not data and "awsimgsrc" in cover:
        # 换 pics.dmm.co.jp 域名再试
        alt = cover.replace("awsimgsrc.dmm.co.jp/pics_dig", "pics.dmm.co.jp")
        data = fetch(alt)
    if not data:
        print("    ❌ 封面下载失败", flush=True)
        continue
    try:
        fa, po, th = save_into_folder(d, base, data)
        conn.execute("""UPDATE movies SET fanart_path=?, poster_path=?, thumb_path=?,
                        local_cover_path=?, jellyfin_status='complete' WHERE id=?""",
                     (fa, po, th, fa, r["mid"]))
        conn.execute("UPDATE local_videos SET fanart_path=?, poster_path=?, thumb_path=? WHERE id=?",
                     (fa, po, th, r["vid"]))
        conn.commit()
        ok += 1
        print(f"    ✅ {Image.open(fa).size}", flush=True)
    except Exception as e:
        print(f"    💥 {type(e).__name__} {e}", flush=True)
    time.sleep(3)

conn.close()
print(f"\n补图完成 {ok}/{len(todo)}")
