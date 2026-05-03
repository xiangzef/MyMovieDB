"""
番号电影整理脚本

功能：
1. 扫描目标目录下所有番号电影文件
2. 规范化文件名（如 HND966C → HND-966-C）
3. 将单独文件放入同番号文件夹，或整理已有文件夹

用法：
    py -3.14 tests/organize_videos.py

作者：小尼克 (WorkBuddy AI)
"""
import sys
import os
import re
import shutil
from pathlib import Path
from typing import Optional, List, Tuple

# ─────────────────────────────────────────────────────────────────────────────
# 番号提取逻辑（来自 organizer.py）
# ─────────────────────────────────────────────────────────────────────────────

_CODE_PATTERNS = [
    re.compile(r'\b(FC2[-_]?PPV[-_]?\d{5,9})\b', re.IGNORECASE),
    re.compile(r'\b(\d{3}[A-Z]{2,6}[-_]?\d{2,5})\b', re.IGNORECASE),
    re.compile(r'\b([A-Z]{2,6}-\d{2,5})\b', re.IGNORECASE),
    re.compile(r'\b([A-Z]{2,6})(\d{3,5})\b', re.IGNORECASE),
]

_CODE_BLACKLIST = re.compile(
    r'^(X264|X265|XC|WEB|HD|MP4|MKV|AVC|HEVC|FHD|SDR|HDR|AAC|AC3|DTS|'
    r'WEBRIPX|INTERNAL|BLURAY|BDRIP|WEBRIP|DVDRIP|HDRIP|SDTV|HDTV|'
    r'REMUX|PROPER|REPACK|EXTENDED|UNRATED|THEATRICAL)$',
    re.IGNORECASE
)

_RE_GARBAGE_PREFIX = re.compile(
    r'^(?:[a-z0-9\-]+\.(?:xyz|com|net|org|cc|me|tv|club|top|site|info|biz)[@-])',
    re.IGNORECASE
)
_RE_CN_BRACKET_PREFIX = re.compile(r'^[【\[（(][^\]】）)]*[】\]）)]\s*', re.IGNORECASE)

VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.wmv', '.mov', '.flv', '.webm', '.m4v', '.mpg', '.mpeg'}
JUNK_EXTENSIONS = {'.torrent', '.url', '.html', '.htm', '.txt', '.ini', '.db', '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.svg'}
SMALL_VIDEO_THRESHOLD = 50 * 1024 * 1024  # 50MB 以下视为小视频/预告片


def _strip_garbage_prefix(name: str) -> str:
    name = _RE_CN_BRACKET_PREFIX.sub('', name)
    name = _RE_GARBAGE_PREFIX.sub('', name)
    return name


def _extract_code(name: str) -> Optional[str]:
    """从文件名提取番号"""
    name = name.strip()
    cleaned = _strip_garbage_prefix(name)
    for i, pat in enumerate(_CODE_PATTERNS):
        m = pat.search(cleaned)
        if m:
            if i == 3:
                raw = f"{m.group(1)}-{m.group(2)}".upper()
            else:
                raw = m.group(1).upper().replace('_', '-')
            if _CODE_BLACKLIST.match(raw):
                continue
            return raw
    for i, pat in enumerate(_CODE_PATTERNS):
        m = pat.search(name)
        if m:
            if i == 3:
                raw = f"{m.group(1)}-{m.group(2)}".upper()
            else:
                raw = m.group(1).upper().replace('_', '-')
            if _CODE_BLACKLIST.match(raw):
                continue
            return raw
    return None


def _extract_code_with_suffix(name: str) -> Tuple[Optional[str], str, str, str]:
    """从文件名提取番号 + 字幕类型 + 显示名 + 多盘标识"""
    base = Path(name).stem
    subtitle_type = "none"
    base_lower = base.lower()

    if base_lower.endswith("-uc"):
        subtitle_type = "bilingual"
        core = base[:-3]
    elif base_lower.endswith("-u"):
        subtitle_type = "english"
        core = base[:-2]
    elif base_lower.endswith("-c"):
        subtitle_type = "chinese"
        core = base[:-2]
    else:
        core = base

    disc_label = ""
    core_lower = core.lower()

    if core_lower.endswith("-a") or core_lower.endswith("-b"):
        disc_label = core[-1].upper()
        core = core[:-2]
    elif core_lower.endswith("-c"):
        disc_label = "C"
        core = core[:-2]

    code = _extract_code(core)
    display_name = ""
    if code and len(core) > len(code) and core[:len(code)].upper() == code:
        display_name = core[len(code):]
    else:
        display_name = ""

    return code, subtitle_type, display_name, disc_label


