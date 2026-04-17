"""
================================================================================
整理功能模块（Phase 0.5）
================================================================================
功能: 按 Jellyfin 标准文件夹结构整理本地视频文件
目标结构:
    {根}\jellyfin\{女演员}\{番号}\{番号}[-C|-U|-UC].mp4
                                   \{番号}.nfo
                                   \{番号}-poster.jpg
                                   \{番号}-fanart.jpg
                                   \{番号}-thumb.jpg
字幕后缀:
    无后缀 = 无字幕 (none)
    -C = 中文字幕 (chinese)
    -U = 英文字幕 (english)
    -UC = 双语字幕 (bilingual)
================================================================================
"""

import re
import os
import shutil
import logging
import asyncio
import subprocess
import threading
from pathlib import Path
from typing import Optional, List, Callable, Iterator, Generator
from datetime import datetime

import database as db
from models import SubtitleType, OrganizeMode, OrganizePreviewItem, OrganizeProgress, SUBTITLE_LABELS

logger = logging.getLogger("organizer")

# ─────────────────────────────────────────────────────────────────────────────
# 全局中止标志（线程安全）
# ─────────────────────────────────────────────────────────────────────────────
_abort_organize = False

def reset_abort():
    global _abort_organize
    _abort_organize = False

def request_abort():
    global _abort_organize
    _abort_organize = True


# ─────────────────────────────────────────────────────────────────────────────
# 视频扩展名
# ─────────────────────────────────────────────────────────────────────────────
VIDEO_EXTENSIONS = {
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv",
    ".m4v", ".mpg", ".mpeg", ".webm", ".ts", ".vob",
}


# ─────────────────────────────────────────────────────────────────────────────
# 番号识别
# ─────────────────────────────────────────────────────────────────────────────

# 各类番号格式（按优先级排列）
_CODE_PATTERNS = [
    # FC2PPV: FC2PPV1234567（支持有无连字符）
    re.compile(r'\b(FC2[-_]?PPV[-_]?\d{5,9})\b', re.IGNORECASE),
    # 300MIUM / 390JAC 等含数字前缀的系列：300MIUM-746 或 300MIUM746
    re.compile(r'\b(\d{3}[A-Z]{2,6}[-_]?\d{2,5})\b', re.IGNORECASE),
    # 常规番号带连字符：CAWD-285、SSIS-196、PFES-120（优先）
    re.compile(r'\b([A-Z]{2,6}-\d{2,5})\b', re.IGNORECASE),
    # 常规番号无连字符：IPX722、MVSD487（次优先，要求字母+数字分界明显）
    re.compile(r'\b([A-Z]{2,6})(\d{3,5})\b', re.IGNORECASE),
]

# 全黑名单：这些匹配结果是误判（常见非番号关键词）
_CODE_BLACKLIST = re.compile(
    r'^(X264|X265|XC|WEB|HD|MP4|MKV|AVC|HEVC|FHD|SDR|HDR|AAC|AC3|DTS|'
    r'WEBRIPX|INTERNAL|BLURAY|BDRIP|WEBRIP|DVDRIP|HDRIP|SDTV|HDTV|'
    r'REMUX|PROPER|REPACK|EXTENDED|UNRATED|THEATRICAL)$',
    re.IGNORECASE
)

# 垃圾前缀清洗：去掉 "amav.xyz-"、"bbsxv.xyz-" 之类的域名水印
_RE_GARBAGE_PREFIX = re.compile(
    r'^(?:[a-z0-9\-]+\.(?:xyz|com|net|org|cc|me|tv|club|top|site|info|biz)[@-])',
    re.IGNORECASE
)

# 中文字符前缀清洗：去掉 【ses23.com】 之类
_RE_CN_BRACKET_PREFIX = re.compile(r'^[【\[（(][^\]】）)]*[】\]）)]\s*', re.IGNORECASE)


def _strip_garbage_prefix(name: str) -> str:
    """清洗文件名前的垃圾前缀：域名水印、中文括号前缀等"""
    name = _RE_CN_BRACKET_PREFIX.sub('', name)  # 先去中文括号
    name = _RE_GARBAGE_PREFIX.sub('', name)      # 再去域名前缀
    return name


def _extract_code(name: str) -> Optional[str]:
    """从文件名（或目录名）提取番号。支持有垃圾前缀的文件名。"""
    name = name.strip()
    # 先尝试清洗垃圾前缀后匹配
    cleaned = _strip_garbage_prefix(name)
    for i, pat in enumerate(_CODE_PATTERNS):
        m = pat.search(cleaned)
        if m:
            if i == 3:
                # 无连字符模式：把 (字母, 数字) 两组合并，补连字符
                raw = f"{m.group(1)}-{m.group(2)}".upper()
            else:
                raw = m.group(1).upper().replace('_', '-')
            if _CODE_BLACKLIST.match(raw):
                continue
            return raw
    # 清洗前也尝试一次（覆盖 bbsxv.xyzSSIS062C 这类无分隔符粘连的情况）
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


