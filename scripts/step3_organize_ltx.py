# -*- coding: utf-8 -*-
"""
Step 3: Z:\av 原地整理为 Jellyfin 结构 + LTX 破解标注
  目标结构: Z:\av\{演员}\{番号}\{番号}-LTX.mp4
                        \{番号}.nfo        (内含 <tag)LTX</tag><tag>破解</tag>)
                        \{番号}-poster.jpg / {番号}-fanart.jpg / {番号}-thumb.jpg
  数据来自刮削结果：data/covers/{code}/ 下 NFO + 裁切图
"""
import json
import os
import re
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = r"F:\github\MyMovieDB"
BACKEND = ROOT + r"\backend"
sys.path.insert(0, BACKEND)
import database as db          # noqa: E402

Z_ROOT = r"Z:\av"
SRC_ID = 14
LTX_SUFFIX = "-LTX"
INVALID_NAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

BAD_ACTOR_NAMES = {"", "n/a", "none", "-", "佚名", "-", "未知", "[]", "[]", "unknown"}


def sanitize(name: str) -> str:
    name = INVALID_NAME_CHARS.sub("_", name).strip().rstrip(". ")
    return name[:80] if name else "unknown"


def pick_actor(actor_json) -> str:
    """从 movies.actors JSON 里取第一个女演员名"""
    try:
        names = json.loads(actor_json) if actor_json else []
    except Exception:
        names = []
    for n in names:
        n = str(n).strip()
        base = re.split(r"[/（(]", n)[0].strip()
        if base and base.lower() not in BAD_ACTOR_NAMES and not re.fullmatch(r"[\[\]\(\)\s]*", base):
            return base
    return "佚名"


def inject_ltx_tags(nfo_path: str):
    """NFO 中注入 <tag>LTX</tag> <tag>破解</tag>（幂等）"""
    with open(nfo_path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()
    if "<tag>LTX</tag>" in text:
        return
    tags = "<tag>LTX</tag>\n  <tag>破解</tag>"
    if "</movie>" in text:
        text = text.replace("</movie>", f"  {tags}\n</movie>")
    else:
        text += f"\n{tags}\n"
    with open(nfo_path, "w", encoding="utf-8") as f:
        f.write(text)


def main():
    conn = db.get_db()
    rows = conn.execute("""
        SELECT v.id AS vid, v.path, v.name, v.code, v.scraped,
               m.id AS mid, m.actors, m.fanart_path, m.poster_path, m.thumb_path,
               m.local_cover_path, m.subtitle_type
        FROM local_videos v
        LEFT JOIN movies m ON v.movie_id = m.id
        WHERE v.source_id = ?
    """, (SRC_ID,)).fetchall()

    moved = skipped = no_movie = 0
    no_assets = []
    for r in rows:
        code = r["code"]
        src_path = str(r["path"])
        if not os.path.exists(src_path):
            skipped += 1
            continue

        if r["scraped"] != 1 or not r["mid"]:
            no_movie += 1
            continue

        # 目标目录
        actor = sanitize(pick_actor(r["actors"]))
        target_dir = os.path.join(Z_ROOT, actor, code)
        os.makedirs(target_dir, exist_ok=True)

        # 视频移动改名为 {code}-LTX{ext}
        ext = os.path.splitext(src_path)[1].lstrip(".")
        new_name = f"{code}{LTX_SUFFIX}.{ext}"
        new_path = os.path.join(target_dir, new_name)
        if src_path == new_path:
            pass
        else:
            if os.path.exists(new_path):
                k = 2
                while os.path.exists(os.path.join(target_dir, f"{code}{LTX_SUFFIX}-{k}.{ext}")):
                    k += 1
                new_name = f"{code}{LTX_SUFFIX}-{k}.{ext}"
                new_path = os.path.join(target_dir, new_name)
            shutil.move(src_path, new_path)

        # 图片复制（fanart/poster/thumb 或 cover 兜底）
        img_src = {"fanart": r["fanart_path"], "poster": r["poster_path"], "thumb": r["thumb_path"]}
        if not any(img_src.values()) and r["local_cover_path"]:
            img_src["fanart"] = r["local_cover_path"]
        for kind, p in img_src.items():
            if not p or not os.path.exists(str(p)):
                continue
            tgt = os.path.join(target_dir, f"{code}-{kind}{os.path.splitext(str(p))[1]}")
            try:
                shutil.copy2(str(p), tgt)
            except Exception as e:
                print(f"[图片复制失败] {code} {e}")
            if kind == "fanart" and not img_src["poster"] and os.path.exists(tgt):
                shutil.copy2(tgt, os.path.join(target_dir, f"{code}-poster{os.path.splitext(str(p))[1]}"))
        if not any(os.path.exists(os.path.join(target_dir, f"{code}-{k}{s}"))
                   for k in ("poster", "fanart") for s in (".jpg", ".png", ".webp")):
            no_assets.append(code)

        # NFO：先看刮削产物 data/covers/{code}/{code}.nfo
        from pathlib import Path
        import scraper as sc
        safe = re.sub(r'[<>:"/\\|?*]', "_", code)
        src_nfo = Path(cfg_covers()) / safe / f"{safe}.nfo"
        tgt_nfo = os.path.join(target_dir, f"{code}.nfo")
        if src_nfo.exists():
            shutil.copy2(src_nfo, tgt_nfo)
        if not os.path.exists(tgt_nfo):
            # 兜底：用 movies 数据现生成
            m = db.get_movie_by_id(r["mid"])
            if m:
                try:
                    sc.generate_nfo(m, Path(tgt_nfo))
                except Exception as e:
                    print(f"[NFO 生成失败] {code}: {e}")
        if os.path.exists(tgt_nfo):
            inject_ltx_tags(tgt_nfo)

        # DB 更新
        conn.execute("UPDATE local_videos SET path=?, name=?, is_jellyfin=1, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                     (new_path, new_name, r["vid"]))
        sub = r["subtitle_type"] or "none"
        have_poster = os.path.exists(os.path.join(target_dir, f"{code}-poster.jpg"))
        st = "complete" if have_poster else "partial"
        conn.execute("""
            UPDATE movies SET video_path=?, source_type='jellyfin',
                jellyfin_status=?, organized_path=?, last_organized_at=CURRENT_TIMESTAMP,
                subtitle_type=COALESCE(?, subtitle_type)
            WHERE id=?
        """, (new_path, st, target_dir, sub, r["mid"]))
        moved += 1

    # 无残留清理（保留所有记录，只统计）
    conn.commit()

    n_total = conn.execute("SELECT count(*) FROM local_videos WHERE source_id=?", (SRC_ID,)).fetchone()[0]
    n_org = conn.execute("SELECT count(*) FROM local_videos WHERE source_id=? AND is_jellyfin=1", (SRC_ID,)).fetchone()[0]
    db.mark_source_as_jellyfin(Z_ROOT, n_total)
    db.update_local_source_scan(SRC_ID, n_total)
    conn.close()

    print(f"[整理] 移动 {moved}，无刮削数据(留根目录) {no_movie}，跳过 {skipped}")
    if no_assets:
        print(f"[缺图] {len(no_assets)} 个: {no_assets[:15]}")
    print(f"[源] Z:\\av local_videos={n_total}, is_jellyfin={n_org}")


def cfg_covers():
    import config as cfg
    import os
    return str(cfg.COVERS_DIR)


if __name__ == "__main__":
    main()
