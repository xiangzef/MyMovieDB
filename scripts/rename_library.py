# -*- coding: utf-8 -*-
"""
Z:\av 全库重命名 + 女优合并（dry-run 用 --apply 才真正执行）

目录/文件名统一为：{番号}+{电影名}+{女优名}+LTX
  Z:\av\{女优(日文,合并)}\{番号}+{电影名}+{女优名}+LTX\  (同名 .mp4/.nfo/-poster.jpg/-fanart.jpg/-thumb.jpg)

女优合并规则：
  RION / 宇都宮しをん / 安齋らら → 同一人，文件夹统一 安齋らら
  英文罗马字 → 日文：RION→安齋らら, Saeko Matsushita→松下紗栄子,
                    Kokomi Sakura→桜ここみ, Ruri Saijo→西條るり,
                    Anri Okita→沖田杏梨, Ema Yumekawa→夢川エマ
"""
import json
import os
import re
import shutil
import sys
import datetime

sys.stdout.reconfigure(encoding="utf-8")
ROOT = r"F:\github\MyMovieDB"
sys.path.insert(0, ROOT + r"\backend")
import database as db   # noqa: E402

Z_ROOT = r"Z:\av"
SRC_ID = 14
APPLY = "--apply" in sys.argv

INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
ACTOR_LATIN_JP = {
    "RION": "安齋らら",
    "Saeko Matsushita": "松下紗栄子",
    "Kokomi Sakura": "桜ここみ",
    "Ruri Saijo": "西條るり",
    "Anri Okita": "沖田杏梨",
    "Ema Yumekawa": "夢川エマ",
    "Shion Utsunomiya": "宇都宮しをん",
    "Saeko matsushita": "松下紗栄子",
}
FOLDER_MERGE = {
    "RION": "安齋らら",
    "宇都宮しをん": "安齋らら",
    "安齋らら": "安齋らら",
}
VIDEO_EXT = (".mp4", ".mkv", ".avi", ".wmv", ".ts", ".mov", ".rmvb", ".m2ts")
IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp")


def clean_name(s: str, cap: int = None) -> str:
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


def canonical_actor(name: str) -> str:
    n = (name or "").strip()
    # 去掉括号里的别名，例如「酒井ちなみ（紫葵）」→「酒井ちなみ」
    n = re.split(r"[（(]", n)[0].strip()
    return ACTOR_LATIN_JP.get(n, n)


def find_video_by_code(code: str) -> "str | None":
    """旧路径失效时，全盘按番号找视频（用户手工改名/移动后）"""
    for root, _dirs, files in os.walk(Z_ROOT):
        for f in files:
            if f.upper().startswith(code.upper()) and f.lower().endswith(VIDEO_EXT):
                return os.path.join(root, f)
    return None


def folder_actor(name: str) -> str:
    n = canonical_actor(name)
    return FOLDER_MERGE.get(n, n)


def build_title(title: str, code: str, actress: str) -> str:
    t = (title or "").strip()
    # 去掉开头的番号
    t = re.sub(r"^\s*" + re.escape(code) + r"[\s\-_・:：]*", "", t, flags=re.IGNORECASE)
    # 去掉结尾的女优名（DMM 标题常见）
    for a in {actress, canonical_actor(actress)}:
        if a and t.endswith(a):
            t = t[: -len(a)].strip()
    # 质量兜底
    if not t or t.upper() == code.upper() or len(t) < 2:
        t = "未詳"
    return clean_name(t, 60)


