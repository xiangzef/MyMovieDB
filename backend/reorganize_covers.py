#!/usr/bin/env python3
"""
重新整理封面文件结构并生成 NFO 文件
- 将 data/covers/{code}-{type}.jpg 移动到 data/covers/{code}/{code}-{type}.jpg
- 从数据库读取影片信息生成 NFO 文件
"""

import os
import shutil
import sqlite3
from pathlib import Path

# 配置 - 使用绝对路径
COVERS_DIR = Path(r"F:\github\MyMovieDB\data\covers")
DB_PATH = Path(r"F:\github\MyMovieDB\data\movies.db")


def escape_xml(text):
    """转义 XML 特殊字符"""
    if not text:
        return ""
    text = str(text)
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    text = text.replace('"', "&quot;")
    text = text.replace("'", "&apos;")
    return text


def generate_nfo(movie_data: dict, nfo_path: Path, local_video_path: str = None) -> bool:
    """生成 NFO 元数据文件"""
    try:
        lines = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>']
        lines.append('<movie>')

        # 基本信息
        lines.append(f'  <title>{escape_xml(movie_data.get("title", ""))}</title>')
        lines.append(f'  <code>{escape_xml(movie_data.get("code", ""))}</code>')
        if movie_data.get("release_date"):
            lines.append(f'  <releasedate>{escape_xml(movie_data.get("release_date"))}</releasedate>')
            lines.append(f'  <year>{movie_data.get("release_date", "")[:4]}</year>')
        if movie_data.get("duration"):
            lines.append(f'  <runtime>{movie_data.get("duration")}</runtime>')
        if movie_data.get("studio"):
            lines.append(f'  <studio>{escape_xml(movie_data.get("studio"))}</studio>')
        if movie_data.get("maker"):
            lines.append(f'  <maker>{escape_xml(movie_data.get("maker"))}</maker>')
        if movie_data.get("director"):
            lines.append(f'  <director>{escape_xml(movie_data.get("director"))}</director>')

        # 演员
        actors = movie_data.get("actors", [])
        if isinstance(actors, str):
            actors = [a.strip() for a in actors.split(",") if a.strip()]
        for actor in (actors or []):
            lines.append(f'  <actor>')
            lines.append(f'    <name>{escape_xml(actor)}</name>')
            lines.append(f'    <type>Actress</type>')
            lines.append(f'  </actor>')

        # 男演员
        actors_male = movie_data.get("actors_male", [])
        if isinstance(actors_male, str):
            actors_male = [a.strip() for a in actors_male.split(",") if a.strip()]
        for actor in (actors_male or []):
            lines.append(f'  <actor>')
            lines.append(f'    <name>{escape_xml(actor)}</name>')
            lines.append(f'    <type>Actor</type>')
            lines.append(f'  </actor>')

        # 标签
        genres = movie_data.get("genres", [])
        if isinstance(genres, str):
            genres = [g.strip() for g in genres.split(",") if g.strip()]
        for genre in (genres or []):
            lines.append(f'  <genre>{escape_xml(genre)}</genre>')

        # 封面图
        if movie_data.get("fanart_path"):
            lines.append(f'  <fanart>{escape_xml(movie_data.get("fanart_path"))}</fanart>')
        if movie_data.get("poster_path"):
            lines.append(f'  <thumb>{escape_xml(movie_data.get("poster_path"))}</thumb>')

        # 本地视频路径
        if local_video_path:
            lines.append(f'  <filenameandpath>{escape_xml(local_video_path)}</filenameandpath>')

        # 简介
        if movie_data.get("plot"):
            lines.append(f'  <plot>{escape_xml(movie_data.get("plot"))}</plot>')

        lines.append('</movie>')

        # 写入文件
        with open(nfo_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        print(f"✅ NFO 生成成功: {nfo_path.name}")
        return True

    except Exception as e:
        print(f"❌ NFO 生成失败: {e}")
        return False


def get_movie_from_db(code: str) -> dict:
    """从数据库获取影片信息"""
    if not DB_PATH.exists():
        return None

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM movies WHERE code = ?", (code,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return dict(row)
    return None


def get_local_video_path(movie_id: int) -> str:
    """获取关联的本地视频路径"""
    if not DB_PATH.exists():
        return None

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT path FROM local_videos WHERE movie_id = ?", (movie_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return row[0]
    return None


def reorganize_covers():
    """重新整理封面文件结构"""
    print("=" * 60)
    print("封面文件整理工具")
    print("=" * 60)

    if not COVERS_DIR.exists():
        print(f"❌ 封面目录不存在: {COVERS_DIR}")
        return

    # 扫描所有文件
    files = list(COVERS_DIR.glob("*.*"))
    print(f"\n📁 扫描到 {len(files)} 个文件")

    # 按番号分组
    codes = set()
    for f in files:
        if f.is_file():
            # 提取番号 (如 MIDA-599-poster.jpg -> MIDA-599)
            name = f.stem
            # 去掉后缀
            for suffix in ["-poster", "-fanart", "-thumb"]:
                if name.endswith(suffix):
                    name = name[:-len(suffix)]
                    break
            codes.add(name)

    print(f"📋 发现 {len(codes)} 个番号: {', '.join(sorted(codes))}")

    # 整理每个番号
    moved_count = 0
    nfo_count = 0

    for code in sorted(codes):
        print(f"\n{'='*50}")
        print(f"处理: {code}")

        # 创建番号文件夹
        code_dir = COVERS_DIR / code
        code_dir.mkdir(exist_ok=True)
        print(f"📁 创建文件夹: {code_dir}")

        # 移动文件
        patterns = [
            (f"{code}-poster.jpg", f"{code}-poster.jpg"),
            (f"{code}-fanart.jpg", f"{code}-fanart.jpg"),
            (f"{code}-thumb.jpg", f"{code}-thumb.jpg"),
            (f"{code}.jpg", f"{code}-poster.jpg"),  # 原图作为 poster
        ]

        for old_name, new_name in patterns:
            old_path = COVERS_DIR / old_name
            new_path = code_dir / new_name
            if old_path.exists() and old_path.is_file():
                shutil.move(str(old_path), str(new_path))
                print(f"  ✅ 移动: {old_name} -> {code}/{new_name}")
                moved_count += 1

        # 从数据库获取影片信息
        movie_data = get_movie_from_db(code)
        if movie_data:
            print(f"  📊 找到数据库记录: {movie_data.get('title', 'N/A')}")

            # 获取本地视频路径
            local_video_path = None
            if movie_data.get("local_video_id"):
                local_video_path = get_local_video_path(movie_data["id"])

            # 更新封面路径
            movie_data["fanart_path"] = str(code_dir / f"{code}-fanart.jpg")
            movie_data["poster_path"] = str(code_dir / f"{code}-poster.jpg")

            # 生成 NFO
            nfo_path = code_dir / f"{code}.nfo"
            if generate_nfo(movie_data, nfo_path, local_video_path):
                nfo_count += 1
        else:
            print(f"  ⚠️ 数据库中未找到该番号")

    print(f"\n{'='*60}")
    print(f"✨ 整理完成!")
    print(f"  移动文件: {moved_count} 个")
    print(f"  生成 NFO: {nfo_count} 个")
    print(f"{'='*60}")


if __name__ == "__main__":
    reorganize_covers()
