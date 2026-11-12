# -*- coding: utf-8 -*-
"""
把用户手工命名的 5 部（含 SSNI-473 新增）连同封面页入库：
  - 修正 local_videos 路径（磁盘上已被用户改名）
  - 建/更新 movies：title / actors / 封面
  - 生成 NFO（含 LTX + 破解 标签）
"""
import json
import os
import re
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = r"F:\github\MyMovieDB"
sys.path.insert(0, ROOT + r"\backend")
import database as db          # noqa: E402
import config as app_cfg       # noqa: E402
import scraper as sc           # noqa: E402
from step3_organize_ltx import inject_ltx_tags   # noqa: E402

Z_ROOT = r"Z:\av"
COVERS = Path(app_cfg.COVERS_DIR)

# code: (标题, 女优)
MANUAL = {
    "ADN-151":  ("未亡人アパート 今宵かぎりは…", "松下紗栄子"),
    "AVOP-004": ("迫力映像V 乳・尻・結合が目前に迫る徹底アングル", "宇都宮しをん"),
    "RBD-916":  ("新奴隷捜査官6", "松下紗栄子"),
    "SNIS-027": ("宇都宮しをん、イキます。", "宇都宮しをん"),
    "SSNI-473": ("人生初！絶頂ポルチオ開発プレス 膣中イキオーガズム", "三上悠亜"),
}

VIDEO_EXT = (".mp4", ".mkv", ".avi", ".wmv", ".ts", ".mov", ".rmvb", ".m2ts")

root_files = os.listdir(Z_ROOT)


def find_video(code):
    cands = [f for f in root_files
             if f.upper().startswith(code.upper()) and f.lower().endswith(VIDEO_EXT)]
    if not cands:
        cands = [f for f in root_files if code.upper() in f.upper() and f.lower().endswith(VIDEO_EXT)]
    return os.path.join(Z_ROOT, cands[0]) if cands else None


def find_jpg(code):
    cands = [f for f in root_files
             if f.upper().startswith(code.upper()) and f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))]
    return os.path.join(Z_ROOT, cands[0]) if cands else None


def make_images(code, src_jpg):
    from PIL import Image
    safe = re.sub(r'[<>:"/\\|?*]', "_", code)
    cdir = COVERS / safe
    cdir.mkdir(parents=True, exist_ok=True)
    img = Image.open(src_jpg).convert("RGB")
    w, h = img.size
    # fanart = 原图
    fanart = cdir / f"{safe}-fanart.jpg"
    img.save(fanart, quality=92)
    # poster = 右侧 2:3 裁切
    pw = int(h * 2 / 3)
    if pw < w:
        poster_img = img.crop((w - pw, 0, w, h))
    else:
        poster_img = img
    poster = cdir / f"{safe}-poster.jpg"
    poster_img.resize((1000, 1500), Image.Resampling.LANCZOS).save(poster, quality=92)
    thumb = cdir / f"{safe}-thumb.jpg"
    poster_img.resize((300, 450), Image.Resampling.LANCZOS).save(thumb, quality=90)
    return str(fanart), str(poster), str(thumb)


conn = db.get_db()
for code, (title, actress) in MANUAL.items():
    print(f"\n=== {code} ===")
    vpath = find_video(code)
    if not vpath:
        print("  ❌ 找不到视频文件")
        continue
    stem = Path(vpath).stem
    ext = Path(vpath).suffix.lstrip(".")
    size = os.path.getsize(vpath)
    print(f"  视频: {os.path.basename(vpath)}")

    # 1) local_videos
    row = conn.execute("SELECT id FROM local_videos WHERE code=? AND source_id=14",
                       (code,)).fetchone()
    if row:
        conn.execute("""UPDATE local_videos SET path=?, name=?, extension=?, file_size=?,
                        scraped=0, movie_id=NULL, updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                     (vpath, os.path.basename(vpath), ext, size, row["id"]))
        vid = row["id"]
        print(f"  更新 local_video id={vid}")
    else:
        vid, _ = db.upsert_local_video({
            "source_id": 14, "name": os.path.basename(vpath), "path": vpath,
            "code": code, "extension": ext, "file_size": size, "is_jellyfin": 0,
        })
        print(f"  新建 local_video id={vid}")
    conn.commit()

    # 2) 封面
    jpg = find_jpg(code)
    fanart = poster = thumb = None
    if jpg:
        fanart, poster, thumb = make_images(code, jpg)
        print(f"  封面: {os.path.basename(jpg)} -> fanart/poster/thumb")
    else:
        print("  ⚠️ 无封面图")

    # 3) movies
    md = {
        "code": code,
        "title": title,
        "title_jp": title,
        "title_cn": None,
        "plot": None,
        "actors": [actress],
        "actors_male": [],
        "genres": ["LTX", "破解"],
        "cover_url": None,
        "detail_url": None,
        "source": "manual",
        "scrape_status": "complete",
        "fanart_path": fanart,
        "poster_path": poster,
        "thumb_path": thumb,
        "local_cover_path": fanart,
    }
    mid, is_new = db.upsert_movie(md)
    conn.execute("""UPDATE movies SET actors=?, title=?, title_jp=?, genres=?,
                    fanart_path=?, poster_path=?, thumb_path=?, local_cover_path=?,
                    source_type='jellyfin', subtitle_type='none' WHERE id=?""",
                 (json.dumps([actress], ensure_ascii=False), title, title,
                  json.dumps(["LTX", "破解"], ensure_ascii=False),
                  fanart, poster, thumb, fanart, mid))
    conn.execute("UPDATE local_videos SET movie_id=?, scraped=1 WHERE id=?", (mid, vid))
    conn.commit()
    print(f"  movies id={mid}（{'新建' if is_new else '更新'}）演员={actress}")

    # 4) NFO（先放在 covers 目录，整理脚本负责搬进 Z 目录并改名）
    nfo = COVERS / re.sub(r'[<>:"/\\|?*]', "_", code) / f"{re.sub(r'[<>:\"/\\\\|?*]', '_', code)}.nfo"
    md2 = dict(md)
    sc.generate_nfo(md2, nfo, vpath)
    inject_ltx_tags(str(nfo))
    print(f"  NFO: {nfo}")

conn.close()
print("\n5 部入库完成")
