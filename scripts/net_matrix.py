# -*- coding: utf-8 -*-
"""网络源连通性矩阵测试：直连 vs 代理"""
import requests
import sys

sys.stdout.reconfigure(encoding="utf-8")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
      "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
      "Accept-Language": "ja,en;q=0.8"}
PROX = {"http": "http://127.0.0.1:7897", "https": "http://127.0.0.1:7897"}

URLS = [
    "https://av-wiki.net/?s=SSIS-338&post_type=product",
    "https://www.javsee.bond/search/SSIS-338&type=&parent=ce",
    "https://www.jav321.com/search?q=SSIS-338",
    "https://www.avbase.net/works/SSIS-338",
    "https://www.dmm.co.jp/mono/dvd/-/detail/=/cid=ssis00338/",
    "https://avdanyuwiki.com/?s=SSIS-338",
    "https://javdb.com/search?q=SSIS-338&f=all",
    "https://javcup.com/search?q=SSIS-338",
]


def test(use_proxy: bool):
    s = requests.Session()
    if not use_proxy:
        s.trust_env = False
    else:
        s.proxies = PROX
    label = "代理" if use_proxy else "直连"
    for url in URLS:
        host = url.split("/")[2]
        try:
            r = s.get(url, headers=UA, timeout=18)
            body = r.text[:1200]
            cf = "Just a moment" if "Just a moment" in r.text else ""
            print(f"[{label}] {host:20s} -> {r.status_code:3d} len={len(r.content):6d} {cf}")
        except Exception as e:
            print(f"[{label}] {host:20s} -> ERR {type(e).__name__}")


test(False)
print("-" * 60)
test(True)
