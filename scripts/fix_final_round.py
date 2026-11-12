# -*- coding: utf-8 -*-
"""最终修复轮：r18dev 7 部换日文/补封面（带重试），剩余 4 部 javarchive 兜底"""
import json
import re
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = r"F:\github\MyMovieDB"
sys.path.insert(0, ROOT + r"\backend")
sys.path.insert(0, ROOT + r"\scripts")

import requests  # noqa: E402
import database as db        # noqa: E402
import scraper               # noqa: E402
import config as app_cfg     # noqa: E402
from step2_offline_scrape import DmmGraphql   # noqa: E402
from salvage_finalize import item_to_movie, r18dev_to_movie   # noqa: E402
import enhanced_scraper as es_mod  # noqa: E402
es_mod.translate_to_chinese = lambda *a, **k: None

dmm = DmmGraphql()
salvage = json.loads(Path(ROOT + r"\data\r18dev_salvage.json").read_text(encoding="utf-8"))
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def dmm_try(cid):
    for attempt in range(3):
        try:
            return dmm.content(cid)
        except Exception as e:
            print(f"    [dmm {attempt+1}/3] {type(e).__name__}", flush=True)
            time.sleep(6 * (attempt + 1))
    return None


def download_cover_with_retry(url, tries=3):
    for t in range(tries):
        try:
            r = requests.get(url, timeout=25, headers={
                "User-Agent": UA, "Referer": "https://www.dmm.co.jp/"})
            if r.status_code == 200 and len(r.content) > 8000:
                return r.content
        except Exception as e:
            print(f"    [cover {t+1}/{tries}] {type(e).__name__}")
        time.sleep(5 * (t + 1))
    return None


# ── A: r18dev 7 部日文化 + 封面 ─────────────────────────────
R18_MOVIE_IDS = {"SNIS-091": 2456, "SNIS-110": 2457, "SOE-646": 2458,
                 "SSPD-142": 2459, "SSPD-144": 2460, "SSPD-157": 2461, "TEK-089": 2462}
