# -*- coding: utf-8 -*-
import os, re, sys
sys.stdout.reconfigure(encoding="utf-8")
CODE_RE = re.compile(r"([A-Z]{2,6})-(\d{2,5})")
EXCL = ["WEB", "HD", "BD", "720", "1080", "4K", "UHD", "SD"]

for stem in ["www.98T.la@JBD-240_restored_wm", "www.98T.la@SDSI-008_restored_wm"]:
    up = stem.upper()
    print("stem repr:", repr(stem))
    for m in CODE_RE.finditer(up):
        prefix, num = m.groups()
        full = m.group(0)
        pos = up.find(full)
        before = up[:pos] if pos > 0 else ""
        print(f"  match={full!r} pos={pos} before={before!r}")
        print("   before.endswith(excl)?", any(before.endswith(w) for w in EXCL))
        print("   mixed?", re.search(r"(\d{2,4})[A-Z]{2,6}$", before))
        print("   prefix excl?", any(prefix.startswith(w) or prefix.endswith(w) for w in EXCL if prefix != w))
# 看真实文件夹内文件名字节
z = r"Z:\av"
for f in sorted(os.listdir(z)):
    if "JBD-240" in f or "SDSI-008" in f:
        print(repr(f), "->", " ".join(hex(b) for b in f.encode("utf-8")[:40]))
