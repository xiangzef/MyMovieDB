# -*- coding: utf-8 -*-
"""
终轮重试（带耐心）：
  A. 25 部仍缺图 → DMM GraphQL 拿 cover_url → 封面多 host/多路下载 → 更新库+复制到 Z 目录
  B. 4 部未刮削 → DMM GraphQL（重试）→ 入库（后跑 step3 归位）
  C. 7 部 r18dev → DMM cid 反查日文数据 + 封面
  D. SNIS-166 重刮
DMM GraphQL：直连/代理交替，直到命中
"""
import json
import os
import re
import shutil
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
import database as db        # noqa: E402
import scraper               # noqa: E402
import config as app_cfg     # noqa: E402
import enhanced_scraper as es_mod  # noqa: E402
es_mod.translate_to_chinese = lambda *a, **k: None

from salvage_finalize import item_to_movie  # noqa: E402

PROXY = "http://127.0.0.1:7897"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
COVERS = Path(app_cfg.COVERS_DIR)
COVERS.mkdir(parents=True, exist_ok=True)

_LOG = open(ROOT + r"\logs\final_retry.log", "a", encoding="utf-8")


def log(msg):
    print(msg, flush=True)
    _LOG.write(msg + "\n")
    _LOG.flush()


def make_dmm(proxied: bool) -> DmmGraphql:
    class P(DmmGraphql):
        def __init__(self, px):
            self.sess = requests.Session()
            if px:
                self.sess.proxies = {"http": PROXY, "https": PROXY}
            else:
                self.sess.trust_env = False
    return P(proxied)


DMMS = [make_dmm(False), make_dmm(True)]


def dmm_call(fn_name, *args, tries=6, code_hint=""):
    last_err = None
    for t in range(tries):
        obj = DMMS[t % 2]
        try:
            return obj.__getattribute__(fn_name)(*args)
        except Exception as e:
            last_err = type(e).__name__
            time.sleep(4 + 3 * (t + 1))
    log(f"    [dmm 全部失败 {code_hint}] 末次错误: {last_err}")
    return None


def download_jacket(url, tries=4):
    """封面下载：原图 URL 直接下；失败重试（代理/直连交替）"""
    from PIL import Image  # noqa: E402
    for t in range(tries):
        px = t % 2 == 0
        kw = {"proxies": {"http": PROXY, "https": PROXY}} if px else {"trust_env": False}
        try:
            r = requests.get(url, timeout=30, headers={
                "User-Agent": UA, "Referer": "https://www.dmm.co.jp/"}, **kw)
            if r.status_code == 200 and len(r.content) > 8000:
                return Image.open(BytesIO(r.content))
        except Exception as e:
            if t == tries - 1:
                log(f"    [封面] {type(e).__name__}")
        time.sleep(4 + 2 * t)
    return None


