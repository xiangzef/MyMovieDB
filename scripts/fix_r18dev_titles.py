# -*- coding: utf-8 -*-
"""
修复 r18dev 补刮的 7 部（movie_id 2456-2462）：
  1. 优先用 content_id 回查 DMM GraphQL 换成日文全量数据 + 重新下载封面
  2. 失败则用 r18dev images.jacket_image.large2 补封面
再战剩余 4 部（ADN-151/AVOP-004/RBD-916/SNIS-027）
"""
import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = r"F:\github\MyMovieDB"
sys.path.insert(0, ROOT + r"\backend")
sys.path.insert(0, ROOT + r"\scripts")

import database as db        # noqa: E402
import scraper               # noqa: E402
import config as app_cfg     # noqa: E402
from step2_offline_scrape import DmmGraphql   # noqa: E402
from salvage_finalize import (item_to_movie, r18dev_to_movie,   # noqa: E402
                              try_dmm_harder, jav321_proxy)
import enhanced_scraper as es_mod  # noqa: E402
es_mod.translate_to_chinese = lambda *a, **k: None

dmm = DmmGraphql()
salvage = json.loads(Path(ROOT + r"\data\r18dev_salvage.json").read_text(encoding="utf-8"))
conn = db.get_db()


def dmm_content_safe(cid):
    for _ in range(2):
        try:
            return dmm.content(cid)
        except Exception as e:
            print(f"    [dmm] {type(e).__name__}，等 5s 重试")
            time.sleep(5)
    return None


# ── A: 修复 7 部 r18dev ─────────────────────────────────────
R18_MOVIE_IDS = {"SNIS-091": 2456, "SNIS-110": 2457, "SOE-646": 2458,
                 "SSPD-142": 2459, "SSPD-144": 2460, "SSPD-157": 2461, "TEK-089": 2462}
for code, mid in R18_MOVIE_IDS.items():
    rec = salvage[code]
    cid = str(rec.get("content_id") or "")
    item = dmm_content_safe(cid) if cid else None
    if item:
        md = item_to_movie(item, code)
        print(f"[{code}] DMM 日文版: {md['title'][:40]}")
    else:
        md = r18dev_to_movie(rec, code)
        img = rec.get("images") or {}
        j = img.get("jacket_image") or {}
        cover = j.get("large2") or j.get("large") or ""
        md["cover_url"] = str(cover).strip()
        print(f"[{code}] r18dev(补封面 {md['cover_url'][:45]})")
    conn.close()
    tmp = db.get_db()   # save_movie_assets/upsert 独立连接，先借它写
    conn = tmp
    try:
        covers_dir = Path(app_cfg.COVERS_DIR)
        md = scraper.save_movie_assets(md, covers_dir, None)
        db.update_movie(mid, md)
        conn.execute("UPDATE movies SET cover_url=? WHERE id=?", (md.get("cover_url"), mid))
        if md.get("fanart_path"):
            conn.execute("UPDATE movies SET fanart_path=?, poster_path=?, thumb_path=? WHERE id=?",
                         (md.get("fanart_path"), md.get("poster_path"), md.get("thumb_path"), mid))
        conn.commit()
        print(f"    ✅ movie_id={mid} 已更新 fanart={md.get('fanart_path')}")
    except Exception as e:
        print(f"    💥 {code}: {type(e).__name__} {e}")

# ── B: 再战剩余 4 部 ───────────────────────────────────────
for code in ["ADN-151", "AVOP-004", "RBD-916", "SNIS-027"]:
    print(f"\n[{code}] ...", flush=True)
    md = try_dmm_harder(code)
    if not md:
        md = jav321_proxy(code)
    if not md:
        print("    仍 MISS")
        continue
    print(f"    命中 ({md.get('source')}): {str(md.get('title'))[:40]}")
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
print("\n修复轮完成")
