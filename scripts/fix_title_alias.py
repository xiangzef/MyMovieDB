# -*- coding: utf-8 -*-
"""
收尾 A：把标题尾部残留的旧艺名（RION / Shion Utsunomiya / 宇都宮しをん 等）从
目录名/文件名里去掉，并同步改名磁盘 + DB。
"""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = r"F:\github\MyMovieDB"
sys.path.insert(0, ROOT + r"\backend")
import database as db  # noqa: E402

Z_ROOT = r"Z:\av"
INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
ALIASES = ["Shion Utsunomiya", "shion utsunomiya", "RION", "rion",
           "宇都宮しをん", "安齋らら"]
VIDEO_EXT = (".mp4", ".mkv", ".avi", ".wmv", ".ts", ".mov", ".rmvb", ".m2ts")


def clean_name(s, cap=None):
    s = INVALID.sub("_", str(s or ""))
    s = re.sub(r"\s+", " ", s).strip(" .")
    if cap and len(s) > cap:
        s = s[:cap].rstrip(" .")
    return s


def actor_list(raw):
    try:
        v = json.loads(raw) if raw else []
        if isinstance(v, str):
            v = [v]
        return [str(x).strip() for x in v if str(x).strip()]
    except Exception:
        return []


def strip_alias(t, actress):
    t = t.strip()
    names = [actress] + ALIASES
    changed = True
    while changed:
        changed = False
        for a in names:
            if a and t.endswith(a):
                t = t[: -len(a)].strip(" -_・:：　")
                changed = True
    return t


conn = db.get_db()
rows = conn.execute("""
    SELECT v.id AS vid, v.code, v.path, m.id AS mid, m.title, m.title_jp,
           m.actors, m.organized_path
    FROM local_videos v JOIN movies m ON v.movie_id=m.id
    WHERE v.source_id=14
""").fetchall()

renamed = 0
for r in rows:
    code = r["code"]
    acts = actor_list(r["actors"])
    actress = acts[0] if acts else "佚名"
    if "（" in actress:
        actress = actress.split("（")[0]
    cur_base = os.path.basename(str(r["organized_path"] or ""))
    if not cur_base:
        continue
    # 当前 base 拆出 title：code+title+actress+LTX
    parts = cur_base.split("+")
    if len(parts) < 4:
        continue
    title = "+".join(parts[1:-2])
    new_title = strip_alias(title, actress)
    if new_title == title:
        continue
    new_base = clean_name(f"{code}+{new_title}+{actress}+LTX", 110)
    old_dir = str(r["organized_path"])
    new_dir = os.path.join(os.path.dirname(old_dir), new_base)
    print(f"[{code}]")
    print(f"  旧: {cur_base}")
    print(f"  新: {new_base}")
    try:
        if os.path.isdir(old_dir) and old_dir != new_dir:
            os.makedirs(os.path.dirname(new_dir), exist_ok=True)
            os.rename(old_dir, new_dir)
        # 目录内文件前缀替换
        for f in os.listdir(new_dir):
            if not f.startswith(cur_base):
                continue
            nf = new_base + f[len(cur_base):]
            if nf != f:
                os.rename(os.path.join(new_dir, f), os.path.join(new_dir, nf))
        # DB
        new_video = os.path.join(new_dir, new_base + os.path.splitext(str(r["path"]))[1])
        conn.execute("UPDATE local_videos SET path=?, name=?, "
                     "fanart_path=?, poster_path=?, thumb_path=? WHERE id=?",
                     (new_video, os.path.basename(new_video),
                      os.path.join(new_dir, new_base + "-fanart.jpg") if os.path.exists(
                          os.path.join(new_dir, new_base + "-fanart.jpg")) else None,
                      os.path.join(new_dir, new_base + "-poster.jpg") if os.path.exists(
                          os.path.join(new_dir, new_base + "-poster.jpg")) else None,
                      os.path.join(new_dir, new_base + "-thumb.jpg") if os.path.exists(
                          os.path.join(new_dir, new_base + "-thumb.jpg")) else None,
                      r["vid"]))
        conn.execute("UPDATE movies SET video_path=?, organized_path=? WHERE id=?",
                     (new_video, new_dir, r["mid"]))
        conn.commit()
        renamed += 1
    except Exception as e:
        print(f"  💥 {type(e).__name__} {e}")
conn.close()
print(f"\n完成 {renamed} 部改名")