def _extract_code_with_suffix(name: str) -> tuple:
    """
    从文件名提取番号 + 字幕类型 + 显示名 + 多盘标识
    返回: (code, subtitle_type, display_name, disc_label)

    字幕类型:
        "none"      = 无字幕（无后缀）
        "chinese"   = 中文字幕（-C 后缀，不区分大小写）
        "english"   = 无马赛克（-U 后缀，不区分大小写）
        "bilingual" = 无马赛克+中文字幕（-UC 后缀，不区分大小写）

    多盘标识 (disc_label): "A" | "B" | "C" | ""
        文件夹里同番号有多个视频文件，命名会带 -A/-B/-C 区分

    处理顺序（非常重要，顺序不能反）：
        1. 先剥离字幕后缀 (-UC > -U > -C)
        2. 再剥离多盘标识 (-A/-B/-C)
        3. 最后提取番号
        这样才能正确处理 CAWD-285-C-A（中文字幕 A 盘）等组合

    无连字符番号（如 IPX722、MVSD487）也被支持，
    _extract_code 中的第4个正则会匹配并自动补连字符 → IPX-722、MVSD-487
    """
    base = Path(name).stem

    # ── Step 1：剥离字幕后缀（优先级 -UC > -U > -C，不区分大小写）──────
    subtitle_type = SubtitleType.NONE.value
    base_lower = base.lower()

    if base_lower.endswith("-uc"):
        subtitle_type = SubtitleType.BILINGUAL.value
        core = base[:-3]
    elif base_lower.endswith("-u"):
        subtitle_type = SubtitleType.ENGLISH.value
        core = base[:-2]
    elif base_lower.endswith("-c"):
        subtitle_type = SubtitleType.CHINESE.value
        core = base[:-2]
    else:
        core = base

    # ── Step 2：剥离多盘标识 -A / -B / -C（在字幕后缀之后）──────────────
    # 注意：-C 已被 Step1 作为字幕后缀处理，这里只处理 -A 和 -B
    # 但如果 subtitle_type 已经不是 none（Step1 已消耗了一个 -C），
    # 那么 core 末尾的 -A/-B/-C 才是多盘标识；
    # 如果 subtitle_type 是 none，core 末尾的 -C 可能是多盘标识 C 盘
    disc_label = ""
    core_lower = core.lower()

    if core_lower.endswith("-a") or core_lower.endswith("-b"):
        disc_label = core[-1].upper()
        core = core[:-2]
    elif core_lower.endswith("-c"):
        # 这里 -C 是多盘 C 盘（因为字幕 -C 已在 Step1 消耗，
        # 若 Step1 没消耗到 -C，说明原始文件名末尾就是 -C，判定为多盘 C 盘）
        disc_label = "C"
        core = core[:-2]

    # ── Step 3：提取番号 ────────────────────────────────────────────────
    code = _extract_code(core)

    # display_name = 去掉番号后的剩余前缀（理论上为空）
    if code and len(core) > len(code) and core[:len(code)].upper() == code:
        display_name = core[len(code):]
    else:
        display_name = ""

    return code, subtitle_type, display_name, disc_label


# ─────────────────────────────────────────────────────────────────────────────
# 安全文件名 / 文件夹名
# ─────────────────────────────────────────────────────────────────────────────
def _safe_file_name(name: str) -> str:
    for ch in r'/\:*?"<>|':
        name = name.replace(ch, "_")
    return name.strip(". ")

def _safe_dir_name(name: str) -> str:
    """生成合法的文件夹名，去掉方括号、下划线前后缀和非法字符"""
    name = _safe_file_name(name)
    # 去掉方括号/中括号（[_楓ふうあ_] → 楓ふうあ）
    name = re.sub(r'[\[\]【】]', '', name)
    # 去掉前后多余的空格、下划线、点
    name = name.strip(' _.')
    return name


# ─────────────────────────────────────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────────────────────────────────────
def _human_size(n: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if n < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}PB"