def _safe_name(name: str) -> str:
    """生成安全文件名/文件夹名"""
    for ch in r'/\:*?"<>|':
        name = name.replace(ch, "_")
    name = re.sub(r'[\[\]【】]', '', name)
    name = name.strip(' _.')
    return name


def _normalize_filename(filename: str) -> Optional[str]:
    """规范化文件名，返回 None 表示无法识别番号"""
    code, subtitle_type, display_name, disc_label = _extract_code_with_suffix(filename)
    if not code:
        return None

    # 重建文件名：番号 + 盘符 + 字幕后缀 + 原始扩展名
    parts = [code]
    if disc_label:
        parts.append(disc_label)
    # 字幕后缀
    if subtitle_type == "chinese":
        parts.append("C")
    elif subtitle_type == "english":
        parts.append("U")
    elif subtitle_type == "bilingual":
        parts.append("UC")

    return ''.join(parts)


def _is_junk_file(path: Path) -> bool:
    """判断是否为垃圾文件（种子、html、图片等）"""
    ext = path.suffix.lower()
    if ext in JUNK_EXTENSIONS:
        return True
    # 小体积视频文件（预告片等）
    if ext in VIDEO_EXTENSIONS and path.stat().st_size < SMALL_VIDEO_THRESHOLD:
        return True
    return False


def _format_size(size: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}GB"


