#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""自测：发布名解析 + 沙盒全流程（scan→fetch→plan→apply），不碰真实媒体库"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import jellyfin_helper as H  # noqa: E402

print("=" * 78)
print("A) 发布名解析测试")
print("=" * 78)
CASES = [
    ("Birders.The.Central.Park.Effect.2012.1080p.WEB-DL.H264.AAC-SONYHD.mp4", {}),
    ("我的章鱼老师.1080p.BD中英双字[66影视www.66Ys.Co].mp4", {}),
    ("[猎捕].The.Hunt.EP01.2015.BluRay.720p.x264.AC3.2Audios-CMCT.mkv", {}),
    ("[萌宠成长记].CCTV1HD.Too.Cute.EP03.HDTV.720p.x264.AC3-CMCT.mkv", {}),
    ("非洲：地球的野性家园.Africa.Earths.Wild.Home.S01E01.Welcome.to.Africa.1080p.HD中字[最新电影www.dyg7.com].mp4", {}),
    ("狮王.荣耀之战.Lion.S01E01.1080p.CHS&ENG.www.xingfan.cc.mp4", {}),
    ("A.Gorilla.Story.-.Told.by.David.Attenborough.(2026).WEBRip-1080p.Proper.mkv", {}),
    ("Planet.Earth.II.S01E03.Islands.1080p.BluRay.x264-SPARKS.mkv", {}),
    ("The.Last.of.Us.S01E01.1080p.WEB-DL.x264.mkv", {}),
    ("泰坦尼克号.1997.国语高清蓝光收藏版.mp4", {}),
]
EXPECT = [
    ("Birders The Central Park Effect", 2012, None, None),
    ("我的章鱼老师", None, None, None),
    ("The Hunt", 2015, 1, 1),
    ("Too Cute", None, 1, 3),
    ("Africa Earths Wild Home", None, 1, 1),
    ("Lion", None, 1, 1),
    ("A Gorilla Story Told by David Attenborough", 2026, None, None),
    ("Planet Earth II", None, 1, 3),
    ("The Last of Us", None, 1, 1),
    ("泰坦尼克号", 1997, None, None),
]
fails = 0
for (name, _d), (et, ey, es, ee) in zip(CASES, EXPECT):
    i = H.parse_release_name(name, ())
    ok = (i["title"] == et and i["year"] == ey and i["season"] == es and i["episode"] == ee)
    fails += 0 if ok else 1
    print(f"  {'OK ' if ok else 'FAIL'} {name[:56]:58s} → {i['title']!r} "
          f"年:{i['year']} S:{i['season']} E:{i['episode']}")
print(f"  解析用例: {len(CASES) - fails}/{len(CASES)} 通过")

print()
print("=" * 78)
print("B) 沙盒全流程：scan → fetch → plan → apply")
print("=" * 78)
SB = Path(r"C:\Temp\opencode\sandbox")
if SB.exists():
    shutil.rmtree(SB, ignore_errors=True)
(SB / "电影").mkdir(parents=True)
(SB / "电视剧" / "Blue Planet II").mkdir(parents=True)
(SB / "电影" / "Cosmos.A.Spacetime.Odyssey.2020.1080p.WEB-DL.DDP5.1.H.264-NTb.mp4").write_bytes(b"x" * 100)
for n in (1, 2):
    (SB / "电视剧" / "Blue Planet II" /
     f"[蓝色星球II].Blue.Planet.II.EP{n:02d}.2017.BluRay.1080p.x264.mkv").write_bytes(b"x" * 100)
# 模拟「下载中」的文件
(SB / "电视剧" / "Blue Planet II" / "Blue.Planet.II.EP03.2017.BluRay.1080p.x264.mkv.bt.xltd").write_bytes(b"x")

H.CFG["movie_root"] = str(SB / "电影")
H.CFG["tv_root"] = str(SB / "电视剧")
H.STATE_DIR = Path(r"C:\Temp\opencode\sandbox_state")
if H.STATE_DIR.exists():
    shutil.rmtree(H.STATE_DIR, ignore_errors=True)
H.STATE_DIR.mkdir(parents=True, exist_ok=True)


class A:
    since = "all"
    paths = None
    only = "both"
    movie_root = None
    tv_root = None
    fetch_host = "vps"
    server = None


print("-- scan --")
H.cmd_scan(A())
print("\n-- fetch --")
H.cmd_fetch(A())
print("\n-- plan --")
H.cmd_plan(A())
print("\n-- apply --")
H.cmd_apply(A())
print("\n-- 沙盒结果 --")
for d in sorted(SB.rglob("*")):
    if d.is_file():
        print("   " + str(d.relative_to(SB)) + f"  ({d.stat().st_size} B)")
print(f"\n解析用例通过率: {len(CASES) - fails}/{len(CASES)}")