conn = db.get_db()
japanese_fixed = cover_fixed = 0
for code, mid in R18_MOVIE_IDS.items():
    rec = salvage[code]
    cid = str(rec.get("content_id") or "")
    md = None
    item = dmm_try(cid) if cid else None
    if item:
        md = item_to_movie(item, code)
        print(f"[{code}] ✅ DMM 日文版: {md['title'][:45]}", flush=True)
    else:
        md = r18dev_to_movie(rec, code)
        j = (rec.get("images") or {}).get("jacket_image") or {}
        md["cover_url"] = str(j.get("large2") or j.get("large") or "").strip()
        print(f"[{code}] r18dev 英文版（封面 {md['cover_url'][:45]}）", flush=True)

    # 封面下载（带重试；已有 fanart 则跳过）
    has_cover = False
    cur = conn.execute("SELECT fanart_path FROM movies WHERE id=?", (mid,)).fetchone()
    if cur and cur["fanart_path"] and Path(str(cur["fanart_path"])).exists():
        has_cover = True
    if md["cover_url"] and not has_cover:
        from PIL import Image   # noqa: E402
        from io import BytesIO
        data = download_cover_with_retry(md["cover_url"])
        if data:
            import re as _re
            safe_code = _re.sub(r'[<>:"/\\|?*]', '_', code)
            cdir = Path(app_cfg.COVERS_DIR) / safe_code
            cdir.mkdir(parents=True, exist_ok=True)
            try:
                img = Image.open(BytesIO(data))
                w, h = img.size
                fanart = cdir / f"{safe_code}-fanart.jpg"
                img.save(fanart, quality=88)
                # poster 右半裁切
                if w >= 750 and h / 2 >= 300:
                    import copy
                    right = img.crop((w - h // 2 + 75 if w > h else 0, 0, w, h))
                    right.save(cdir / f"{safe_code}-poster.jpg", quality=88)
                conn.execute("UPDATE movies SET fanart_path=?, poster_path=COALESCE("
                             "(SELECT poster_path FROM movies WHERE id=?), ?) WHERE id=?",
                             (str(fanart), mid, str(cdir / f"{safe_code}-poster.jpg"), mid))
                cover_fixed += 1
                md["fanart_path"] = str(fanart)
            except Exception as e:
                print(f"    [图片处理] {type(e).__name__} {e}")

    if item:
        db.update_movie(mid, md)
        conn.execute("UPDATE movies SET cover_url=? WHERE id=?", (md.get("cover_url"), mid))
        japanese_fixed += 1
        print(f"    💾 movie_id={mid} 日文元数据已更新")
    elif md.get("fanart_path"):
        conn.execute("UPDATE movies SET fanart_path=?, poster_path=? WHERE id=?",
                     (md.get("fanart_path"), md.get("poster_path"), mid))
    conn.commit()
conn.close()
print(f"\n[r18dev 修复] 日文化 {japanese_fixed}/7，补封面 {cover_fixed}/7")

# ── B: 剩余 4 部 — javarchive.com 兜底 ──────────────────────
def javarchive(code):
    letters, number = code.split("-")
    cid = f"{letters.lower()}{int(number):05d}"
    sess = requests.Session()
    sess.trust_env = False
    try:
        r = sess.get(f"https://javarchive.com/search?q={cid}", headers={"User-Agent": UA}, timeout=25)
        if r.status_code != 200:
            return None
        links = list(dict.fromkeys(re.findall(r'href="(/\d+-[^"]+\.html)"', r.text)))
        target = [l for l in links if cid in l]
        if not target:
            return None
        r2 = sess.get("https://javarchive.com" + target[0], headers={"User-Agent": UA}, timeout=25)
        if r2.status_code != 200:
            return None
        html = r2.text
        m = re.search(r"<title>([^<]+)</title>", html)
        title_raw = m.group(1) if m else ""
        title = re.sub(r"\s*\|.+$", "", title_raw).strip()
        cover = None
        for m in re.finditer(r'<img[^>]+src="(http[^"]+(?:\.jpg|\.png))"', html):
            src = m.group(1)
            if "javstore" in src or "poster" in src or re.search(r"\d{5,}w?", src):
                cover = src
                break
        if not cover:
            for pat in (f"{cid}pl", f"{cid}ps", cid):
                m = re.search(rf'(http[^"]+/{re.escape(pat)}[^"]*\.(?:jpg|png))', html)
                if m:
                    cover = m.group(1)
                    break
        if not cover:
            return None
        dm = re.search(r"时长\s*[:：]\s*([0-9:]+)", html)
        dur = None
        if dm and ":" in dm.group(1):
            parts = [int(x) for x in dm.group(1).split(":")]
            dur = parts[0] * 60 + parts[1] if len(parts) == 2 else parts[0]
        da = re.search(r"日期\s*[:：]\s*(\d{4})/(\d{2})/(\d{2})", html)
        rd = f"{da.group(1)}-{da.group(2)}-{da.group(3)}" if da else None
        actors = []
        for m in re.finditer(r"/(?:actress|search)/[^\"'>]*>([^<>]+)</a>", html):
            name = m.group(1).strip()
            if name and not name.isdigit() and name not in actors and len(name) < 40:
                actors.append(name)
        return {
            "code": code, "title": title or code, "title_jp": title or code,
            "plot": None, "release_date": rd, "duration": dur,
            "studio": None, "maker": None, "director": None, "series": None,
            "genres": [], "actors": actors[:8], "actors_male": [],
            "cover_url": cover, "detail_url": "https://javarchive.com" + target[0],
            "source": "javarchive", "scrape_status": "complete",
        }
    except Exception as e:
        print(f"    [javarchive] {type(e).__name__}")
        return None


conn = db.get_db()
for code in ["ADN-151", "AVOP-004", "RBD-916", "SNIS-027"]:
    print(f"\n[{code}] javarchive ...", flush=True)
    md = None
    # 先再试一次 DMM（网络可能恢复）
    _, letters, number = code.split("-")[0], code.split("-")[0], code.split("-")[1]
    cid = f"{letters.lower()}{int(number):05d}"
    item = dmm_try(cid)
    if item:
        md = item_to_movie(item, code)
        print(f"    dmm-graphql OK: {md['title'][:40]}")
    if not md:
        md = javarchive(code)
        if md:
            print(f"    javarchive OK: {md['title'][:40]} cover={md['cover_url'][:50]}")
    if not md:
        print("    仍 MISS")
        continue
    v = conn.execute("SELECT id, path FROM local_videos WHERE source_id=14 AND code=?", (code,)).fetchone()
    try:
        covers_dir = Path(app_cfg.COVERS_DIR)
        md = scraper.save_movie_assets(md, covers_dir, str(v["path"]))
        movie_id, _ = db.upsert_movie(md)
        db.mark_video_scraped(v["id"], movie_id)
        db.link_movie_to_local_video(movie_id, v["id"])
        print(f"    💾 入库 movie_id={movie_id}")
    except Exception as e:
        print(f"    💥 {type(e).__name__} {e}")
    time.sleep(2)
conn.close()
print("\n最终修复轮完成")
