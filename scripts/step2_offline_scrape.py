# -*- coding: utf-8 -*-
"""
Step 2 终版：离线批量刮削 Z:\av（源 14），修复批次刮削被 CF/20 秒预算坑死的问题
源顺序（每片命中即停）:
  1. dmm graphql   —— 移植自 peach/src/peach/sources/dmm.py（直连，无年龄门，不需日本IP）
  2. av-wiki       —— 直连实测 200 可用（旧番覆盖不全）
  3. jav321 POST   —— 走代理（127.0.0.1:7897），备用补漏
成功后走与 main.py 一致的后处理: save_movie_assets → upsert_movie → 关联
"""
import json
import os
import re
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = r"F:\github\MyMovieDB"
BACKEND = ROOT + r"\backend"
sys.path.insert(0, BACKEND)

import database as db        # noqa: E402
import scraper               # noqa: E402
import config as app_cfg     # noqa: E402

PROXY = "http://127.0.0.1:7897"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

import requests  # noqa: E402

# ── 关掉英文标题翻译（google 直连不可用，避免每片挂 30s）──────────
import enhanced_scraper as es_mod  # noqa: E402
es_mod.translate_to_chinese = lambda *a, **k: None

# ════════════════════════════════════════════════════════════════
# 源 1: DMM GraphQL（移植 peach dmm.py）
# ════════════════════════════════════════════════════════════════
DETAIL_QUERY = (
    "query PeachContent($id: ID!) { ppvContent(id: $id) { id title description makerContentId makerReleasedAt"
    " duration maker { id name } label { id name } series { id name } actresses { id name }"
    " directors { id name } genres { id name } packageImage { largeUrl mediumUrl } sampleImages { imageUrl } } }"
)
SEARCH_QUERY = (
    "query PeachSearch($limit: Int!, $sort: ContentSearchPPVSort!, $queryWord: String)"
    " { legacySearchPPV(limit: $limit, sort: $sort, queryWord: $queryWord) { result { contents { id } } } }"
)
_CODE_RE = re.compile(r"^(\d{3})?([A-Z]{2,8})-?(\d{1,5})$")
_CID_RE = re.compile(r"^(?:h_\d+|\d+)?([a-z]+)(\d+)([a-z]*)$")


def code_parts(code):
    m = _CODE_RE.match(str(code or "").strip().upper())
    return (m.group(1) or "", m.group(2), m.group(3)) if m else None


def guessed_cid(code):
    parts = code_parts(code)
    if not parts:
        return ""
    digits, letters, number = parts
    return f"{digits}{letters.lower()}{int(number):05d}"


def matching_cids(code, cids):
    parts = code_parts(code)
    if not parts:
        return []
    digits, letters, number = parts
    found = []
    for cid in cids:
        text = str(cid or "").lower()
        m = _CID_RE.match(text)
        if not m or m.group(1) != letters.lower() or int(m.group(2)) != int(number):
            continue
        if digits and not text.startswith(digits):
            continue
        found.append((bool(m.group(3)), str(cid)))
    return [cid for _, cid in sorted(found, key=lambda i: i[0])]


def dmm_code_to_date(value):
    from datetime import datetime, timedelta, timezone
    JST = timezone(timedelta(hours=9))
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return text[:10]
    return moment.astimezone(JST).date().isoformat()


