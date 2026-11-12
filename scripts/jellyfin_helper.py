#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Jellyfin / Emby 影视整理助手（本地运行）

把 NAS 上新下载的影视资源，整理成 Jellyfin / Emby 能直接识别的结构：
  电影\\{中文名} {英文名}\\{原始发布名}.ext + movie.nfo + poster/fanart/thumb
  电视剧\\{中文名} {英文名}\\Season N\\{剧名} SxxEyy.ext + tvshow.nfo + season.nfo + 每集 nfo/剧照

子命令：
  scan    扫描新增资源，解析发布名，输出识别结果
  fetch   抓 TMDB 元数据（本地跑，或甩给 VPS 跑）生成 pack
  plan    根据 pack 生成整理计划（只打印，不动文件）
  apply   执行整理：重命名 / 移动 / 写 NFO / 下载图片
  push    把元数据与图片通过 API 写进 Jellyfin / Emby，并触发扫库
  run     scan → fetch → plan → apply → push 一条龙
  probe   检测媒体服务器到 TMDB 的真实连通性

典型用法：
  # 1) 看看最近下了什么，识别得对不对
  python scripts/jellyfin_helper.py scan --since 2d
  # 2) 抓元数据（本机不通 TMDB 就 --fetch-host vps，让 VPS 代抓）
  python scripts/jellyfin_helper.py fetch --since 2d --fetch-host vps
  # 3) 看整理计划
  python scripts/jellyfin_helper.py plan --since 2d
  # 4) 执行整理（写文件）
  python scripts/jellyfin_helper.py apply --since 2d
  # 5) 灌进 Jellyfin/Emby 并扫库
  python scripts/jellyfin_helper.py push --since 2d

