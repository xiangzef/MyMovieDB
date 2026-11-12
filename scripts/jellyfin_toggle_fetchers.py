#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""临时禁用 Jellyfin 库里的 TMDB/TVDB 远程刮削源（NAS 访问不到 api.themoviedb.org，
每次刮削都会卡 100 秒超时）。用 --restore 还原。

凭据不写死在脚本里：见 _media_servers.py（环境变量 / ~/.jellyfin_helper/config.json）
"""
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _media_servers import auth_header, get_server, need_token

JF, TOK, _UID = get_server("jellyfin")
need_token("jellyfin", TOK)
H = auth_header(TOK)
BACKUP = Path(r"C:\Temp\opencode\jf_libopts_backup.json")


def req(url, method="GET", data=None):
    body = None if data is None else json.dumps(data).encode()
    r = urllib.request.Request(url, data=body, method=method, headers=H)
    with urllib.request.urlopen(r, timeout=60) as resp:
        raw = resp.read().decode("utf-8", "ignore")
    return json.loads(raw) if raw.strip() else {}


def stop_running():
    tasks = req(JF + "/ScheduledTasks")
    for t in tasks:
        if t.get("Key") == "RefreshLibrary" and t.get("State") == "Running":
            tid = t.get("Id")
            try:
                req(f"{JF}/ScheduledTasks/Running/{tid}", method="DELETE")
                print("已停止正在运行的 RefreshLibrary")
            except Exception as e:
                print("停止失败:", e)


def apply(disable=True):
    libs = req(JF + "/Library/VirtualFolders")
    backup = []
    for lib in libs:
        if lib.get("CollectionType") not in ("movies", "tvshows"):
            continue
        opts = lib["LibraryOptions"]
        backup.append({"Id": lib["ItemId"], "Name": lib["Name"], "LibraryOptions": opts})
        for to in opts.get("TypeOptions", []):
            if to.get("ItemType") not in ("Movie", "Series", "Season", "Episode"):
                continue
            dis = list(to.get("DisabledMetadataFetchers") or [])
            if disable:
                for n in ("The Movie Database", "TheMovieDb", "TheTVDB"):
                    if n not in dis:
                        dis.append(n)
            else:
                dis = [n for n in dis if n not in ("The Movie Database", "TheMovieDb", "TheTVDB")]
            to["DisabledMetadataFetchers"] = dis
        payload = {"Id": str(lib["ItemId"]), "LibraryOptions": opts}
        req(JF + "/Library/VirtualFolders/LibraryOptions", method="POST", data=payload)
        print(f"库「{lib['Name']}」已{'禁用' if disable else '恢复'} TMDB/TVDB")
    if disable:
        json.dump(backup, open(BACKUP, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("已备份原始配置 ->", BACKUP)
    else:
        print("已还原")


if __name__ == "__main__":
    stop_running()
    apply(disable="--restore" not in sys.argv)