class DmmGraphql:
    ENDPOINT = "https://api.video.dmm.co.jp/graphql"
    HEADERS = {"Content-Type": "application/json", "Accept": "application/json",
               "User-Agent": UA}

    def __init__(self):
        self.sess = requests.Session()
        self.sess.trust_env = False   # 直连，明确不带代理

    def graphql(self, query, variables):
        body = json.dumps({"query": query, "variables": variables})
        r = self.sess.post(self.ENDPOINT, data=body.encode(), headers=self.HEADERS, timeout=20)
        if r.status_code != 200:
            return None
        raw = r.json()
        return raw.get("data") if isinstance(raw, dict) else None

    def content(self, cid):
        data = self.graphql(DETAIL_QUERY, {"id": cid})
        if not data:
            return None
        item = data.get("ppvContent")
        return item if isinstance(item, dict) and item.get("id") else None

    def identified(self, code, cid):
        item = self.content(cid)
        if not item:
            return None
        cid_l = str(item["id"]).lower()
        parts = code_parts(code)
        if not parts:
            return None
        digits, letters, number = parts
        m = _CID_RE.match(cid_l)
        if not m or m.group(1) != letters.lower() or int(m.group(2)) != int(number):
            return None
        return item

    def scrape(self, code):
        if not code_parts(code):
            return None
        guess = guessed_cid(code)
        item = self.identified(code, guess)
        if item is None:
            _, letters, number = code_parts(code)
            data = self.graphql(SEARCH_QUERY, {"limit": 30, "sort": "RELEASE_DATE",
                                               "queryWord": f"{letters} {number}"})
            if not data:
                return None
            contents = ((data.get("legacySearchPPV") or {}).get("result") or {}).get("contents") or []
            for cid in [c for c in matching_cids(code, (r.get("id") for r in contents if isinstance(r, dict))) if c != guess][:2]:
                item = self.identified(code, cid)
                if item:
                    break
        if not item:
            return None

        rows = lambda key: [r for r in item.get(key) or [] if isinstance(r, dict) and r.get("name")]
        mk = (item.get("maker") or {}).get("name") or ""
        cover = (item.get("packageImage") or {}).get("largeUrl") or ""
        studio = mk
        return {
            "code": code,
            "title": item.get("title") or code,
            "title_jp": item.get("title") or code,
            "plot": str(item.get("description") or "").strip() or None,
            "release_date": dmm_code_to_date(item.get("makerReleasedAt")),
            "duration": int(item["duration"] / 60) if isinstance(item.get("duration"), (int, float)) and item["duration"] > 0 else None,
            "studio": studio,
            "maker": mk,
            "director": rows("directors")[0]["name"] if rows("directors") else None,
            "series": ((item.get("series") or {}).get("name") or None),
            "genres": [r["name"] for r in rows("genres")],
            "actors": [r["name"] for r in rows("actresses")],
            "actors_male": [],
            "cover_url": cover,
            "detail_url": f"https://video.dmm.co.jp/av/content/?id={item['id']}",
            "source": "dmm-graphql",
            "scrape_status": "complete",
        }


# ════════════════════════════════════════════════════════════════
# 源 2: av-wiki（直连，本项目 LegacyScraperWrapper）
# ════════════════════════════════════════════════════════════════
_AVW = [s for s in app_cfg.SCRAPER_SOURCES if s["id"] == "av-wiki"][0]
_WRAPPER = es_mod.LegacyScraperWrapper(_AVW, es_mod.EnhancedConfig(request_delay=0.4))


def avwiki_direct(code):
    try:
        return _WRAPPER.scrape(code)
    except Exception:
        return None