def main():
    conn = db.get_db()
    rows = conn.execute("""
        SELECT v.id AS vid, v.code, v.path AS vpath, v.name AS vname,
               m.id AS mid, m.title, m.title_jp, m.actors, m.fanart_path,
               m.poster_path, m.thumb_path, m.local_cover_path
        FROM local_videos v JOIN movies m ON v.movie_id = m.id
        WHERE v.source_id = ?
        ORDER BY v.code
    """, (SRC_ID,)).fetchall()

    manifest = []
    planned = []
    for r in rows:
        code = r["code"]
        old_path = str(r["vpath"])
        if not os.path.exists(old_path):
            found = find_video_by_code(code)
            if found:
                print(f"[路径修正] {code}: {old_path} -> {found}")
                old_path = found
                conn.execute("UPDATE local_videos SET path=?, name=? WHERE id=?",
                             (found, os.path.basename(found), r["vid"]))
                conn.commit()
            else:
                print(f"[跳过-文件不存在] {code}: {old_path}")
                continue
        actors = actor_list(r["actors"])
        actress_db = actors[0] if actors else "佚名"
        actress_jp = canonical_actor(actress_db)
        folder = folder_actor(actress_db) or "佚名"
        title = r["title_jp"] or r["title"] or ""
        mtitle = build_title(title, code, actress_jp)
        base = clean_name(f"{code}+{mtitle}+{actress_jp}+LTX", 110)
        new_dir = os.path.join(Z_ROOT, folder, base)
        new_video = os.path.join(new_dir, base + os.path.splitext(old_path)[1])
        planned.append((r, code, old_path, base, folder, new_dir, new_video))

    if not APPLY:
        print(f"[DRY-RUN] 共 {len(planned)} 部待重命名\n")
        for (r, code, old_path, base, folder, new_dir, new_video) in planned[:12]:
            print(f"{code}")
            print(f"  旧: {old_path}")
            print(f"  新目录: {new_dir}")
            print(f"  新视频: {os.path.basename(new_video)}")
        print("\n演员文件夹分布:")
        from collections import Counter
        c = Counter(p[4] for p in planned)
        for k, v in c.most_common():
            print(f"  {k}: {v}")
        return

    # ── 真正执行 ──
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    for (r, code, old_path, base, folder, new_dir, new_video) in planned:
        old_dir = os.path.dirname(old_path)
        try:
            os.makedirs(new_dir, exist_ok=True)

            # 1) 视频
            if os.path.abspath(old_path) != os.path.abspath(new_video):
                if os.path.exists(new_video):
                    # 目标已存在（理论上不会），加序号
                    k = 2
                    stem, ext = os.path.splitext(base)
                    while os.path.exists(os.path.join(new_dir, f"{stem}-{k}{ext}")):
                        k += 1
                    new_video = os.path.join(new_dir, f"{stem}-{k}{ext}")
                shutil.move(old_path, new_video)
            manifest.append({"code": code, "old": old_path, "new": new_video})

            # 2) 文件夹内其他文件（NFO/图片/字幕）
            assets = {"nfo": None, "fanart": None, "poster": None, "thumb": None, "subs": []}
            if os.path.isdir(old_dir) and os.path.abspath(old_dir) != os.path.abspath(Z_ROOT):
                for f in os.listdir(old_dir):
                    fp = os.path.join(old_dir, f)
                    if not os.path.isfile(fp):
                        continue
                    low = f.lower()
                    if fp == old_path:
                        continue
                    if low.endswith(".nfo"):
                        tgt = os.path.join(new_dir, base + ".nfo")
                        shutil.move(fp, tgt)
                        assets["nfo"] = tgt
                    elif low.endswith(".srt"):
                        if low.endswith(".zh.srt"):
                            tgt = os.path.join(new_dir, base + ".zh.srt")
                        else:
                            tgt = os.path.join(new_dir, base + os.path.splitext(f)[1])
                        if os.path.exists(tgt):
                            tgt = os.path.join(new_dir, base + "-2" + os.path.splitext(f)[1])
                        shutil.move(fp, tgt)
                        assets["subs"].append(tgt)
                    elif low.endswith(IMAGE_EXT):
                        if "fanart" in low:
                            kind = "fanart"
                        elif "poster" in low:
                            kind = "poster"
                        elif "thumb" in low:
                            kind = "thumb"
                        else:
                            kind = None
                        if kind:
                            tgt = os.path.join(new_dir, base + f"-{kind}" + os.path.splitext(f)[1])
                            shutil.move(fp, tgt)
                            assets[kind] = tgt
                        else:
                            # 其他图（手工封面等）：保留
                            tgt = os.path.join(new_dir, base + "-cover" + os.path.splitext(f)[1])
                            if not os.path.exists(tgt):
                                shutil.move(fp, tgt)
                # 删除空目录
                try:
                    if os.path.isdir(old_dir) and not os.listdir(old_dir):
                        os.rmdir(old_dir)
                except OSError:
                    pass

            # 2b) 根目录的手工封面（老路径就在 Z:\av 时）
            if os.path.abspath(old_dir) == os.path.abspath(Z_ROOT):
                for f in os.listdir(Z_ROOT):
                    fp = os.path.join(Z_ROOT, f)
                    if not os.path.isfile(fp):
                        continue
                    if f.upper().startswith(code.upper()) and f.lower().endswith(IMAGE_EXT):
                        tgt = os.path.join(new_dir, base + "-cover" + os.path.splitext(f)[1])
                        if not os.path.exists(tgt):
                            shutil.move(fp, tgt)
                            manifest.append({"code": code, "old": fp, "new": tgt})

            # 3) 缺图则从 covers 目录补
            safe = re.sub(r'[<>:"/\\|?*]', "_", code)
            for kind, src in (("fanart", r["fanart_path"]), ("poster", r["poster_path"]),
                              ("thumb", r["thumb_path"])):
                tgt = os.path.join(new_dir, base + f"-{kind}.jpg")
                if os.path.exists(tgt):
                    assets[kind] = tgt
                    continue
                if src and os.path.exists(str(src)):
                    shutil.copy2(str(src), tgt)
                    assets[kind] = tgt

            # 4) NFO 兜底（从 covers 生成/复制）
            if not assets["nfo"]:
                cand = os.path.join(str(COVERS_DIR()), safe, f"{safe}.nfo")
                tgt = os.path.join(new_dir, base + ".nfo")
                if os.path.exists(cand):
                    shutil.copy2(cand, tgt)
                    assets["nfo"] = tgt

            # 5) DB 回写
            new_name = os.path.basename(new_video)
            conn.execute("""UPDATE local_videos SET path=?, name=?, is_jellyfin=1,
                            fanart_path=?, poster_path=?, thumb_path=?,
                            updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                         (new_video, new_name, assets["fanart"], assets["poster"],
                          assets["thumb"], r["vid"]))
            conn.execute("""UPDATE movies SET video_path=?, organized_path=?,
                            fanart_path=COALESCE(?, fanart_path),
                            poster_path=COALESCE(?, poster_path),
                            thumb_path=COALESCE(?, thumb_path),
                            source_type='jellyfin', jellyfin_status=? WHERE id=?""",
                         (new_video, new_dir, assets["fanart"], assets["poster"],
                          assets["thumb"],
                          "complete" if assets["poster"] or assets["fanart"] else "partial",
                          r["mid"]))
            conn.commit()
            print(f"[OK] {code} -> {folder}\\{base}")
        except Exception as e:
            print(f"[FAIL] {code}: {type(e).__name__} {e}")
            conn.rollback()

    # 女优名日文化（DB actors）
    av_movies = conn.execute(
        "SELECT id, actors FROM movies WHERE id IN "
        "(SELECT movie_id FROM local_videos WHERE source_id=?)", (SRC_ID,)).fetchall()
    for r in av_movies:
        acts = actor_list(r["actors"])
        new_acts = [ACTOR_LATIN_JP.get(a, a) for a in acts]
        if new_acts != acts:
            conn.execute("UPDATE movies SET actors=? WHERE id=?",
                         (json.dumps(new_acts, ensure_ascii=False), r["id"]))
    conn.commit()

    out = os.path.join(ROOT, "data", f"rename_manifest_{ts}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"\n完成 {len(manifest)} 个文件移动，清单: {out}")
    conn.close()


def COVERS_DIR():
    import config as cfg
    return cfg.COVERS_DIR


if __name__ == "__main__":
    main()