# ─────────────────────────────────────────────────────────────────────────────
# 扫描文件（Generator: yield 每个找到的文件）
# ─────────────────────────────────────────────────────────────────────────────
def scan_video_files_gen(
    source_paths: List[str],
    progress_callback: Optional[Callable] = None,
) -> Generator[dict, None, None]:
    """
    扫描多个源目录，yield 每个视频文件的元数据（流式，逐文件产出）。
    不再等全部扫描完才返回。
    """
    for source_path in source_paths:
        p = Path(source_path)
        if not p.exists():
            logger.warning(f"[Organizer] 路径不存在: {source_path}")
            continue

        try:
            for file_path in p.rglob("*"):
                if _abort_organize:
                    return
                if not file_path.is_file():
                    continue
                ext = file_path.suffix.lower()
                if ext not in VIDEO_EXTENSIONS:
                    continue

                code, subtitle_type, display_name, disc_label = _extract_code_with_suffix(file_path.name)
                item = {
                    "path": str(file_path),
                    "name": file_path.name,
                    "display_name": display_name,
                    "code": code,
                    "subtitle_type": subtitle_type,
                    "disc_label": disc_label,  # 多盘标识 A/B/C
                    "size": 0,  # stat 放后面，避免阻塞网络路径
                }

                # 实时 yield（每找到一个文件就产出）
                yield item

        except PermissionError:
            logger.warning(f"[Organizer] 权限不足，跳过: {source_path}")
        except Exception as e:
            logger.error(f"[Organizer] 扫描出错 {source_path}: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# 扫描文件（兼容旧接口，批量返回）
# ─────────────────────────────────────────────────────────────────────────────
def scan_video_files(source_paths: List[str]) -> List[dict]:
    return list(scan_video_files_gen(source_paths))


# ─────────────────────────────────────────────────────────────────────────────
# 目标路径构建
# ─────────────────────────────────────────────────────────────────────────────
def build_target_path(
    code: str,
    actor_name: str,
    subtitle_type: str,
    target_root: str,
    disc_label: str = ""
) -> tuple:
    """
    构建 Jellyfin 标准目标路径
    disc_label: 多盘标识 "A"/"B"/"C"，为空则不加
    """
    target_root = Path(target_root)
    actor_safe = _safe_dir_name(actor_name)
    code_safe = _safe_file_name(code)

    target_dir = target_root / "jellyfin" / actor_safe / code_safe

    video_ext = ".mp4"
    suffix_map = {
        SubtitleType.CHINESE.value: "-C",
        SubtitleType.ENGLISH.value: "-U",
        SubtitleType.BILINGUAL.value: "-UC",
    }
    suffix_str = suffix_map.get(subtitle_type, "")
    
    # 添加多盘标识（如有）
    disc_str = f"-{disc_label}" if disc_label else ""
    target_file = target_dir / f"{code_safe}{suffix_str}{disc_str}{video_ext}"

    return str(target_dir), str(target_file)


# ─────────────────────────────────────────────────────────────────────────────
# NFO 生成
# ─────────────────────────────────────────────────────────────────────────────
def _escape_xml(text: str) -> str:
    if not text:
        return ""
    text = str(text)
    for char, entity in [("&", "&amp;"), ("<", "&lt;"), (">", "&gt;"),
                          ('"', "&quot;"), ("'", "&apos;")]:
        text = text.replace(char, entity)
    return text


def generate_organize_nfo(
    movie_data: dict,
    target_dir: str,
    subtitle_type: str = "none"
) -> Optional[str]:
    code = movie_data.get("code", "")
    if not code:
        return None
    safe_code = _safe_file_name(code)
    nfo_path = Path(target_dir) / f"{safe_code}.nfo"
    nfo_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        lines = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>']
        lines.append("<movie>")
        lines.append(f"  <title>{_escape_xml(movie_data.get('title', code))}</title>")
        lines.append(f"  <code>{_escape_xml(code)}</code>")
        if movie_data.get("release_date"):
            lines.append(f"  <releasedate>{_escape_xml(movie_data['release_date'])}</releasedate>")
            lines.append(f"  <year>{movie_data['release_date'][:4]}</year>")
        if movie_data.get("duration"):
            lines.append(f"  <runtime>{movie_data['duration']}</runtime>")
        if movie_data.get("studio"):
            lines.append(f"  <studio>{_escape_xml(movie_data['studio'])}</studio>")
        if movie_data.get("maker"):
            lines.append(f"  <maker>{_escape_xml(movie_data['maker'])}</maker>")
        if movie_data.get("director"):
            lines.append(f"  <director>{_escape_xml(movie_data['director'])}</director>")
        if movie_data.get("plot"):
            lines.append(f"  <plot>{_escape_xml(movie_data['plot'])}</plot>")

        actors = movie_data.get("actors", [])
        if isinstance(actors, str):
            actors = [a.strip() for a in actors.split(",") if a.strip()]
        for actor in (actors or []):
            lines.append("  <actor>")
            lines.append(f"    <name>{_escape_xml(actor)}</name>")
            lines.append("    <type>Actress</type>")
            lines.append("  </actor>")

        actors_male = movie_data.get("actors_male", [])
        if isinstance(actors_male, str):
            actors_male = [a.strip() for a in actors_male.split(",") if a.strip()]
        for actor in (actors_male or []):
            lines.append("  <actor>")
            lines.append(f"    <name>{_escape_xml(actor)}</name>")
            lines.append("    <type>Actor</type>")
            lines.append("  </actor>")

        genres = movie_data.get("genres", [])
        if isinstance(genres, str):
            genres = [g.strip() for g in genres.split(",") if g.strip()]
        for genre in (genres or []):
            lines.append(f"  <genre>{_escape_xml(genre)}</genre>")

        if subtitle_type and subtitle_type != SubtitleType.NONE.value:
            lines.append(f"  <subtitle_type>{_escape_xml(subtitle_type)}</subtitle_type>")
            lines.append("  <local_subtitle>true</local_subtitle>")

        lines.append("</movie>")
        nfo_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info(f"[Organize] NFO 生成: {nfo_path}")
        return str(nfo_path)
    except Exception as e:
        logger.error(f"[Organize] NFO 生成失败 {nfo_path}: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# 封面复制
# ─────────────────────────────────────────────────────────────────────────────
def _copy_asset_files(movie_data: dict, target_dir: str, code: str):
    safe_code = _safe_file_name(code)
    for attr, fname in [
        ("poster_path", f"{safe_code}-poster.jpg"),
        ("fanart_path", f"{safe_code}-fanart.jpg"),
        ("thumb_path", f"{safe_code}-thumb.jpg"),
    ]:
        src = movie_data.get(attr)
        if src and Path(src).exists():
            try:
                dst = Path(target_dir) / fname
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
            except Exception as e:
                logger.warning(f"[Organize] 封面复制失败 {src} → {dst}: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# 工具
# ─────────────────────────────────────────────────────────────────────────────
def _get_primary_actor(movie_data: dict) -> Optional[str]:
    actors = movie_data.get("actors", [])
    if isinstance(actors, str):
        actors = [a.strip() for a in actors.split(",") if a.strip()]
    return actors[0] if actors else None


def _target_exists(f: dict, movies_map: dict, target_root: str) -> bool:
    code = f.get("code")
    if not code:
        return False
    movie_data = movies_map.get(code, {})
    _, target_file = build_target_path(
        code,
        _get_primary_actor(movie_data) or "未知演员",
        f["subtitle_type"] or "none",
        target_root,
        f.get("disc_label", ""),
    )
    return Path(target_file).exists()


def _emit_preview_item(f: dict, movies_map: dict, target_root: str,
                       progress_callback: Callable):
    code = f.get("code")
    # 无法识别番号的文件无法整理，直接跳过（不崩溃）
    if not code:
        progress_callback(OrganizeProgress(
            event="found",
            source_path=f.get("path", ""),
            code="???",
            action="skip",
            reason="无法识别番号",
        ))
        return
    movie_data = movies_map.get(code, {})
    target_dir, target_file = build_target_path(
        code,
        _get_primary_actor(movie_data) or "未知演员",
        f["subtitle_type"] or "none",
        target_root,
        f.get("disc_label", ""),
    )
    exists = Path(target_file).exists()
    actor = _get_primary_actor(movie_data) or "未知演员"
    progress_callback(OrganizeProgress(
        event="found",
        source_path=f["path"],
        code=code or "???",
        target_dir=target_dir,
        target_file=target_file,
        actor_name=actor,
        file_size=f.get("size", 0),
        is_existing=exists,
    ))


# ─────────────────────────────────────────────────────────────────────────────
# 异步文件操作（subprocess，非阻塞，可实时读 stdout/stderr）
# ─────────────────────────────────────────────────────────────────────────────
async def _async_move_file(src: str, dst: str, loop: asyncio.AbstractEventLoop) -> tuple:
    """
    用 robocopy（Windows）或 mv（Linux）异步移动文件。
    返回 (success: bool, message: str, bytes_copied: int)
    """
    dst_dir = str(Path(dst).parent)
    dst_file = Path(dst).name

    try:
        # Windows: robocopy 天然支持大文件 + 实时进度 + 网络路径
        proc = await loop.create_subprocess_exec(
            "robocopy",
            str(Path(src).parent),
            dst_dir,
            dst_file,
            "/MOV",           # 移动（不是复制）
            "/NP",            # 不加进程百分比前缀（方便解析）
            "/NDL",           # 不打印目录名
            "/NC",            # 不打印文件类别
            "/BYTES",         # 输出字节数
            "/V",             # 详细输出（显示跳过原因）
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        rc = proc.returncode

        out_text = stdout.decode("utf-8", errors="replace").strip()
        err_text = stderr.decode("utf-8", errors="replace").strip()

        # robocopy 返回码：0=无文件复制，1=成功复制，2=多余文件，>7=失败
        if rc <= 1:
            return True, f"移动成功 {out_text}", 0
        elif rc == 2:
            return True, f"移动成功（部分跳过）{out_text}", 0
        else:
            return False, f"robocopy 失败 (rc={rc}) {err_text}", 0

    except FileNotFoundError:
        # robocopy 不可用，降级为同步 shutil
        return await loop.run_in_executor(None, lambda: _sync_move(src, dst))


async def _async_copy_file(src: str, dst: str, loop: asyncio.AbstractEventLoop) -> tuple:
    """用 robocopy 异步复制文件。"""
    dst_dir = str(Path(dst).parent)

    try:
        proc = await loop.create_subprocess_exec(
            "robocopy",
            str(Path(src).parent),
            dst_dir,
            Path(src).name,
            "/COPYALL",       # 复制所有属性
            "/NP",
            "/NDL",
            "/NC",
            "/BYTES",
            "/V",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        rc = proc.returncode

        out_text = stdout.decode("utf-8", errors="replace").strip()
        err_text = stderr.decode("utf-8", errors="replace").strip()

        if rc <= 1:
            return True, f"复制成功 {out_text}", 0
        elif rc == 2:
            return True, f"复制成功（部分跳过）{out_text}", 0
        else:
            return False, f"robocopy 失败 (rc={rc}) {err_text}", 0

    except FileNotFoundError:
        return await loop.run_in_executor(None, lambda: _sync_copy(src, dst))


def _sync_move(src: str, dst: str) -> tuple:
    """同步 shutil.move 降级"""
    try:
        Path(dst).parent.mkdir(parents=True, exist_ok=True)
        shutil.move(src, dst)
        return True, "移动成功", 0
    except Exception as e:
        return False, f"移动失败: {e}", 0


def _sync_copy(src: str, dst: str) -> tuple:
    """同步 shutil.copy2 降级"""
    try:
        Path(dst).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return True, "复制成功", 0
    except Exception as e:
        return False, f"复制失败: {e}", 0


# ─────────────────────────────────────────────────────────────────────────────
# 核心整理逻辑（Generator，流式产出每个文件的处理结果）
# ─────────────────────────────────────────────────────────────────────────────
def organize_files_gen(
    source_paths: List[str],
    target_root: str,
    mode: OrganizeMode,
    auto_scrape: bool = False,
    progress_callback: Optional[Callable] = None,
):
    """
    Generator 版本的整理逻辑。
    yield OrganizeProgress 事件，调用方负责消费并推送给 SSE。
    不再攒所有结果，而是逐文件流式处理。
    """
    global _abort_organize
    reset_abort()

    if progress_callback is None:
        def noop(p): pass
        progress_callback = noop

    # ── 扫描阶段：流式产出每个文件（不再等全部扫完）────────────────────────
    files = []
    for item in scan_video_files_gen(source_paths, progress_callback):
        files.append(item)
        # 立即 yield 扫描到的文件（让前端立即看到）
        code = item.get("code")
        movie_data = {}  # 扫描阶段还没查库，先用空数据
        _emit_preview_item(item, {}, target_root, progress_callback)

    if _abort_organize:
        progress_callback(OrganizeProgress(event="done", message="用户中止", success_count=0, fail_count=0))
        return

    if not files:
        progress_callback(OrganizeProgress(event="done", message="未找到视频文件", success_count=0, fail_count=0))
        return

    # 批量查库（一次查完，后续不再查）
    codes = [f["code"] for f in files if f["code"]]
    movies_map = db.get_movies_by_codes(codes) if codes else {}

    # 补全文件 size（异步获取，避免在扫描时阻塞）
    for f in files:
        try:
            f["size"] = Path(f["path"]).stat().st_size
        except Exception:
            f["size"] = 0

    # 预览模式：直接发 summary，然后结束
    if mode == OrganizeMode.PREVIEW:
        progress_callback(OrganizeProgress(
            event="summary",
            total=len(files),
            new_count=sum(1 for f in files if not _target_exists(f, movies_map, target_root)),
            exists_count=sum(1 for f in files if _target_exists(f, movies_map, target_root)),
            error_count=sum(1 for f in files if not f["code"]),
            estimated_size=_human_size(sum(f["size"] for f in files)),
        ))
        return

    # ── 执行阶段（复制/移动）：逐文件处理，流式 yield ───────────────────
    success_count = 0
    fail_count = 0

    for f in files:
        if _abort_organize:
            progress_callback(OrganizeProgress(
                event="done",
                success_count=success_count,
                fail_count=fail_count,
                message="用户中止"
            ))
            return

        if not f["code"]:
            progress_callback(OrganizeProgress(
                event="error",
                source_path=f["path"],
                reason="无法识别番号",
            ))
            fail_count += 1
            continue

        # 跳过 FC2 视频（不属于正版电影）
        if f["code"].upper().startswith("FC2"):
            progress_callback(OrganizeProgress(
                event="skipped",
                source_path=f["path"],
                code=f["code"],
                reason="FC2视频不属于正版电影",
                file_size=f["size"],
            ))
            continue

        # 检查是否有刮削信息（只在 MOVE 模式下检查）
        if mode == OrganizeMode.MOVE and f["code"]:
            movie_data_check = movies_map.get(f["code"], {})
            has_scrape_info = bool(
                movie_data_check.get("title") or 
                movie_data_check.get("title_jp") or
                (movie_data_check.get("actors") and len(movie_data_check.get("actors", [])) > 0)
            )
            if not has_scrape_info:
                progress_callback(OrganizeProgress(
                    event="skipped",
                    source_path=f["path"],
                    code=f["code"],
                    reason="未刮削（无影片信息），不迁移",
                    file_size=f["size"],
                ))
                continue

        movie_data = movies_map.get(f["code"], {})
        target_dir, target_file = build_target_path(
            f["code"],
            _get_primary_actor(movie_data) or "未知演员",
            f["subtitle_type"] or "none",
            target_root,
            f.get("disc_label", ""),
        )

        # 检查目标是否已存在
        if Path(target_file).exists():
            try:
                src_size = f["size"]
                dst_size = Path(target_file).stat().st_size
                if src_size <= dst_size:
                    progress_callback(OrganizeProgress(
                        event="skipped",
                        source_path=f["path"],
                        target_dir=target_dir,
                        reason=f"目标文件已存在（{_human_size(dst_size)}）",
                        file_size=src_size,
                    ))
                    continue
            except Exception:
                pass

        # 创建目标目录
        try:
            Path(target_dir).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            progress_callback(OrganizeProgress(
                event="error",
                source_path=f["path"],
                reason=f"无法创建目标目录: {e}",
            ))
            fail_count += 1
            continue

        # 复制/移动文件（返回 (success, message) — subprocess 调用由 main.py 执行）
        # 这里只负责 emit 事件，实际 I/O 由 main.py 的 asyncio loop 执行
        progress_callback(OrganizeProgress(
            event="file_ready",
            source_path=f["path"],
            target_file=target_file,
            file_size=f["size"],
            action=mode.value,
        ))
        success_count += 1

    progress_callback(OrganizeProgress(
        event="done",
        success_count=success_count,
        fail_count=fail_count,
        message="整理完成" if fail_count == 0 else f"完成（{fail_count} 个失败）",
    ))


# ─────────────────────────────────────────────────────────────────────────────
# 同步执行（直接复制/移动，由 main.py 调用）
# 注意：organize_files_gen 已改为流式，文件实际 I/O 放在这里单独处理
# ─────────────────────────────────────────────────────────────────────────────
def organize_files_sync(
    source_paths: List[str],
    target_root: str,
    mode: OrganizeMode,
    auto_scrape: bool = False,
    progress_callback: Optional[Callable] = None,
) -> dict:
    """
    整理主逻辑，使用流式扫描：
    - scan_video_files_gen：每找到一个视频文件立即通过 callback 通知（不等待全部扫描完）
    - db.get_movies_by_codes：在独立线程中执行（不阻塞扫描线程）
    由 main.py 的 asyncio loop 在 executor 中调用。
    """
    global _abort_organize
    reset_abort()

    if progress_callback is None:
        def noop(p): pass
        progress_callback = noop

    # ── 流式扫描：每个文件立即 emit found 事件 ──────────────────────────────
    files: List[dict] = []
    for item in scan_video_files_gen(source_paths):
        if _abort_organize:
            progress_callback(OrganizeProgress(event="done", message="用户中止", success_count=0, fail_count=0))
            return {"status": "aborted"}
        # stat 取大小（网络路径可能有延迟，但这是必要的）
        try:
            item["size"] = Path(item["path"]).stat().st_size
        except Exception:
            item["size"] = 0
        files.append(item)
        # 每个文件立即通知前端（不等到全部扫描完）
        # movies_map 在 streaming 阶段尚为空，actor_name 等详情在 PREVIEW/EXECUTE 循环中补全
        progress_callback(OrganizeProgress(
            event="found",
            source_path=item["path"],
            code=item["code"],
            display_name=item["display_name"],
            file_size=item["size"],
        ))

    if _abort_organize:
        progress_callback(OrganizeProgress(event="done", message="用户中止", success_count=0, fail_count=0))
        return {"status": "aborted"}

    if not files:
        progress_callback(OrganizeProgress(event="done", message="未找到视频文件", success_count=0, fail_count=0))
        return {"status": "done", "total": 0}

    # ── 批量查询影片数据库（在 executor 线程中执行，不阻塞扫描）──────────────
    codes = [f["code"] for f in files if f["code"]]
    movies_map: dict = {}
    if codes:
        movies_map = db.get_movies_by_codes(codes)

    # ── PREVIEW 模式 ─────────────────────────────────────────────────────────
    if mode == OrganizeMode.PREVIEW:
        for f in files:
            _emit_preview_item(f, movies_map, target_root, progress_callback)
        progress_callback(OrganizeProgress(
            event="summary",
            total=len(files),
            new_count=sum(1 for f in files if not _target_exists(f, movies_map, target_root)),
            exists_count=sum(1 for f in files if _target_exists(f, movies_map, target_root)),
            error_count=sum(1 for f in files if not f["code"]),
            estimated_size=_human_size(sum(f["size"] for f in files)),
        ))
        return {"status": "preview_done", "total": len(files)}

    # ── COPY / MOVE 模式 ────────────────────────────────────────────────────
    success_count = 0
    fail_count = 0
    skip_no_info = 0  # 跳过未刮削的文件数

    for f in files:
        if _abort_organize:
            progress_callback(OrganizeProgress(event="done", success_count=success_count, fail_count=fail_count, message="用户中止"))
            return {"status": "aborted"}

        if not f["code"]:
            progress_callback(OrganizeProgress(event="error", source_path=f["path"], reason="无法识别番号"))
            fail_count += 1
            continue

        # 跳过 FC2 视频（不属于正版电影）
        if f["code"].upper().startswith("FC2"):
            progress_callback(OrganizeProgress(
                event="skipped",
                source_path=f["path"],
                code=f["code"],
                reason="FC2视频不属于正版电影",
                file_size=f["size"],
            ))
            continue

        # 检查是否有刮削信息（只在 MOVE 模式下检查，COPY 模式可以保留）
        # 迁移（move）时只迁移已有刮削信息的电影
        if mode == OrganizeMode.MOVE and f["code"]:
            movie_data = movies_map.get(f["code"], {})
            # 判断是否有有效刮削信息：至少有标题或演员
            has_scrape_info = bool(
                movie_data.get("title") or 
                movie_data.get("title_jp") or
                (movie_data.get("actors") and len(movie_data.get("actors", [])) > 0)
            )
            if not has_scrape_info:
                progress_callback(OrganizeProgress(
                    event="skipped",
                    source_path=f["path"],
                    code=f["code"],
                    reason="未刮削（无影片信息），不迁移",
                    file_size=f["size"],
                ))
                skip_no_info += 1
                continue

        movie_data = movies_map.get(f["code"], {})
        target_dir, target_file = build_target_path(
            f["code"],
            _get_primary_actor(movie_data) or "未知演员",
            f["subtitle_type"] or "none",
            target_root,
            f.get("disc_label", ""),
        )

        if Path(target_file).exists():
            try:
                src_size = f["size"]
                dst_size = Path(target_file).stat().st_size
                if src_size <= dst_size:
                    progress_callback(OrganizeProgress(
                        event="skipped",
                        source_path=f["path"],
                        target_dir=target_dir,
                        reason=f"目标文件已存在（{_human_size(dst_size)}）",
                        file_size=src_size,
                    ))
                    continue
            except Exception:
                pass

        try:
            Path(target_dir).mkdir(parents=True, exist_ok=True)

            if mode == OrganizeMode.COPY:
                shutil.copy2(f["path"], target_file)
                action = "copied"
            else:
                shutil.move(f["path"], target_file)
                action = "moved"

            movie_id = movie_data.get("id") if movie_data else None
            if movie_data:
                _copy_asset_files(movie_data, target_dir, f["code"])
                generate_organize_nfo(movie_data, target_dir, f["subtitle_type"] or "none")
                if movie_id:
                    db.update_movie_organize_info(movie_id, f["subtitle_type"] or "none", target_dir)

            progress_callback(OrganizeProgress(
                event=action,
                source_path=f["path"],
                target_dir=target_dir,
                file_size=f["size"],
            ))
            success_count += 1

            # ── 移动/复制后的额外处理 ──
            # 1. 清理源文件夹
            _cleanup_source_folder(f["path"], progress_callback)

            # 2. 更新 Jellyfin 扫描记录 + 同步 local_videos 路径
            #    target_file 是整理后的视频完整路径，如 E:/jellyfin/演员/番号/番号-C.mp4
            _update_jellyfin_scan_record(
                target_dir=target_dir,
                code=f["code"],
                movie_id=movie_id,
                new_video_path=target_file,
                new_name=Path(target_file).stem,
                new_extension=Path(target_file).suffix.lstrip("."),
                progress_callback=progress_callback,
            )

            # 3. 从刮削列表中移除原路径记录
            _remove_from_scrape_list(f["path"], f["code"], progress_callback)

        except Exception as e:
            logger.error(f"[Organize] 文件操作失败 {f['path']}: {e}")
            progress_callback(OrganizeProgress(
                event="error",
                source_path=f["path"],
                reason=str(e),
            ))
            fail_count += 1

    progress_callback(OrganizeProgress(
        event="done",
        success_count=success_count,
        fail_count=fail_count,
        message="整理完成" if fail_count == 0 else f"完成（{fail_count} 个失败），{skip_no_info} 个未刮削跳过",
    ))
    return {"status": "done", "total": len(files), "success": success_count, "fail": fail_count}


# ─────────────────────────────────────────────────────────────────────────────
# 源文件夹清理 + Jellyfin 扫描记录更新 + 刮削列表清理
# ─────────────────────────────────────────────────────────────────────────────

# 垃圾文件扩展名（广告/种子/说明文件，可以安全删除）
_JUNK_EXTENSIONS = {
    ".torrent", ".url", ".lnk", ".htm", ".html",
    ".ini", ".db", ".txt",
}

# 垃圾文件名关键词（匹配文件名前缀/关键词）
_JUNK_NAME_PATTERNS = [
    re.compile(r'^(readme|说明|使用说明|免责声明|招募|加入|公告)', re.IGNORECASE),
    re.compile(r'\.(torrent|url|lnk)$', re.IGNORECASE),
]

# 目录本身就是整理目标的根路径标识（不删除这些目录）
_PROTECTED_ROOT_KEYWORDS = ["jellyfin", "downloads", "download"]


def _is_junk_file(file_path: str) -> bool:
    """
    判断是否为垃圾/广告文件（可安全删除的辅助文件）。
    判断依据：扩展名 + 文件名关键词。
    注意：不以文件大小作为判据（小视频片段可能是正常内容）。
    """
    p = Path(file_path)
    ext = p.suffix.lower()
    name = p.name

    if ext in _JUNK_EXTENSIONS:
        return True
    for pat in _JUNK_NAME_PATTERNS:
        if pat.search(name):
            return True
    return False


def _is_residual_only_folder(folder: Path) -> tuple:
    """
    检查文件夹是否只剩下垃圾/辅助文件（没有有价值的内容）。
    返回: (can_delete: bool, reason: str)

    判断逻辑：
    - 空文件夹：可删除
    - 只有垃圾文件（.torrent/.url/.txt 等）：可删除
    - 只有图片文件（jpg/png/jpeg/gif/webp）且无视频文件：
      这些通常是封面图/广告图，整理完视频后可删除
    - 有 .nfo 文件但无视频：可删除（整理后已无视频，nfo 孤立）
    - 有任何视频文件：不可删除
    """
    try:
        entries = list(folder.iterdir())
    except PermissionError:
        return False, "无权限读取"
    except Exception as e:
        return False, str(e)

    if not entries:
        return True, "空文件夹"

    image_exts = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
    nfo_ext = ".nfo"

    has_video = False
    has_subdir = False
    junk_files = []
    image_files = []
    nfo_files = []
    other_files = []

    for entry in entries:
        if entry.is_dir():
            has_subdir = True
            continue
        ext = entry.suffix.lower()
        if ext in VIDEO_EXTENSIONS:
            has_video = True
            break
        elif _is_junk_file(str(entry)):
            junk_files.append(entry)
        elif ext in image_exts:
            image_files.append(entry)
        elif ext == nfo_ext:
            nfo_files.append(entry)
        else:
            other_files.append(entry)

    if has_video:
        return False, "仍有视频文件"
    if has_subdir:
        return False, "含子目录"
    if other_files:
        # 有无法识别的文件，保守不删
        return False, f"含未知文件: {other_files[0].name}"
    if not (junk_files or image_files or nfo_files):
        return True, "空文件夹"

    # 只剩垃圾/图片/nfo，可删除
    total_residual = len(junk_files) + len(image_files) + len(nfo_files)
    return True, f"只剩 {total_residual} 个辅助文件（种子/封面/nfo）"


def _cleanup_source_folder(source_path: str, progress_callback: Callable) -> bool:
    """
    整理完成后清理源文件夹：
    - 如果为空，直接删除
    - 如果只剩垃圾/辅助文件（.torrent/.jpg/.nfo 等），删除整个文件夹
    - 如果还有其他视频或未知文件，不删除

    同时处理父目录递归清理（如 /下载/CAWD-285/ 整理完后，
    如果 /下载/ 也空了，也一并清理）。

    返回: 是否删除了文件夹
    """
    source_dir = Path(source_path).parent
    if not source_dir.exists() or not source_dir.is_dir():
        return False

    # 保护根路径（不删除用户配置的视频源根目录本身）
    source_dir_lower = str(source_dir).lower()
    for kw in _PROTECTED_ROOT_KEYWORDS:
        if source_dir_lower.endswith(kw.lower()):
            return False

    can_delete, reason = _is_residual_only_folder(source_dir)
    if not can_delete:
        return False

    try:
        import time
        time.sleep(0.05)  # 短暂等待，确保文件句柄已释放
        shutil.rmtree(str(source_dir), ignore_errors=True)

        if not source_dir.exists():
            logger.info(f"[Organize] 已删除源文件夹: {source_dir} ({reason})")
            progress_callback(OrganizeProgress(
                event="cleaned",
                folder_path=str(source_dir),
                message=f"已清理源文件夹（{reason}）",
            ))
            # 尝试递归清理父目录
            _cleanup_source_folder(str(source_dir), progress_callback)
            return True
        else:
            logger.warning(f"[Organize] 源文件夹删除失败（可能被占用）: {source_dir}")
    except Exception as e:
        logger.warning(f"[Organize] 清理源文件夹失败 {source_dir}: {e}")

    return False


def _update_jellyfin_scan_record(
    target_dir: str,
    code: str,
    movie_id: Optional[int],
    new_video_path: str,
    new_name: str,
    new_extension: str,
    progress_callback: Callable,
):
    """
    整理完成后更新 Jellyfin 扫描记录：
    1. 检查目标父目录是否已在 local_sources 中（is_jellyfin=1）
    2. 若在 Jellyfin 目录中，调用 db.sync_local_video_after_organize 同步 local_videos 记录
    3. 发送 jellyfin_updated 事件

    target_dir: 整理后的电影文件夹路径（如 E:/jellyfin/女演员名/番号/）
    """
    if not movie_id:
        return

    try:
        jellyfin_parent = str(Path(target_dir).parent)  # E:/jellyfin/女演员名/ 或 E:/jellyfin/
        root_parent = str(Path(target_dir).parent.parent)  # E:/jellyfin/

        # 查找 local_sources 中是否有包含目标目录的 Jellyfin 源
        conn = db.get_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, path, is_jellyfin FROM local_sources WHERE is_jellyfin = 1"
        )
        jf_sources = cursor.fetchall()
        conn.close()

        is_in_jellyfin = False
        for src in jf_sources:
            src_path = str(src[1]).rstrip("/\\")
            tgt_str = str(target_dir).replace("\\", "/")
            src_str = src_path.replace("\\", "/")
            if tgt_str.startswith(src_str):
                is_in_jellyfin = True
                break

        # 同步 local_videos 记录（无论是否 Jellyfin 目录都需要更新路径）
        db.sync_local_video_after_organize(
            movie_id=movie_id,
            new_video_path=new_video_path,
            new_code=code,
            new_name=new_name,
            new_extension=new_extension,
        )

        logger.info(
            f"[Organize] local_videos 已同步: movie_id={movie_id} → {new_video_path}"
            f"{'（Jellyfin 目录）' if is_in_jellyfin else ''}"
        )
        progress_callback(OrganizeProgress(
            event="jellyfin_updated",
            target_dir=target_dir,
            code=code,
            jellyfin_updated=is_in_jellyfin,
        ))

    except Exception as e:
        logger.warning(f"[Organize] 更新 Jellyfin 扫描记录失败: {e}")


def _remove_from_scrape_list(source_path: str, code: str, progress_callback: Callable):
    """
    整理完成后，从刮削列表中清理原路径的 local_videos 记录：
    1. 精确匹配原视频文件路径
    2. 删除（或标记）该 local_videos 记录（原路径文件已不存在，记录无效）
    3. 同时检查对应的 movies 记录，确保 organized_path 已填写

    注意：不删除 movies 记录，只删除对应的 local_videos 原路径条目。
    整理后会创建新的 local_videos 条目（在 _update_jellyfin_scan_record 中通过
    sync_local_video_after_organize 完成）。
    """
    try:
        conn = db.get_db()
        cursor = conn.cursor()

        # 精确匹配原始路径
        cursor.execute(
            "SELECT id, movie_id, scraped FROM local_videos WHERE path = ?",
            (source_path,)
        )
        rows = cursor.fetchall()

        if not rows:
            # 再尝试规范化路径后匹配（处理 \\ 和 / 混用）
            norm_path = str(Path(source_path))
            cursor.execute(
                "SELECT id, movie_id, scraped FROM local_videos WHERE path = ?",
                (norm_path,)
            )
            rows = cursor.fetchall()

        deleted_count = 0
        for row in rows:
            video_id, movie_id, scraped = row[0], row[1], row[2]
            # 删除原路径的 local_videos 记录（文件已被移走，路径失效）
            # 注意：sync_local_video_after_organize 会在新路径创建/更新记录
            cursor.execute("DELETE FROM local_videos WHERE id = ?", (video_id,))
            deleted_count += 1
            logger.info(f"[Organize] 已删除原路径 local_videos 记录 id={video_id}: {source_path}")

        if deleted_count > 0:
            conn.commit()
            progress_callback(OrganizeProgress(
                event="scrape_list_updated",
                code=code,
                scrape_list_updated=True,
                message=f"已清理 {deleted_count} 条原路径记录",
            ))
        else:
            # 没有找到原路径记录，可能从未扫描过该路径，正常情况
            logger.debug(f"[Organize] 原路径无 local_videos 记录: {source_path}")

        conn.close()

    except Exception as e:
        logger.warning(f"[Organize] 清理刮削列表失败: {e}")
