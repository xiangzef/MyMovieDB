#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TMDB 元数据抓取器（独立模块，可在本机或 VPS 上跑）

背景：api.themoviedb.org 在国内被 DNS 污染且 api 域名不可达，只有网页版
www.themoviedb.org 能访问。本模块直接解析网页里的 schema.org ld+json 拿数据，
所以放在哪台能访问 tmdb.org 的机器上都行（NAS 那台不行，VPS 可以）。

用法：
    python3 _tmdb_fetch.py spec.json out.json
    python3 _tmdb_fetch.py spec.json out.json --search-only

spec.json 格式：
    [
      {"kind": "movie", "query": "My Octopus Teacher", "year": 2020},
      {"kind": "tv",   "query": "The Hunt", "year": 2015, "season": 1, "max_eps": 7}
    ]
输出：
    每个元素 = {kind, query, year, candidates:[{tmdb_id, title, original_title, year, ...}],
                 best:{...完整元数据含 images/episodes...}}
"""
import json
import re
import subprocess
import sys

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
BASE = "https://www.themoviedb.org"


# ----------------------------------------------------------------- 抓取层
def curl(url):
    """用 curl 抓（urllib 会被 Cloudflare 挡，curl 带 UA 可以）"""
    cmd = ["curl", "-sL", "-m", "40", "-A", UA, "--compressed",
           "-H", "Accept-Language: zh-CN,zh;q=0.9,en;q=0.8", url]
    r = subprocess.run(cmd, capture_output=True, timeout=60)
    return r.stdout.decode("utf-8", "ignore")


def txt(s):
    if not s:
        return None
    s = re.sub(r"<[^>]+>", " ", s)
    for a, b in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&#39;", "'"),
                 ("&quot;", '"'), ("&nbsp;", " "), ("&#8212;", "-"), ("&hellip;", "...")):
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s).strip()


def ld_json(html, want_type=None):
    for m in re.finditer(r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S):
        try:
            d = json.loads(m.group(1))
        except Exception:
            continue
        if want_type is None or d.get("@type") == want_type:
            return d
    return {}


def images(html):
    """返回 (poster_url, backdrop_url)，统一成 original 尺寸"""
    imgs = {}
    for s, p in re.findall(r'https://(?:image|media)\.themoviedb\.org/t/p/([a-z0-9_]+(?:/[a-z0-9_]+)*)/([A-Za-z0-9._-]+\.jpg)', html):
        imgs.setdefault(p, []).append(s)
    poster = backdrop = None
    m = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html) or \
        re.search(r'<meta[^>]+content="([^"]+)"[^>]+property="og:image"', html)
    if m:
        mm = re.search(r'([A-Za-z0-9._-]+\.jpg)$', m.group(1))
        if mm:
            poster = mm.group(1)
    if not poster:
        for p, sizes in imgs.items():
            if any(s in ("w500", "original") for s in sizes):
                poster = p
                break
    for p, sizes in imgs.items():
        if any(s.startswith(("w1920", "w1280")) for s in sizes):
            backdrop = p
            break
    if not backdrop:
        for p, sizes in imgs.items():
            if any(s in ("w780", "w1066") for s in sizes):
                backdrop = p
                break
    return (f"https://image.tmdb.org/t/p/original/{poster}" if poster else None,
            f"https://image.tmdb.org/t/p/original/{backdrop}" if backdrop else None)


def runtime_min(rt):
    if not rt:
        return None
    m = re.match(r"(?:(\d+)h)?\s*(?:(\d+)m)?", rt.strip())
    if not m or not (m.group(1) or m.group(2)):
        return None
    return int(m.group(1) or 0) * 60 + int(m.group(2) or 0)


# ----------------------------------------------------------------- 搜索
def _results_container(html, kind):
    """只取搜索结果容器（页面里还有人物/剧集等其它区块，不能混进来）"""
    key = "movie_results" if kind == "movie" else "tv_results"
    i = html.find(f'id="{key}"')
    if i < 0:
        return ""
    j = html.find('id="person_results"', i)
    if j < 0:
        j = html.find('id="movie_results"', i + 10) if kind == "tv" else len(html)
    return html[i:j if j > i else len(html)]


def search(kind, query, year=None, pages=2):
    """返回候选 [{tmdb_id, title, year, overview, poster, rating...}]（直接解析搜索结果卡片）"""
    path = "movie" if kind == "movie" else "tv"
    out, seen = [], set()
    for page in range(1, pages + 1):
        html = curl(f"{BASE}/search/{path}?query={_q(query)}&language=en-US&page={page}")
        cont = _results_container(html, kind)
        if not cont:
            break
        chunks = cont.split('class="comp:media-card')
        for ch in chunks[1:]:
            m = re.search(r'data-media-type="%s"[^>]*?href="/%s/(\d+)-([^"?]*)' % (kind, path), ch)
            if not m:
                continue
            tid = int(m.group(1))
            if tid in seen:
                continue
            seen.add(tid)
            title = one(r'<h2[^>]*><span>([^<]*)</span></h2>', ch) or m.group(2).replace("-", " ")
            yr = one(r'<span class="release_date[^"]*">([^<]*)</span>', ch)
            year_m = re.search(r"(19|20)\d{2}", yr or "")
            year_v = int(year_m.group(0)) if year_m else None
            ov = one(r"<p>(.*?)</p>", ch)
            poster = None
            pm = re.search(r'(https://media\.themoviedb\.org/t/p/[^"\s]+?\.jpg)', ch)
            if pm:
                poster = re.sub(r"/t/p/[^/]+/", "/t/p/original/", pm.group(1))
            out.append({"tmdb_id": tid, "title": title, "year": year_v,
                        "overview": ov, "poster": poster,
                        "rating": None, "rating_count": None, "imdb_id": None})
        if len(out) >= 40:
            break
    return out


def one(pattern, html, group=1, flags=re.S):
    m = re.search(pattern, html, flags)
    return txt(m.group(group)) if m else None


def variants_of(query, zh_hint=None):
    """查询变体：原样 → 去年份 → 逐步缩短前缀/后缀 → 中文名"""
    queries = []
    if query:
        queries.append(query)
        noyear = re.sub(r"\b(19|20)\d{2}\b", "", query).strip()
        if noyear and noyear != query:
            queries.append(noyear)
        words = query.split()
        for n in (4, 3, 2):
            for q in (" ".join(words[:n]), " ".join(words[-n:])):
                if q and q not in queries:
                    queries.append(q)
    if zh_hint and zh_hint not in queries:
        queries.append(zh_hint)
    return queries


def significant_count(q):
    """有效词个数（长度≥4 且不是停用词）—— 太少说明这个查询太泛，不足以定片"""
    toks = [x for x in re.split(r"[.\s_\-]+", q or "") if len(x) >= 4 and x.lower() not in STOP]
    return len(toks)


def search_best(kind, query, year=None, zh_hint=None, min_score=28):
    """逐个查询变体搜索 + 打分，第一个可信的命中就返回。
    变体太泛（有效词 < 2）时，必须整名对得上才认。"""
    for q in variants_of(query, zh_hint):
        cands = search(kind, q, year)
        if not cands:
            continue
        best = pick_best_strict(cands, q, year, zh_hint, min_score)
        if not best:
            continue
        if significant_count(q) < 2:
            strict = pick_best_strict(cands, query, year, zh_hint, min_score)
            if not strict:
                continue
            best = strict
        best["matched_query"] = q
        best["_loose"] = (q != query)
        return best
    return None


def search_any(kind, query, year=None, zh_hint=None, max_cands=40):
    """把所有变体的候选合并（调试 / 展示用）"""
    seen, best = set(), []
    for q in variants_of(query, zh_hint):
        for c in search(kind, q, year):
            if c["tmdb_id"] in seen:
                continue
            seen.add(c["tmdb_id"])
            c["matched_query"] = q
            best.append(c)
        if len(best) >= max_cands:
            break
    return best[:max_cands]


def _q(s):
    import urllib.parse
    return urllib.parse.quote(s)


def _year(L, html):
    m = re.search(r'<span class="tag release_date">\((\d{4})\)</span>', html)
    if m:
        return int(m.group(1))
    for k in ("datePublished", "startDate", "dateCreated"):
        v = L.get(k)
        if v and re.match(r"\d{4}", str(v)):
            return int(str(v)[:4])
    return None


# ----------------------------------------------------------------- 详情
def movie_detail(tid):
    zh = curl(f"{BASE}/movie/{tid}?language=zh-CN")
    en = curl(f"{BASE}/movie/{tid}?language=en-US")
    Lz, Le = ld_json(zh, "Movie"), ld_json(en, "Movie")
    pz, bz = images(zh)
    people = []
    for m in re.finditer(r'<li class="profile">\s*<p><a href="/person/[^"]*"[^>]*>(.*?)</a></p>(?:\s*<p class="character">(.*?)</p>)?', zh, re.S):
        people.append({"name": txt(m.group(1)), "character": txt(m.group(2)) if m.lastindex and m.lastindex >= 2 else None})
    return {
        "tmdb_id": tid,
        "title": txt(Lz.get("name")),
        "original_title": txt(Le.get("name")),
        "overview": txt(Lz.get("description")),
        "tagline": _tagline(zh),
        "year": _year(Le, en),
        "release_date": _date(zh),
        "runtime_min": runtime_min(Lz.get("duration")),
        "rating": (Lz.get("aggregateRating") or {}).get("ratingValue"),
        "rating_count": (Lz.get("aggregateRating") or {}).get("ratingCount"),
        "genres": Lz.get("genre") or [],
        "imdb_id": (re.search(r"https://www\.imdb\.com/title/(tt\d+)", en) or [None, None])[1],
        "poster": pz, "backdrop": bz,
        "people": people[:8],
    }


def series_detail(tid, season=1, max_eps=0):
    zh = curl(f"{BASE}/tv/{tid}?language=zh-CN")
    en = curl(f"{BASE}/tv/{tid}?language=en-US")
    Lz, Le = ld_json(zh, "TVSeries"), ld_json(en, "TVSeries")
    pz, bz = images(zh)
    shtml = curl(f"{BASE}/tv/{tid}/season/{season}?language=zh-CN")
    SL = ld_json(shtml, "TVSeason")
    eps, seen = [], set()
    for m in re.finditer(r'href="(/tv/[^"]*?/season/(\d+)/episode/(\d+)[^"]*)"', shtml):
        num = int(m.group(3))
        if num in seen or (max_eps and num > max_eps):
            continue
        seen.add(num)
        url = "https://www.themoviedb.org" + m.group(1).split("?")[0]
        ehtml = curl(url + "?language=zh-CN")
        EL = ld_json(ehtml, "TVEpisode")
        if not EL:
            continue
        eps.append({
            "episode": EL.get("episodeNumber") or num,
            "season": (EL.get("partOfSeason") or {}).get("seasonNumber") or season,
            "title": txt(EL.get("name")),
            "overview": txt(EL.get("description")),
            "aired": EL.get("datePublished"),
            "rating": (EL.get("aggregateRating") or {}).get("ratingValue"),
            "rating_count": (EL.get("aggregateRating") or {}).get("ratingCount"),
            "runtime_min": runtime_min(EL.get("duration")),
            "still": (EL.get("image") or "").replace("/t/p/w780/", "/t/p/original/") or None,
        })
    eps.sort(key=lambda e: e["episode"])
    return {
        "tmdb_id": tid,
        "title": txt(Lz.get("name")),
        "original_title": txt(Le.get("name")),
        "overview": txt(Lz.get("description")),
        "year": _year(Le, en),
        "rating": (Lz.get("aggregateRating") or {}).get("ratingValue"),
        "rating_count": (Lz.get("aggregateRating") or {}).get("ratingCount"),
        "genres": Lz.get("genre") or [],
        "imdb_id": (re.search(r"https://www\.imdb\.com/title/(tt\d+)", en) or [None, None])[1],
        "poster": pz, "backdrop": bz,
        "total_episodes": Lz.get("numberOfEpisodes"),
        "season": {
            "season_number": SL.get("seasonNumber") or season,
            "name": txt(SL.get("name")),
            "overview": txt(SL.get("description")),
            "poster": (SL.get("image") or "").replace("/t/p/w500/", "/t/p/original/") or None,
            "year": _year(SL, shtml),
        },
        "episodes": eps,
    }


def detail_auto(tid, kind, season=1, max_eps=0):
    """按 TMDB 页面实际类型取详情。
    注意：TMDB 的 id 在 movie/tv 之间不通用（/movie/121446 与 /tv/121446 是两部片），
    所以先按调用方给的类型试，不匹配再换另一种。"""
    order = ["movie", "tv"] if kind == "movie" else ["tv", "movie"]
    for k in order:
        probe = curl(f"{BASE}/{k}/{tid}?language=en-US")
        want = "Movie" if k == "movie" else "TVSeries"
        if ld_json(probe, want):
            if k == "movie":
                return k, movie_detail(tid)
            return k, series_detail(tid, season, max_eps)
    return kind, (movie_detail(tid) if kind == "movie" else series_detail(tid, season, max_eps))


def _tagline(html):
    m = re.search(r'<h3 class="tagline"[^>]*>(.*?)</h3>', html, re.S)
    return txt(m.group(1)) if m else None


def _date(html):
    m = re.search(r'<span class="release">\s*([\d-]+)', html)
    return m.group(1) if m else None


# ----------------------------------------------------------------- 候选打分
STOP = {"the", "and", "for", "with", "that", "this", "from", "part", "chapter", "volume", "vol"}


def norm(s):
    s = (s or "").lower()
    s = re.sub(r"[^\w一-鿿]+", "", s)
    return s


def score(cand, query, year, zh_hint=None):
    """给候选打分：年份吻合 > 标题相似 > 热度"""
    s = 0.0
    cy = cand.get("year")
    if year and cy:
        s += 40 if abs(cy - year) <= 1 else (20 if abs(cy - year) <= 3 else -25)
    q = norm(query)
    t = norm(cand.get("title"))
    o = norm(cand.get("original_title"))
    qtoks = [x for x in re.split(r"[.\s_\-]+", query) if len(x) > 1]
    if q and (q == t or q == o):
        s += 45
    elif q and (q in t or q in o or t in q or o in q):
        s += 25
    else:
        if qtoks:
            hit = sum(1 for x in qtoks if norm(x) and (norm(x) in t or norm(x) in o))
            s += 30 * hit / len(qtoks)
    # 特征词必须对上，否则很可能是同系列的不同作品（宁可不匹配，也不要错配）
    strong = [x for x in qtoks if len(x) >= 4 and x.lower() not in STOP]
    if strong:
        miss = [x for x in strong if norm(x) not in t and norm(x) not in o]
        if miss:
            s = min(s, 15)
    if zh_hint:
        s += 20 if norm(zh_hint) == norm(cand.get("title")) else 0
    rc = cand.get("rating_count") or 0
    s += min(10, rc / 500.0)
    return s


def pick_best_strict(cands, query, year, zh_hint=None, min_score=28):
    """严格按给定查询打分挑最佳候选"""
    best, bs = None, -1e9
    for c in cands:
        sc = score(c, query, year, zh_hint)
        if sc > bs:
            best, bs = c, sc
    if best and bs >= min_score:
        best = dict(best)
        best["_score"] = round(bs, 1)
        return best
    return None


def pick_best(cands, query, year, zh_hint=None, min_score=28):
    """宽松版：先严格，再退回「命中它的缩短查询」"""
    b = pick_best_strict(cands, query, year, zh_hint, min_score)
    if b:
        return b
    loose = [(score(c, c.get("matched_query") or query, year, zh_hint), c) for c in cands]
    loose.sort(key=lambda x: -x[0])
    if loose and loose[0][0] >= min_score:
        b = dict(loose[0][1])
        b["_score"] = round(loose[0][0], 1)
        b["_loose"] = True
        return b
    return None


# ----------------------------------------------------------------- main
def main():
    spec = json.load(open(sys.argv[1], encoding="utf-8"))
    outfile = sys.argv[2] if len(sys.argv) > 2 else "/tmp/tmdb_out.json"
    search_only = "--search-only" in sys.argv
    results = []
    for item in spec:
        kind = item["kind"]
        query = item.get("query") or ""
        year = item.get("year")
        zh_hint = item.get("zh_title")
        print(f"[search] {kind} {query!r} year={year}", flush=True)
        cands = search_any(kind, query, year, zh_hint)
        best = search_best(kind, query, year, zh_hint)
        # 电影 / 剧集 互为兜底（有些资源是剧集但文件名没有集号）
        if not best and not search_only:
            other = "tv" if kind == "movie" else "movie"
            best = search_best(other, query, year, zh_hint)
            if best:
                kind = other
                print("   (跨类型兜底命中)", flush=True)
        # 已知 tmdbid（目录里有 NFO）时直接用，不做搜索
        if item.get("tmdb_id"):
            best = {"tmdb_id": int(item["tmdb_id"]), "title": query, "_score": 999}
            print("   -> 用 NFO 里的 tmdbid 直接抓取", flush=True)
        rec = {"kind": kind, "query": query, "year": year, "zh_title": zh_hint, "ref": item.get("ref"),
               "candidates": cands[:8], "best": best}
        if best and not search_only:
            if kind == "movie":
                k2, m2 = detail_auto(best["tmdb_id"], "movie", item.get("season", 1), item.get("max_eps", 0))
            else:
                k2, m2 = detail_auto(best["tmdb_id"], "tv", item.get("season", 1), item.get("max_eps", 0))
            kind = k2
            rec["meta"] = m2
            rec["kind"] = kind
            print(f"   -> 命中 {m2.get('title')} ({m2.get('year')}) "
                  f"score={best.get('_score')} eps={len(m2.get('episodes') or [])}", flush=True)
        else:
            print(f"   -> 未命中（候选 {len(cands)} 个）", flush=True)
        results.append(rec)
    json.dump(results, open(outfile, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("WROTE", outfile)


if __name__ == "__main__":
    main()
