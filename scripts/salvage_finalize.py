# -*- coding: utf-8 -*-
"""
补刮终章：
  A. 7 部 r18dev 命中 → 用 r18dev 的 content_id 回查 DMM GraphQL 拿日文全量数据
     （失败则直接用 r18dev 的英文数据）
  B. 剩余 4 部 (ADN-151/AVOP-004/RBD-916/SNIS-027) → DMM 搜索多排序方式 + jav321 代理
成功即走 save_movie_assets → upsert_movie → 关联（与 step2_offline_scrape 相同）
"""
import json
import os
import re
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = r"F:\github\MyMovieDB"
sys.path.insert(0, ROOT + r"\backend")
sys.path.insert(0, ROOT + r"\scripts")

import requests  # noqa: E402
import database as db        # noqa: E402
import scraper               # noqa: E402
import config as app_cfg     # noqa: E402
from step2_offline_scrape import (DmmGraphql, dmm_code_to_date,  # noqa: E402
                                  code_parts, matching_cids, _CID_RE)
import enhanced_scraper as es_mod  # noqa: E402
es_mod.translate_to_chinese = lambda *a, **k: None

PROXY = "http://127.0.0.1:7897"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

salvage = json.loads(Path(ROOT + r"\data\r18dev_salvage.json").read_text(encoding="utf-8"))
dmm = DmmGraphql()


def item_to_movie(item, code, source="dmm-graphql"):
    rows = lambda key: [r for r in item.get(key) or [] if isinstance(r, dict) and r.get("name")]
    mk = (item.get("maker") or {}).get("name") or ""
    cover = (item.get("packageImage") or {}).get("largeUrl") or ""
    return {
        "code": code,
        "title": item.get("title") or code,
        "title_jp": item.get("title") or code,
        "plot": str(item.get("description") or "").strip() or None,
        "release_date": dmm_code_to_date(item.get("makerReleasedAt")),
        "duration": int(item["duration"] / 60) if isinstance(item.get("duration"), (int, float)) and item["duration"] > 0 else None,
        "studio": mk, "maker": mk,
        "director": rows("directors")[0]["name"] if rows("directors") else None,
        "series": ((item.get("series") or {}).get("name") or None),
        "genres": [r["name"] for r in rows("genres")],
        "actors": [r["name"] for r in rows("actresses")],
        "actors_male": [],
        "cover_url": cover,
        "detail_url": f"https://video.dmm.co.jp/av/content/?id={item['id']}",
        "source": source,
        "scrape_status": "complete",
    }


def r18dev_to_movie(rec, code):
    actors = [a.get("name") or "" for a in rec.get("actresses") or [] if isinstance(a, dict)]
    genres = [g.get("name") for g in rec.get("genres") or [] if isinstance(g, dict) and g.get("name")]
    cover = rec.get("images", {}).get("jacket_image", {}).get("large") if isinstance(rec.get("images"), dict) else None
    cover = cover or rec.get("image_large") or ""
    return {
        "code": code,
        "title": rec.get("title") or code,
        "title_jp": rec.get("title") or code,
        "plot": rec.get("comment") or None,
        "release_date": rec.get("release_date") or None,
        "duration": int(rec["runtime_minutes"]) if rec.get("runtime_minutes") else None,
        "studio": (rec.get("maker") or {}).get("name") if isinstance(rec.get("maker"), dict) else None,
        "maker": (rec.get("label") or {}).get("name") if isinstance(rec.get("label"), dict) else None,
        "director": None, "series": None,
        "genres": genres, "actors": actors, "actors_male": [],
        "cover_url": cover,
        "detail_url": f"https://r18.dev/videos/vod/movies/detail/-/dvd_id={code.lower()}/json",
        "source": "r18dev",
        "scrape_status": "complete",
    }


def dmm_graphql_safe(query, variables):
    try:
        return dmm.graphql(query, variables)
    except Exception as e:
        print(f"    [dmm] 网络异常 {type(e).__name__}，重试一次", flush=True)
        time.sleep(3)
        try:
            return dmm.graphql(query, variables)
        except Exception:
            return None


def dmm_content_safe(cid):
    try:
        return dmm.content(cid)
    except Exception as e:
        print(f"    [dmm] 异常 {type(e).__name__}", flush=True)
        return None


def try_dmm_harder(code):
    """DMM 搜索：多种排序/多种 query 词兜底"""
    _, letters, number = code_parts(code)
    for qw, sort in ((f"{letters} {number}", "RELEASE_DATE"),
                     (f"{letters} {number}", "POPULARITY"),
                     (code.replace("-", " "), "RELEASE_DATE")):
        data = dmm_graphql_safe(
            "query S($limit: Int!, $sort: ContentSearchPPVSort!, $queryWord: String)"
            " { legacySearchPPV(limit: $limit, sort: $sort, queryWord: $queryWord)"
            " { result { contents { id title } } } }",
            {"limit": 40, "sort": sort, "queryWord": qw})
        if not data:
            continue
        contents = ((data.get("legacySearchPPV") or {}).get("result") or {}).get("contents") or []
        cids = [c.get("id") for c in contents if isinstance(c, dict)]
        for cid in matching_cids(code, cids):
            item = dmm.identified(code, cid)
            if item:
                return item_to_movie(item, code)
    return None


