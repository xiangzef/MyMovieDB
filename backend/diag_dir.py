"""查看 X:\中转站 目录结构"""
from pathlib import Path

base = Path(r"X:\中转站")
if not base.exists():
    print("路径不存在")
    import sys; sys.exit(1)

print(f"=== X:\\中转站 目录结构 ===\n")

for d in sorted(base.iterdir()):
    if d.is_dir():
        files = [f for f in d.rglob("*") if f.is_file()]
        print(f"[{d.name}] ({len(files)} files)")
        for f in sorted(files)[:5]:
            print(f"  {f.name}")
        if len(files) > 5:
            print(f"  ... 还有 {len(files)-5} 个文件")
        print()
    else:
        print(f"[FILE] {d.name}")
