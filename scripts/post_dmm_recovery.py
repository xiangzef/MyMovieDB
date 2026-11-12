# -*- coding: utf-8 -*-
"""
DMM 经代理恢复后的收尾批：
  1. 32 部缺图老片 → DMM GraphQL → save_movie_assets 下载封面 → 复制进 Z:\av 整理目录
  2. 4 部未刮削（ADN-151/AVOP-004/RBD-916/SNIS-027）→ DMM → 入库（之后逐次跑 step3 归位）
  3. 7 部 r18dev → DMM cid 反查日文版 + 封面
  4. SNIS-166 垃圾记录 → DMM 重刮
全程走代理 127.0.0.1:7897
"""
import json
import os
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = r"F:\github\MyMovieDB"
sys.path.insert(0, ROOT + r"\backend")
sys.path.insert(0, ROOT + r"\scripts")

os.environ["HTTP_PROXY"] = "http://127.0.0.1:7897"
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7897"
os.environ["NO_PROXY"] = ""

import database as db        # noqa: E402
import scraper               # noqa: E402
import config as app_cfg     # noqa: E402
import enhanced_scraper as es_mod  # noqa: E402
from step2_offline_scrape import DmmGraphql   # noqa: E402
es_mod.translate_to_chinese = lambda *a, **k: None
dmm = DmmGraphql()
dmm.sess = __import__("requests").Session()
dmm.sess.trust_env = True          # 让它也走代理

COVERS = Path(app_cfg.COVERS_DIR)
COVERS.mkdir(parents=True, exist_ok=True)


def dmm_scrape(code, tries=3):
    for t in range(tries):
        try:
            md = dmm.scrape(code)
            return md
        except Exception as e:
            print(f"    [dmm {t+1}/{tries}] {type(e).__name__}")
            time.sleep(6 * (t + 1))
    return None


def copy_imgs_to_zdir(mid, vid=None):
    """movies 图齐了之后，复制进它 Z:\av 的整理目录（若无则跳过）"""
    conn = db.get_db()
    r = conn.execute("""
        SELECT v.code, m.fanart_path, m.poster_path, m.thumb_path, v.id,
               m.organized_path
        FROM movies m JOIN local_videos v ON v.movie_id=m.id
        WHERE m.id=?
    """, (mid,)).fetchone()
    conn.close()
    if not r:
        return
    import shutil, re
    code = r["code"]
    zdir = r["organized_path"] or str(Path(r["fanart_path"]).parent.parent) \
        if r["fanart_path"] else None
    # 更稳妥：local_video 当前 path 的父目录
    if vid:
        conn = db.get_db()
        p = conn.execute("SELECT path FROM local_videos WHERE id=?", (vid,)).fetchone()
        conn.close()
        if p:
            zdir = str(Path(str(p["path"])).parent)
    if not zdir or not os.path.isdir(zdir):
        print(f"    [{code}] 无 Z 目录，仅存库")
        return
    safe = re.sub(r'[<>:"/\\|?*]', "_", code)
    for kind in ("fanart", "poster", "thumb"):
        p = r[kind + "_path"] if kind != "thumb" else r["thumb_path"]
        if not p or not os.path.exists(str(p)):
            continue
        dst = os.path.join(zdir, f"{code}-{kind}" + os.path.splitext(str(p))[1])
        try:
            shutil.copy2(str(p), dst)
        except Exception as e:
            print(f"    [{code}] 复制失败 {kind}: {e}")


MISSING = ['SNIS-896', 'SSIS-338', 'SSNI-644', 'SSNI-780', 'IPX-493', 'SNIS-070',
           'SNIS-205', 'SNIS-539', 'SNIS-623', 'SNIS-692', 'SNIS-752', 'SNIS-918',
           'SNIS-939', 'SSIS-037', 'SSIS-088', 'SSIS-124', 'SSIS-241', 'SSIS-541',
           'SSNI-344', 'SSNI-452', 'SSNI-542', 'SSNI-618', 'SSNI-674', 'SSNI-700',
           'SSNI-727', 'SSNI-730', 'SSNI-802', 'SSNI-865', 'SSNI-888', 'SSNI-916',
           'SSNI-939', 'SOE-480', 'SSPD-149',
           ]
MISSING = [c for c in MISSING if c]