def jav321_proxy(code):
    os.environ["HTTP_PROXY"] = PROXY
    os.environ["HTTPS_PROXY"] = PROXY
    try:
        sess = requests.Session()
        sess.trust_env = True
        sess.headers.update({"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9",
                             "Referer": "https://www.jav321.com/"})
        r = sess.post("https://www.jav321.com/search", timeout=30,
                      data={"data[search][q]": code, "search_video": ""})
        if r.status_code != 200:
            return None
        html = r.text
        m = re.search(r"<title>(.*?)</title>", html, re.S)
        title = m.group(1).strip() if m else ""
        m = re.search(r'src="(https://pics\.dmm\.co\.jp/[^"]+ps\.jpg)"', html)
        cover = m.group(1) if m else ""
        fields = {}
        for label in (r"発売日", r"収録時間", r"メーカー", r"監督"):
            mm = re.search(label + r"</h4>\s*<[^>]*>(.*?)</", html, re.S)
            if mm:
                fields[label] = re.sub(r"<[^>]+>", "", mm.group(1)).strip()
        actors = [a for a in re.findall(r"/p2/star/\?query=([^\"]+)", html)][:8]
        from urllib.parse import unquote
        actors = [unquote(a) for a in actors]
        if not (cover or title):
            return None
        dm = re.search(r"(\d{2,4})\s*分", html)
        return {
            "code": code, "title": title or code, "title_jp": title or code,
            "release_date": fields.get(r"発売日") or None,
            "duration": int(dm.group(1)) if dm else None,
            "studio": fields.get(r"メーカー") or None, "maker": fields.get(r"メーカー") or None,
            "director": fields.get(r"監督") or None, "series": None,
            "genres": [], "actors": actors, "actors_male": [],
            "cover_url": cover, "detail_url": r.url, "plot": None,
            "source": "jav321", "scrape_status": "complete",
        }
    except Exception:
        return None
    finally:
        os.environ.pop("HTTP_PROXY", None)
        os.environ.pop("HTTPS_PROXY", None)


def finalize(code, movie_data):
    conn = db.get_db()
    v = conn.execute(
        "SELECT id, path FROM local_videos WHERE source_id=14 AND code=?", (code,)).fetchone()
    conn.close()
    if not v:
        print(f"    无 local_video 行，跳过入库")
        return False
    covers_dir = Path(app_cfg.COVERS_DIR)
    covers_dir.mkdir(parents=True, exist_ok=True)
    try:
        movie_data = scraper.save_movie_assets(movie_data, covers_dir, str(v["path"]))
        movie_id, is_new = db.upsert_movie(movie_data)
        db.mark_video_scraped(v["id"], movie_id)
        db.link_movie_to_local_video(movie_id, v["id"])
        print(f"    💾 入库 movie_id={movie_id} 起源 {movie_data.get('source')}")
        return True
    except Exception as e:
        print(f"    💥 后处理失败: {type(e).__name__} {e}")
        return False


ok, fail = [], {}
codes = sorted(set(salvage.keys()) | {"ADN-151", "AVOP-004", "RBD-916", "SNIS-027"})
for code in codes:
    print(f"\n[{code}] ...", flush=True)
    md = None
    if code in salvage:
        rec = salvage[code]
        cid = str(rec.get("content_id") or rec.get("id") or "")
        item = dmm_content_safe(cid) if cid else None
        if item:
            md = item_to_movie(item, code)
            print(f"    r18dev cid={cid} -> dmm-graphql 日文数据: {md['title'][:40]}")
        else:
            md = r18dev_to_movie(rec, code)
            print(f"    r18dev 英文数据: {md['title'][:40]} cover={md['cover_url'][:50] if md['cover_url'] else '无'}")
    else:
        md = try_dmm_harder(code)
        if md:
            print(f"    dmm-graphql 深搜 OK: {md['title'][:40]}")
        else:
            md = jav321_proxy(code)
            if md:
                print(f"    jav321 OK: {md['title'][:40]}")
        time.sleep(1.0)

    if md and finalize(code, md):
        ok.append(code)
    else:
        fail[code] = "miss-or-postfail"

out = Path(ROOT) / "data" / "salvage_zav_report.json"
out.write_text(json.dumps({"ok": ok, "fail": fail}, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\n补刮完成: 成功 {len(ok)}, 仍失败 {len(fail)} -> {out}")
