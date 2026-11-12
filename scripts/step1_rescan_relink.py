# -*- coding: utf-8 -*-
"""
Step 1: 库检索数据重建
  1. 备份 movies.db
  2. 删除已失效的 local_sources（Z:\影视库 / W:\jellyfin / W:\影视库）
  3. 删除磁盘上已不存在的 local_videos 行
  4. 重扫 X:\jellyfin（严格 Jellyfin 目录 + 宽松文件名兜底）
  5. movies 按 code 重连 local_videos / video_path；失效的断开关联但保留记录
"""
import os
import re
import sys
import shutil
import sqlite3
import datetime

sys.stdout.reconfigure(encoding="utf-8")
ROOT = r"F:\github\MyMovieDB"
BACKEND = ROOT + r"\backend"
sys.path.insert(0, BACKEND)

import database as db          # noqa: E402
import jellyfin as jf          # noqa: E402

X_ROOT = r"X:\jellyfin"
DEAD_SOURCE_IDS = [11, 12, 13]   # Z:\影视库 / W:\jellyfin / W:\影视库

# ── 番号提取（复制 main.py 逻辑 + 无短横线兜底）──────────────────
CODE_RE = re.compile(r"([A-Z]{2,6})-(\d{2,5})")
LOOSE_RE = re.compile(r"([A-Z]{2,6})-?(\d{3,5})")
EXCL_WORDS = ["WEB", "HD", "BD", "720", "1080", "4K", "UHD", "SD"]
SPECIAL = [re.compile(r"(FC2-PPV-\d{5,7})", re.IGNORECASE)]


def extract_code(stem: str):
    up = stem.upper()
    for p in SPECIAL:
        m = p.search(up)
        if m:
            return m.group(1).upper()
    for m in CODE_RE.finditer(up):
        prefix, num = m.groups()
        full = m.group(0)
        pos = up.find(full)
        before = up[:pos] if pos > 0 else ""
        if any(before.endswith(w) for w in EXCL_WORDS):
            continue
        if re.search(r"(\d{2,4})[A-Z]{2,6}$", before):
            continue
        if any(prefix.startswith(w) or prefix.endswith(w) for w in EXCL_WORDS if prefix != w):
            continue
        return f"{prefix}-{num}"
    m = LOOSE_RE.search(up)
    if m:
        prefix, num = m.groups()
        if not prefix.isdigit() and prefix not in EXCL_WORDS:
            return f"{prefix}-{num}"
    return None


def subtitle_from_name(stem: str):
    up = stem.upper()
    # 找番号后剩余的尾部
    m = CODE_RE.search(up)
    if not m:
        return None
    tail = up[m.end():]
    if re.search(r"[-_. ]?UC\b", tail):
        return "bilingual"
    if re.search(r"[-_. ]?C\b", tail):
        return "chinese"
    if re.search(r"[-_. ]?U\b", tail):
        return "english"
    return None


def collect_assets(dir_path, files, code):
    poster = fanart = thumb = nfo = None
    nfo_candidates = []
    code_uc = code.upper()
    for fname in files:
        ext = os.path.splitext(fname)[1].lower()
        stem = os.path.splitext(fname)[0]
        if ext == ".nfo":
            if stem.upper() == code_uc:
                nfo = os.path.join(dir_path, fname)
            else:
                nfo_candidates.append((stem, os.path.join(dir_path, fname)))
        elif ext in jf.IMAGE_EXTENSIONS:
            low = fname.lower()
            if code_uc.lower() in stem.lower() or not poster:
                if "poster" in low or "cover" in low:
                    poster = os.path.join(dir_path, fname)
                elif "fanart" in low or "background" in low or "backdrop" in low:
                    fanart = os.path.join(dir_path, fname)
                elif "thumb" in low:
                    thumb = os.path.join(dir_path, fname)
    if not nfo and nfo_candidates:
        suf = jf.re.compile(r"[-_](C|U|UC|4K|HD|KT|TT)$", jf.re.IGNORECASE)
        for stem, p in nfo_candidates:
            if suf.sub("", stem).upper() == code_uc:
                nfo = p
                break
        if not nfo:
            nfo = nfo_candidates[0][1]
    return nfo, poster, fanart, thumb


