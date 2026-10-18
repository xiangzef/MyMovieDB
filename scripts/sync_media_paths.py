"""按磁盘实际状态同步 local_videos / local_sources，幂等，可反复跑。

背景：NAS 上正在做媒体库整理，会删除重复番号副本、合并同名演员目录、
移动文件。这些动作一做完，local_videos.path 就会指向不存在的位置。
本脚本不假设任何一次具体的删/移，而是每次都拿数据库和磁盘现状对账。

判定分三类：
  OK        文件存在，不用动
  DRIFT     文件还在，只是路径变了（目录改名 / 换根 / 层级调整）→ UPDATE path
  GONE      磁盘上确实找不到 → 默认只报告，--prune 才删行

「路径变了」的定位策略（按代价从低到高，全部要求唯一命中）：
  1. 同名文件在同一个源根下唯一存在      → 直接改
  2. 顶层目录名去掉分隔符后以番号开头     → 进该目录找以番号开头的文件
     例：库里 /影视库/ABW-358/ABW-358UC.mp4，实际 /影视库/ABW-358UC/ABW-358UC.mp4
  3. 全源根递归找同名文件唯一命中          → --deep 开启，代价高

用法：
    # 只看不动（迁移前后都应该先跑一次）
    python scripts/sync_media_paths.py --check

    # 改路径 + 重算 video_count，报告写日志目录
    python scripts/sync_media_paths.py --apply

    # 连同真消失的行一起删（不可逆，先跑 --check 看清单）
    python scripts/sync_media_paths.py --apply --prune

在容器里跑（/media/* 已经是容器视角）：
    docker exec -i mymoviedb python3 - < scripts/sync_media_paths.py --check

在宿主机上跑（要给映射，日志才能直接落到 NAS）：
    python3 scripts/sync_media_paths.py --check \
        --map /media/jellyfin/jellyfin=/volume2/home1/jellyfin \
        --map /media/jellyfin/影视库=/volume2/home1/影视库 \
        --map /media/jellyfin2/jellyfin=/volume3/home2/jellyfin \
        --map /volume2/docker/mymoviedb/data/movies.db=/volume2/docker/mymoviedb/data/movies.db \
        --log-dir /volume2/docker/mymoviedb/migration-log
"""
import argparse
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone

VIDEO_EXT = (".mp4", ".mkv", ".avi", ".wmv", ".mov", ".webm", ".m4v", ".ts")
_SEP = re.compile(r"[^0-9a-zA-Z]+")


def norm(s):
    """去掉所有分隔符，用于番号/目录名模糊比对。ABW-358UC -> ABW358UC"""
    return _SEP.sub("", s or "").upper()


def utcnow():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Mapper:
    """把库里的容器路径翻译成宿主机路径；没给映射就原样用（在容器里跑）。"""

    def __init__(self, pairs):
        self.pairs = list(pairs or [])

    def to_host(self, path):
        for c, h in self.pairs:
            if path == c or path.startswith(c.rstrip("/") + "/"):
                return h.rstrip("/") + path[len(c.rstrip("/")):]
        return path


class RootIndex:
    """源根目录的顶层条目缓存，只在需要定位漂移时才扫，避免全盘 walk。"""

    def __init__(self):
        self._cache = {}

    def top(self, root):
        if root not in self._cache:
            try:
                self._cache[root] = {e.name: e.path for e in os.scandir(root) if e.is_dir()}
            except OSError:
                self._cache[root] = {}
        return self._cache[root]