依赖：requests（可选，缺失时用 urllib）、Python 3.8+
"""
import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
STATE_DIR = Path(os.environ.get("JELLYFIN_HELPER_HOME", Path.home() / ".jellyfin_helper"))
STATE_DIR.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------------ 配置
# 说明：token / 密码一律不放源码里（仓库是公开的）。
# 优先级：环境变量 > ~/.jellyfin_helper/config.json > 下面的默认值（仅路径/地址）
DEFAULT_CFG = {
    "movie_root": r"Y:\电影",
    "tv_root": r"Y:\电视剧",
    "vps": "root@47.101.178.144",
    "vps_workdir": "/tmp",
    "jellyfin": {"base": "http://192.168.1.179:8096", "token": "", "user": ""},
    "emby": {"base": "http://192.168.1.179:8097", "token": "", "user": ""},
    "metadata_language": "zh-CN",
    "fetch_host": "vps",
    "min_score": 28,
}
ENV_CFG = {
    "movie_root": "JELLYFIN_HELPER_MOVIE_ROOT",
    "tv_root": "JELLYFIN_HELPER_TV_ROOT",
    "vps": "JELLYFIN_HELPER_VPS",
}
ENV_TOKEN = {
    "jellyfin": "JELLYFIN_TOKEN",
    "emby": "EMBY_TOKEN",
}
ENV_USER = {
    "jellyfin": "JELLYFIN_USER",
    "emby": "EMBY_USER",
}
CFG_FILE = STATE_DIR / "config.json"
CFG = dict(DEFAULT_CFG)
if CFG_FILE.exists():
    try:
        CFG.update(json.load(open(CFG_FILE, encoding="utf-8")))
    except Exception:
        pass
for key, env in ENV_CFG.items():
    if os.environ.get(env):
        CFG[key] = os.environ[env]
for srv_key in ("jellyfin", "emby"):
    if os.environ.get(ENV_TOKEN.get(srv_key, "")):
        CFG.setdefault(srv_key, {})["token"] = os.environ[ENV_TOKEN[srv_key]]
    if os.environ.get(ENV_USER.get(srv_key, "")):
        CFG.setdefault(srv_key, {})["user"] = os.environ[ENV_USER[srv_key]]
if not os.environ.get("JELLYFIN_HELPER_NO_CONFIG_WRITE"):
    try:  # 生成/回写配置（回写时保留已有内容，含 token）
        json.dump(CFG, open(CFG_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    except Exception:
        pass

VIDEO_EXT = (".mp4", ".mkv", ".avi", ".wmv", ".ts", ".m2ts", ".mov", ".rmvb", ".flv", ".webm", ".mpg", ".mpeg")
# 迅雷/PT 还没下完的临时文件
INCOMPLETE_EXT = (".bt.xltd", ".xltd", ".!qb", ".tmp", ".part", ".aria2", ".crdownload", ".downloading")
INCOMPLETE = {}
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


# ================================================================== 工具
def log(msg):
    print(msg, flush=True)


def http(url, method="GET", data=None, headers=None, timeout=60, raw=False):
    h = {"User-Agent": UA}
    if headers:
        h.update(headers)
    body = None
    if isinstance(data, bytes):
        body = data
    elif data is not None:
        body = json.dumps(data).encode()
        h.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=body, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = resp.read()
    except urllib.error.HTTPError as e:
        content = e.read()
        if raw:
            return e.code, content
        return e.code, content.decode("utf-8", "ignore")
    except Exception as e:
        if raw:
            return None, repr(e).encode()
        return None, repr(e)
    if raw:
        return 200, content
    try:
        return 200, json.loads(content.decode("utf-8", "ignore"))
    except Exception:
        return 200, content.decode("utf-8", "ignore")


def download(url, dest: Path, force=False):
    if not url:
        return False
    if dest.exists() and dest.stat().st_size > 1000 and not force:
        return True
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = resp.read()
        if len(data) < 500:
            return False
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return True
    except Exception as e:
        log(f"      [下载失败] {url} -> {e}")
        return False


# ================================================================== 发布名解析
# 需要剔除的发行标签
TAG_PATTERNS = [
    r"\b\d{3,4}[pi]\b", r"\b(?:4k|8k|uhd)\b",
    r"\b(?:x|h|hevc|avc|mpeg2?|divx)[- ]?26[45]\b",
    r"\bweb[- ]?dl\b|\bweb[- ]?rip\b|\bweb\b|\bblu[- ]?ray\b|\bbluray\b|\bbdrip\b|\bbd\b|\bbrrip\b"
    r"|\bdvdrip\b|\bremastered\b|\bhdrip\b|\bhdtv\b|\bdvdr\b|\bdvd\b|\bweb-dl\b",
    r"\b(?:aac|ac3|eac3|dts(?:[- ]?hd)?|truehd|atmos|flac|mp3|opus|ddp?\+?5[ .]?1)\b",
    r"\b\d{1,2}[- ]?audios?\b",
    r"\b10bit\b|\b8bit\b|\bhdr10\+?\b|\bhdr\b|\bsdr\b|\bdolby[- ]?vision\b|\bdv\b|\bshq\b",
    r"\bchs\b|\bcht\b|\bbig5\b|\bgb18030\b|\bgb\b",
    r"中文字幕|中英双语|双语字幕|国英双语|国语中字|国语|粤语|简繁|繁简|中英双字|高清|超清|蓝光原盘"
    r"|修复版|内嵌字幕|外挂字幕|高清电影|蓝光电影|收藏版|抢先版|蓝光收藏版|中字|双语|中英|国配",
    r"\bhd\b|\bfhd\b|\buhd\b",
    r"\b(?:internal|limited|imax|extended|unrated|criterion|proper|repack|uncut)\b",
    r"\bcctv\d*(?:hd)?\b|\bcgtn\d*\b|\bbbc\d*(?:hd)?\b",
    r"\b(?:hhd|beast|dsnp|ntb|yts|yify|chd|amzn)\b",
]
GROUP_WORDS = {"cmct", "rarbg", "sonyhd", "ntb", "frds", "frdscore", "beast", "hds", "yts", "yify",
               "chd", "amzn", "evo", "sparks", "rartv", "nzbgeek", "ntv", "tracker", "ettv", "max"}
# 这些词不能从标题里删（是标题的一部分）
KEEP_WORDS = {"the", "a", "an", "of", "and", "in", "on", "to", "for", "at", "by", "with", "from",
              "ii", "iii", "iv", "vol", "volume", "part", "chapter"}


def _has_cjk(s):
    return bool(re.search(r"[\u4e00-\u9fff]", s or ""))


def _cjk_ratio(s):
    if not s:
        return 0.0
    cjk = len(re.findall(r"[\u4e00-\u9fff]", s))
    return cjk / max(1, len(re.sub(r"\s", "", s)))


def _split_cjk(text):
    """中英文之间插空格，方便按词切标签"""
    text = re.sub(r"([A-Za-z0-9])([\u4e00-\u9fff])", r"\1 \2", text)
    text = re.sub(r"([\u4e00-\u9fff])([A-Za-z0-9])", r"\1 \2", text)
    return text


ZH_TAG_WORDS = ("字幕", "双语", "发布", "高清", "修复", "合集", "特别篇", "收藏", "地址",
                "电影", "剧集", "网站", "www", "中字", "国语", "粤语", "版本", "下载", "片源")


def zh_from_text(text):
    """从一串文字里挑出最像「中文片名」的部分（排除 字幕/发布/合集 这类标签）"""
    if not text:
        return None
    chunks = re.split(r"[\[\]【】（）()\[\.\s·、,，:：|]+", text)
    for c in chunks:
        c = c.strip()
        if not (2 <= len(c) <= 16) or not _has_cjk(c):
            continue
        if re.search(r"\d", c):
            continue
        if any(w in c for w in ZH_TAG_WORDS):
            continue
        if _cjk_ratio(c) < 0.7:
            continue
        return c
    return None


def parse_release_name(filename, parent_dirs=()):
    """解析发布名 → {title, zh_hint, year, season, episode, is_episode, ext}"""
    stem = Path(filename).stem
    ext = Path(filename).suffix.lower()

    # 方括号内容 → 中文片名提示（要「基本全是中文」且不是标签才认）
    zh_hint = None
    for a, b in re.findall(r"\[([^\]]{1,80})\]|【([^】]{1,80})】", stem):
        t = (a or b).strip()
        if _cjk_ratio(t) >= 0.6 and len(t) <= 24 and not re.search(r"\d{4}", t) \
                and not any(w in t for w in ZH_TAG_WORDS):
            zh_hint = t
            break
    if not zh_hint:
        # 退而求其次：文件夹名里的中文（很多国产剧中文名写在文件夹上）
        for d in parent_dirs:
            zh_hint = zh_from_text(d)
            if zh_hint:
                break

    # 季集号
    season = episode = None
    ep_pat = re.compile(r"[Ss](\d{1,2})[ ._-]?[Ee](\d{1,3})"
                        r"|(?:^|[^A-Za-z0-9])EP(\d{1,3})(?:[^0-9]|$)"
                        r"|(?:^|[^A-Za-z0-9])E(\d{1,3})(?:[^0-9]|$)", re.I)
    m_ep = ep_pat.search(stem)
    if m_ep:
        if m_ep.group(1):
            season, episode = int(m_ep.group(1)), int(m_ep.group(2))
        else:
            episode = int(m_ep.group(3) or m_ep.group(4))
    # 集号后面的片段是「分集小标题」（如 S01E01.Welcome.to.Africa），要从剧名里去掉
    ep_sub = None
    if m_ep:
        tail = stem[m_ep.end():]
        tail = re.split(r"[\[\【]|\d{4}|1080|720|2160|x26[45]|H26[45]", tail, maxsplit=1, flags=re.I)[0]
        tail = re.sub(r"[._\-\s]+", " ", tail).strip()
        if 0 < len(tail) <= 60 and not re.search(r"\d{3,4}", tail):
            ep_sub = tail
    # 目录里的 Season N / 第N季
    if season is None:
        for d in parent_dirs:
            m2 = re.search(r"(?:Season|S)\s*(\d{1,2})", d, re.I) or re.search(r"第\s*(\d{1,2})\s*季", d)
            if m2:
                season = int(m2.group(1))
                break
    if episode is not None and season is None:
        season = 1

    # 年份
    year = None
    year_str = None
    my = re.search(r"(?<!\d)((?:19|20)\d{2})(?!\d)", stem)
    if my:
        y = int(my.group(1))
        if 1900 < y < 2030:
            year, year_str = y, my.group(1)

    # 清洗标题：剧集只取集号之前的部分（后面是小标题）
    base = stem[:m_ep.start()] if (m_ep and m_ep.start() > 0) else stem
    work = re.sub(r"[\[\【][^\]】]{0,80}[\]】]", " ", base)             # 去方括号
    if year_str:
        work = re.sub(re.escape(year_str), " ", work)                   # 去年份
    work = _split_cjk(work)
    work = re.sub(r"[._]+", " ", work)
    work = re.sub(r"\s+", " ", work).strip()
    for pat in TAG_PATTERNS:
        work = re.sub(pat, " ", work, flags=re.I)
    work = re.sub(r"-", " ", work)
    work = re.sub(r"\s+", " ", work).strip()

    # 中文片名 + 英文片名（国产剧常见："非洲：地球的野性家园.Africa.Earths.Wild.Home"）
    zh_title = None
    m2 = re.match(r"^([\u4e00-\u9fff：:，,、\s\-]{2,40})\s+(.*)$", work)
    if m2:
        zh_title = m2.group(1).strip(" -:：")
        work = m2.group(2).strip()
        if not zh_hint:
            zh_hint = zh_title

    toks = [t for t in work.split(" ") if t]
    # 结尾的压制组标签（-CMCT / .SPARKS / -EVO 这类）：全大写或含数字，且其它部分还有内容
    while len(toks) > 1:
        last = toks[-1]
        low = last.lower().strip(".")
        is_group = (low in GROUP_WORDS
                    or (2 <= len(low) <= 10 and re.search(r"\d", low) and low.isalnum())
                    or (3 <= len(low) <= 10 and last.isupper() and last.isalnum() and low not in KEEP_WORDS))
        if is_group:
            toks.pop()
            continue
        break
    title = " ".join(toks).strip(" -.,()[]{}<>【】_")
    title = re.sub(r"\s{2,}", " ", title).strip()

    return {"title": title, "zh_hint": zh_hint, "zh_title": zh_title, "year": year, "season": season,
            "episode": episode, "episode_sub": ep_sub, "is_episode": episode is not None, "ext": ext}


# ================================================================== 扫描
def parse_since(s):
    """'2d' / '12h' / '30m' / '7' → 秒数；'all' → 0（不过滤）"""
    if isinstance(s, (int, float)):
        return int(s * 86400)
    s = (s or "2d").strip().lower()
    if s in ("all", "0", "none"):
        return 0
    m = re.match(r"^(\d+(?:\.\d+)?)\s*([dhm]?)$", s)
    if not m:
        return 2 * 86400
    n = float(m.group(1))
    unit = m.group(2) or "d"
    return int(n * {"d": 86400, "h": 3600, "m": 60}[unit])


def iter_new_files(root: Path, since_days=2, paths=None):
    """返回 [(file_path, 解析结果)]；顺带把「还没下完」的文件记下来"""
    out = []
    roots = [Path(p) for p in paths] if paths else [root]
    secs = parse_since(since_days)
    cutoff = time.time() - secs if secs else 0
    for r in roots:
        if not r.exists():
            log(f"  ! 目录不存在: {r}")
            continue
        for dirpath, dirnames, filenames in os.walk(r):
            d = Path(dirpath)
            for fn in filenames:
                low = fn.lower()
                if any(low.endswith(x) for x in INCOMPLETE_EXT):
                    INCOMPLETE.setdefault(str(d), []).append(fn)
                    continue
                if not low.endswith(VIDEO_EXT):
                    continue
                fp = d / fn
                try:
                    if cutoff and fp.stat().st_mtime < cutoff:
                        continue
                except OSError:
                    continue
                parent_dirs = tuple(d.parts[-2:][::-1])
                out.append((fp, parse_release_name(fn, parent_dirs)))
    return out


def read_nfo_ids(folder: Path):
    """读目录里的 NFO，取出已知的 tmdbid/imdbid/标题（已整理过的资源靠它直接定位）"""
    for name in ("movie.nfo", "tvshow.nfo"):
        p = folder / name
        if not p.exists():
            continue
        try:
            t = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        def g(tag):
            m = re.search(rf"<{tag}>([^<]*)</{tag}>", t)
            return m.group(1).strip() if m else None
        tm = g("tmdbid") or (re.search(r'<uniqueid[^>]*type="tmdb"[^>]*>([^<]+)</uniqueid>', t) or [None, None])[1]
        im = g("imdbid") or g("imdb_id") or (re.search(r'<uniqueid[^>]*type="imdb"[^>]*>([^<]+)</uniqueid>', t) or [None, None])[1]
        yr = g("year")
        return {"tmdb_id": int(tm) if tm and str(tm).isdigit() else None,
                "imdb_id": im, "title": g("title"), "original_title": g("originaltitle"),
                "year": int(yr) if yr and yr.isdigit() else None, "file": name}
    return None


def group_items(scanned):
    """把扫描结果聚成「影片」或「剧集」单元"""
    movies, series = [], {}
    for fp, info in scanned:
        if info["is_episode"]:
            key = (str(fp.parent), info["season"] or 1)
            series.setdefault(key, {"kind": "tv", "season": info["season"] or 1,
                                    "dir": fp.parent, "files": [], "info": info, "nfo": None})
            series[key]["files"].append((fp, info))
        else:
            movies.append({"kind": "movie", "file": fp, "info": info,
                           "nfo": read_nfo_ids(fp.parent)})
    for k in list(series):
        eps = series[k]["files"]
        series[k]["files"] = sorted(eps, key=lambda x: x[1]["episode"] or 0)
        # 剧集名：取所有分集里去掉集号后最长/最常见的一个
        names = [i["title"] for _, i in eps]
        series[k]["info"]["title"] = max(set(names), key=names.count) if names else ""
        zh = [i["zh_hint"] for _, i in eps if i["zh_hint"]]
        series[k]["info"]["zh_hint"] = zh[0] if zh else None
        years = [i["year"] for _, i in eps if i["year"]]
        series[k]["info"]["year"] = max(set(years), key=years.count) if years else None
        # 剧集 NFO 在剧集根目录
        root = series[k]["dir"]
        for _ in range(2):
            if (root.parent / "tvshow.nfo").exists():
                root = root.parent
                break
            root = root.parent
        series[k]["nfo"] = read_nfo_ids(root)
        if series[k]["nfo"] and not series[k]["info"]["zh_hint"]:
            series[k]["info"]["zh_hint"] = series[k]["nfo"].get("title")
    return movies, list(series.values())


def scan_roots(args):
    """按 --only 决定扫哪些库，返回 (scanned, roots)"""
    roots = []
    only = getattr(args, "only", "both")
    if only in ("movie", "both"):
        roots.append(Path(CFG["movie_root"]))
    if only in ("tv", "both"):
        roots.append(Path(CFG["tv_root"]))
    scanned = []
    for r in roots:
        scanned += iter_new_files(r, args.since, args.paths if only == "both" else None)
    return scanned, roots


def cmd_scan(args):
    INCOMPLETE.clear()
    scanned, roots = scan_roots(args)
    movies, series = group_items(scanned)
    log(f"\n扫描 {', '.join(str(r) for r in roots)}（最近 {args.since}）\n")
    log("── 电影 ──")
    for m in movies:
        i = m["info"]
        nfo = m.get("nfo") or {}
        tag = f"  [NFO tmdb={nfo.get('tmdb_id')}]" if nfo.get("tmdb_id") else ""
        log(f"  {m['file'].name}\n      → 标题「{i['title']}」 年份:{i['year']} 中文提示:{i['zh_hint'] or '-'}{tag}")
    log("\n── 剧集 ──")
    for s in series:
        i = s["info"]
        nfo = s.get("nfo") or {}
        eps = ",".join(str(x[1]["episode"]) for x in s["files"])
        tag = f"  [NFO tmdb={nfo.get('tmdb_id')}]" if nfo.get("tmdb_id") else ""
        log(f"  {s['dir']}  (Season {s['season']})\n      → 剧名「{i['title']}」 年份:{i['year']} "
            f"中文提示:{i['zh_hint'] or '-'} 集数:{eps}{tag}")
    if not movies and not series:
        log("  （没有发现新增视频文件）")
    if INCOMPLETE:
        log("\n⚠ 以下文件还在下载中，本次不处理：")
        for d, files in INCOMPLETE.items():
            log(f"   {d}\n      {', '.join(files)}")
    save_state("scanned", {"movies": movies, "series": series})
    log(f"\n已保存到 {STATE_DIR/'scanned.json'}")


# ================================================================== 抓元数据
def fetch_vps(spec, out_json):
    """把抓取任务甩给 VPS（它能访问 www.themoviedb.org）"""
    host = CFG["vps"]
    local_mod = HERE / "_tmdb_fetch.py"
    spec_p = STATE_DIR / "_spec.json"
    out_p = STATE_DIR / "_spec_out.json"
    json.dump(spec, open(spec_p, "w", encoding="utf-8"), ensure_ascii=False)
    subprocess.run(["scp", "-q", "-o", "BatchMode=yes", str(local_mod), f"{host}:{CFG['vps_workdir']}/_tmdb_fetch.py"], check=True)
    subprocess.run(["scp", "-q", "-o", "BatchMode=yes", str(spec_p), f"{host}:{CFG['vps_workdir']}/_spec.json"], check=True)
    log(f"  已在 VPS 上执行抓取（{host}）…")
    r = subprocess.run(["ssh", "-o", "BatchMode=yes", host,
                        f"python3 {CFG['vps_workdir']}/_tmdb_fetch.py {CFG['vps_workdir']}/_spec.json "
                        f"{CFG['vps_workdir']}/_spec_out.json"],
                       capture_output=True, timeout=1800)
    log("  " + (r.stdout.decode("utf-8", "ignore").strip().replace("\n", "\n  ")))
    if r.returncode != 0:
        log("  VPS 抓取失败: " + r.stderr.decode("utf-8", "ignore")[:300])
        return None
    subprocess.run(["scp", "-q", "-o", "BatchMode=yes", f"{host}:{CFG['vps_workdir']}/_spec_out.json", str(out_p)], check=True)
    return json.load(open(out_p, encoding="utf-8"))


def fetch_local(spec, out_json):
    local_mod = HERE / "_tmdb_fetch.py"
    spec_p = STATE_DIR / "_spec.json"
    json.dump(spec, open(spec_p, "w", encoding="utf-8"), ensure_ascii=False)
    r = subprocess.run([sys.executable, str(local_mod), str(spec_p), str(out_json)],
                       capture_output=True, timeout=1800)
    log("  " + (r.stdout.decode("utf-8", "ignore").strip().replace("\n", "\n  ")))
    if r.returncode != 0:
        log("  本地抓取失败: " + r.stderr.decode("utf-8", "ignore")[:300])
        return None
    return json.load(open(out_json, encoding="utf-8"))


def cmd_fetch(args):
    state = rescan(args)          # 每次都以当前 --since 重新扫描，避免用旧状态
    movies, series = state["movies"], state["series"]
    spec = []
    idx = 0
    for m in movies:
        i = m["info"]
        nfo = m.get("nfo") or {}
        spec.append({"kind": "movie", "query": i["title"], "year": i["year"], "zh_title": i["zh_hint"],
                     "tmdb_id": nfo.get("tmdb_id"), "ref": {"i": idx, "kind": "movie"}})
        idx += 1
    for s in series:
        i = s["info"]
        nfo = s.get("nfo") or {}
        spec.append({"kind": "tv", "query": i["title"], "year": i["year"], "zh_title": i["zh_hint"],
                     "season": s["season"], "tmdb_id": nfo.get("tmdb_id"),
                     "max_eps": max([x[1]["episode"] or 0 for x in s["files"]] or [0]),
                     "ref": {"i": idx, "kind": "tv"}})
        idx += 1
    log(f"\n需要抓取 {len(spec)} 个条目")
    if not spec:
        return
    out_json = STATE_DIR / "pack.json"
    res = fetch_vps(spec, out_json) if args.fetch_host == "vps" else fetch_local(spec, out_json)
    if res is None:
        return
    json.dump(res, open(out_json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    ok = sum(1 for r in res if r.get("best"))
    log(f"\n命中 {ok}/{len(res)}  →  {out_json}")


def rescan(args):
    scanned, _ = scan_roots(args)
    movies, series = group_items(scanned)
    state = {"movies": movies, "series": series}
    save_state("scanned", state)
    return state


# ================================================================== 计划
def safe_name(name, maxlen=110):
    """Windows 文件名清洗：去掉非法字符（<>:"/\\|?*），压缩空格，去掉结尾的点/空格"""
    s = str(name or "")
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", s)          # 非法字符 → 空格
    s = re.sub(r"\s+", " ", s).strip()
    s = s.rstrip(". ")
    if len(s) > maxlen:
        s = s[:maxlen].rstrip(". ")
    return s