# ════════════════════════════════════════════════════════════════
# 源 3: jav321 POST（走代理）
# ════════════════════════════════════════════════════════════════
def jav321_proxy(code):
    os.environ["HTTP_PROXY"] = PROXY
    os.environ["HTTPS_PROXY"] = PROXY
    try:
        sess = requests.Session()
        sess.headers.update({"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                             "Referer": "https://www.jav321.com/"})
        r = sess.post("https://www.jav321.com/search", timeout=25,
                      data={"data[search][q]": code, "search_video": ""})
        if r.status_code != 200:
            return None
        html = r.text
        # 标题
        m = re.search(r"<title>(.*?)</title>", html, re.S)
        title = m.group(1).strip() if m else ""
        if title.lower().startswith(("検索", "search")):
            title = ""
        # 封面
        m = re.search(r'src="(https://pics\.dmm\.co\.jp/[^"]+ps\.jpg)"', html)
        cover = m.group(1) if m else ""
        if not re.search(r"([A-Z]+-?\d+)", (title + cover).upper()):
            return None
        fields = {}
        for label in (r"発売日", r"収録時間", r"監督", r"系列.", r"メーカー", r"出演者"):
            mm = re.search(label + r"</h4>\s*<[^>]*>(.*?)</", html, re.S)
            if mm:
                fields[label] = re.sub(r"<[^>]+>", "", mm.group(1)).strip()
        actors = re.findall(r"/p2/star/\?query=([^\"']+)", html)
        from urllib.parse import unquote
        actors = [unquote(a) for a in actors][:8] if actors else []
        html_no_tag = re.sub(r"<[^>]+>", "", html)
        plot_m = re.search(r"(?:あらすじ|作品紹介)[::\s]*(.{40,300}?)\s*(?:【|$)", html_no_tag, re.S)
        duration_mm = re.search(r"(\d{2,4})\s*分", fields.get(r"収録時間", "") or html_no_tag)
        return {
            "code": code, "title": title or code, "title_jp": title or code,
            "release_date": fields.get("発売日") or None,
            "duration": int(duration_mm.group(1)) if duration_mm else None,
            "studio": fields.get("メーカー") or None,
            "maker": fields.get("メーカー") or None,
            "director": fields.get("監督") or None,
            "genres": [],
            "actors": actors,
            "actors_male": [],
            "cover_url": cover,
            "detail_url": r.url,
            "plot": plot_m.group(1).strip() if plot_m else None,
            "source": "jav321",
            "scrape_status": "complete",
        }
    except Exception as e:
        print(f"    [jav321] 异常: {type(e).__name__}", flush=True)
        return None
    finally:
        os.environ.pop("HTTP_PROXY", None)
        os.environ.pop("HTTPS_PROXY", None)


# ════════════════════════════════════════════════════════════════
# 主流程
# ════════════════════════════════════════════════════════════════
def main():
    report = {"ok": [], "fail": {}, "linked": []}
    conn = db.get_db()
    todos = conn.execute(
        "SELECT id, code, path FROM local_videos WHERE source_id=14 AND scraped=0 ORDER BY code").fetchall()
    print(f"待刮 {len(todos)} 部", flush=True)
    dmm = DmmGraphql()

    for i, v in enumerate(todos, 1):
        vid, code, vpath = v["id"], v["code"], v["path"]
        print(f"\n[{i}/{len(todos)}] {code} ...", flush=True)
        movie_data = None

        # 1) DMM GraphQL 直连
        try:
            movie_data = dmm.scrape(code)
            if movie_data:
                print(f"    dmm-graphql OK: {movie_data['title'][:40]}", flush=True)
        except Exception as e:
            print(f"    dmm-graphql 异常 {type(e).__name__}", flush=True)
        time.sleep(1.5)

        # 2) av-wiki 直连
        if not movie_data:
            movie_data = avwiki_direct(code)
            if movie_data:
                movie_data.setdefault("code", code)
                movie_data["scrape_status"] = movie_data.get("scrape_status") or "complete"
                print(f"    av-wiki OK: {str(movie_data.get('title'))[:40]}", flush=True)
            time.sleep(1.0)

        # 3) jav321 POST（代理）
        if not movie_data:
            movie_data = jav321_proxy(code)
            if movie_data:
                print(f"    jav321 OK: {str(movie_data.get('title'))[:40]}", flush=True)

        # 番号一致性兜底
        if movie_data and movie_data.get("code", "").upper() != code.upper():
            movie_data["code"] = code

        if not movie_data:
            report["fail"][code] = "all-sources-miss"
            print("    ❌ 全部源未命中", flush=True)
            continue

        try:
            covers_dir = Path(app_cfg.COVERS_DIR)
            covers_dir.mkdir(parents=True, exist_ok=True)
            movie_data = scraper.save_movie_assets(movie_data, covers_dir, vpath)
            movie_id, is_new = db.upsert_movie(movie_data)
            db.mark_video_scraped(vid, movie_id)
            db.link_movie_to_local_video(movie_id, vid)
            report["ok"].append({"code": code, "movie_id": movie_id,
                                 "source": movie_data.get("source"),
                                 "new": is_new})
            print(f"    💾 入库 movie_id={movie_id}（来源 {movie_data.get('source')}）", flush=True)
        except Exception as e:
            report["fail"][code] = f"post-process: {type(e).__name__} {e}"
            print(f"    💥 后处理失败: {e}", flush=True)

    conn.close()
    out = Path(ROOT) / "data" / "scrape_zav_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n完成: 成功 {len(report['ok'])}, 失败 {len(report['fail'])}，报告 {out}", flush=True)


if __name__ == "__main__":
    main()
