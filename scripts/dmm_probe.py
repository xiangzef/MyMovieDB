# -*- coding: utf-8 -*-
"""DMM GraphQL 直连/代理双路连通性测试"""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")
import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
REQ = {"query": "query Q($id: ID!) { ppvContent(id: $id) { id title } }",
       "variables": {"id": "snis00800"}}


def dmm(label, proxies, timeout=25):
    s = requests.Session()
    if proxies:
        s.proxies = proxies
    else:
        s.trust_env = False
    try:
        r = s.post("https://api.video.dmm.co.jp/graphql", data=json.dumps(REQ).encode(),
                   headers={"Content-Type": "application/json", "User-Agent": UA},
                   timeout=timeout)
        print(f"{label}: {r.status_code} {r.text[:100]}")
    except Exception as e:
        print(f"{label}: ERR {type(e).__name__} {str(e)[:80]}")


dmm("直连", None)
dmm("代理", {"http": "http://127.0.0.1:7897", "https": "http://127.0.0.1:7897"})