def build_plan():
    state = load_state("scanned")
    pack = load_state("pack")
    if state is None:
        log("没有扫描结果，先跑 scan")
        return []
    if pack is None:
        log("没有元数据 pack，先跑 fetch")
        return []
    plan = []
    pmap = {}
    pmap2 = {}
    for rec in pack:
        ref = rec.get("ref") or {}
        if ref.get("i") is not None:
            pmap[ref["i"]] = rec
        pmap2.setdefault((rec.get("query"), rec.get("year")), rec)
    for idx, m in enumerate(state["movies"]):
        i = m["info"]
        rec = pmap.get(idx) or pmap2.get((i["title"], i["year"]))
        meta = (rec or {}).get("meta")
        if not meta:
            plan.append({"kind": "movie", "skip": "未匹配到 TMDB", "src": str(m["file"]), "info": i})
            continue
        folder = safe_name(f"{meta['title']} {meta['original_title']}")
        plan.append({"kind": "movie", "src": str(m["file"]),
                     "dst_dir": str(Path(CFG["movie_root"]) / folder),
                     "dst_file": Path(m["file"]).name, "meta": meta})
    base = len(state["movies"])
    for j, s in enumerate(state["series"]):
        i = s["info"]
        rec = pmap.get(base + j) or pmap2.get((i["title"], i["year"]))
        meta = (rec or {}).get("meta")
        if not meta:
            plan.append({"kind": "tv", "skip": "未匹配到 TMDB", "src": str(s["dir"]), "info": i})
            continue
        folder = safe_name(f"{meta['title']} {meta['original_title']}")
        plan.append({"kind": "tv", "src": str(s["dir"]), "dst_dir": str(Path(CFG["tv_root"]) / folder),
                     "season": s["season"], "files": [(str(fp), inf["episode"]) for fp, inf in s["files"]],
                     "meta": meta})
    return plan