def main():
    # 0) 备份
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    src_db = os.path.join(ROOT, "data", "movies.db")
    dst_db = os.path.join(ROOT, "backups", f"movies_step1_{ts}.db")
    shutil.copy2(src_db, dst_db)
    print(f"[备份] {dst_db}")

    # 1) 删除失效源（级联删 local_videos）
    for sid in DEAD_SOURCE_IDS:
        ok = db.delete_local_source(sid)
        print(f"[删除源] id={sid} -> {'OK' if ok else '不存在'}")

    # 2) 清理死 local_videos 行
    conn = db.get_db()
    rows = conn.execute("SELECT id, path FROM local_videos").fetchall()
    dead = [r["id"] for r in rows if not os.path.exists(str(r["path"]))]
    conn.executemany("DELETE FROM local_videos WHERE id = ?", [(i,) for i in dead])
    conn.commit()
    print(f"[清理] local_videos 死记录删除 {len(dead)} 行（剩 {len(rows)-len(dead)}）")

    # 3a) 严格 Jellyfin 结构扫描
    results = jf.scan_jellyfin_directory(X_ROOT)
    handled = set()
    items = []
    for r in results:
        code = db.normalize_code(r["code"])
        items.append((code, r["video_path"], r["nfo_path"], r["poster_file"],
                      r["fanart_file"], r["thumb_file"], r["metadata"]))
        handled.add(r["video_path"].lower())
    print(f"[扫描A] 严格 Jellyfin 目录命中 {len(items)} 个")

    # 3b) 宽松兜底扫描（目录名不是标准番号的）
    loose_count = 0
    for dir_path, _subdirs, files in os.walk(X_ROOT):
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in jf.VIDEO_EXTENSIONS:
                continue
            vpath = os.path.join(dir_path, fname)
            if vpath.lower() in handled:
                continue
            stem = os.path.splitext(fname)[0]
            code = extract_code(stem)
            if not code:
                code = extract_code(os.path.basename(dir_path))
            if not code:
                continue
            code = db.normalize_code(code)
            nfo, poster, fanart, thumb = collect_assets(dir_path, files, code)
            items.append((code, vpath, nfo, poster, fanart, thumb, None))
            handled.add(vpath.lower())
            loose_count += 1
    print(f"[扫描B] 宽松兜底新增 {loose_count} 个（合计 {len(items)}）")

    # 3c) 入库 local_videos + 有 NFO 的走 import_jellyfin_movie
    db_lv = db_scrape = sk_jf = 0
    for code, vpath, nfo, poster, fanart, thumb, metadata in items:
        try:
            data = {
                "source_id": 10,
                "name": os.path.basename(vpath),
                "path": vpath,
                "code": code,
                "extension": os.path.splitext(vpath)[1].lstrip("."),
                "file_size": os.path.getsize(vpath) if os.path.exists(vpath) else 0,
                "fanart_path": fanart,
                "poster_path": poster,
                "thumb_path": thumb,
                "is_jellyfin": 1,
            }
            db.upsert_local_video(data)
            db_lv += 1
            if metadata is not None:
                mid = db.import_jellyfin_movie(code, metadata, vpath, poster, fanart, thumb)
                if mid == 0:
                    sk_jf += 1
                else:
                    db_scrape += 1
        except Exception as e:
            print(f"[入库失败] {code} {vpath}: {e}")
    print(f"[入库] local_videos {db_lv}，jellyfin 导入 movies 新建/更新 {db_scrape}，已存在跳过 {sk_jf}")

    # 3d) 更新源 10 计数
    n10 = conn.execute("SELECT count(*) FROM local_videos WHERE source_id=10").fetchone()[0]
    db.update_local_source_scan(10, n10)
    print(f"[源10] X:\\jellyfin video_count -> {n10}")

    # 4) movies 按 code 重连：先删除无 code 的 candidates
    lv = conn.execute(
        "SELECT id, code, path, is_jellyfin, file_size, movie_id FROM local_videos").fetchall()
    by_code = {}
    for r in lv:
        c = r["code"]
        if not c:
            continue
        by_code.setdefault(c, []).append(r)

    def rank(r):
        return (-(r["is_jellyfin"] or 0), -(r["file_size"] or 0))

    movies = conn.execute(
        "SELECT id, code, video_path, local_video_id, source_type FROM movies").fetchall()
    relinked = already = orphan = kept = 0
    for m in movies:
        code = m["code"]
        cands = by_code.get(code)
        cur_vp = m["video_path"] or ""
        if cands:
            cands.sort(key=rank)
            best = cands[0]
            sub = None
            if os.path.exists(best["path"]):
                sub = subtitle_from_name(os.path.splitext(best["path"])[0])
            if best["path"] != cur_vp:
                loc = str(best["path"])
                so = "jellyfin" if loc.startswith(X_ROOT) else m["source_type"] or "web"
                conn.execute("""
                    UPDATE movies SET video_path=?, local_video_id=?,
                        source_type=?, jellyfin_status='complete',
                        subtitle_type=COALESCE(?, subtitle_type)
                    WHERE id=?""", (loc, best["id"], so, sub, m["id"]))
                relinked += 1
            else:
                if sub and not m["local_video_id"]:
                    conn.execute("UPDATE movies SET local_video_id=? WHERE id=?",
                                 (best["id"], m["id"]))
                already += 1
            # local_videos 侧补 movie_id / scraped
            if not best["movie_id"]:
                conn.execute("UPDATE local_videos SET movie_id=?, scraped=1 WHERE id=?",
                             (m["id"], best["id"]))
        else:
            if cur_vp and not os.path.exists(cur_vp):
                # 断开关联，保留记录
                st = "broken" if (m["source_type"] == "jellyfin") else (m["source_type"] or "web")
                conn.execute("UPDATE movies SET video_path='', local_video_id=NULL WHERE id=?",
                             (m["id"],))
                orphan += 1
            else:
                kept += 1
    conn.commit()

    print(f"\n[重连] movies 换路径 {relinked}，已一致 {already}，无文件断开 {orphan}，无需处理 {kept}")
    n_jf = conn.execute("SELECT count(*) FROM movies WHERE source_type='jellyfin'").fetchone()[0]
    dead_vp = conn.execute(
        "SELECT count(*) FROM movies WHERE video_path!='' AND video_path IS NOT NULL"
    ).fetchone()[0]
    print(f"[现状] source_type=jellyfin: {n_jf}；有 video_path 的 movies: {dead_vp}")
    conn.close()


if __name__ == "__main__":
    main()
