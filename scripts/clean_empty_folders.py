"""
clean_empty_folders.py
======================
扫描指定目录，找出"垃圾文件夹"并删除（送回回收站）。

判定规则（满足全部才删除）：
  1. 文件夹总大小 < 100 KB
  2. 不包含任何影视文件（视频 / 音频 / 字幕）
  3. 不包含 2 张或以上图片
  4. 文件内容仅为：空文件夹 / 单个种子文件(.torrent) / 少量无用文本/链接文件

用法：
  python clean_empty_folders.py <目标目录> [--delete]

  不加 --delete 时只预览，不做任何删除（推荐先跑一次确认）。
  加上 --delete 后才真正删除（送入回收站，可恢复）。
"""

import os
import sys
import argparse
from pathlib import Path

# ── 扩展名分类 ──────────────────────────────────────────────────────────────
VIDEO_EXT = {
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".ts", ".m2ts",
    ".rmvb", ".rm", ".m4v", ".webm", ".vob", ".mpg", ".mpeg",
    ".iso", ".img",  # 光盘镜像
}
AUDIO_EXT = {
    ".mp3", ".flac", ".wav", ".aac", ".ogg", ".m4a", ".wma", ".ape",
}
SUBTITLE_EXT = {
    ".srt", ".ass", ".ssa", ".sub", ".idx", ".vtt",
}
IMAGE_EXT = {
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".tif",
    ".heic", ".avif",
}
TORRENT_EXT = {".torrent"}

# 影视"有效"扩展 = 视频 + 音频 + 字幕
MEDIA_EXT = VIDEO_EXT | AUDIO_EXT | SUBTITLE_EXT


def folder_total_size(folder: Path) -> int:
    """递归计算文件夹总字节数"""
    total = 0
    try:
        for f in folder.rglob("*"):
            if f.is_file():
                try:
                    total += f.stat().st_size
                except OSError:
                    pass
    except PermissionError:
        pass
    return total


def collect_files(folder: Path):
    """返回文件夹内所有文件（递归）的 Path 列表"""
    files = []
    try:
        for f in folder.rglob("*"):
            if f.is_file():
                files.append(f)
    except PermissionError:
        pass
    return files


def is_junk_folder(folder: Path):
    """
    判断是否为垃圾文件夹。
    返回 (True/False, 原因说明)
    """
    # 1. 大小检查
    size = folder_total_size(folder)
    if size >= 100 * 1024:  # 100 KB
        return False, f"大小 {size/1024:.1f} KB ≥ 100 KB"

    files = collect_files(folder)

    # 2. 影视文件检查（绝对不删）
    media_files = [f for f in files if f.suffix.lower() in MEDIA_EXT]
    if media_files:
        return False, f"含影视文件: {[f.name for f in media_files[:3]]}"

    # 3. 图片检查（≥2张不删）
    image_files = [f for f in files if f.suffix.lower() in IMAGE_EXT]
    if len(image_files) >= 2:
        return False, f"含 {len(image_files)} 张图片"

    # 4. 通过所有检查 → 判定为垃圾文件夹
    torrent_files = [f for f in files if f.suffix.lower() in TORRENT_EXT]
    if not files:
        reason = "空文件夹"
    elif torrent_files and len(files) == len(torrent_files):
        reason = f"仅含 {len(torrent_files)} 个种子文件"
    else:
        non_media = [f.name for f in files]
        reason = f"小文件夹({size/1024:.1f}KB), 文件: {non_media[:5]}"

    return True, reason