def save_img(movie_code, img):
    safe = re.sub(r'[<>:"/\\|?*]', "_", movie_code)
    cdir = COVERS / safe
    cdir.mkdir(parents=True, exist_ok=True)
    fanart = cdir / f"{safe}-fanart.jpg"
    poster = cdir / f"{safe}-poster.jpg"
    img.save(fanart, quality=88)
    w, h = img.size
    # poster 取右半（横图）或原图（竖图）
    if w > h:
        right = img.crop((w - h // 2 + 40 if w - h // 2 > 0 else 0, 0, w, h))
    else:
        right = img
    right.save(poster, quality=88)
    return str(fanart), str(poster)


def install_movies_imgs(mid, vid, fanart, poster):
    conn = db.get_db()
    conn.execute("UPDATE movies SET fanart_path=?, poster_path=?, jellyfin_status='complete' WHERE id=?",
                 (fanart, poster, mid))
    conn.execute("UPDATE movies SET local_cover_path=? WHERE id=?", (fanart, mid))
    # 找 Z 整理目录（local_video 当前 path 的父目录）
    zdir = None
    r = conn.execute("SELECT code, path FROM local_videos WHERE movie_id=?", (mid,)).fetchone()
    if r and r["path"] and os.path.exists(str(r["path"])):
        zdir = str(Path(str(r["path"])).parent)
    conn.commit()
    conn.close()
    if not zdir:
        return
    code = r["code"]
    for kind, p in (("fanart", fanart), ("poster", poster)):
        dst = os.path.join(zdir, f"{code}-{kind}.jpg")
        try:
            shutil.copy2(p, dst)
            log(f"    [{code}] {kind} -> {zdir}")
        except Exception as e:
            log(f"    [{code}] 复制失败 {kind}: {e}")


def md_cover_url(md):
    return (md or {}).get("cover_url") or ""


# ══════ A: 25 部缺图 ══════
A = ['SNIS-896', 'IPX-493', 'SNIS-070', 'SNIS-205', 'SNIS-539', 'SNIS-623',
     'SNIS-752', 'SNIS-918', 'SNIS-939', 'SSIS-124', 'SSIS-241', 'SSIS-541',
     'SSNI-344', 'SSNI-452', 'SSNI-618', 'SSNI-674', 'SSNI-700', 'SSNI-727',
     'SSNI-730', 'SSNI-802', 'SSNI-865', 'SSNI-888', 'SSNI-916', 'SOE-480',
     'SSPD-149']
log("═══ A) 25 部缺图补图 ═══")
n_ok = 0
for i, code in enumerate(A, 1):
    log(f"[{i}/{len(A)}] {code}")
    conn = db.get_db()
    r = conn.execute("SELECT id FROM movies WHERE code=?", (code,)).fetchone()
    conn.close()
    if not r:
        log("    无 movie")
        continue
    mid = r["id"]
    # graphql detail
    from step2_offline_scrape import code_parts
    _, letters, number = code_parts(code)
    cid = f"{letters.lower()}{int(number):05d}"
    item = dmm_call("content", cid, code_hint=code)
    if not item:
        from step2_offline_scrape import matching_cids, _CID_RE  # noqa: E402
        for j in range(2):
            d = dmm_call("graphql",
                         "query S($limit: Int!, $sort: ContentSearchPPVSort!, $queryWord: String)"
                         " { legacySearchPPV(limit: $limit, sort: $sort, queryWord: $queryWord)"
                         " { result { contents { id } } } }",
                         {"limit": 30, "sort": "RELEASE_DATE", "queryWord": f"{letters} {number}"})
            if not d:
                continue
            contents = ((d.get("legacySearchPPV") or {}).get("result") or {}).get("contents") or []
            cids = matching_cids(code, (c.get("id") for c in contents if isinstance(c, dict)))
            for c in cids:
                item = dmm_call("content", c, code_hint=code)
                if item:
                    break
            if item:
                break
    if not item:
        log(f"    {code}: DMM 无数据，跳过")
        continue
    from step2_offline_scrape import dmm_code_to_date
    md = item_to_movie(item, code)
    img = download_jacket(md["cover_url"]) if md["cover_url"] else None
    if img:
        fa, po = save_img(code, img)
        install_movies_imgs(mid, None, fa, po)
        n_ok += 1
        log(f"    ✅ {code} 封面 OK ({img.size[0]}x{img.size[1]})")
    else:
        log(f"    ❌ {code} 封面下载失败 cover={md['cover_url'][:60]}")
    time.sleep(2)
log(f"A 完成: {n_ok}/{len(A)}")

# ══════ B: 4 部未刮削 ══════
log("\n═══ B) 4 部未刮削 ═══")
conn = db.get_db()
for code in ("ADN-151", "AVOP-004", "RBD-916", "SNIS-027"):
    log(f"[{code}]")
    from step2_offline_scrape import code_parts
    if not code_parts(code):
        log("    番号解析失败")
        continue
    _, letters, number = code_parts(code)
    cid = f"{letters.lower()}{int(number):05d}"
    item = dmm_call("content", cid, code_hint=code)
    if not item:
        from step2_offline_scrape import matching_cids
        d = dmm_call("graphql",
                     "query S($limit: Int!, $sort: ContentSearchPPVSort!, $queryWord: String)"
                     " { legacySearchPPV(limit: $limit, sort: $sort, queryWord: $queryWord)"
                     " { result { contents { id } } } }",
                     {"limit": 30, "sort": "RELEASE_DATE", "queryWord": f"{letters} {number}"})
        if d:
            contents = ((d.get("legacySearchPPV") or {}).get("result") or {}).get("contents") or []
            for c in matching_cids(code, (c.get("id") for c in contents if isinstance(c, dict))):
                item = dmm_call("content", c, code_hint=code)
                if item:
                    break
    if not item:
        log("    最终 MISS")
        continue
    from step2_offline_scrape import dmm_code_to_date
    md = item_to_movie(item, code)
    v = conn.execute("SELECT id, path FROM local_videos WHERE source_id=14 AND code=?", (code,)).fetchone()
    img = download_jacket(md["cover_url"]) if md["cover_url"] else None
    if img:
        fa, po = save_img(code, img)
        md["fanart_path"], md["poster_path"] = fa, po
    try:
        movie_id, _ = db.upsert_movie(md)
        db.mark_video_scraped(v["id"], movie_id)
        db.link_movie_to_local_video(movie_id, v["id"])
        log(f"    💾 入库 movie_id={movie_id}")
    except Exception as e:
        log(f"    💥 {type(e).__name__} {e}")
    time.sleep(2)
conn.close()

# ══════ C: 7 部 r18dev 日文化 ══════
log("\n═══ C) 7 部 r18dev 日文化 ═══")
R18_MID = {"SNIS-091": 2456, "SNIS-110": 2457, "SOE-646": 2458,
           "SSPD-142": 2459, "SSPD-144": 2460, "SSPD-157": 2461, "TEK-089": 2462}
salvage = json.loads(Path(ROOT + r"\data\r18dev_salvage.json").read_text(encoding="utf-8"))
conn = db.get_db()
for code, mid in R18_MID.items():
    cid = str((salvage.get(code) or {}).get("content_id") or "")
    item = dmm_call("content", cid, code_hint=code, tries=4)
    if not item:
        log(f"[{code}] 仍无 DMM 日文数据")
        continue
    md = item_to_movie(item, code)
    img = download_jacket(md["cover_url"]) if md["cover_url"] else None
    if img and not (conn.execute("SELECT fanart_path FROM movies WHERE id=?", (mid,)).fetchone()[0]
                    and os.path.exists(conn.execute("SELECT fanart_path FROM movies WHERE id=?", (mid,)).fetchone()[0] or "")):
        fa, po = save_img(code, img)
        md["fanart_path"], md["poster_path"] = fa, po
    try:
        db.update_movie(mid, md)
        conn.execute("UPDATE movies SET cover_url=?, source=NULL WHERE id=?", (md.get("cover_url"), mid))
        if md.get("fanart_path"):
            conn.execute("UPDATE movies SET fanart_path=?, poster_path=? WHERE id=?",
                         (md.get("fanart_path"), md.get("poster_path"), mid))
        conn.commit()
        log(f"    ✅ {code} 日文版: {md['title'][:40]}")
        install_movies_imgs(mid, None, md.get("fanart_path") or "", md.get("poster_path") or "")
    except Exception as e:
        log(f"    💥 {code}: {type(e).__name__} {e}")
    time.sleep(2)
conn.close()

# ══════ D: SNIS-166 ══════
log("\n═══ D) SNIS-166 ═══")
from step2_offline_scrape import code_parts
if code_parts("SNIS-166"):
    item = dmm_call("content", "snis00166", code_hint="SNIS-166", tries=4)
    if item:
        md = item_to_movie(item, "SNIS-166")
        img = download_jacket(md["cover_url"]) if md["cover_url"] else None
        if img:
            fa, po = save_img("SNIS-166", img)
            md["fanart_path"], md["poster_path"] = fa, po
        db.update_movie(1263, md)
        conn = db.get_db()
        conn.execute("UPDATE movies SET actors=?, cover_url=? WHERE id=1263",
                     (json.dumps(md.get("actors") or ["佚名"], ensure_ascii=False), md.get("cover_url")))
        if md.get("fanart_path"):
            conn.execute("UPDATE movies SET fanart_path=?, poster_path=? WHERE id=1263",
                         (md.get("fanart_path"), md.get("poster_path")))
        conn.commit()
        conn.close()
        log(f"    ✅ SNIS-166: {md['title'][:40]} actors={md.get('actors')}")
    else:
        log("    SNIS-166 DMM MISS")
log("\n终轮重试完成")
