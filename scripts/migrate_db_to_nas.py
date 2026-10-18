# 把 Windows 版数据库的盘符路径改写成 NAS 容器内路径
# 用法：
#   python scripts/migrate_db_to_nas.py            # 干跑，只统计不落盘
#   python scripts/migrate_db_to_nas.py --apply    # 生成 data/movies.db.nas
#
# 盘符与 NAS 的对应关系来自本机 net use + docker-compose.yml：
#   W: -> \\192.168.1.179\home1 -> /volume2/home1  -> /media/jellyfin
#   X: -> \\192.168.1.179\home2 -> /volume3/home2  -> /media/jellyfin2
#   Z: -> \\192.168.1.179\home5 -> /volume5/home5/影视库 -> /media/影视库
#
# home1 / home2 是整 share 挂载，容器内要保留 jellyfin、影视库这些子目录；
# home5 只挂了 影视库 一层，所以 Z:\影视库 直接对应 /media/影视库。
#
# 封面缓存路径（data\covers\... 与 F:\github\...\data\covers\...）不改：
# 前端 index.html 的 localToApi 会截出 covers\<code>\<file> 尾段，
# 重写成 /covers/<code>/<file>，后端从 /app/data/covers 读，跟 data 目录一起拷即可。

import argparse
import re
import shutil
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "movies.db"
DST = ROOT / "data" / "movies.db.nas"

# Windows 源目录 -> 容器内目录。必须按完整源目录前缀匹配，不能按盘符一对一，
# 否则 Z:\影视库\a.mp4 会被错改成 /media/影视库/影视库/a.mp4。
SOURCE_MAP = [
    (r"X:\jellyfin", "/media/jellyfin2/jellyfin"),
    (r"X:\中转站",   "/media/jellyfin2/中转站"),
    (r"W:\jellyfin", "/media/jellyfin/jellyfin"),
    (r"W:\影视库",   "/media/jellyfin/影视库"),
    (r"Z:\影视库",   "/media/影视库"),
]
# 长前缀优先，避免 X:\jellyfin 被 X:\ 中转站 之类的短前缀抢先匹配
SOURCE_MAP.sort(key=lambda kv: -len(kv[0]))

# 需要改写的字段
TARGETS = [
    ("local_sources", ["path"]),
    ("local_videos", ["path", "poster_path", "thumb_path", "fanart_path"]),
    ("movies", ["video_path", "poster_path", "thumb_path", "fanart_path",
                "organized_path", "local_cover_path"]),
]

# init_local_videos_table() 建表时漏了这三列，只补了 is_jellyfin。
# get_all_movies / 搜索 / 本地视频列表都 SELECT lv.fanart_path，
# 缺列时这三个接口全部 500。这里兜底补齐，Windows 库已有则是空操作。
REQUIRED_COLUMNS = {
    "local_videos": {
        "fanart_path": "ALTER TABLE local_videos ADD COLUMN fanart_path TEXT",
        "poster_path": "ALTER TABLE local_videos ADD COLUMN poster_path TEXT",
        "thumb_path": "ALTER TABLE local_videos ADD COLUMN thumb_path TEXT",
    },
}

# X:jellyfin\... 这类漏了盘符后反斜杠的历史脏数据
_DRIVE_RE = re.compile(r"^([A-Za-z]):(?![\\/])")
# 封面缓存：...\data\covers\<code>\<file>
# 这类路径在 Windows 上是仓库里的绝对路径，在 Linux 上不存在，
# 但前端 localToApi 会截出尾段重写成 /covers/<code>/<file>，所以保持原样。
_COVERS_RE = re.compile(r"(?i)(^|\\)data\\covers\\[^\\]+\\[^\\]+$")


def convert(value):
    """单个路径值改写。返回 (新值, 状态)，
    状态 ∈ rewritten / covers_cache / skipped / unmapped / empty"""
    if value is None:
        return value, "empty"
    raw = value.strip()
    if not raw:
        return value, "empty"

    # 只动带盘符的 Windows 绝对路径。
    # 相对路径（data\covers\...）和 URL 保持原样，它们不依赖文件系统根。
    if not re.match(r"^[A-Za-z]:", raw):
        return value, "skipped"

    normalized = _DRIVE_RE.sub(r"\1:\\", raw).replace("/", "\\").rstrip("\\")

    for win_prefix, linux_dir in SOURCE_MAP:
        if normalized.lower() == win_prefix.lower():
            return linux_dir, "rewritten"
        if normalized.lower().startswith(win_prefix.lower() + "\\"):
            rest = normalized[len(win_prefix) + 1:].replace("\\", "/")
            return f"{linux_dir}/{rest}", "rewritten"

    if _COVERS_RE.search(normalized):
        return value, "covers_cache"
    return value, "unmapped"