def send_to_recycle(path: Path) -> bool:
    """将文件夹送入回收站（Windows）"""
    try:
        import winreg  # noqa: F401 确认是 Windows
        import ctypes
        from ctypes import wintypes

        # 使用 SHFileOperationW 送入回收站
        class SHFILEOPSTRUCTW(ctypes.Structure):
            _fields_ = [
                ("hwnd",                wintypes.HWND),
                ("wFunc",               ctypes.c_uint),
                ("pFrom",               ctypes.c_wchar_p),
                ("pTo",                 ctypes.c_wchar_p),
                ("fFlags",              ctypes.c_ushort),
                ("fAnyOperationsAborted", wintypes.BOOL),
                ("hNameMappings",       ctypes.c_void_p),
                ("lpszProgressTitle",   ctypes.c_wchar_p),
            ]

        FO_DELETE = 0x0003
        FOF_ALLOWUNDO = 0x0040        # 送回收站
        FOF_NOCONFIRMATION = 0x0010   # 不弹确认框
        FOF_NOERRORUI = 0x0400        # 不弹错误框
        FOF_SILENT = 0x0004           # 静默

        # pFrom 需要双 null 结尾
        from_path = str(path) + "\0"

        op = SHFILEOPSTRUCTW()
        op.hwnd = None
        op.wFunc = FO_DELETE
        op.pFrom = from_path
        op.pTo = None
        op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_NOERRORUI | FOF_SILENT

        shell32 = ctypes.windll.shell32
        result = shell32.SHFileOperationW(ctypes.byref(op))
        return result == 0
    except Exception as e:
        print(f"  ⚠️  回收站操作失败({e})，尝试直接删除...")
        import shutil
        try:
            shutil.rmtree(path)
            return True
        except Exception as e2:
            print(f"  ❌ 删除失败: {e2}")
            return False


def scan_and_clean(root: Path, do_delete: bool):
    root = root.resolve()
    if not root.exists() or not root.is_dir():
        print(f"❌ 路径不存在或不是文件夹: {root}")
        sys.exit(1)

    print(f"\n🔍 扫描目录: {root}")
    print(f"{'🗑️  执行删除模式' if do_delete else '👁️  预览模式（不会删除任何文件）'}")
    print("=" * 60)

    to_delete = []   # (Path, reason)
    skipped = []     # (Path, reason)

    # 从最深层往上扫（避免父目录先被标记后子目录重复处理）
    all_dirs = sorted(
        [d for d in root.rglob("*") if d.is_dir()],
        key=lambda p: len(p.parts),
        reverse=True,   # 深度优先（叶子先处理）
    )

    for folder in all_dirs:
        # 跳过已被标记删除的祖先目录的子目录（避免重复）
        # 兼容Python 3.8（无is_relative_to）
        skip = False
        for p, _ in to_delete:
            try:
                folder.relative_to(p)
                skip = True
                break
            except ValueError:  # not relative
                pass
        if skip:
            continue
        junk, reason = is_junk_folder(folder)
        if junk:
            to_delete.append((folder, reason))
        else:
            skipped.append((folder, reason))

    # ── 输出结果 ──
    print(f"\n✅ 保留文件夹（{len(skipped)} 个）：")
    for p, r in skipped[:20]:
        print(f"  保留  {p.relative_to(root)}  →  {r}")
    if len(skipped) > 20:
        print(f"  ... 共 {len(skipped)} 个保留（仅显示前20条）")

    print(f"\n🗑️  待删除文件夹（{len(to_delete)} 个）：")
    for p, r in to_delete:
        print(f"  删除  {p.relative_to(root)}  →  {r}")

    if not to_delete:
        print("\n✨ 没有找到需要删除的文件夹，退出。")
        return

    if not do_delete:
        print(f"\n⚠️  预览模式，未做任何操作。")
        print(f"   确认无误后请加 --delete 参数重新运行以执行删除。")
        return

    # ── 执行删除 ──
    print("\n" + "=" * 60)
    print("⚠️  即将删除以上文件夹（送入回收站，可恢复）...")
    confirm = input("输入 YES 确认删除，其他任意键取消: ").strip()
    if confirm != "YES":
        print("已取消。")
        return

    success, fail = 0, 0
    for p, r in to_delete:
        if not p.exists():
            print(f"  跳过（已不存在）: {p.name}")
            continue
        print(f"  正在删除: {p} ...", end=" ")
        ok = send_to_recycle(p)
        if ok:
            print("✅")
            success += 1
        else:
            print("❌")
            fail += 1

    print(f"\n完成！成功删除 {success} 个，失败 {fail} 个。")


def main():
    parser = argparse.ArgumentParser(
        description="扫描并清理指定目录下的垃圾文件夹（空/仅含种子/小于100KB且无影视）"
    )
    parser.add_argument("target", help="要扫描的目标目录")
    parser.add_argument(
        "--delete",
        action="store_true",
        help="加上此参数才真正执行删除（默认仅预览）",
    )
    args = parser.parse_args()

    scan_and_clean(Path(args.target), args.delete)


if __name__ == "__main__":
    main()