class VideoOrganizer:
    """番号电影整理器"""

    def __init__(self, target_path: str):
        self.target_path = Path(target_path)
        self.total_processed = 0
        self.total_created = 0
        self.total_moved = 0
        self.total_deleted = 0
        self.total_renamed = 0
        self.errors: List[str] = []

    def log(self, msg: str):
        """实时输出进度"""
        print(f"[{self.total_processed}] {msg}")

    def organize(self):
        """执行整理"""
        print(f"\n{'='*60}")
        print(f"开始整理: {self.target_path}")
        print(f"{'='*60}\n")

        # Step 1: 扫描所有视频文件
        print("📂 扫描视频文件...")
        video_files = []
        for f in self.target_path.rglob("*"):
            if not f.is_file():
                continue
            ext = f.suffix.lower()
            if ext not in VIDEO_EXTENSIONS:
                continue
            video_files.append(f)

        print(f"找到 {len(video_files)} 个视频文件\n")

        if not video_files:
            print("⚠️ 未找到任何视频文件")
            return

        # Step 2: 分类处理
        for video_path in video_files:
            self.total_processed += 1
            try:
                self._process_video(video_path)
            except Exception as e:
                self.errors.append(f"{video_path}: {e}")
                print(f"  ❌ 错误: {e}")

        # Step 3: 统计结果
        self._print_summary()

    def _process_video(self, video_path: Path):
        """处理单个视频文件"""
        parent = video_path.parent
        filename = video_path.name

        # 提取番号信息
        code, subtitle_type, display_name, disc_label = _extract_code_with_suffix(filename)
        if not code:
            self.log(f"⏭️ 跳过无法识别番号: {filename}")
            return

        # 规范化文件名
        normalized_name = _normalize_filename(filename)
        ext = video_path.suffix

        if not normalized_name:
            self.log(f"⏭️ 跳过无法识别番号: {filename}")
            return

        # 判断：视频是否直接在目标目录下
        if parent == self.target_path:
            # 检查是否有同名空文件夹（之前遗留）
            target_dir = self.target_path / _safe_name(code)
            if target_dir.exists() and target_dir.is_dir():
                # 如果是空文件夹，直接删除
                if not any(target_dir.iterdir()):
                    target_dir.rmdir()
                else:
                    # 非空文件夹，可能有其他视频，合并进去
                    pass
            else:
                target_dir.mkdir(exist_ok=True)

            # 检查是否有同名文件（需要先改名）
            same_name_file = self.target_path / code
            if same_name_file.exists() and same_name_file.is_file():
                # 文件名冲突，临时改名
                temp_path = self.target_path / f"{code}_temp{ext}"
                same_name_file.rename(temp_path)
                video_path = temp_path

            new_path = target_dir / (normalized_name + ext)

            # 如果目标已存在（同名文件），比较大小
            if new_path.exists():
                # 目标已存在，比较大小，保留大的
                if new_path.stat().st_size >= video_path.stat().st_size:
                    self.log(f"⏭️ 目标已存在且更大，跳过: {normalized_name}{ext}")
                    return
                else:
                    self.log(f"🗑️ 替换更小的目标: {normalized_name}{ext}")

            shutil.move(str(video_path), str(new_path))
            self.total_moved += 1
            self.log(f"📁 {code} → 创建文件夹并移入")

        elif parent.parent == self.target_path and parent.name != _safe_name(code):
            # 情况2：视频在目标目录的子文件夹中 → 清理文件夹内容，重命名文件夹
            folder_name = parent.name

            # 清理垃圾文件
            junk_deleted = 0
            for junk_file in parent.iterdir():
                if _is_junk_file(junk_file):
                    try:
                        junk_file.unlink()
                        junk_deleted += 1
                        self.total_deleted += 1
                    except Exception:
                        pass

            # 清理完后，检查是否只剩视频文件（可能多个盘）
            remaining_videos = [f for f in parent.iterdir() if f.suffix.lower() in VIDEO_EXTENSIONS]

            # 重命名文件夹
            new_folder_name = _safe_name(code)
            if folder_name != new_folder_name:
                new_parent = self.target_path / new_folder_name
                if new_parent.exists():
                    # 文件夹已存在，合并
                    for remaining_video in remaining_videos:
                        target_path = new_parent / remaining_video.name
                        if remaining_video != target_path:
                            if target_path.exists():
                                if target_path.stat().st_size >= remaining_video.stat().st_size:
                                    remaining_video.unlink()
                                    continue
                            shutil.move(str(remaining_video), str(target_path))
                    # 删除空文件夹
                    try:
                        if not any(parent.iterdir()):
                            shutil.rmtree(str(parent))
                    except:
                        pass
                else:
                    shutil.move(str(parent), str(new_parent))
                self.total_renamed += 1
                self.log(f"📁 {folder_name} → {new_folder_name}" + (f" (清理{junk_deleted}个垃圾)" if junk_deleted else ""))

        else:
            # 情况3：嵌套在更深的目录，尝试向上检查
            for ancestor in video_path.parents:
                if ancestor == self.target_path:
                    break
                # 检查是否是番号文件夹但名称不对
                ancestor_name = ancestor.name
                code_in_ancestor, _, _, _ = _extract_code_with_suffix(ancestor_name)
                if code_in_ancestor and ancestor_name != _safe_name(code_in_ancestor):
                    new_name = self.target_path / _safe_name(code_in_ancestor)
                    if ancestor.name != _safe_name(code_in_ancestor):
                        shutil.move(str(ancestor), str(new_name))
                        self.total_renamed += 1
                    break

            self.log(f"✅ 已处理: {filename}")

    def _print_summary(self):
        """打印整理结果汇总"""
        print(f"\n{'='*60}")
        print(f"整理完成!")
        print(f"{'='*60}")
        print(f"📊 处理文件: {self.total_processed}")
        print(f"📁 新建文件夹: {self.total_created}")
        print(f"📦 移动文件: {self.total_moved}")
        print(f"✏️ 重命名文件夹: {self.total_renamed}")
        print(f"🗑️ 删除垃圾文件: {self.total_deleted}")

        if self.errors:
            print(f"\n❌ 错误 ({len(self.errors)}):")
            for err in self.errors[:10]:
                print(f"   - {err}")
            if len(self.errors) > 10:
                print(f"   ... 还有 {len(self.errors) - 10} 个错误")


def select_folder() -> str:
    """打开文件夹选择对话框"""
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()

    folder = filedialog.askdirectory(title="选择要整理的视频文件夹")
    root.destroy()

    return folder


def main():
    print("=" * 60)
    print("番号电影整理工具")
    print("=" * 60)

    # 选择文件夹
    print("\n📂 打开文件夹选择器...")
    folder = select_folder()

    if not folder:
        print("❌ 未选择文件夹，退出")
        sys.exit(0)

    print(f"✅ 已选择: {folder}\n")

    # 执行整理
    organizer = VideoOrganizer(folder)
    organizer.organize()


if __name__ == "__main__":
    main()