def find_candidates(row_path, code, source_root_host, index, deep=False, all_roots=()):
    """在各个媒体根下找这个视频现在在哪。返回候选路径列表。"""
    out = []

    # 策略 1：同名文件在原位置的同级或子目录里
    parent = os.path.dirname(row_path)
    guess = os.path.join(parent, os.path.basename(row_path))
    if os.path.isfile(guess):
        out.append(guess)

    # 路径形如 <root>/<演员>/<番号>/<文件>，取出演员名
    actor = ""
    try:
        actor = os.path.basename(os.path.dirname(os.path.dirname(row_path)))
    except Exception:
        pass

    # 策略 2：在每个根下找 <演员>/<番号开头>/<番号开头的视频>
    # 源根 + 其余根都要找——演员目录合并时会整棵跨卷搬家（X: 的涼森れむ -> W:），
    # 只在原根里找会误判成「文件消失」。
    roots = []
    for r in (source_root_host,) + tuple(all_roots):
        if r and r not in roots and os.path.isdir(r):
            roots.append(r)

    for root in roots:
        if actor:
            adir = os.path.join(root, actor)
            if os.path.isdir(adir) and adir != os.path.dirname(parent):
                for name in os.listdir(adir):
                    d = os.path.join(adir, name)
                    if not os.path.isdir(d):
                        continue
                    if code and not norm(name).startswith(norm(code)):
                        continue
                    try:
                        for f in os.scandir(d):
                            if f.is_file() and f.name.lower().endswith(VIDEO_EXT):
                                if not code or norm(f.name).startswith(norm(code)):
                                    out.append(f.path)
                    except OSError:
                        pass
        # 无演员名时退化为扫根目录的顶层
        if code and not actor:
            for name, dpath in index.top(root).items():
                if not norm(name).startswith(norm(code)):
                    continue
                try:
                    for f in os.scandir(dpath):
                        if f.is_file() and f.name.lower().endswith(VIDEO_EXT) and norm(f.name).startswith(norm(code)):
                            out.append(f.path)
                except OSError:
                    pass

    # 策略 3：全源根递归找同名文件
    if deep:
        base = os.path.basename(row_path)
        for dirpath, _dirs, files in os.walk(source_root_host):
            if base in files:
                out.append(os.path.join(dirpath, base))

    # 去重且保持顺序
    seen, uniq = set(), []
    for p in out:
        if p not in seen and os.path.isfile(p):
            seen.add(p)
            uniq.append(p)
    return uniq


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="/app/data/movies.db")
    ap.add_argument("--map", action="append", default=[],
                    help="容器路径=宿主机路径，可多次")
    ap.add_argument("--log-dir", default=None, help="报告与 SQL 输出目录")
    ap.add_argument("--check", action="store_true", help="只看不动（默认行为）")
    ap.add_argument("--apply", action="store_true", help="真的写库")
    ap.add_argument("--prune", action="store_true", help="连 GONE 的行一起删，需配合 --apply")
    ap.add_argument("--deep", action="store_true", help="启用全源根递归查找，慢")
    args = ap.parse_args()

    dry = not args.apply
    m = Mapper([tuple(p.split("=", 1)) for p in args.map])
    db_host = m.to_host(args.db)

    if not os.path.exists(db_host):
        print("找不到数据库: %s" % db_host)
        return 2

    conn = sqlite3.connect(db_host)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    index = RootIndex()

    rows = cur.execute(
        "SELECT v.id, v.path, v.code, v.source_id, s.path AS src "
        "FROM local_videos v LEFT JOIN local_sources s ON v.source_id = s.id"
    ).fetchall()

    # 所有已注册的媒体根，跨卷合并时演员目录会整棵搬家，定位要跨根找
    all_roots = [m.to_host(r["path"]) for r in cur.execute("SELECT path FROM local_sources")]

    ok, drift, gone, ambiguous = [], [], [], []

    for r in rows:
        host = m.to_host(r["path"])
        if os.path.isfile(host):
            ok.append(r)
            continue
        root = m.to_host(r["src"]) if r["src"] else os.path.dirname(host)
        if not root or not os.path.isdir(root):
            # 源目录本身没了（演员目录已被合并到别的卷），不能就此放弃：
            # 仍然跨所有已注册根去找
            root = all_roots[0] if all_roots else os.path.dirname(host)
        cands = find_candidates(host, r["code"], root, index, deep=args.deep, all_roots=all_roots)
        if len(cands) == 1:
            drift.append((r, cands[0]))
        elif len(cands) > 1:
            # 同番号可能有多个字幕版本(-C/-U/-UC)，优先认原文件名那个
            base = os.path.basename(host)
            exact = [c for c in cands if os.path.basename(c) == base]
            if len(exact) == 1:
                drift.append((r, exact[0]))
            else:
                ambiguous.append((r, cands))
        else:
            gone.append((r, "所有已注册根下均未找到"))

    print("=== local_videos 对账 ===")
    print("  总数 %d | 正常 %d | 路径漂移 %d | 真消失 %d | 候选不唯一 %d"
          % (len(rows), len(ok), len(drift), len(gone), len(ambiguous)))

    if drift:
        print("\n--- 路径漂移（文件在，路径要改）---")
        for r, new in drift:
            print("  id=%-5s %-12s" % (r["id"], r["code"]))
            print("      旧: %s" % r["path"])
            print("      新: %s" % new)

    if ambiguous:
        print("\n--- 候选不唯一，需人工判断 ---")
        for r, c in ambiguous:
            print("  id=%s %s -> %d 个候选" % (r["id"], r["code"], len(c)))
            for x in c[:5]:
                print("      %s" % x)

    if gone:
        print("\n--- 真消失（文件不在磁盘上）---")
        for r, why in gone:
            print("  id=%-5s %-12s %s  (%s)" % (r["id"], r["code"], r["path"], why))

    # local_sources 的 path 存在性与 video_count 重算
    src_rows = cur.execute("SELECT id, path FROM local_sources").fetchall()
    src_fix = []
    for s in src_rows:
        host = m.to_host(s["path"])
        real = cur.execute("SELECT COUNT(*) FROM local_videos WHERE source_id = ?", (s["id"],)).fetchone()[0]
        stored = cur.execute("SELECT video_count FROM local_sources WHERE id = ?", (s["id"],)).fetchone()[0]
        exists = os.path.isdir(host)
        if not exists or real != stored:
            src_fix.append((s["id"], s["path"], exists, stored, real))
    print("\n=== local_sources ===")
    if not src_fix:
        print("  路径全部存在，video_count 全部一致，无需改动")
    for sid, p, exists, stored, real in src_fix:
        print("  [%s] %s  目录存在=%s  video_count %s -> %s" % (sid, p, exists, stored, real))

    # ── 写库 ──
    if dry:
        print("\n[--check] 未写任何改动。加 --apply 执行。")
        conn.close()
        return 0

    conn.execute("BEGIN")
    for s in src_rows:
        cur.execute("UPDATE local_sources SET video_count = "
                    "(SELECT COUNT(*) FROM local_videos WHERE source_id = ?) WHERE id = ?",
                    (s["id"], s["id"]))
    sql_lines = []
    for r, new in drift:
        old, newp = r["path"], r["path"].replace(m.to_host(r["path"]), new, 1) if False else new
        # 写回库里的容器视角路径
        new_db = new
        for c, h in m.pairs:
            if new == h or new.startswith(h.rstrip("/") + "/"):
                new_db = c.rstrip("/") + new[len(h.rstrip("/")):]
                break
        cur.execute("UPDATE local_videos SET path = ? WHERE id = ?", (new_db, r["id"]))
        sql_lines.append("-- id=%s code=%s" % (r["id"], r["code"]))
        sql_lines.append("UPDATE local_videos SET path = '%s' WHERE id = %s;  -- was: %s"
                         % (new_db.replace("'", "''"), r["id"], old.replace("'", "''")))

    pruned = 0
    if args.prune:
        for r, _why in gone:
            cur.execute("DELETE FROM local_videos WHERE id = ?", (r["id"],))
            sql_lines.append("DELETE FROM local_videos WHERE id = %s;  -- %s"
                             % (r["id"], r["path"].replace("'", "''")))
            pruned += 1

    conn.commit()
    conn.close()

    print("\n=== 已执行 ===")
    print("  改路径 %d 条 | 删行 %d 条 | 重算 video_count %d 个源" % (len(drift), pruned, len(src_rows)))

    if args.log_dir:
        os.makedirs(args.log_dir, exist_ok=True)
        stamp = utcnow()
        logp = os.path.join(args.log_dir, "mymoviedb-sync.log")
        with open(logp, "a", encoding="utf-8") as f:
            f.write("%s\tSYNC\tAPPLY\t%s\t%d\tOK\t路径漂移改写 %d 条\n"
                    % (stamp, args.db, len(drift), len(drift)))
            f.write("%s\tSYNC\tAPPLY\t%s\t%d\tOK\t重算 local_sources.video_count %d 个\n"
                    % (stamp, args.db, len(src_rows), len(src_rows)))
            if pruned:
                f.write("%s\tSYNC\tDELETE\t%s\t%d\tOK\t--prune 删除真消失记录\n"
                        % (stamp, args.db, pruned))
        with open(os.path.join(args.log_dir, "db-changes.sql"), "w", encoding="utf-8") as f:
            f.write("-- MyMovieDB 同步 SQL  生成于 %s  库: %s\n" % (stamp, db_host))
            f.write("\n".join(sql_lines) + "\n")
        with open(os.path.join(args.log_dir, "sync-gone.tsv"), "w", encoding="utf-8") as f:
            f.write("id\tcode\tpath\treason\n")
            for r, why in gone:
                f.write("%s\t%s\t%s\t%s\n" % (r["id"], r["code"], r["path"], why))
        print("  日志已写入 %s" % args.log_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
