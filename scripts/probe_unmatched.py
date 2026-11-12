# -*- coding: utf-8 -*-
"""逐个排查 4 部未命中片：DMM GraphQL（直连/代理）+ r18.dev（重试）+ javsee 直连页面"""
import json
import re
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
import requests

for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
    import os
    os.environ.pop(k, None)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
PROX = {"http": "http://127.0.0.1:7897", "https": "http://127.0.0.1:7897"}
CODES = ["ADN-151", "AVOP-004", "RBD-916", "SNIS-027"]

DETAIL = ("query Q($id: ID!) { ppvContent(id: $id) { id title makerContentId actresses { name } } }")
SEARCH = ("query S($limit: Int!, $sort: ContentSearchPPVSort!, $queryWord: String)"
          " { legacySearchPPV(limit: $limit, sort: $sort, queryWord: $queryWord)"
          " { result { contents { id title } } } }")


def gql(sess, query, variables, label):
    try:
        r = sess.post("https://api.video.dmm.co.jp/graphql",
                      data=json.dumps({"query": query, "variables": variables}).encode(),
                      headers={"Content-Type": "application/json", "User-Agent": UA},
                      timeout=25)
        if r.status_code != 200:
            print(f"  [{label}] HTTP {r.status_code}")
            return None
        return r.json()
    except Exception as e:
        print(f"  [{label}] ERR {type(e).__name__}")
        return None


def probe(code):
    letters, number = code.split("-")
    cid = f"{letters.lower()}{int(number):05d}"
    print(f"\n=== {code}  猜测 cid={cid} ===")

    for label, sess in (("直连", requests.Session()),
                        ("代理", requests.Session())):
        sess.trust_env = False
        if label == "代理":
            sess.proxies = PROX
        d = gql(sess, DETAIL, {"id": cid}, label + ":detail")
        if d:
            item = (d.get("data") or {}).get("ppvContent")
            print(f"  [{label}] detail -> {json.dumps(item, ensure_ascii=False)[:220]}")
        # 搜索
        d2 = gql(sess, SEARCH, {"limit": 20, "sort": "RELEASE_DATE",
                                "queryWord": f"{letters} {number}"}, label + ":search")
        if d2:
            data = d2.get("data") or {}
            contents = ((data.get("legacySearchPPV") or {}).get("result") or {}).get("contents") or []
            print(f"  [{label}] search -> {len(contents)} 条: "
                  + ", ".join(f"{c.get('id')}" for c in contents[:8]))

    # r18.dev 重试（之前 ConnectionError 疑似瞬断）
    for url in (f"https://r18.dev/videos/vod/movies/detail/-/dvd_id={cid}/json",
                f"https://r18.dev/videos/vod/movies/detail/-/combined={cid}/json"):
        ok = False
        for t in range(3):
            try:
                s = requests.Session()
                s.trust_env = False
                r = s.get(url, headers={"User-Agent": UA}, timeout=25)
                print(f"  [r18] {url.split('=')[-1]} -> {r.status_code} len={len(r.content)}")
                if r.status_code == 200:
                    d = r.json()
                    print(f"        content_id={d.get('content_id')} title={str(d.get('title'))[:50]}")
                ok = True
                break
            except Exception as e:
                print(f"  [r18 {t+1}/3] {type(e).__name__}")
                time.sleep(5)
        if ok:
            break

    # javsee 直连搜索页真实内容看看
    try:
        s = requests.Session()
        s.trust_env = False
        r = s.get(f"https://www.javsee.bond/search/{code}&type=&parent=ce",
                  headers={"User-Agent": UA}, timeout=25)
        print(f"  [javsee] {r.status_code} len={len(r.content)}")
        if r.status_code == 200:
            html = r.text
            titles = re.findall(r"<h3[^>]*>.*?<a[^>]*>([^<]{4,80})</a>", html, re.S)
            print(f"        h3 标题数={len(titles)} 样例={titles[:3]}")
            if "検索結果" in html:
                print("        含「検索結果」字样")
            if "not found" in html.lower() or "見つかりません" in html:
                print("        页面提示未找到")
    except Exception as e:
        print(f"  [javsee] ERR {type(e).__name__}")

    # av-wiki 搜索页（?s=）而不是直接拼 slug
    try:
        s = requests.Session()
        s.trust_env = False
        r = s.get(f"https://av-wiki.net/?s={code}&post_type=product",
                  headers={"User-Agent": UA}, timeout=25)
        print(f"  [av-wiki search] {r.status_code} len={len(r.content)}")
        if r.status_code == 200:
            hits = re.findall(r'<h2[^>]*class="[^"]*entry-title[^"]*"[^>]*>\s*<a[^>]*>([^<]+)</a>', r.text)
            if not hits:
                hits = re.findall(r'<a[^>]+href="https://av-wiki\.net/[^"]+"[^>]*>([^<]{4,90})</a>', r.text)
            print(f"        结果 {len(hits)}: {hits[:3]}")
    except Exception as e:
        print(f"  [av-wiki] ERR {type(e).__name__}")


for c in CODES:
    probe(c)
    time.sleep(2)
