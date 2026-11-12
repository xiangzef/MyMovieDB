# -*- coding: utf-8 -*-
"""给 33 部缺图老片补图：data/covers -> X:\jellyfin 附近 -> 重命名 movie fanart 并复制到 Z:\av 整理目录"""
import os
import re
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"F:\github\MyMovieDB\backend")
import database as db          # noqa: E402
import config as app_cfg       # noqa: E402

ROOT = Path(r"F:\github\MyMovieDB")
X_ROOT = r"X:\jellyfin"
Z_ROOT = r"Z:\av"

conn = db.get_db()
rows = conn.execute("""
    SELECT v.id AS vid, v.code, v.path AS zpath, m.id AS mid,
           m.actors, m.fanart_path, m.organized_path
    FROM local_videos v JOIN movies m ON v.movie_id=m.id
    WHERE v.source_id=14
""").fetchall()

import json


def code_dir_in_covers(code):
    safe = re.sub(r'[<>:"/\\|?*]', "_", code)
    d = Path(app_cfg.COVERS_DIR) / safe
    return d if d.exists() else None


def images_in(dirpath):
    out = {}
    for f in os.listdir(str(dirpath)):
        low = f.lower()
        stem = os.path.splitext(f)[0].lower()
        if not low.endswith((".jpg", ".jpeg", ".png", ".webp")):
            continue
        if "fanart" in low or "back" in stem:
            out.setdefault("fanart", os.path.join(str(dirpath), f))
        elif "poster" in low or "cover" in low:
            out.setdefault("poster", os.path.join(str(dirpath), f))
        elif "thumb" in low:
            out.setdefault("thumb", os.path.join(str(dirpath), f))
    return out


fixed = 0
still = []
for r in rows:
    if r["fanart_path"] and os.path.exists(str(r["fanart_path"])):
        continue  # 图是好的
    code = r["code"]
    # 1) data/covers
    cdir = code_dir_in_covers(code)
    imgs = images_in(cdir) if cdir else {}
    # 2) X:\jellyfin 全盘按番号找（目录越多越慢，只搜一层演员目录下的番号目录）
    if not imgs:
        hit_img = None
        for actor_dir in os.listdir(X_ROOT):
            sub = os.path.join(X_ROOT, actor_dir, code)
            if os.path.isdir(sub):
                imgs = images_in(sub)
                break
    zdir = str(Path(str(r["zpath"])).parent)          # Z:\av\{演员}\{code}
    if not os.path.isdir(zdir):
        zdir = None

    def pick(kind):
        for k in (kind, "fanart", "poster", "thumb"):
            if k in imgs and os.path.exists(imgs[k]):
                return imgs[k]
        return None

    fa = pick("fanart")
    if not fa and imgs:
        fa = pick("poster")
    if not fa and zdir:
        # 目标目录里是否其实已经有图（step3 已复制过就不再算缺）
        if any(os.path.exists(os.path.join(zdir, f"{code}-{k}{s}"))
               for k in ("poster", "fanart") for s in (".jpg", ".png", ".webp")):
            fixed += 1
            continue
    if not fa or not zdir:
        still.append(code)
        continue

    ext = os.path.splitext(fa)[1]
    dst_fanart = os.path.join(zdir, f"{code}-fanart{ext}")
    dst_poster = os.path.join(zdir, f"{code}-poster{ext}")
    try:
        shutil.copy2(fa, dst_fanart)
        shutil.copy2(fa, dst_poster)
        conn.execute("UPDATE movies SET fanart_path=?, poster_path=?, jellyfin_status='complete' WHERE id=?",
                     (dst_fanart, dst_poster, r["mid"]))
        # local_video 也指向新 fanart
        conn.execute("UPDATE local_videos SET fanart_path=? WHERE id=?",
                     (dst_fanart, r["vid"]))
        # 源 movies.fanart_path 更新为新位置
        conn.execute("UPDATE movies SET fanart_path=? WHERE id=?", (dst_fanart, r["mid"]))
        fixed += 1
        print(f"[{code}] <- {fa} -> {zdir}")
    except Exception as e:
        print(f"[{code}] 复制失败 {e}")
        still.append(code)

conn.commit()
print(f"\n补图完成 {fixed},{len(still)} 个仍缺: {still}")
conn.close()
