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
from pathlib import Path
from typing import Optional, List, Callable
from datetime import datetime

import database as db
from models import SubtitleType, OrganizeMode, OrganizePreviewItem, OrganizeProgress, SUBTITLE_LABELS

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# 全局中断控制
# ─────────────────────────────────────────────────────────────────────────────
_abort_organize = False


def abort_organize():
    """请求中止整理操作"""
    global _abort_organize
    _abort_organize = True


def reset_abort():
    """重置中止标志（新任务开始前调用）"""
    global _abort_organize
    _abort_organize = False


# ─────────────────────────────────────────────────────────────────────────────
# 正则：番号 + 字幕后缀 提取
# ─────────────────────────────────────────────────────────────────────────────

# 字幕后缀模式（加在番号识别之后）
# 例: IPZZ-792-C → code=IPZZ-792, suffix=C
#     FC2-PPV-123456 → code=FC2-PPV-123456, suffix=None
#     FC2-PPV-123456-C → code=FC2-PPV-123456, suffix=C
_SUBTITLE_SUFFIX_RE = re.compile(
    r'^(?P<code>(?:FC2-PPV-\d{5,7}|HEYDOUGA-\d{4}-\d{3,5}|[A-Z]{2,6}-\d{2,5}))'
    r'(?:-(?P<suffix>C|U|UC))?'                   # 可选字幕后缀
    r'(?P<ext>\.[^.]+)?$',                        # 可选扩展名
    re.IGNORECASE
)

# 视频扩展名白名单
VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.wmv', '.mov', '.webm', '.m4v', '.ts'}


# ─────────────────────────────────────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────────────────────────────────────

def _safe_dir_name(name: str) -> str:
    """
    去除目录名中的非法字符（Windows 文件系统限制）
    参考: gfriends.py 的 _safe_filename 逻辑
    """
    if not name:
        return "未知演员"
    # Windows 非法字符: < > : " / \\ | ? * 以及控制字符
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name)
    # 去除前后空格和点
    name = name.strip().strip('.')
    # 限制最大长度（Windows MAX_PATH 预防）
    if len(name) > 200:
        name = name[:200]
    return name or "未知演员"


def _safe_file_name(name: str) -> str:
    """去除文件名中的非法字符"""
    if not name:
        return name
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name)
    return name.strip()


def _extract_code_with_suffix(filename: str) -> tuple:
    """
    从文件名中提取番号和字幕后缀

    参数:
        filename: 文件名（不含路径），如 "IPZZ-792-C.mp4"

    返回:
        (code, subtitle_type, display_name)
        - code: 番号（不含后缀），如 "IPZZ-792"
        - subtitle_type: none/chinese/english/bilingual
        - display_name: 带后缀的显示名，如 "IPZZ-792-C"
        返回 (None, None, None) 如果无法识别番号
    """
    name = Path(filename).stem  # 去扩展名
    match = _SUBTITLE_SUFFIX_RE.match(name)

    if not match:
        return None, None, None

    code = match.group("code").upper()
    suffix_raw = (match.group("suffix") or "").upper()

    # 字幕后缀映射
    suffix_map = {
        "C": SubtitleType.CHINESE.value,
        "U": SubtitleType.ENGLISH.value,
        "UC": SubtitleType.BILINGUAL.value,
    }
    subtitle_type = suffix_map.get(suffix_raw, SubtitleType.NONE.value)

    display_name = name  # 带字幕后缀的原始显示名

    return code, subtitle_type, display_name


def _human_size(size_bytes: int) -> str:
    """将字节数转换为可读大小字符串"""
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / 1024 / 1024:.1f}MB"
    else:
        return f"{size_bytes / 1024 / 1024 / 1024:.2f}GB"


# ─────────────────────────────────────────────────────────────────────────────
# 扫描
# ─────────────────────────────────────────────────────────────────────────────

