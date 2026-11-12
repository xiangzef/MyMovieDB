#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
整理 NAS 上新下载的 4 部纪录片 → Jellyfin 标准库结构 + 写 NFO + 下载图片

用法:
    python organize_new_media.py            # dry-run, 只打印计划
    python organize_new_media.py --apply    # 真正执行

背景:
    NAS 上 Jellyfin/Emby 都访问不到 api.themoviedb.org（代理 mihomo 未运行），
    媒体服务器无法自动刮削。所以元数据由本机从 TMDB 抓取后写成 NFO + 本地图片，
    Jellyfin 扫描时直接读取，保证 4 部片子上架即有中文标题/海报/剧集信息。
"""
import json
import os
import shutil
import sys
import urllib.request
from pathlib import Path

MOVIE_ROOT = Path(r"Y:\电影")
TV_ROOT = Path(r"Y:\电视剧")
PACK = Path(r"C:\Temp\opencode\tmdb_final.json")
APPLY = "--apply" in sys.argv
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

# ---------------------------------------------------------------- 作业定义
# 每个作业: kind= movie/tv, tmdb=TMDB id, src=现目录名, dst=目标目录名
JOBS = [
    {
        "kind": "movie", "tmdb": 121446,
        "src": "观鸟者：中央公园效应[中文字幕].Birders.The.Central.Park.Effect.2012.1080p.WEB-DL.H264.AAC-SONYHD",
        "dst": "观鸟者：中央公园效应 Birders The Central Park Effect",
        "videos": [("Birders.The.Central.Park.Effect.2012.1080p.WEB-DL.H264.AAC-SONYHD.mp4",
                    "Birders.The.Central.Park.Effect.2012.1080p.WEB-DL.H264.AAC-SONYHD.mp4")],
        "junk": ["AC2FA216618D62B0C3171D39B0054534A3E08C4D.torrent",
                 "【更多无水印蓝光原盘请访问 www.HDBTHD.com】【更多无水印蓝光原盘请访问 www.HDBTHD.com】.MP4",
                 "【更多无水印蓝光电影请访问 www.HDBTHD.com】【更多无水印蓝光电影请访问 www.HDBTHD.com】.DOC",
                 "【更多无水印高清电影请访问 www.HDBTHD.com】【更多无水印高清电影请访问 www.HDBTHD.com】.MKV"],
    },
    {
        "kind": "movie", "tmdb": 682110,
        "src": "我的章鱼老师.1080p.BD中英双字",
        "dst": "我的章鱼老师 My Octopus Teacher",
        "videos": [("我的章鱼老师.1080p.BD中英双字[66影视www.66Ys.Co].mp4",
                    "我的章鱼老师.1080p.BD中英双字[66影视www.66Ys.Co].mp4")],
        "junk": [],
    },
    {
        "kind": "tv", "tmdb": 64313, "season": 1,
        "src": "猎捕.2015.国英双语.中英字幕",
        "dst": "猎捕 The Hunt",
        "episodes": [
            ("[猎捕].The.Hunt.EP01.2015.BluRay.720p.x264.AC3.2Audios-CMCT.mkv", 1),
            ("[猎捕].The.Hunt.EP02.2015.BluRay.720p.x264.AC3.2Audios-CMCT.mkv", 2),
            ("[猎捕].The.Hunt.EP03.2015.BluRay.720p.x264.AC3.2Audios-CMCT.mkv", 3),
            ("[猎捕].The.Hunt.EP04.2015.BluRay.720p.x264.AC3.2Audios-CMCT.mkv", 4),
            ("[猎捕].The.Hunt.EP05.2015.BluRay.720p.x264.AC3.2Audios-CMCT.mkv", 5),
            ("[猎捕].The.Hunt.EP06.2015.BluRay.720p.x264.AC3.2Audios-CMCT.mkv", 6),
            ("[猎捕].The.Hunt.EP07.2015.BluRay.720p.x264.AC3.2Audios-CMCT.mkv", 7),
        ],
        "extras": [("猎捕.2015.jpg", "local-poster.jpg"), ("猎捕.2015.txt", "info.txt")],
        "junk": [],
    },
    {
        "kind": "tv", "tmdb": 59615, "season": 1,
        "src": "萌宠成长记.2013.国语中字￡呆呆熊",
        "dst": "萌宠成长记 Too Cute",
        "episodes": [
            ("[萌宠成长记].CCTV1HD.Too.Cute.EP01.HDTV.720p.x264.AC3-CMCT.mkv", 1),
            ("[萌宠成长记].CCTV1HD.Too.Cute.EP02.HDTV.720p.x264.AC3-CMCT.mkv", 2),
            ("[萌宠成长记].CCTV1HD.Too.Cute.EP03.HDTV.720p.x264.AC3-CMCT.mkv", 3),
            ("[萌宠成长记].CCTV1HD.Too.Cute.EP04.HDTV.720p.x264.AC3-CMCT.mkv", 4),
            ("[萌宠成长记].CCTV1HD.Too.Cute.EP05.HDTV.720p.x264.AC3-CMCT.mkv", 5),
            ("[萌宠成长记].CCTV1HD.Too.Cute.EP06.HDTV.720p.x264.AC3-CMCT.mkv", 6),
        ],
        "extras": [("萌宠成长记.2013.jpg", "local-cover.jpg")],
        "junk": ["ED79D6B204D94AF09FD444616700C1550A3CBBFD.torrent"],
    },
]


# ---------------------------------------------------------------- 小工具
def esc(s):
    """XML 文本转义"""
    if s is None:
        return ""
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def dl(url, dest: Path):
    if not url:
        return False
    if dest.exists() and dest.stat().st_size > 1000:
        return True
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return len(data) > 1000
    except Exception as e:
        print(f"    [下载失败] {url} -> {e}")
        return False


def write_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def head(tag, body):
    return f'<?xml version="1.0" encoding="utf-8" standalone="yes"?>\n<{tag}>\n{body}</{tag}>\n'


def movie_nfo(zh, en):
    b = []
    b.append(f"  <title>{esc(zh.get('title'))}</title>")
    b.append(f"  <originaltitle>{esc(en.get('title'))}</originaltitle>")
    b.append(f"  <sorttitle>{esc(zh.get('title'))}</sorttitle>")
    b.append(f"  <plot>{esc(zh.get('overview'))}</plot>")
    b.append(f"  <outline>{esc(zh.get('overview'))}</outline>")
    if zh.get("tagline"):
        b.append(f"  <tagline>{esc(zh.get('tagline'))}</tagline>")
    if zh.get("runtime_min"):
        b.append(f"  <runtime>{zh['runtime_min']}</runtime>")
    if zh.get("year"):
        b.append(f"  <year>{zh['year']}</year>")
    if zh.get("release_date"):
        b.append(f"  <releasedate>{zh['release_date']}</releasedate>")
        b.append(f"  <premiered>{zh['release_date']}</premiered>")
    if zh.get("rating"):
        b.append(f"  <rating>{round(float(zh['rating']), 1)}</rating>")
        b.append(f"  <votes>{zh.get('rating_count') or 0}</votes>")
    for g in zh.get("genres") or []:
        b.append(f"  <genre>{esc(g)}</genre>")
    b.append(f"  <imdbid>{esc(zh.get('imdb_id'))}</imdbid>")
    b.append(f"  <tmdbid>{zh.get('tmdb_id')}</tmdbid>")
    b.append(f"  <uniqueid type=\"imdb\" default=\"true\">{esc(zh.get('imdb_id'))}</uniqueid>")
    b.append(f"  <uniqueid type=\"tmdb\" default=\"true\">{zh.get('tmdb_id')}</uniqueid>")
    for p in (zh.get("people") or [])[:8]:
        nm, role = p.get("name"), p.get("character") or ""
        b.append("  <actor>")
        b.append(f"    <name>{esc(nm)}</name>")
        if role:
            b.append(f"    <role>{esc(role)}</role>")
        b.append("    <type>Actor</type>")
        b.append("  </actor>")
    b.append("  <lockdata>false</lockdata>")
    return head("movie", "\n".join(b))


def tvshow_nfo(zh, en):
    b = []
    b.append(f"  <title>{esc(zh.get('title'))}</title>")
    b.append(f"  <originaltitle>{esc(en.get('title'))}</originaltitle>")
    b.append(f"  <sorttitle>{esc(zh.get('title'))}</sorttitle>")
    b.append(f"  <plot>{esc(zh.get('overview'))}</plot>")
    b.append(f"  <outline>{esc(zh.get('overview'))}</outline>")
    if zh.get("year"):
        b.append(f"  <year>{zh['year']}</year>")
    b.append("  <status>Ended</status>")
    b.append("  <season>-1</season>")
    b.append("  <episode>-1</episode>")
    if zh.get("rating"):
        b.append(f"  <rating>{round(float(zh['rating']), 1)}</rating>")
        b.append(f"  <votes>{zh.get('rating_count') or 0}</votes>")
    for g in zh.get("genres") or []:
        b.append(f"  <genre>{esc(g)}</genre>")
    b.append(f"  <imdbid>{esc(zh.get('imdb_id'))}</imdbid>")
    b.append(f"  <tmdbid>{zh.get('tmdb_id')}</tmdbid>")
    b.append(f"  <uniqueid type=\"imdb\" default=\"true\">{esc(zh.get('imdb_id'))}</uniqueid>")
    b.append(f"  <uniqueid type=\"tmdb\" default=\"true\">{zh.get('tmdb_id')}</uniqueid>")
    b.append("  <lockdata>false</lockdata>")
    return head("tvshow", "\n".join(b))


def season_nfo(zh, season_no):
    s = zh.get("season") or {}
    b = []
    b.append(f"  <title>第 {season_no} 季</title>")
    if s.get("name"):
        b.append(f"  <showtitle>{esc(zh.get('title'))}</showtitle>")
    b.append(f"  <plot>{esc(s.get('overview'))}</plot>")
    if s.get("year"):
        b.append(f"  <year>{s['year']}</year>")
    b.append(f"  <seasonnumber>{season_no}</seasonnumber>")
    b.append(f"  <tmdbid>{zh.get('tmdb_id')}</tmdbid>")
    b.append("  <lockdata>false</lockdata>")
    return head("season", "\n".join(b))


def episode_nfo(zh, ep):
    b = []
    b.append(f"  <title>{esc(ep.get('title'))}</title>")
    b.append(f"  <showtitle>{esc(zh.get('title'))}</showtitle>")
    b.append(f"  <season>{ep.get('season')}</season>")
    b.append(f"  <episode>{ep.get('episode')}</episode>")
    if ep.get("aired"):
        b.append(f"  <aired>{ep['aired']}</aired>")
        b.append(f"  <premiered>{ep['aired']}</premiered>")
    b.append(f"  <plot>{esc(ep.get('overview'))}</plot>")
    if ep.get("rating"):
        b.append(f"  <rating>{round(float(ep['rating']), 1)}</rating>")
    if ep.get("runtime_min"):
        b.append(f"  <runtime>{ep['runtime_min']}</runtime>")
    b.append("  <lockdata>false</lockdata>")
    return head("episodedetails", "\n".join(b))


# ---------------------------------------------------------------- 主流程
def main():
    pack = {f"{r['kind']}:{r['id']}": r for r in json.load(open(PACK, encoding="utf-8"))}
    plan_lines = []
    for job in JOBS:
        key = f"{job['kind']}:{job['tmdb']}"
        rec = pack[key]
        zh, en = rec["zh-CN"], rec["en-US"]
        root = MOVIE_ROOT if job["kind"] == "movie" else TV_ROOT
        src = root / job["src"]
        dst = root / job["dst"]
        print("=" * 78)
        print(f"[{job['kind']}] {zh.get('title')} / {en.get('title')}  ({zh.get('year')})")
        print(f"  源目录: {src}")
        print(f"  目标  : {dst}")
        if not src.exists():
            print("  !! 源目录不存在，跳过")
            continue
        if dst.exists() and dst != src:
            print("  !! 目标目录已存在，跳过（需人工确认）")
            continue

        if job["kind"] == "movie":
            if not APPLY:
                for s, d in job["videos"]:
                    print(f"  移动视频: {s}  ->  {d}")
                for j in job.get("junk", []):
                    print(f"  删除垃圾: {j}")
                print(f"  写文件  : movie.nfo / poster.jpg / fanart.jpg / thumb.jpg")
                continue
            dst.mkdir(parents=True, exist_ok=True)
            for s, d in job["videos"]:
                sp = src / s
                if sp.exists():
                    shutil.move(str(sp), str(dst / d))
                    print(f"  移动视频: {d}")
            for j in job.get("junk", []):
                jp = src / j
                if jp.exists():
                    jp.unlink()
                    print(f"  删除垃圾: {j}")
            write_text(dst / "movie.nfo", movie_nfo(zh, en))
            print("  写 NFO : movie.nfo")
            dl(zh.get("poster"), dst / "poster.jpg")
            dl(zh.get("backdrop"), dst / "fanart.jpg")
            dl(zh.get("poster"), dst / "thumb.jpg")
            print("  下载图片: poster.jpg / fanart.jpg / thumb.jpg")
            # 清空源目录后删除
            try:
                if not any(src.iterdir()):
                    src.rmdir()
                    print(f"  删除空源目录: {src.name}")
            except Exception:
                pass
        else:
            season_no = job.get("season", 1)
            eps_meta = {e["episode"]: e for e in (zh.get("episodes") or [])}
            # 目标文件名: {剧名} S01E01.ext
            if not APPLY:
                for s, n in job["episodes"]:
                    ext = Path(s).suffix
                    print(f"  移动剧集: {s}  ->  {job['dst']} Season {season_no} {job['dst']} S{season_no:02d}E{n:02d}{ext}")
                for s, d in job.get("extras", []):
                    print(f"  附加文件: {s} -> {d}")
                for j in job.get("junk", []):
                    print(f"  删除垃圾: {j}")
                print(f"  写文件  : tvshow.nfo / season.nfo / 每集 .nfo / poster.jpg / fanart.jpg / season-poster.jpg")
                continue
            sdir = dst / f"Season {season_no}"
            sdir.mkdir(parents=True, exist_ok=True)
            for s, n in job["episodes"]:
                sp = src / s
                if not sp.exists():
                    print(f"  !! 缺少: {s}")
                    continue
                ext = Path(s).suffix
                base = f"{job['dst']} S{season_no:02d}E{n:02d}"
                shutil.move(str(sp), str(sdir / (base + ext)))
                print(f"  移动剧集: {base}{ext}")
            for s, d in job.get("extras", []):
                sp = src / s
                if sp.exists():
                    shutil.move(str(sp), str(dst / d))
                    print(f"  附加文件: {d}")
            for j in job.get("junk", []):
                jp = src / j
                if jp.exists():
                    jp.unlink()
                    print(f"  删除垃圾: {j}")
            write_text(dst / "tvshow.nfo", tvshow_nfo(zh, en))
            write_text(sdir / "season.nfo", season_nfo(zh, season_no))
            print("  写 NFO : tvshow.nfo / season.nfo")
            dl(zh.get("poster"), dst / "poster.jpg")
            dl(zh.get("backdrop"), dst / "fanart.jpg")
            dl(zh.get("poster"), dst / "thumb.jpg")
            dl((zh.get("season") or {}).get("poster"), sdir / "season-poster.jpg")
            print("  下载图片: poster/fanart/thumb/season-poster")
            for s, n in job["episodes"]:
                ext = Path(s).suffix
                base = f"{job['dst']} S{season_no:02d}E{n:02d}"
                meta = eps_meta.get(n)
                if meta:
                    write_text(sdir / (base + ".nfo"), episode_nfo(zh, meta))
                    if meta.get("still"):
                        dl(meta["still"], sdir / (base + "-thumb.jpg"))
            print(f"  写剧集 NFO + 剧照 x{len(job['episodes'])}")
            try:
                if not any(src.iterdir()):
                    src.rmdir()
                    print(f"  删除空源目录: {src.name}")
            except Exception:
                pass
    print("=" * 78)
    print("DRY-RUN 完成（加 --apply 执行）" if not APPLY else "执行完成")


if __name__ == "__main__":
    main()
