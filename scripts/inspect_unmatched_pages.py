# -*- coding: utf-8 -*-
"""看清 av-wiki / javsee / r18.dev 的真实返回内容"""
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


def strip(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)).strip()


for code in CODES:
    print(f"\n════════ {code} ════════")
    # 1) av-wiki 搜索页
    try:
        s = requests.Session()
        s.trust_env = False
        r = s.get(f"https://av-wiki.net/?s={code}&post_type=product", headers={"User-Agent": UA}, timeout=30)
        html = r.text
        idx = [m.start() for m in re.finditer(re.escape(code.upper()), html.upper())]
        print(f"[av-wiki] {r.status_code} len={len(html)} 出现 {code} 次数={len(idx)}")
        for i in idx[:3]:
            print("   ...", strip(html[max(0, i - 150):i + 200])[:260])
        # 产品链接
        links = re.findall(r'href="(https://av-wiki\.net/[^"]+)"', html)
        cand = [l for l in links if code.lower().replace("-", "") in l.lower() or code.lower() in l.lower()]
        print("   候选产品链接:", list(dict.fromkeys(cand))[:5])
    except Exception as e:
        print(f"[av-wiki] ERR {type(e).__name__}")

    # 2) javsee
    try:
        s = requests.Session()
        s.trust_env = False
        r = s.get(f"https://www.javsee.bond/search/{code}&type=&parent=ce", headers={"User-Agent": UA}, timeout=30)
        html = r.text
        idx = [m.start() for m in re.finditer(re.escape(code.upper()), html.upper())]
        print(f"[javsee] {r.status_code} len={len(html)} 出现 {code} 次数={len(idx)}")
        for i in idx[:3]:
            print("   ...", strip(html[max(0, i - 150):i + 220])[:300])
        if not idx:
            print("   页面文字片段:", strip(html)[:200])
    except Exception as e:
        print(f"[javsee] ERR {type(e).__name__}")

    # 3) r18.dev 走代理
    letters, number = code.split("-")
    cid = f"{letters.lower()}{int(number):05d}"
    for label, kw in (("r18-代理", {"proxies": PROX}), ("r18-直连", {"trust_env": False})):
        try:
            s = requests.Session()
            for kk, vv in kw.items():
                if kk == "trust_env":
                    s.trust_env = False
                else:
                    s.proxies = vv
            r = s.get(f"https://r18.dev/videos/vod/movies/detail/-/dvd_id={cid}/json",
                      headers={"User-Agent": UA}, timeout=25)
            print(f"[{label}] {r.status_code} len={len(r.content)}")
            if r.status_code == 200:
                d = r.json()
                print(f"        content_id={d.get('content_id')} title={str(d.get('title'))[:60]}")
        except Exception as e:
            print(f"[{label}] ERR {type(e).__name__}")
    time.sleep(2)
