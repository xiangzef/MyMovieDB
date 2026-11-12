#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Final TMDB metadata pack for the 4 new Jellyfin items."""
import json
import re
import subprocess
import sys

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
BASE = "https://www.themoviedb.org"


def get(url):
    cmd = ["curl", "-sL", "-m", "40", "-A", UA, "--compressed",
           "-H", "Accept-Language: zh-CN,zh;q=0.9,en;q=0.8", url]
    return subprocess.run(cmd, capture_output=True, timeout=60).stdout.decode("utf-8", "ignore")


def txt(s):
    if not s:
        return None
    s = re.sub(r"<[^>]+>", " ", s)
    for a, b in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&#39;", "'"),
                 ("&quot;", '"'), ("&nbsp;", " "), ("&#8212;", "-"), ("&hellip;", "...")):
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s).strip()


def lds(html):
    out = []
    for m in re.finditer(r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S):
        try:
            out.append(json.loads(m.group(1)))
        except Exception:
            pass
    return out


def pick_ld(html, typ):
    for d in lds(html):
        if d.get("@type") == typ:
            return d
    return {}


def images(html):
    """return (poster_path, backdrop_path) original-size urls"""
    imgs = {}
    for s, p in re.findall(r'https://(?:image|media)\.themoviedb\.org/t/p/([a-z0-9_]+(?:/[a-z0-9_]+)*)/([A-Za-z0-9._-]+\.jpg)', html):
        imgs.setdefault(p, []).append(s)
    poster = backdrop = None
    # poster: og:image
    m = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html) or \
        re.search(r'<meta[^>]+content="([^"]+)"[^>]+property="og:image"', html)
    if m:
        mm = re.search(r'([A-Za-z0-9._-]+\.jpg)$', m.group(1))
        if mm:
            poster = mm.group(1)
    if not poster:
        for p, sizes in imgs.items():
            if any(s == "w500" or s == "original" for s in sizes):
                poster = p
                break
    # backdrop: biggest landscape variant
    for p, sizes in imgs.items():
        if any(s.startswith("w1920") or s.startswith("w1280") for s in sizes):
            backdrop = p
            break
    if not backdrop:
        for p, sizes in imgs.items():
            if any(s == "w780" or s == "w1066" for s in sizes):
                backdrop = p
                break
    return (f"https://image.tmdb.org/t/p/original/{poster}" if poster else None,
            f"https://image.tmdb.org/t/p/original/{backdrop}" if backdrop else None)


def runtime_min(rt):
    if not rt:
        return None
    m = re.match(r"(?:(\d+)h)?\s*(?:(\d+)m)?", rt.strip())
    if not m:
        return None
    h, mi = m.group(1), m.group(2)
    if not h and not mi:
        return None
    return int(h or 0) * 60 + int(mi or 0)


def parse_movie(mid, lang):
    html = get(f"{BASE}/movie/{mid}?language={lang}")
    L = pick_ld(html, "Movie")
    d = {
        "type": "movie", "tmdb_id": int(mid), "lang": lang,
        "title": txt(L.get("name")),
        "overview": txt(L.get("description")),
        "tagline": txt(re.search(r'<h3 class="tagline"[^>]*>(.*?)</h3>', html, re.S).group(1)) if re.search(r'<h3 class="tagline"[^>]*>(.*?)</h3>', html, re.S) else None,
        "genres": L.get("genre") or [],
        "imdb_id": (re.search(r"https://www\.imdb\.com/title/(tt\d+)", html) or [None, None])[1],
        "rating": (L.get("aggregateRating") or {}).get("ratingValue"),
        "rating_count": (L.get("aggregateRating") or {}).get("ratingCount"),
        "runtime_min": runtime_min(L.get("duration")),
    }
    m = re.search(r'<span class="release">\s*([\d-]+)', html)
    d["release_date"] = m.group(1) if m else None
    m = re.search(r'<span class="tag release_date">\((\d{4})\)</span>', html)
    d["year"] = int(m.group(1)) if m else None
    m = re.search(r'<span class="runtime">\s*([^<]+?)\s*</span>', html)
    d["runtime_text"] = txt(m.group(1)) if m else None
    m = re.search(r'<span class="certification">\s*([^<]+?)\s*</span>', html)
    d["certification"] = txt(m.group(1)) if m else None
    d["poster"], d["backdrop"] = images(html)
    people = []
    for m in re.finditer(r'<li class="profile">\s*<p><a href="/person/[^"]*"[^>]*>(.*?)</a></p>(?:\s*<p class="character">(.*?)</p>)?', html, re.S):
        people.append({"name": txt(m.group(1)), "character": txt(m.group(2)) if m.lastindex and m.lastindex >= 2 else None})
    d["people"] = people
    return d


