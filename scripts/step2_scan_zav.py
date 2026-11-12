# -*- coding: utf-8 -*-
"""
Step 2: 扫描 Z:\av -> local_videos 入库（source_id=14, is_jellyfin=0）
含手工修正映射：
  snis00872hhb_restored.mp4   -> SNIS-087 （DMM cid 规律: prefix + 5位补零）
  1sdsi00004hhb_LTX.mp4       -> SDSI-004 （与目录名 SDSI-004_LTX 互相印证）
  SDSI-008 / SDSI-040 两个失败文件现场诊断
"""
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = r"F:\github\MyMovieDB"
BACKEND = ROOT + r"\backend"
sys.path.insert(0, BACKEND)
import database as db  # noqa: E402

Z_ROOT = r"Z:\av"
SRC_ID = 14

CODE_RE = re.compile(r"([A-Z]{2,6})-(\d{2,5})")
EXCL_WORDS = ["WEB", "HD", "BD", "720", "1080", "4K", "UHD", "SD"]
SPECIAL = [re.compile(r"(FC2-PPV-\d{5,7})", re.IGNORECASE)]

# 手工映射：文件名(不含扩展名，含垃圾前缀) -> 番号
# 主正则修复前被误拒/无法识别的文件，逐个确认
MANUAL = {
    "www.98T.la@JBD-240_restored_wm": "JBD-240",
    "www.98T.la@RBD-772_restored-LTX": "RBD-772",
    "www.98T.la@RBD-776_restored_wm": "RBD-776",
    "www.98T.la@RBD-805_restored_wm": "RBD-805",
    "www.98T.la@RBD-826_restored-LTX": "RBD-826",
    "www.98T.la@RBD-867_restored_wm": "RBD-867",
    "www.98T.la@RBD-916 新奴隷捜査官6 松下紗栄子_restored_wm": "RBD-916",
    "www.98T.la@SDSI-008_restored_wm": "SDSI-008",
    "www.98T.la@SDSI-040_restored_wm": "SDSI-040",
    "www.98T.la@snis00872hhb_restored": "SNIS-087",   # DMM cid: snis00872 -> 87
    "1sdsi00004hhb_LTX": "SDSI-004",                  # 与目录名 SDSI-004_LTX 互相印证
}


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
    # 兜底：DMM cid 风格 prefix+5位补零（如 snis00872 / sdsi00004）
    m = re.match(r"^[a-z]{2,6}(\d{5})", up.replace("_RESTORED", "").replace("_WM", ""))
    if m:
        prefix = re.match(r"^([a-z]{2,6})", up).group(1).upper()
        num = str(int(m.group(1)))
        if not prefix.isdigit() and prefix not in EXCL_WORDS and len(num) >= 2:
            return f"{prefix}-{num}"
    return None


def subtitle_from_name(stem: str):
    up = stem.upper()
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


def main():
    conn = db.get_db()

    # 收集 Z:\av 全部视频
    items = []
    unranked = []
    for dir_path, _dirs, files in os.walk(Z_ROOT):
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in db.VIDEO_EXTENSIONS if hasattr(db, "VIDEO_EXTENSIONS") else ext not in {
                ".mp4", ".mkv", ".avi", ".wmv", ".flv", ".mov", ".mpg", ".mpeg", ".m2ts", ".ts"}:
                continue
            stem = os.path.splitext(fname)[0]
            vpath = os.path.join(dir_path, fname)
            code = MANUAL.get(stem) or extract_code(stem)
            if not code:
                unranked.append((os.path.relpath(vpath, Z_ROOT), stem))
                continue
            code = db.normalize_code(code)
            items.append((code, vpath, stem, ext))

    print(f"共收集 {len(items)} 个视频，{len(unranked)} 个提取失败")
    for rel, stem in unranked:
        print("  失败:", rel, "| stem:", repr(stem))

    # 入库（is_jellyfin=0，subtitle_type 由扩展名推断）
    ins = upd = 0
    for code, vpath, stem, ext in items:
        data = {
            "source_id": SRC_ID,
            "name": os.path.basename(vpath),
            "path": vpath,
            "code": code,
            "extension": ext.lstrip("."),
            "file_size": os.path.getsize(vpath),
            "is_jellyfin": 0,
        }
        db.upsert_local_video(data)
        ins += 1
    print(f"upsert_local_video -> {ins}")

    # 与 movies 重连：code 已存在 -> 直接关联，不再联网刮
    lv = conn.execute(
        "SELECT id, code, path FROM local_videos WHERE source_id=? AND scraped=0",
        (SRC_ID,)).fetchall()
    linked = 0
    for r in lv:
        mv = conn.execute("SELECT id FROM movies WHERE code=?", (r["code"],)).fetchone()
        if mv:
            conn.execute("UPDATE local_videos SET movie_id=?, scraped=1 WHERE id=?",
                         (mv["id"], r["id"]))
            # movies.video_path 若空或失效 -> 指向 Z:\av 的这个文件（仅当 movies 还没有别的有效路径）
            mvp = conn.execute("SELECT video_path FROM movies WHERE id=?", (mv["id"],)).fetchone()[0]
            if mvp and not os.path.exists(mvp):
                conn.execute("UPDATE movies SET video_path=?, local_video_id=? WHERE id=?",
                             (r["path"], r["id"], mv["id"]))
            elif not mvp:
                conn.execute("UPDATE movies SET video_path=?, local_video_id=? WHERE id=?",
                             (r["path"], r["id"], mv["id"]))
            linked += 1
    conn.commit()
    print(f"与已有 movies 重连: {linked}")

    # 统计待刮
    todo = conn.execute("""
        SELECT count(*) FROM local_videos lv
        WHERE lv.source_id=? AND lv.scraped=0 OR (lv.source_id=? AND lv.scraped=1 AND lv.movie_id IS NULL)
    """, (SRC_ID, SRC_ID)).fetchone()[0]
    remain = conn.execute(
        "SELECT count(*) FROM local_videos WHERE source_id=? AND scraped=0", (SRC_ID,)).fetchone()[0]
    print(f"待联网刮削（scraped=0）: {remain}")
    conn.close()


if __name__ == "__main__":
    main()