def ensure_columns(conn):
    cur = conn.cursor()
    for table, cols in REQUIRED_COLUMNS.items():
        existing = [r[1] for r in cur.execute(f"PRAGMA table_info({table})")]
        for col, sql in cols.items():
            if col not in existing:
                cur.execute(sql)
                print(f"  + {table}.{col} 列已补齐")
    conn.commit()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真正写出 movies.db.nas")
    ap.add_argument("--src", default=str(SRC))
    ap.add_argument("--dst", default=str(DST))
    args = ap.parse_args()

    src = Path(args.src)
    dst = Path(args.dst)
    if not src.exists():
        print(f"❌ 源库不存在: {src}")
        return 1

    print(f"源库: {src} ({src.stat().st_size:,} 字节)")
    print(f"目标: {dst}")
    print(f"模式: {'写入' if args.apply else '干跑（加 --apply 才写文件）'}\n")

    if args.apply:
        shutil.copy2(src, dst)
        print(f"已复制源库到 {dst}")
    conn = sqlite3.connect(dst if args.apply else src)

    ensure_columns(conn)
    cur = conn.cursor()

    unmapped = []
    print("字段改写统计：")
    for table, cols in TARGETS:
        existing = [r[1] for r in cur.execute(f"PRAGMA table_info({table})")]
        for col in cols:
            if col not in existing:
                print(f"  {table}.{col}: 字段不存在，跳过")
                continue
            rows = cur.execute(
                f"SELECT id, {col} FROM {table} "
                f"WHERE {col} IS NOT NULL AND TRIM({col}) != ''"
            ).fetchall()
            stats = {"rewritten": 0, "covers_cache": 0, "skipped": 0, "unmapped": 0}
            updates = []
            for row_id, value in rows:
                new_value, status = convert(value)
                stats[status] += 1
                if status == "rewritten":
                    updates.append((new_value, row_id))
                elif status == "unmapped":
                    unmapped.append((table, col, row_id, value))
            if args.apply and updates:
                cur.executemany(f"UPDATE {table} SET {col} = ? WHERE id = ?", updates)
            print(f"  {table}.{col}: 改写 {stats['rewritten']}, "
                  f"封面缓存保留 {stats['covers_cache']}, "
                  f"其他保留 {stats['skipped']}, 未匹配 {stats['unmapped']}")

    if args.apply:
        conn.commit()

    # 复查：库里不该再有指向媒体目录的盘符路径。
    # 封面缓存的盘符路径是预期内的，前端会重写，不算残留。
    print("\n复查（仍指向媒体目录的盘符路径）：")
    residual = 0
    for table, cols in TARGETS:
        existing = [r[1] for r in cur.execute(f"PRAGMA table_info({table})")]
        for col in cols:
            if col not in existing:
                continue
            for (value,) in cur.execute(
                f"SELECT {col} FROM {table} WHERE {col} IS NOT NULL"
            ):
                _, status = convert(value)
                if status == "unmapped":
                    print(f"  ❌ {table}.{col} = {value}")
                    residual += 1
    print("  无" if residual == 0 else f"  共 {residual} 处")

    print("\n改写后的视频源：")
    for row in cur.execute("SELECT id, path, is_jellyfin, video_count FROM local_sources ORDER BY id"):
        print(f"  [{row[0]}] {row[1]}  jellyfin={row[2]}  计数={row[3]}")

    print("\n改写后的路径样本：")
    for table, col in (("local_videos", "path"), ("movies", "video_path"),
                       ("movies", "poster_path"), ("movies", "organized_path")):
        for (value,) in cur.execute(
            f"SELECT {col} FROM {table} WHERE {col} IS NOT NULL "
            f"AND TRIM({col}) != '' LIMIT 2"
        ):
            print(f"  {table}.{col} = {value}")

    if unmapped:
        print(f"\n⚠️ 有 {len(unmapped)} 处盘符路径匹配不到映射，需人工确认：")
        for table, col, row_id, value in unmapped[:20]:
            print(f"  {table}.{col} id={row_id}: {value}")
        if args.apply:
            conn.rollback()
            print("\n已回滚，未落盘。")
            conn.close()
            return 2

    if args.apply:
        conn.commit()
        conn.close()
        print(f"\n✅ 完成: {dst} ({dst.stat().st_size:,} 字节)")
        print("下一步：")
        print("  1. 停掉 NAS 容器")
        print("  2. 把 movies.db.nas 改名成 movies.db，连同 data/covers、data/avatars")
        print("     一起传到 /volume2/docker/mymoviedb/data/（属主 uid 1024）")
        print("  3. 启动容器")
    else:
        conn.close()
        print("\n干跑结束，未写任何文件。确认无误后加 --apply。")

    return 0


if __name__ == "__main__":
    sys.exit(main())