def scan_video_files(source_paths: List[str]) -> List[dict]:
    """
    扫描多个源目录，返回所有视频文件列表

    返回: [{path, name, size, code, subtitle_type, display_name}, ...]
    """
    results = []

    for source_path in source_paths:
        p = Path(source_path)
        if not p.exists():
            logger.warning(f"[Organizer] 路径不存在: {source_path}")
            continue

        try:
            for file_path in p.rglob("*"):
                if _abort_organize:
                    break
                if not file_path.is_file():
                    continue
                ext = file_path.suffix.lower()
                if ext not in VIDEO_EXTENSIONS:
                    continue

                code, subtitle_type, display_name = _extract_code_with_suffix(file_path.name)

                results.append({
                    "path": str(file_path),
                    "name": file_path.name,
                    "display_name": display_name,
                    "code": code,
                    "subtitle_type": subtitle_type,
                    "size": file_path.stat().st_size if file_path.exists() else 0,
                })
        except PermissionError:
            logger.warning(f"[Organizer] 权限不足，跳过: {source_path}")
        except Exception as e:
            logger.error(f"[Organizer] 扫描出错 {source_path}: {e}")

    return results


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

    参数:
        code: 番号，如 "IPZZ-792"
        actor_name: 女演员名，如 "三上悠亜"
        subtitle_type: none/chinese/english/bilingual
        target_root: 目标根目录，如 "E:/jellyfin"

    返回:
        (target_dir, target_file)
        - target_dir: 目标文件夹，如 "E:/jellyfin/三上悠亜/IPZZ-792/"
        - target_file: 目标文件（含字幕后缀），如 "IPZZ-792-C.mp4"
    """
    target_root = Path(target_root)
    actor_safe = _safe_dir_name(actor_name)
    code_safe = _safe_file_name(code)

    # 构建文件夹路径
    target_dir = target_root / "jellyfin" / actor_safe / code_safe

    # 构建目标文件名（带字幕后缀）
    video_ext = ".mp4"  # 默认扩展名，整理时保持原扩展名
    # 注意：target_file 的番号不带字幕后缀，因为字幕信息存在 NFO 里
    # 但用户希望文件名保留字幕后缀方便识别，这里构建完整文件名
    suffix_map = {
        SubtitleType.CHINESE.value: "-C",
        SubtitleType.ENGLISH.value: "-U",
        SubtitleType.BILINGUAL.value: "-UC",
    }
    suffix_str = suffix_map.get(subtitle_type, "")
    target_file = target_dir / f"{code_safe}{suffix_str}{video_ext}"

    return str(target_dir), str(target_file)


# ─────────────────────────────────────────────────────────────────────────────
# NFO 生成（含字幕信息）
# ─────────────────────────────────────────────────────────────────────────────

def _escape_xml(text: str) -> str:
    """XML 特殊字符转义"""
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
    """
    为整理后的影片生成 NFO 文件（含字幕标签）

    参数:
        movie_data: 影片数据字典
        target_dir: 目标文件夹
        subtitle_type: 字幕类型

    返回: NFO 文件路径，失败返回 None
    """
    code = movie_data.get("code", "")
    if not code:
        return None

    safe_code = _safe_file_name(code)
    nfo_path = Path(target_dir) / f"{safe_code}.nfo"
    nfo_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        lines = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>']
        lines.append("<movie>")

        # 基本信息
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

        # 剧情
        if movie_data.get("plot"):
            lines.append(f"  <plot>{_escape_xml(movie_data['plot'])}</plot>")

        # 演员
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

        # 类别
        genres = movie_data.get("genres", [])
        if isinstance(genres, str):
            genres = [g.strip() for g in genres.split(",") if g.strip()]
        for genre in (genres or []):
            lines.append(f"  <genre>{_escape_xml(genre)}</genre>")

        # ── 字幕信息（Jellyfin 自定义字段）─────────────────────────
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
# 核心整理逻辑
# ─────────────────────────────────────────────────────────────────────────────

def _copy_asset_files(movie_data: dict, target_dir: str, code: str):
    """
    复制封面文件到目标目录
    - poster.jpg: 从 movie_data.poster_path 复制
    - fanart.jpg: 从 movie_data.fanart_path 复制
    - thumb.jpg: 从 movie_data.thumb_path 复制
    """
    safe_code = _safe_file_name(code)
    target_dir_path = Path(target_dir)

    paths_to_copy = [
        (movie_data.get("poster_path"), f"{safe_code}-poster.jpg"),
        (movie_data.get("fanart_path"), f"{safe_code}-fanart.jpg"),
        (movie_data.get("thumb_path"), f"{safe_code}-thumb.jpg"),
    ]

    for src_path, dst_name in paths_to_copy:
        if not src_path:
            continue
        src = Path(src_path)
        if not src.exists():
            continue
        try:
            shutil.copy2(src, target_dir_path / dst_name)
        except Exception as e:
            logger.warning(f"[Organize] 封面复制失败 {src} → {dst_name}: {e}")


def organize_files(
    source_paths: List[str],
    target_root: str,
    mode: OrganizeMode,
    progress_callback: Callable[[OrganizeProgress], None]
) -> dict:
    """
    执行整理（预览/复制/移动），使用 generator 模式。
    每次 yield 推送一个 OrganizeProgress，可被 asyncio.to_thread 非阻塞驱动。

    参数:
        source_paths: 源目录列表
        target_root: 目标根目录
        mode: 预览/复制/移动
        progress_callback: SSE 推送回调（兼容旧接口）

    返回: 汇总结果
    """
    global _abort_organize
    reset_abort()

    # 1. 扫描文件
    files = scan_video_files(source_paths)

    # 2. 批量查询数据库（减少 DB 查询次数）
    codes = [f["code"] for f in files if f["code"]]
    movies_map = db.get_movies_by_codes(codes) if codes else {}

    # 3. 预览阶段：收集所有文件信息
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
        return {"total": len(files), "status": "preview_done"}

    # 4. 执行阶段（复制/移动）
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
            return {"total": len(files), "success": success_count, "fail": fail_count, "status": "aborted"}

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
            src_size = f["size"]
            dst_size = Path(target_file).stat().st_size
            if src_size <= dst_size:
                progress_callback(OrganizeProgress(
                    event="skipped",
                    source_path=f["path"],
                    target_dir=target_dir,
                    reason=f"目标文件已存在（大小: {_human_size(dst_size)}）",
                    file_size=src_size,
                ))
                continue

        # 复制/移动
        try:
            Path(target_dir).mkdir(parents=True, exist_ok=True)

            if mode == OrganizeMode.COPY:
                shutil.copy2(f["path"], target_file)
                action = "copied"
            else:  # MOVE
                shutil.move(f["path"], target_file)
                action = "moved"

            # 复制封面
            if movie_data:
                _copy_asset_files(movie_data, target_dir, f["code"])

            # 生成 NFO（含字幕信息）
            if movie_data:
                generate_organize_nfo(movie_data, target_dir, f["subtitle_type"] or "none")

                # 更新数据库的整理信息
                movie_id = movie_data.get("id")
                if movie_id:
                    db.update_movie_organize_info(movie_id, f["subtitle_type"] or "none", target_dir)

            progress_callback(OrganizeProgress(
                event=action,
                source_path=f["path"],
                target_dir=target_dir,
                target_file=target_file,
                file_size=f["size"],
                code=f["code"],
                subtitle_type=f["subtitle_type"],
                actor_name=_get_primary_actor(movie_data) or "未知演员",
            ))
            success_count += 1

        except Exception as e:
            logger.error(f"[Organize] 整理失败 {f['path']}: {e}")
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
        message=f"完成：成功 {success_count}，失败 {fail_count}",
    ))

    return {"total": len(files), "success": success_count, "fail": fail_count, "status": "done"}


def organize_files_gen(
    source_paths: List[str],
    target_root: str,
    mode: OrganizeMode,
) -> Iterator[OrganizeProgress]:
    """
    Generator 版本的 organize_files，每次 yield 一个 OrganizeProgress。
    专为 asyncio.to_thread 设计，可在不阻塞事件循环的情况下逐个推送进度。
    """
    global _abort_organize
    reset_abort()

    # 1. 扫描文件（同步 I/O，在线程中执行，不阻塞事件循环）
    files = scan_video_files(source_paths)

    # 2. 批量查询数据库
    codes = [f["code"] for f in files if f["code"]]
    movies_map = db.get_movies_by_codes(codes) if codes else {}

    # 3. 预览阶段
    if mode == OrganizeMode.PREVIEW:
        for f in files:
            if _abort_organize:
                return
            yield from _gen_preview_items(f, movies_map, target_root)

        yield OrganizeProgress(
            event="summary",
            total=len(files),
            new_count=sum(1 for f in files if not _target_exists(f, movies_map, target_root)),
            exists_count=sum(1 for f in files if _target_exists(f, movies_map, target_root)),
            error_count=sum(1 for f in files if not f["code"]),
            estimated_size=_human_size(sum(f["size"] for f in files)),
        )
        return

    # 4. 执行阶段（复制/移动）
    success_count = 0
    fail_count = 0

    for f in files:
        if _abort_organize:
            yield OrganizeProgress(
                event="done",
                success_count=success_count,
                fail_count=fail_count,
                message="用户中止"
            )
            return

        if not f["code"]:
            yield OrganizeProgress(
                event="error",
                source_path=f["path"],
                reason="无法识别番号",
            )
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
            src_size = f["size"]
            dst_size = Path(target_file).stat().st_size
            if src_size <= dst_size:
                yield OrganizeProgress(
                    event="skipped",
                    source_path=f["path"],
                    target_dir=target_dir,
                    reason=f"目标文件已存在（大小: {_human_size(dst_size)}）",
                    file_size=src_size,
                )
                continue

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

            if movie_data:
                generate_organize_nfo(movie_data, target_dir, f["subtitle_type"] or "none")
                movie_id = movie_data.get("id")
                if movie_id:
                    db.update_movie_organize_info(movie_id, f["subtitle_type"] or "none", target_dir)

            yield OrganizeProgress(
                event=action,
                source_path=f["path"],
                target_dir=target_dir,
                target_file=target_file,
                file_size=f["size"],
                code=f["code"],
                subtitle_type=f["subtitle_type"],
                actor_name=_get_primary_actor(movie_data) or "未知演员",
            )
            success_count += 1

        except Exception as e:
            logger.error(f"[Organize] 整理失败 {f['path']}: {e}")
            yield OrganizeProgress(
                event="error",
                source_path=f["path"],
                reason=str(e),
            )
            fail_count += 1

    yield OrganizeProgress(
        event="done",
        success_count=success_count,
        fail_count=fail_count,
        message=f"完成：成功 {success_count}，失败 {fail_count}",
    )


def _gen_preview_items(f, movies_map, target_root) -> Iterator[OrganizeProgress]:
    """预览项 generator helper"""
    if not f["code"]:
        yield OrganizeProgress(
            event="found",
            source_path=f["path"],
            code=f["display_name"] or f["name"],
            subtitle_type="none",
            subtitle_label="无法识别番号",
            target_dir="",
            target_file="",
            actor_name="",
            status="error",
            reason="无法从文件名识别番号",
            file_size=f["size"],
        )
        return

    movie_data = movies_map.get(f["code"], {})
    actor_name = _get_primary_actor(movie_data) or "未知演员"
    target_dir, target_file = build_target_path(
        f["code"], actor_name,
        f["subtitle_type"] or "none",
        target_root
    )

    is_new = not _target_exists(f, movies_map, target_root)
    yield OrganizeProgress(
        event="found",
        source_path=f["path"],
        code=f["display_name"],
        subtitle_type=f["subtitle_type"] or "none",
        subtitle_label=f.get("subtitle_label", ""),
        target_dir=target_dir,
        target_file=target_file,
        actor_name=actor_name,
        status="new" if is_new else "exists",
        file_size=f["size"],
    )


# ─────────────────────────────────────────────────────────────────────────────
# 辅助函数
# ─────────────────────────────────────────────────────────────────────────────

def _get_primary_actor(movie_data: dict) -> Optional[str]:
    """获取主女演员（第一个）"""
    actors = movie_data.get("actors", [])
    if isinstance(actors, str):
        actors = [a.strip() for a in actors.split(",") if a.strip()]
    if actors:
        return actors[0]
    return None


def _target_exists(f: dict, movies_map: dict, target_root: str) -> bool:
    """判断目标文件是否已存在"""
    if not f["code"]:
        return False
    movie_data = movies_map.get(f["code"], {})
    _, target_file = build_target_path(
        f["code"],
        _get_primary_actor(movie_data) or "未知演员",
        f["subtitle_type"] or "none",
        target_root
    )
    return Path(target_file).exists()


def _emit_preview_item(
    f: dict,
    movies_map: dict,
    target_root: str,
    progress_callback: Callable[[OrganizeProgress], None]
):
    """发送单个预览项"""
    if not f["code"]:
        progress_callback(OrganizeProgress(
            event="found",
            source_path=f["path"],
            code=f["display_name"] or f["name"],
            subtitle_type="none",
            subtitle_label="无法识别番号",
            target_dir="",
            target_file="",
            actor_name="",
            status="error",
            reason="无法从文件名识别番号",
            file_size=f["size"],
        ))
        return

    movie_data = movies_map.get(f["code"], {})
    actor_name = _get_primary_actor(movie_data) or "未知演员"
    target_dir, target_file = build_target_path(
        f["code"], actor_name,
        f["subtitle_type"] or "none",
        target_root
    )

    exists = Path(target_file).exists()
    progress_callback(OrganizeProgress(
        event="found",
        source_path=f["path"],
        code=f["code"],
        subtitle_type=f["subtitle_type"] or "none",
        subtitle_label=SUBTITLE_LABELS.get(f["subtitle_type"] or "none", "无字幕"),
        target_dir=target_dir,
        target_file=target_file,
        actor_name=actor_name,
        status="exists" if exists else "new",
        reason="目标文件已存在" if exists else None,
        file_size=f["size"],
    ))
