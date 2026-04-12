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
RE_CODE = re.compile(r'^([A-Z]{2,6}-\d{2,5})', re.IGNORECASE)
RE_EXCLUDE_MIXED = re.compile(r'^(WEBIPZZ|HDABC|390JNT)', re.IGNORECASE)

def _extract_code(name: str) -> Optional[str]:
    name = name.strip()
    if RE_EXCLUDE_MIXED.match(name):
        return None
    m = RE_CODE.match(name)
    if m:
        raw = m.group(1).upper()
        # 标准化末尾数字：JNT-001 → JNT-1
        return re.sub(r'-0+(\d+)$', r'-\1', raw)
    return None


def _extract_code_with_suffix(name: str) -> tuple:
    """
    从文件名提取番号 + 字幕类型 + 显示名
    返回: (code, subtitle_type, display_name)
    subtitle_type: "none" | "chinese" | "english" | "bilingual"
    display_name: 去掉番号后的原始文件名（保留其他后缀）
    """
    base = Path(name).stem

    # 字幕后缀优先级：-UC > -U > -C（不能同时有多个）
    subtitle_type = SubtitleType.NONE.value
    if base.endswith("-UC") or base.endswith("-uc"):
        subtitle_type = SubtitleType.BILINGUAL.value
        core = base[:-3]
    elif base.endswith("-U") or base.endswith("-u"):
        subtitle_type = SubtitleType.ENGLISH.value
        core = base[:-2]
    elif base.endswith("-C") or base.endswith("-c"):
        subtitle_type = SubtitleType.CHINESE.value
        core = base[:-2]
    else:
        core = base

    code = _extract_code(core)
    # display_name = 去掉番号部分的剩余部分（如 IPZZ-792-C → -C）
    if code and core[len(code):]:
        display_name = core[len(code):]  # e.g. "-C"
    else:
        display_name = ""

    return code, subtitle_type, display_name


# ─────────────────────────────────────────────────────────────────────────────
# 安全文件名 / 文件夹名
# ─────────────────────────────────────────────────────────────────────────────
def _safe_file_name(name: str) -> str:
    for ch in r'/\:*?"<>|':
        name = name.replace(ch, "_")
    return name.strip(". ")

def _safe_dir_name(name: str) -> str:
    name = _safe_file_name(name)
    for ch in '. ':
        name = name.replace(ch, "_")
    return name.strip("_")


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

                code, subtitle_type, display_name = _extract_code_with_suffix(file_path.name)
                item = {
                    "path": str(file_path),
                    "name": file_path.name,
                    "display_name": display_name,
                    "code": code,
                    "subtitle_type": subtitle_type,
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
    target_root: str
) -> tuple:
    """
    构建 Jellyfin 标准目标路径
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
    target_file = target_dir / f"{code_safe}{suffix_str}{video_ext}"

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
    code = f["code"]
    if not code:
        return False
    movie_data = movies_map.get(code, {})
    _, target_file = build_target_path(
        code,
        _get_primary_actor(movie_data) or "未知演员",
        f["subtitle_type"] or "none",
        target_root,
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

        movie_data = movies_map.get(f["code"], {})
        target_dir, target_file = build_target_path(
            f["code"],
            _get_primary_actor(movie_data) or "未知演员",
            f["subtitle_type"] or "none",
            target_root
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

    for f in files:
        if _abort_organize:
            progress_callback(OrganizeProgress(event="done", success_count=success_count, fail_count=fail_count, message="用户中止"))
            return {"status": "aborted"}

        if not f["code"]:
            progress_callback(OrganizeProgress(event="error", source_path=f["path"], reason="无法识别番号"))
            fail_count += 1
            continue

        movie_data = movies_map.get(f["code"], {})
        target_dir, target_file = build_target_path(
            f["code"],
            _get_primary_actor(movie_data) or "未知演员",
            f["subtitle_type"] or "none",
            target_root
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

            if movie_data:
                _copy_asset_files(movie_data, target_dir, f["code"])
                generate_organize_nfo(movie_data, target_dir, f["subtitle_type"] or "none")
                movie_id = movie_data.get("id")
                if movie_id:
                    db.update_movie_organize_info(movie_id, f["subtitle_type"] or "none", target_dir)

            progress_callback(OrganizeProgress(
                event=action,
                source_path=f["path"],
                target_dir=target_dir,
                file_size=f["size"],
            ))
            success_count += 1

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
        message="整理完成" if fail_count == 0 else f"完成（{fail_count} 个失败）",
    ))
    return {"status": "done", "total": len(files), "success": success_count, "fail": fail_count}