conn = db.get_db()
print("═══ 1) 33 部缺图老片补图 ═══")
for i, code in enumerate(MISSING, 1):
    print(f"[{i}/{len(MISSING)}] {code}", flush=True)
    r = conn.execute("SELECT id FROM movies WHERE code=?", (code,)).fetchone()
    if not r:
        print("    无 movie，跳过")
        continue
    mid = r["id"]
    md = dmm_scrape(code)
    if not md:
        print("    DMM MISS")
        continue
    try:
        md = scraper.save_movie_assets(md, COVERS, None)
        conn = db.open_db if False else db.get_db()
        conn.execute("""UPDATE movies SET fanart_path=?, poster_path=?, thumb_path=?,
                        cover_url=?, jellyfin_status='complete' WHERE id=?""",
                     (md.get("fanart_path"), md.get("poster_path"), md.get("thumb_path"),
                      md.get("cover_url"), mid))
        # local_cover_path 也顺手
        conn.execute("UPDATE movies SET local_cover_path=? WHERE id=?", (md.get("fanart_path"), mid))
        conn.commit()
        copy_imgs_to_zdir(mid)
        print(f"    ✅ mid={mid} fanart={str(md.get('fanart_path'))[-40:]}")
    except Exception as e:
        import traceback
        print(f"    💥 {type(e).__name__} {e}")
        traceback.print_exc(limit=2)
        conn = db.get_db()
    time.sleep(2)
conn.close()

print("\n═══ 2) 4 部未刮削 ═══")
conn = db.get_db()
for code in ("ADN-151", "AVOP-004", "RBD-916", "SNIS-027"):
    print(f"[{code}]", flush=True)
    md = dmm_scrape(code)
    if not md:
        print("    DMM MISS（仍留根目录）")
        continue
    v = conn.execute("SELECT id, path FROM local_videos WHERE source_id=14 AND code=?", (code,)).fetchone()
    try:
        md = scraper.save_movie_assets(md, COVERS, str(v["path"]))
        movie_id, _ = db.upsert_movie(md)
        db.mark_video_scraped(v["id"], movie_id)
        db.link_movie_to_local_video(movie_id, v["id"])
        print(f"    💾 入库 movie_id={movie_id}")
    except Exception as e:
        print(f"    💥 {type(e).__name__} {e}")
    time.sleep(2)
conn.close()

print("\n═══ 3) 7 部 r18dev 日文化 ═══")
R18_MID = {"SNIS-091": 2456, "SNIS-110": 2457, "SOE-646": 2458,
           "SSPD-142": 2459, "SSPD-144": 2460, "SSPD-157": 2461, "TEK-089": 2462}
salvage = json.loads(Path(ROOT + r"\data\r18dev_salvage.json").read_text(encoding="utf-8"))
from salvage_finalize import item_to_movie  # noqa: E402

conn = db.get_db()
for code, mid in R18_MID.items():
    cid = str((salvage.get(code) or {}).get("content_id") or "")
    print(f"[{code}] cid={cid}", flush=True)
    try:
        item = dmm.content(cid) if cid else None
    except Exception as e:
        item = None
        print(f"    [dmm] {type(e).__name__}")
    if not item:
        print("    仍无 DMM 数据")
        time.sleep(2)
        continue
    md = item_to_movie(item, code)
    try:
        md = scraper.save_movie_assets(md, COVERS, None)
        db.update_movie(mid, md)
        conn.execute("UPDATE movies SET cover_url=?, source=NULL WHERE id=?", (md.get("cover_url"), mid))
        conn.commit()
        copy_imgs_to_zdir(mid)
        print(f"    ✅ 日文版: {md['title'][:40]}")
    except Exception as e:
        print(f"    💥 {type(e).__name__} {e}")
    time.sleep(2)
conn.close()

print("\n═══ 4) SNIS-166 重刮 ═══")
conn = db.get_db()
md = dmm_scrape("SNIS-166")
if md:
    md = scraper.save_movie_assets(md, COVERS, None)
    db.update_movie(1263, md)
    conn.execute("UPDATE movies SET cover_url=? WHERE id=1263", (md.get("cover_url"),))
    conn.commit()
    conn.execute("UPDATE movies SET actors=? WHERE id=1263",
                 (json.dumps(md.get("actors") or ["佚名"], ensure_ascii=False),))
    conn.commit()
    print(f"    ✅ SNIS-166: {md['title'][:40]} actors={md.get('actors')}")
    # 若演员变了， Step3 需要重跑修剪（先记住，主脚本提示手动跑）
else:
    print("    DMM MISS")
conn.close()
print("\n收尾批完成")
