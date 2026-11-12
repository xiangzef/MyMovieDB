#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 TMDB 元数据 + 本地图片直接写进 Jellyfin（补齐 NFO 未被采纳的字段：genre/rating/海报）

凭据不写死在脚本里：见 _media_servers.py（环境变量 / ~/.jellyfin_helper/config.json）
"""
import json
import mimetypes
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _media_servers import auth_header, get_server, need_token

WHICH = "emby" if "--emby" in sys.argv else "jellyfin"
JF, TOK, UID = get_server(WHICH)
need_token(WHICH, TOK)
PACK = Path(r"C:\Temp\opencode\tmdb_final.json")
H = auth_header(TOK)

MOVIE_ROOT = "Y:\\电影"
TV_ROOT = "Y:\\电视剧"


def api(url, method="GET", data=None, headers=None, raw=False):
    h = dict(H)
    if headers:
        h.update(headers)
    body = data if isinstance(data, bytes) else (None if data is None else json.dumps(data).encode())
    r = urllib.request.Request(url, data=body, method=method, headers=h)
    with urllib.request.urlopen(r, timeout=90) as resp:
        content = resp.read()
    if raw:
        return content
    return json.loads(content.decode("utf-8", "ignore")) if content.strip() else {}


def find_items():
    libs = api(JF + "/Library/VirtualFolders")
    out = {}
    for lib in libs:
        if lib.get("CollectionType") not in ("movies", "tvshows"):
            continue
        q = (f"{JF}/Users/{UID}/Items?ParentId={lib['ItemId']}&Recursive=true"
             f"&Fields=Path,ProviderIds,Overview,ProductionYear,PremiereDate,CommunityRating,"
             f"OfficialRating,Genres,RunTimeTicks,ImageTags,DateCreated,Type,ParentId&Limit=5000")
        for it in api(q).get("Items", []):
            p = it.get("Path") or ""
            if any(k in p for k in ("观鸟者", "章鱼", "猎捕", "萌宠")):
                out[p] = it
    return out


def upload_image(item_id, image_type, file_path: Path):
    if not file_path.exists():
        print(f"    ! 图片缺失 {file_path}")
        return False
    import base64
    data = base64.b64encode(file_path.read_bytes()).decode()
    api(f"{JF}/Items/{item_id}/Images/{image_type}", method="POST", data=data.encode(),
        headers={"Content-Type": "image/jpeg"})
    print(f"    + 上传 {image_type}: {file_path.name}")
    return True


def update(item_id, payload):
    api(f"{JF}/Items/{item_id}", method="POST", data=payload)
    print(f"    * 更新元数据: {payload.get('Name')}")


def main():
    pack = {f"{r['kind']}:{r['id']}": r for r in json.load(open(PACK, encoding="utf-8"))}
    items = find_items()
    print(f"找到 {len(items)} 条目标条目\n")

    # ---------------- 电影 ----------------
    for tmdb_id, folder in ((121446, "观鸟者：中央公园效应 Birders The Central Park Effect"),
                            (682110, "我的章鱼老师 My Octopus Teacher")):
        rec = pack[f"movie:{tmdb_id}"]
        zh, en = rec["zh-CN"], rec["en-US"]
        item = next((v for k, v in items.items() if folder in k and v.get("Type") == "Movie"), None)
        if not item:
            print(f"!! 找不到电影: {folder}")
            continue
        print(f"[电影] {zh['title']} ({zh.get('year')})")
        payload = {
            "Name": zh["title"],
            "OriginalTitle": en["title"],
            "SortName": zh["title"],
            "Overview": zh.get("overview"),
            "Taglines": [zh["tagline"]] if zh.get("tagline") else [],
            "Genres": zh.get("genres") or [],
            "CommunityRating": float(zh["rating"]) if zh.get("rating") else None,
            "ProductionYear": zh.get("year"),
            "PremiereDate": (zh.get("release_date") + "T00:00:00Z") if zh.get("release_date") else None,
            "RuntimeTicks": int(zh["runtime_min"] * 10_000_000) if zh.get("runtime_min") else None,
            "ProviderIds": {"Imdb": zh.get("imdb_id"), "Tmdb": str(zh.get("tmdb_id"))},
            "People": [{"Name": p["name"], "Role": p.get("character") or "", "Type": "Actor"}
                       for p in (zh.get("people") or [])[:6]],
        }
        payload = {k: v for k, v in payload.items() if v not in (None, [], {})}
        update(item["Id"], payload)
        d = Path(MOVIE_ROOT) / folder
        upload_image(item["Id"], "Primary", d / "poster.jpg")
        upload_image(item["Id"], "Backdrop", d / "fanart.jpg")
        upload_image(item["Id"], "Thumb", d / "thumb.jpg")

    # ---------------- 剧集 ----------------
    for tmdb_id, folder in ((64313, "猎捕 The Hunt"), (59615, "萌宠成长记 Too Cute")):
        rec = pack[f"tv:{tmdb_id}"]
        zh, en = rec["zh-CN"], rec["en-US"]
        d = Path(TV_ROOT) / folder
        series = next((v for k, v in items.items() if folder in k and v.get("Type") == "Series"), None)
        if not series:
            print(f"!! 找不到剧集: {folder}")
            continue
        print(f"[剧集] {zh['title']} ({zh.get('year')})")
        payload = {
            "Name": zh["title"],
            "OriginalTitle": en["title"],
            "SortName": zh["title"],
            "Overview": zh.get("overview"),
            "Genres": zh.get("genres") or [],
            "CommunityRating": float(zh["rating"]) if zh.get("rating") else None,
            "ProductionYear": zh.get("year"),
            "Status": "Ended",
            "ProviderIds": {"Imdb": zh.get("imdb_id"), "Tmdb": str(zh.get("tmdb_id"))},
        }
        payload = {k: v for k, v in payload.items() if v not in (None, [], {})}
        update(series["Id"], payload)
        upload_image(series["Id"], "Primary", d / "poster.jpg")
        upload_image(series["Id"], "Backdrop", d / "fanart.jpg")
        upload_image(series["Id"], "Thumb", d / "thumb.jpg")

        # 季
        season = next((v for k, v in items.items() if folder in k and v.get("Type") == "Season"), None)
        sinfo = zh.get("season") or {}
        if season and sinfo:
            sp = {"Name": "第 1 季", "Overview": sinfo.get("overview"), "IndexNumber": 1}
            if sinfo.get("year"):
                sp["PremiereDate"] = f"{sinfo['year']}-01-01T00:00:00Z"
            sp = {k: v for k, v in sp.items() if v}
            try:
                update(season["Id"], sp)
            except Exception as e:
                print(f"    ! 季元数据更新失败（Emby 季节点不支持该接口）: {e}")
            upload_image(season["Id"], "Primary", d / "Season 1" / "season-poster.jpg")

        # 每集
        for ep in (zh.get("episodes") or []):
            n = ep["episode"]
            episode = next((v for k, v in items.items()
                            if folder in k and v.get("Type") == "Episode" and k.endswith(f"S01E{n:02d}.mkv")), None)
            if not episode:
                continue
            ep_payload = {
                "Name": ep.get("title"),
                "Overview": ep.get("overview"),
                "CommunityRating": float(ep["rating"]) if ep.get("rating") else None,
                "PremiereDate": (ep["aired"] + "T00:00:00Z") if ep.get("aired") else None,
                "IndexNumber": n, "ParentIndexNumber": 1,
            }
            ep_payload = {k: v for k, v in ep_payload.items() if v not in (None, [], {})}
            try:
                update(episode["Id"], ep_payload)
            except Exception as e:
                print(f"    ! 剧集元数据更新失败（Emby 不支持该接口，NFO 已覆盖）: {e}")
            upload_image(episode["Id"], "Primary", d / "Season 1" / f"{folder} S01E{n:02d}-thumb.jpg")

    print("\n完成")


if __name__ == "__main__":
    main()
