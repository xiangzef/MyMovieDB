# -*- coding: utf-8 -*-
"""列出 Z:\av 全部文件并模拟番号提取"""
import os, re, sys
sys.stdout.reconfigure(encoding="utf-8")

CODE_PATTERN = re.compile(r'([A-Z]{2,6})-(\d{2,5})')
SPECIAL = [re.compile(r'(FC2-PPV-\d{5,7})', re.IGNORECASE)]
EXCL_WORDS = ['WEB', 'HD', 'BD', '720', '1080', '4K', 'UHD', 'SD']

def extract(fn):
    up = fn.upper()
    for p in SPECIAL:
        m = p.search(up)
        if m:
            return m.group(1)
    for m in CODE_PATTERN.finditer(up):
        prefix, number = m.groups()
        full = m.group(0)
        pos = up.find(full)
        if pos > 0:
            before = up[:pos]
            for e in EXCL_WORDS:
                if before.endswith(e):
                    break
            else:
                if re.search(r'(\d{2,4})[A-Z]{2,6}$', before):
                    continue
                if prefix.startswith(e) or prefix.endswith(e):
                    if prefix != e:
                        continue
                return f"{prefix}-{number}"
        else:
            return f"{prefix}-{number}"
    return None

zroot = r"Z:\av"
files = []
for root, dirs, ff in os.walk(zroot):
    for f in ff:
        if f.lower().endswith((".mp4", ".mkv", ".avi", ".wmv", ".ts", ".iso", ".rmvb", ".mov", ".m2ts")):
            rel = os.path.relpath(os.path.join(root, f), zroot)
            files.append((rel, extract(os.path.splitext(f)[0])))

print(f"共 {len(files)} 个视频")
ok = [t for t in files if t[1]]
bad = [t for t in files if not t[1]]
print(f"可提取番号: {len(ok)}  提取失败: {len(bad)}")
print("\n--- 提取失败 ---")
for rel, c in bad:
    print("  ", rel)
codes = [c for _, c in ok]
dup = set(x for x in codes if codes.count(x) > 1)
print("\n--- 疑似重复番号 ---")
for d in dup:
    print("  ", d, [rel for rel, c in ok if c == d])
print("\n--- 样例(前30) ---")
for rel, c in ok[:30]:
    print(f"  [{c}]  {rel}")
