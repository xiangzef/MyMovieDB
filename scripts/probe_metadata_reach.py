#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探测 Jellyfin / Emby 到 TMDB 的真实连通性，区分「DNS 污染」与「被封锁」。

原理：用服务端自己的 HTTP 客户端去取一个 URL
      POST /Items/{itemId}/RemoteImages/Download?type=Primary&imageUrl=<url>
      Jellyfin 会去下载该 URL，失败信息会出现在服务器日志里：
        - 拿到 HTTP 状态码(4xx/5xx)  → 网络通，域名/IP 能到
        - Connection refused / 超时   → 连不上（污染 IP 或被封锁）

用法:
    python probe_metadata_reach.py            # 用 sslip.io 伪装 IP 探测
    python probe_metadata_reach.py --ip 65.9.130.24

凭据不写死在脚本里：见 _media_servers.py（环境变量 / ~/.jellyfin_helper/config.json）
"""
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _media_servers import auth_header, get_server, need_token

JF, TOK, UID = get_server("jellyfin")
need_token("jellyfin", TOK)
H = auth_header(TOK)

REAL_IPS = ["65.9.130.24", "65.9.130.126", "54.192.138.65"]


def api(url, method="GET", body=None, timeout=40):
    r = urllib.request.Request(url, data=body, method=method, headers=H)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "ignore")[:200]
    except Exception as e:
        return None, repr(e)


def find_movie():
    q = (f"{JF}/Users/{UID}/Items?ParentId=3227ce1e069754c594af25ea66d69fc7"
         f"&Recursive=true&Fields=Path&Limit=500")
    items = json.loads(api(q)[1]).get("Items", [])
    return next((i for i in items if i.get("Type") == "Movie"), None)


def probe(item_id, url):
    t0 = time.time()
    st, body = api(f"{JF}/Items/{item_id}/RemoteImages/Download?type=Primary&imageUrl={urllib.parse.quote(url)}",
                   method="POST", body=b"{}", timeout=90)
    ms = int((time.time() - t0) * 1000)
    verdict = ("DNS 解析失败 / 连不上（多半是污染 IP）" if st is None or ms > 25000 else
               f"拿到 HTTP {st} → 网络通" if st and st >= 400 else f"HTTP {st}")
    print(f"  {url}\n     -> {ms:>6} ms  {verdict}  {body[:90]}")


if __name__ == "__main__":
    import urllib.parse
    mv = find_movie()
    if not mv:
        print("找不到测试用影片")
        sys.exit(1)
    print(f"用 {mv['Name']} 做探测载体\n")
    ips = sys.argv[1:] or REAL_IPS
    print("[1] 走正常域名（对照：应该是污染失败）")
    probe(mv["Id"], "http://api.themoviedb.org/probe.txt")
    print("\n[2] 用 sslip.io 把域名指向真实 IP（成功=网络通）")
    for ip in ips:
        probe(mv["Id"], f"http://{ip.replace('.', '-')}.sslip.io/probe.txt")
    print("\n[3] 对照组：普通域名能否解析（验证容器 DNS 本身没问题）")
    probe(mv["Id"], "http://47-101-178-144.sslip.io/probe.txt")
