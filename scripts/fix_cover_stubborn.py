# -*- coding: utf-8 -*-
"""6 部顽固缺图：多图床 × 多路径 × 直连/代理，长超时重试"""
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

CODES = ["SNIS-205", "SNIS-918", "SNIS-939", "SSIS-541", "SSNI-618", "SSNI-730"]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
PROXY = {"http": "http://127.0.0.1:7897", "https": "http://127.0.0.1:7897"}


def urls_for(code):
    letters, number = code.split("-")
    cid = f"{letters.lower()}{int(number):05d}"
    return [
        f"https://awsimgsrc.dmm.co.jp/pics_dig/digital/video/{cid}/{cid}pl.jpg",
        f"https://pics.dmm.co.jp/digital/video/{cid}/{cid}pl.jpg",
        f"https://pics.dmm.co.jp/mono/movie/adult/{cid}/{cid}pl.jpg",
        f"https://awsimgsrc.dmm.co.jp/pics_dig/digital/video/{cid}/{cid}ps.jpg",
        f"https://pics.dmm.co.jp/digital/video/{cid}/{cid}ps.jpg",
    ]


def fetch(url):
    for mode in ("direct", "proxy", "direct"):
        try:
            kw = {"trust_env": False} if mode == "direct" else {"proxies": PROXY}
            r = requests.get(url, timeout=45, headers={
                "User-Agent": UA, "Referer": "https://www.dmm.co.jp/",
                "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8"}, **kw)
            if r.status_code == 200 and len(r.content) > 6000:
                return r.content
        except Exception:
            pass
        time.sleep(2)
    return None


def save(folder, base, data):
    img = Image.open(BytesIO(data)).convert("RGB")
    w, h = img.size
    img.save(os.path.join(folder, base + "-fanart.jpg"), quality=92)
    pw = int(h * 2 / 3)
    p = img.crop((w - pw, 0, w, h)) if pw < w else img
    p.resize((1000, 1500), Image.Resampling.LANCZOS).save(
        os.path.join(folder, base + "-poster.jpg"), quality=92)
    p.resize((300, 450), Image.Resampling.LANCZOS).save(
        os.path.join(folder, base + "-thumb.jpg"), quality=90)


conn = db.get_db()
for code in CODES:
    r = conn.execute("""
        SELECT v.id AS vid, m.id AS mid, m.organized_path,
               substr(m.organized_path, length(m.organized_path) - 200) AS _x
        FROM local_videos v JOIN movies m ON v.movie_id=m.id
        WHERE v.source_id=14 AND v.code=?
    """, (code,)).fetchone()
    if not r:
        print(code, "无记录")
        continue
    folder = str(r["organized_path"])
    base = os.path.basename(folder)
    print(f"[{code}] {base[:50]}")
    done = False
    for url in urls_for(code):
        data = fetch(url)
        if data:
            try:
                save(folder, base, data)
                conn.execute("""UPDATE movies SET fanart_path=?, poster_path=?, thumb_path=?,
                                local_cover_path=?, jellyfin_status='complete' WHERE id=?""",
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
                print(f"   ✅ {Image.open(os.path.join(folder, base + '-fanart.jpg')).size} <- {url.split('/')[2]}")
                done = True
                break
            except Exception as e:
                print(f"   处理失败 {type(e).__name__} {e}")
    if not done:
        print("   ❌ 全部失败")
    time.sleep(3)
conn.close()
print("完成")