def parse_series(mid, lang, season, max_eps):
    html = get(f"{BASE}/tv/{mid}?language={lang}")
    L = pick_ld(html, "TVSeries")
    d = {
        "type": "tv", "tmdb_id": int(mid), "lang": lang,
        "title": txt(L.get("name")),
        "overview": txt(L.get("description")),
        "genres": L.get("genre") or [],
        "imdb_id": (re.search(r"https://www\.imdb\.com/title/(tt\d+)", html) or [None, None])[1],
        "rating": (L.get("aggregateRating") or {}).get("ratingValue"),
        "rating_count": (L.get("aggregateRating") or {}).get("ratingCount"),
        "total_episodes": L.get("numberOfEpisodes"),
    }
    m = re.search(r'<span class="tag release_date">\((\d{4})\)</span>', html)
    d["year"] = int(m.group(1)) if m else None
    d["poster"], d["backdrop"] = images(html)

    shtml = get(f"{BASE}/tv/{mid}/season/{season}?language={lang}")
    SL = pick_ld(shtml, "TVSeason")
    d["season"] = {
        "season_number": SL.get("seasonNumber") or season,
        "name": txt(SL.get("name")),
        "overview": txt(SL.get("description")),
        "poster": (SL.get("image") or "").replace("/t/p/w500/", "/t/p/original/") or None,
        "year": None,
    }
    m = re.search(r'<span class="tag release_date">\((\d{4})\)</span>', shtml)
    if m:
        d["season"]["year"] = int(m.group(1))

    eps = {}
    for m in re.finditer(r'href="(/tv/[^"]*?/season/(\d+)/episode/(\d+)[^"]*)"', shtml):
        num = int(m.group(3))
        if num in eps or (max_eps and num > max_eps):
            continue
        eps[num] = "https://www.themoviedb.org" + m.group(1)
    out_eps = []
    for num in sorted(eps):
        url = eps[num]
        ehtml = get(url + (f"&language={lang}" if "?" in url else f"?language={lang}"))
        EL = pick_ld(ehtml, "TVEpisode")
        if not EL:
            continue
        out_eps.append({
            "episode": EL.get("episodeNumber") or num,
            "season": (EL.get("partOfSeason") or {}).get("seasonNumber") or season,
            "title": txt(EL.get("name")),
            "overview": txt(EL.get("description")),
            "aired": EL.get("datePublished"),
            "rating": (EL.get("aggregateRating") or {}).get("ratingValue"),
            "rating_count": (EL.get("aggregateRating") or {}).get("ratingCount"),
            "runtime_min": runtime_min(EL.get("duration")),
            "still": (EL.get("image") or "").replace("/t/p/w780/", "/t/p/original/") or None,
            "url": url,
        })
    d["episodes"] = out_eps
    return d


def main():
    spec = json.load(open(sys.argv[1], encoding="utf-8"))
    out = []
    for it in spec:
        rec = {"kind": it["kind"], "id": it["id"]}
        for lang in ("zh-CN", "en-US"):
            try:
                if it["kind"] == "movie":
                    rec[lang] = parse_movie(it["id"], lang)
                else:
                    rec[lang] = parse_series(it["id"], lang, it.get("season", 1), it.get("max_eps", 0))
            except Exception as e:
                rec[lang] = {"error": repr(e)}
        out.append(rec)
        print("DONE", it["kind"], it["id"], "eps:", len(rec.get("zh-CN", {}).get("episodes") or []), flush=True)
    json.dump(out, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("WROTE", sys.argv[2])


if __name__ == "__main__":
    main()