def cmd_plan(args):
    plan = build_plan()
    log("\n" + "=" * 78)
    for p in plan:
        if p.get("skip"):
            log(f"[跳过] {p['kind']}: {p['src']}\n        原因: {p['skip']}（不会强行匹配）")
            continue
        m = p["meta"]
        log(f"[{p['kind']}] {m.get('title')} / {m.get('original_title')} ({m.get('year')}) "
            f"tmdb={m.get('tmdb_id')} imdb={m.get('imdb_id')}")
        if p["kind"] == "movie":
            log(f"     {p['src']}\n  -> {p['dst_dir']}\n     └ {p['dst_file']}")
        else:
            log(f"     {p['src']}\n  -> {p['dst_dir']}\\Season {p['season']}")
            for fp, ep in p["files"]:
                ext = Path(fp).suffix
                log(f"     └ {m.get('title')} {m.get('original_title')} S{p['season']:02d}E{ep:02d}{ext}")
    log("=" * 78)
    save_state("plan", plan)
    log(f"计划已保存 {STATE_DIR/'plan.json'}（apply 会用它）")


# ================================================================== 执行
def xml_esc(s):
    if s is None:
        return ""
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


def movie_nfo(meta):
    b = [f"  <title>{xml_esc(meta.get('title'))}</title>",
         f"  <originaltitle>{xml_esc(meta.get('original_title'))}</originaltitle>",
         f"  <sorttitle>{xml_esc(meta.get('title'))}</sorttitle>",
         f"  <plot>{xml_esc(meta.get('overview'))}</plot>",
         f"  <outline>{xml_esc(meta.get('overview'))}</outline>"]
    if meta.get("tagline"):
        b.append(f"  <tagline>{xml_esc(meta['tagline'])}</tagline>")
    if meta.get("runtime_min"):
        b.append(f"  <runtime>{meta['runtime_min']}</runtime>")
    if meta.get("year"):
        b.append(f"  <year>{meta['year']}</year>")
    if meta.get("release_date"):
        b.append(f"  <releasedate>{meta['release_date']}</releasedate>")
        b.append(f"  <premiered>{meta['release_date']}</premiered>")
    if meta.get("rating"):
        b.append(f"  <rating>{round(float(meta['rating']), 1)}</rating>")
        b.append(f"  <votes>{meta.get('rating_count') or 0}</votes>")
    for g in meta.get("genres") or []:
        b.append(f"  <genre>{xml_esc(g)}</genre>")
    b.append(f"  <imdbid>{xml_esc(meta.get('imdb_id'))}</imdbid>")
    b.append(f"  <tmdbid>{meta.get('tmdb_id')}</tmdbid>")
    b.append(f"  <uniqueid type=\"imdb\" default=\"true\">{xml_esc(meta.get('imdb_id'))}</uniqueid>")
    b.append(f"  <uniqueid type=\"tmdb\" default=\"true\">{meta.get('tmdb_id')}</uniqueid>")
    for p in (meta.get("people") or [])[:8]:
        b.append("  <actor>")
        b.append(f"    <name>{xml_esc(p.get('name'))}</name>")
        if p.get("character"):
            b.append(f"    <role>{xml_esc(p['character'])}</role>")
        b.append("    <type>Actor</type>")
        b.append("  </actor>")
    b.append("  <lockdata>false</lockdata>")
    return '<?xml version="1.0" encoding="utf-8" standalone="yes"?>\n<movie>\n' + "\n".join(b) + "\n</movie>\n"


