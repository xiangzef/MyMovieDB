# -*- coding: utf-8 -*-
"""收尾：删除空目录 + NFO 演员名日文化 + 补 LTX 标签 + 源计数刷新"""
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = r"F:\github\MyMovieDB"
sys.path.insert(0, ROOT + r"\backend")
import database as db  # noqa: E402

Z_ROOT = r"Z:\av"
ACTOR_JP = {
    "RION": "安齋らら",
    "Saeko Matsushita": "松下紗栄子",
    "Kokomi Sakura": "桜ここみ",
    "Ruri Saijo": "西條るり",
    "Anri Okita": "沖田杏梨",
    "Ema Yumekawa": "夢川エマ",
    "Shion Utsunomiya": "宇都宮しをん",
}

# 1) 删除空的旧女优目录
for d in ("RION", "宇都宮しをん", "Saeko Matsushita", "Kokomi Sakura", "Ema Yumekawa"):
    p = os.path.join(Z_ROOT, d)
    if os.path.isdir(p):
        if not any(os.scandir(p)):
            os.rmdir(p)
            print(f"删除空目录: {d}")
        else:
            print(f"⚠️ 非空，保留: {d}")

# 2) NFO 修复
n_fixed = n_actor = n_tag = 0
for root, _dirs, files in os.walk(Z_ROOT):
    for f in files:
        if not f.lower().endswith(".nfo"):
            continue
        p = os.path.join(root, f)
        with open(p, "r", encoding="utf-8", errors="ignore") as fh:
            text = fh.read()
        new = text
        for en, jp in ACTOR_JP.items():
            new = new.replace(f"<name>{en}</name>", f"<name>{jp}</name>")
        if new != text:
            n_actor += 1
        # 补 LTX / 破解 标签
        if "<tag>LTX</tag>" not in new:
            if "</movie>" in new:
                new = new.replace("</movie>", "  <tag>LTX</tag>\n  <tag>破解</tag>\n</movie>")
            else:
                new += "\n<tag>LTX</tag>\n<tag>破解</tag>\n"
            n_tag += 1
        # SNIS-091/110 无演员 → 补上
        code = f.split("+")[0].upper()
        if code in ("SNIS-091", "SNIS-110") and "<actor>" not in new:
            block = ("  <actor>\n    <name>宇都宮しをん</name>\n"
                     "    <type>Actress</type>\n  </actor>\n")
            new = new.replace("</movie>", block + "</movie>")
            n_actor += 1
        if new != text:
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(new)
            n_fixed += 1
print(f"NFO 修改 {n_fixed} 个（英文名 {n_actor}，标签 {n_tag}）")

# 3) 源计数刷新
conn = db.get_db()
n = conn.execute("SELECT count(*) FROM local_videos WHERE source_id=14").fetchone()[0]
conn.close()
db.mark_source_as_jellyfin(Z_ROOT, n)
db.update_local_source_scan(14, n)
print(f"源 14 视频数: {n}")
