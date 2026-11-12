# -*- coding: utf-8 -*-
"""SNIS-939 换高清封面（要求 > 600px 宽）"""
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
ROOT = r"F:\github\MyMovieDB"
sys.path.insert(0, ROOT + r"\backend")
for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
    os.environ.pop(k, None)

import requests  # noqa: E402
from PIL import Image          # noqa: E402
from io import BytesIO
import database as db          # noqa: E402

CODE = "SNIS-939"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
PROXY = {"http": "http://127.0.0.1:7897", "https": "http://127.0.0.1:7897"}
letters, number = CODE.split("-")
cid = f"{letters.lower()}{int(number):05d}"
URLS = [
    f"https://awsimgsrc.dmm.co.jp/pics_dig/digital/video/{cid}/{cid}pl.jpg",
    f"https://pics.dmm.co.jp/digital/video/{cid}/{cid}pl.jpg",
    f"https://awsimgsrc.dmm.co.jp/pics_dig/digital/video/{cid}/{cid}pl.jpg?x=1",
]
conn = db.get_db()
r = conn.execute("""SELECT v.id AS vid, m.id AS mid, m.organized_path
                    FROM local_videos v JOIN movies m ON v.movie_id=m.id
                    WHERE v.source_id=14 AND v.code=?""", (CODE,)).fetchone()
folder = str(r["organized_path"])
base = os.path.basename(folder)

for url in URLS:
    for mode in ("direct", "proxy", "direct", "proxy"):
        try:
            kw = {"trust_env": False} if mode == "direct" else {"proxies": PROXY}
            rr = requests.get(url, timeout=60, headers={
                "User-Agent": UA, "Referer": "https://www.dmm.co.jp/"}, **kw)
            if rr.status_code == 200 and len(rr.content) > 8000:
                img = Image.open(BytesIO(rr.content)).convert("RGB")
                if img.size[0] < 600:
                    print(f"  小图 {img.size}，跳过")
                    continue
                w, h = img.size
                img.save(os.path.join(folder, base + "-fanart.jpg"), quality=92)
                pw = int(h * 2 / 3)
                p = img.crop((w - pw, 0, w, h)) if pw < w else img
                p.resize((1000, 1500), Image.Resampling.LANCZOS).save(
                    os.path.join(folder, base + "-poster.jpg"), quality=92)
                p.resize((300, 450), Image.Resampling.LANCZOS).save(
                    os.path.join(folder, base + "-thumb.jpg"), quality=90)
                print(f"   ✅ {img.size} <- {url.split('/')[2]} ({mode})")
                conn.execute("""UPDATE movies SET fanart_path=?, poster_path=?, thumb_path=?,
                                local_cover_path=? WHERE id=?""",
                             (os.path.join(folder, base + "-fanart.jpg"),
                              os.path.join(folder, base + "-poster.jpg"),
                              os.path.join(folder, base + "-thumb.jpg"),
                              os.path.join(folder, base + "-fanart.jpg"), r["mid"]))
                conn.execute("""UPDATE local_videos SET fanart_path=?, poster_path=?, thumb_path=?
                                WHERE id=?""",
                             (os.path.join(folder, base + "-fanart.jpg"),
                              os.path.join(folder, base + "-poster.jpg"),
                              os.path.join(folder, base + "-thumb.jpg"), r["vid"]))
                conn.commit()
                conn.close()
                sys.exit(0)
        except Exception as e:
            pass
        time.sleep(2)
print("   ❌ 未取到高清图")
conn.close()