def tvshow_nfo(meta):
    b = [f"  <title>{xml_esc(meta.get('title'))}</title>",
         f"  <originaltitle>{xml_esc(meta.get('original_title'))}</originaltitle>",
         f"  <sorttitle>{xml_esc(meta.get('title'))}</sorttitle>",
         f"  <plot>{xml_esc(meta.get('overview'))}</plot>",
         f"  <outline>{xml_esc(meta.get('overview'))}</outline>"]
    if meta.get("year"):
        b.append(f"  <year>{meta['year']}</year>")
    b.append("  <status>Ended</status>")
    b.append("  <season>-1</season>")
    b.append("  <episode>-1</episode>")
    if meta.get("rating"):
        b.append(f"  <rating>{round(float(meta['rating']), 1)}</rating>")
    for g in meta.get("genres") or []:
        b.append(f"  <genre>{xml_esc(g)}</genre>")
    b.append(f"  <imdbid>{xml_esc(meta.get('imdb_id'))}</imdbid>")
    b.append(f"  <tmdbid>{meta.get('tmdb_id')}</tmdbid>")
    b.append(f"  <uniqueid type=\"imdb\" default=\"true\">{xml_esc(meta.get('imdb_id'))}</uniqueid>")
    b.append(f"  <uniqueid type=\"tmdb\" default=\"true\">{meta.get('tmdb_id')}</uniqueid>")
    b.append("  <lockdata>false</lockdata>")
    return '<?xml version="1.0" encoding="utf-8" standalone="yes"?>\n<tvshow>\n' + "\n".join(b) + "\n</tvshow>\n"


def season_nfo(meta, season_no):
    s = meta.get("season") or {}
    b = [f"  <title>第 {season_no} 季</title>",
         f"  <showtitle>{xml_esc(meta.get('title'))}</showtitle>",
         f"  <plot>{xml_esc(s.get('overview'))}</plot>",
         f"  <seasonnumber>{season_no}</seasonnumber>"]
    if s.get("year"):
        b.append(f"  <year>{s['year']}</year>")
    b.append("  <lockdata>false</lockdata>")
    return '<?xml version="1.0" encoding="utf-8" standalone="yes"?>\n<season>\n' + "\n".join(b) + "\n</season>\n"


def episode_nfo(meta, ep):
    b = [f"  <title>{xml_esc(ep.get('title'))}</title>",
         f"  <showtitle>{xml_esc(meta.get('title'))}</showtitle>",
         f"  <season>{ep.get('season')}</season>",
         f"  <episode>{ep.get('episode')}</episode>"]
    if ep.get("aired"):
        b.append(f"  <aired>{ep['aired']}</aired>")
        b.append(f"  <premiered>{ep['aired']}</premiered>")
    b.append(f"  <plot>{xml_esc(ep.get('overview'))}</plot>")
    if ep.get("rating"):
        b.append(f"  <rating>{round(float(ep['rating']), 1)}</rating>")
    if ep.get("runtime_min"):
        b.append(f"  <runtime>{ep['runtime_min']}</runtime>")
    b.append("  <lockdata>false</lockdata>")
    return ('<?xml version="1.0" encoding="utf-8" standalone="yes"?>\n<episodedetails>\n'
            + "\n".join(b) + "\n</episodedetails>\n")


def write_text(path: Path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def cmd_apply(args):
    plan = load_state("plan")
    if plan is None:
        plan = build_plan()
    if not plan:
        log("没有计划，先跑 plan")
        return
    for p in plan:
        if p.get("skip"):
            log(f"[跳过] {p['src']}（{p['skip']}）")
            continue
        meta = p["meta"]
        dst = Path(p["dst_dir"])
        if p["kind"] == "movie":
            src = Path(p["src"])
            dst.mkdir(parents=True, exist_ok=True)
            target = dst / p["dst_file"]
            if src.resolve() != target.resolve():
                if target.exists():
                    log(f"  ! 目标已存在，跳过移动: {target}")
                else:
                    shutil.move(str(src), str(target))
                    log(f"  移动 → {target}")
            write_text(dst / "movie.nfo", movie_nfo(meta))
            download(meta.get("poster"), dst / "poster.jpg")
            download(meta.get("backdrop"), dst / "fanart.jpg")
            download(meta.get("poster"), dst / "thumb.jpg")
            log(f"  写入 movie.nfo + 海报/背景图")
        else:
            sdir = dst / f"Season {p['season']}"
            sdir.mkdir(parents=True, exist_ok=True)
            base = safe_name(f"{meta['title']} {meta['original_title']}")
            eps_meta = {e["episode"]: e for e in (meta.get("episodes") or [])}
            for fp, ep in p["files"]:
                src = Path(fp)
                ext = src.suffix
                target = sdir / f"{base} S{p['season']:02d}E{ep:02d}{ext}"
                if src.resolve() != target.resolve() and not target.exists():
                    shutil.move(str(src), str(target))
                    log(f"  移动 → {target.name}")
                em = eps_meta.get(ep)
                if em:
                    write_text(sdir / f"{base} S{p['season']:02d}E{ep:02d}.nfo", episode_nfo(meta, em))
                    download(em.get("still"), sdir / f"{base} S{p['season']:02d}E{ep:02d}-thumb.jpg")
            write_text(dst / "tvshow.nfo", tvshow_nfo(meta))
            write_text(sdir / "season.nfo", season_nfo(meta, p["season"]))
            download(meta.get("poster"), dst / "poster.jpg")
            download(meta.get("backdrop"), dst / "fanart.jpg")
            download(meta.get("poster"), dst / "thumb.jpg")
            download((meta.get("season") or {}).get("poster"), sdir / "season-poster.jpg")
            log(f"  写入 tvshow/season/分集 NFO + 图片")
    log("\n整理完成")


# ================================================================== 推送到服务器
def srv(which):
    s = CFG.get(which) or {}
    if not s.get("token"):
        log(f"[!] 没有 {which} 的 token。")
        log(f"    请在 {CFG_FILE} 里填，或设环境变量 "
            f"{ENV_TOKEN.get(which, '')} / {ENV_USER.get(which, '')}")
        sys.exit(2)
    return s


def api_srv(which, path, method="GET", data=None, timeout=90, raw=False):
    s = srv(which)
    url = s["base"] + path
    headers = {"Authorization": 'MediaBrowser Token="%s"' % s["token"]}
    if isinstance(data, bytes):
        headers["Content-Type"] = "image/jpeg"
        st, body = http(url, method, data, headers, timeout, raw=True)
        return st, body
    if data is not None:
        headers["Content-Type"] = "application/json"
    st, body = http(url, method, data, headers, timeout, raw=raw)
    return st, body


def upload_image(which, item_id, image_type, file_path: Path):
    if not file_path.exists():
        return False
    b64 = base64.b64encode(file_path.read_bytes()).decode()
    st, _ = api_srv(which, f"/Items/{item_id}/Images/{image_type}", "POST", b64.encode())
    return st in (200, 204)


def cmd_push(args):
    plan = load_state("plan")
    if plan is None:
        plan = build_plan()
    targets = [which for which in ("jellyfin", "emby") if not args.server or which == args.server]
    for which in targets:
        s = srv(which)
        log(f"\n── {which} ({s['base']}) ──")
        _, libs = api_srv(which, "/Library/VirtualFolders")
        if isinstance(libs, str):
            log(f"  ! 拿不到库列表: {libs[:120]}")
            continue
        for lib in libs:
            if lib.get("CollectionType") not in ("movies", "tvshows"):
                continue
            st, body = api_srv(which, f"/Users/{s['user']}/Items?ParentId={lib['ItemId']}&Recursive=true"
                                     f"&Fields=Path,ProviderIds,Type&Limit=5000")
            items = (body.get("Items") or []) if isinstance(body, dict) else []
            for p in plan:
                if p.get("skip"):
                    continue
                m = p["meta"]
                title = m.get("title")
                orig = m.get("original_title")
                if p["kind"] == "movie":
                    hit = next((i for i in items if i.get("Type") == "Movie"
                                and (title in (i.get("Name") or "") or orig in (i.get("Name") or "")
                                     or title in (i.get("Path") or "") or orig in (i.get("Path") or ""))), None)
                    if not hit:
                        continue
                    payload = {"Name": title, "OriginalTitle": orig, "SortName": title,
                               "Overview": m.get("overview"), "Genres": m.get("genres") or [],
                               "CommunityRating": float(m["rating"]) if m.get("rating") else None,
                               "ProductionYear": m.get("year"),
                               "PremiereDate": (m.get("release_date") + "T00:00:00Z") if m.get("release_date") else None,
                               "RuntimeTicks": int(m["runtime_min"] * 10_000_000) if m.get("runtime_min") else None,
                               "ProviderIds": {"Imdb": m.get("imdb_id"), "Tmdb": str(m.get("tmdb_id"))}}
                    payload = {k: v for k, v in payload.items() if v not in (None, [], {})}
                    api_srv(which, f"/Items/{hit['Id']}", "POST", payload)
                    d = Path(p["dst_dir"])
                    upload_image(which, hit["Id"], "Primary", d / "poster.jpg")
                    upload_image(which, hit["Id"], "Backdrop", d / "fanart.jpg")
                    upload_image(which, hit["Id"], "Thumb", d / "thumb.jpg")
                    log(f"  ✓ {title}（元数据+图片已推送）")
                else:
                    hit = next((i for i in items if i.get("Type") == "Series"
                                and (title in (i.get("Name") or "") or orig in (i.get("Name") or "")
                                     or title in (i.get("Path") or "") or orig in (i.get("Path") or ""))), None)
                    if not hit:
                        continue
                    payload = {"Name": title, "OriginalTitle": orig, "SortName": title,
                               "Overview": m.get("overview"), "Genres": m.get("genres") or [],
                               "CommunityRating": float(m["rating"]) if m.get("rating") else None,
                               "ProductionYear": m.get("year"), "Status": "Ended",
                               "ProviderIds": {"Imdb": m.get("imdb_id"), "Tmdb": str(m.get("tmdb_id"))}}
                    payload = {k: v for k, v in payload.items() if v not in (None, [], {})}
                    api_srv(which, f"/Items/{hit['Id']}", "POST", payload)
                    d = Path(p["dst_dir"])
                    upload_image(which, hit["Id"], "Primary", d / "poster.jpg")
                    upload_image(which, hit["Id"], "Backdrop", d / "fanart.jpg")
                    upload_image(which, hit["Id"], "Thumb", d / "thumb.jpg")
                    log(f"  ✓ {title}（剧集元数据已推送）")
                    # 分集：标题 / 简介 / 评分 / 剧照
                    base = safe_name(f"{m.get('title')} {m.get('original_title')}")
                    sdir = d / f"Season {p['season']}"
                    eps_meta = {e["episode"]: e for e in (m.get("episodes") or [])}
                    for fp, ep in p["files"]:
                        em = eps_meta.get(ep)
                        if not em:
                            continue
                        ext = Path(fp).suffix
                        ep_path = str(sdir / f"{base} S{p['season']:02d}E{ep:02d}{ext}")
                        ehit = next((i for i in items if i.get("Type") == "Episode" and i.get("Path") == ep_path), None)
                        if not ehit:
                            ehit = next((i for i in items if i.get("Type") == "Episode"
                                         and ep_path.split("\\")[-1] in (i.get("Path") or "")), None)
                        if not ehit:
                            continue
                        ep_payload = {"Name": em.get("title"), "Overview": em.get("overview"),
                                      "CommunityRating": float(em["rating"]) if em.get("rating") else None,
                                      "PremiereDate": (em["aired"] + "T00:00:00Z") if em.get("aired") else None,
                                      "IndexNumber": ep, "ParentIndexNumber": p["season"]}
                        ep_payload = {k: v for k, v in ep_payload.items() if v not in (None, [], {})}
                        api_srv(which, f"/Items/{ehit['Id']}", "POST", ep_payload)
                        upload_image(which, ehit["Id"], "Primary",
                                     sdir / f"{base} S{p['season']:02d}E{ep:02d}-thumb.jpg")
                    log(f"    · 分集 {len(p['files'])} 集已推送")
        # 触发扫库
        api_srv(which, "/Library/Refresh", "POST", b"")
        log(f"  → 已触发 {which} 扫库")


# ================================================================== 连通性探测
def local_probe(ips):
    """本机精确探测：直接连真实 IP（SNI/Host 保持 api.themoviedb.org）并看响应体是不是 TMDB 的 JSON。
    （污染 IP 会连到 twitter/facebook 等真实站点，光看状态码分不出来）"""
    import subprocess
    curl = "curl.exe" if os.name == "nt" else "curl"
    out = []
    probes = [("走本机 DNS（可能被污染）", None)]
    probes += [(f"真实 IP {ip}", ip) for ip in ips]
    for name, ip in probes:
        cmd = [curl, "-s", "-m", "12", "-w", "\n__CODE__%{http_code}",
               "https://api.themoviedb.org/3/configuration"]
        if ip:
            cmd += ["--resolve", f"api.themoviedb.org:443:{ip}"]
        try:
            p = subprocess.run(cmd, capture_output=True, timeout=20)
            text = p.stdout.decode("utf-8", "ignore")
            code = text.rsplit("__CODE__", 1)[-1].strip() if "__CODE__" in text else "?"
            body = text.rsplit("__CODE__", 1)[0].strip()[:140]
            is_tmdb = '"status_code"' in body
            out.append((name, code, is_tmdb, body))
        except Exception as e:
            out.append((name, "ERR", False, repr(e)[:80]))
    return out


def cmd_probe(args):
    ips = args.ips or ["65.9.130.24", "65.9.130.126", "54.192.138.65"]
    log("【本机精确探测】看响应体是不是 TMDB 的 JSON\n")
    for name, code, is_tmdb, body in local_probe(ips):
        mark = "✅ 真的到 TMDB 了" if is_tmdb else "❌ 不是 TMDB（被污染到别的站点了）"
        log(f"  {name:24s} HTTP {code:>4}  {mark}")
        log(f"      {body[:100]}")

    s = srv(args.server or "jellyfin")
    st, body = api_srv(args.server or "jellyfin",
                       f"/Users/{s['user']}/Items?ParentId=3227ce1e069754c594af25ea66d69fc7"
                       f"&Recursive=true&Fields=Path,Type&Limit=500")
    items = (body.get("Items") or []) if isinstance(body, dict) else []
    mv = next((i for i in items if i.get("Type") == "Movie"), None)
    if not mv:
        log("\n找不到可用的影片做探测载体，跳过服务器内探测")
        return
    log(f"\n【{args.server or 'jellyfin'} 容器内探测】用 {mv.get('Name')} 发起请求\n")
    tests = [("污染域名（对照，应失败）", "http://api.themoviedb.org/probe.txt")]
    for ip in ips:
        tests.append((f"真实 IP {ip}", f"http://{ip.replace('.', '-')}.sslip.io/probe.txt"))
    for name, url in tests:
        t0 = time.time()
        api_srv(args.server or "jellyfin",
                f"/Items/{mv['Id']}/RemoteImages/Download?type=Primary&imageUrl={urllib.parse.quote(url)}",
                "POST", b"{}", timeout=90)
        ms = int((time.time() - t0) * 1000)
        log(f"  {name:24s} {ms:>6} ms  {verdict(args.server or 'jellyfin')}")


def verdict(server="jellyfin"):
    """看服务器日志尾部判断这次请求到底发生了什么（单看 HTTP 状态码分不出 403 和拒连）"""
    _, files = api_srv(server, "/System/Logs")
    if not isinstance(files, list) or not files:
        return "判断不了"
    newest = sorted(files, key=lambda x: x.get("Name", ""))[-1]
    _, body = api_srv(server, f"/System/Logs/Log?name={newest['Name']}&tail=150")
    if not isinstance(body, str):
        return "判断不了"
    # 只看最后一次探测（最后一个 RemoteImages/Download 之后的内容）
    idx = body.rfind("RemoteImages/Download")
    tail = body[idx:] if idx >= 0 else body[-3000:]
    m = re.search(r"does not indicate success:\s*(\d{3})", tail)
    if m:
        code = m.group(1)
        if code in ("403", "404", "400", "401"):
            return f"连上了（远端回 HTTP {code}；TMDB 对陌生 Host 也回 403，能握手就说明网络通）"
        return f"远端返回 HTTP {code}（多半是被污染到的黑洞/拦截页）→ 不可用"
    if "timed out" in tail or "Timeout" in tail:
        return "连接超时 → 连不上（DNS 污染或被封）"
    if ("Connection refused" in tail or "No such host" in tail
            or "actively refused" in tail or "attempt" in tail):
        return "连接被拒/解析失败 → 连不上"
    return "结果不明"


# ================================================================== 状态
def save_state(key, data):
    json.dump(data, open(STATE_DIR / f"{key}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)


def load_state(key):
    p = STATE_DIR / f"{key}.json"
    if not p.exists():
        return None
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return None


# ================================================================== CLI
def main():
    ap = argparse.ArgumentParser(description="Jellyfin/Emby 影视整理助手")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add_common(p):
        p.add_argument("--since", default="2d", help="最近多少天的文件算新增（2d/12h/all）")
        p.add_argument("--paths", nargs="*", help="直接指定目录（覆盖库根目录扫描）")
        p.add_argument("--only", choices=["movie", "tv", "both"], default="both", help="扫哪个库")
        p.add_argument("--movie-root", help="电影库根目录")
        p.add_argument("--tv-root", help="电视剧库根目录")

    p = sub.add_parser("scan", help="扫描新增资源")
    add_common(p)
    p.set_defaults(func=cmd_scan)

    p = sub.add_parser("fetch", help="抓 TMDB 元数据")
    add_common(p)
    p.add_argument("--fetch-host", choices=["vps", "local"], default=CFG["fetch_host"])
    p.set_defaults(func=cmd_fetch)

    p = sub.add_parser("plan", help="生成整理计划")
    add_common(p)
    p.set_defaults(func=cmd_plan)

    p = sub.add_parser("apply", help="执行整理（移动文件+写 NFO+下图）")
    add_common(p)
    p.set_defaults(func=cmd_apply)

    p = sub.add_parser("push", help="推送到 Jellyfin/Emby 并扫库")
    add_common(p)
    p.add_argument("--server", choices=["jellyfin", "emby"])
    p.set_defaults(func=cmd_push)

    p = sub.add_parser("run", help="scan→fetch→plan→apply→push")
    add_common(p)
    p.add_argument("--fetch-host", choices=["vps", "local"], default=CFG["fetch_host"])
    p.add_argument("--server", choices=["jellyfin", "emby"])
    p.add_argument("--apply", dest="apply_ok", action="store_true",
                   help="真正执行整理与推送（不加只出计划）")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("probe", help="检测服务器到 TMDB 的连通性")
    p.add_argument("--server", choices=["jellyfin", "emby"])
    p.add_argument("--ips", nargs="*")
    p.set_defaults(func=cmd_probe)

    args = ap.parse_args()
    if getattr(args, "movie_root", None):
        CFG["movie_root"] = args.movie_root
    if getattr(args, "tv_root", None):
        CFG["tv_root"] = args.tv_root
    if not hasattr(args, "since"):
        args.since = "2d"
    if not hasattr(args, "paths"):
        args.paths = None
    if not hasattr(args, "only"):
        args.only = "both"
    args.func(args)


def cmd_run(args):
    cmd_scan(args)
    args.fetch_host = getattr(args, "fetch_host", CFG["fetch_host"])
    cmd_fetch(args)
    cmd_plan(args)
    if args.apply_ok:
        cmd_apply(args)
        cmd_push(args)
    else:
        log("\n（未加 --apply，只做了计划；确认无误后执行 apply / push）")


if __name__ == "__main__":
    main()
