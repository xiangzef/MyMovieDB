"""
SQLite 数据库模块
"""
import sqlite3
from datetime import datetime
from typing import List, Optional
from pathlib import Path
import json

DATABASE_PATH = Path(__file__).parent.parent / "data" / "movies.db"


def get_db():
    """获取数据库连接"""
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """初始化数据库表"""
    conn = get_db()
    cursor = conn.cursor()
    
    # 创建表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS movies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            title_jp TEXT,
            release_date TEXT,
            duration INTEGER,
            studio TEXT,
            maker TEXT,
            director TEXT,
            cover_url TEXT,
            preview_url TEXT,
            detail_url TEXT,
            genres TEXT,
            actors TEXT,
            actors_male TEXT,
            local_cover_path TEXT,
            local_video_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 添加可能缺失的列（向后兼容）
    existing_columns = [col[1] for col in cursor.execute("PRAGMA table_info(movies)")]

    # 逐步添加字段（SQLite 不支持一次性 ADD TABLE IF NOT EXISTS）
    new_columns = {
        "detail_url": "ALTER TABLE movies ADD COLUMN detail_url TEXT",
        "local_cover_path": "ALTER TABLE movies ADD COLUMN local_cover_path TEXT",
        "actors_male": "ALTER TABLE movies ADD COLUMN actors_male TEXT",
        "local_video_id": "ALTER TABLE movies ADD COLUMN local_video_id INTEGER",
    }
    for col_name, sql in new_columns.items():
        if col_name not in existing_columns:
            try:
                cursor.execute(sql)
            except Exception:
                pass  # 已存在则忽略
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_movies_code ON movies(code)")
    
    conn.commit()
    conn.close()


def create_movie(movie_data: dict) -> int:
    """创建新影片"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO movies (
            code, title, title_jp, release_date, duration,
            studio, maker, director, cover_url, preview_url,
            detail_url, genres, actors, actors_male, local_cover_path, local_video_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        movie_data.get("code"),
        movie_data.get("title"),
        movie_data.get("title_jp"),
        movie_data.get("release_date"),
        movie_data.get("duration"),
        movie_data.get("studio"),
        movie_data.get("maker"),
        movie_data.get("director"),
        movie_data.get("cover_url"),
        movie_data.get("preview_url"),
        movie_data.get("detail_url"),
        json.dumps(movie_data.get("genres", []), ensure_ascii=False),
        json.dumps(movie_data.get("actors", []), ensure_ascii=False),
        json.dumps(movie_data.get("actors_male", []), ensure_ascii=False),
        movie_data.get("local_cover_path"),
        movie_data.get("local_video_id"),
    ))

    movie_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return movie_id


def get_movie_by_code(code: str) -> Optional[dict]:
    """根据编号查询影片"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM movies WHERE code = ?", (code,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None


def get_movie_by_id(movie_id: int) -> Optional[dict]:
    """根据ID查询影片，同时取出关联本地视频的多图路径"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM movies WHERE id = ?", (movie_id,))
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        return None
    
    result = dict(row)
    
    # 额外取关联的 local_videos 的图片路径
    local_video_id = result.get("local_video_id")
    if local_video_id:
        cursor.execute(
            "SELECT fanart_path, poster_path, thumb_path FROM local_videos WHERE id = ?",
            (local_video_id,)
        )
        lv_row = cursor.fetchone()
        if lv_row:
            result.update(dict(lv_row))
    
    conn.close()
    return result


def get_all_movies(page: int = 1, page_size: int = 20) -> tuple:
    """获取所有影片（分页）"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM movies")
    total = cursor.fetchone()[0]
    
    offset = (page - 1) * page_size
    cursor.execute("""
        SELECT m.*, lv.fanart_path, lv.poster_path, lv.thumb_path
        FROM movies m
        LEFT JOIN local_videos lv ON m.local_video_id = lv.id
        ORDER BY m.created_at DESC
        LIMIT ? OFFSET ?
    """, (page_size, offset))
    
    rows = cursor.fetchall()
    conn.close()
    
    return total, [dict(row) for row in rows]


def search_movies(keyword: str, page: int = 1, page_size: int = 20) -> tuple:
    """搜索影片"""
    conn = get_db()
    cursor = conn.cursor()
    
    search_pattern = f"%{keyword}%"
    cursor.execute("""
        SELECT COUNT(*) FROM movies 
        WHERE code LIKE ? OR title LIKE ? OR title_jp LIKE ?
    """, (search_pattern, search_pattern, search_pattern))
    total = cursor.fetchone()[0]
    
    offset = (page - 1) * page_size
    cursor.execute("""
        SELECT m.*, lv.fanart_path, lv.poster_path, lv.thumb_path
        FROM movies m
        LEFT JOIN local_videos lv ON m.local_video_id = lv.id
        WHERE m.code LIKE ? OR m.title LIKE ? OR m.title_jp LIKE ?
        ORDER BY m.created_at DESC
        LIMIT ? OFFSET ?
    """, (search_pattern, search_pattern, search_pattern, page_size, offset))
    
    rows = cursor.fetchall()
    conn.close()
    
    return total, [dict(row) for row in rows]


def merge_movie_data(existing: dict, new_data: dict) -> dict:
    """
    智能合并影片数据
    - 如果新数据有值而旧数据为空，更新
    - 如果新旧数据都有值但不同，保留新数据（认为新数据更准确）
    - 如果新数据有旧数据没有的字段，添加
    """
    merged = existing.copy()
    
    # 需要比较和更新的字段
    updatable_fields = [
        "title", "title_jp", "release_date", "duration",
        "studio", "maker", "director", "cover_url",
        "preview_url", "detail_url", "genres", "actors",
        "actors_male", "local_cover_path", "local_video_id"
    ]
    
    for field in updatable_fields:
        new_value = new_data.get(field)
        old_value = existing.get(field)
        
        # 处理列表字段（genres, actors, actors_male）
        if field in ("genres", "actors", "actors_male"):
            # 如果新数据有值而旧数据为空或不同，更新
            if new_value and isinstance(new_value, list) and len(new_value) > 0:
                if not old_value or (isinstance(old_value, str) and len(json.loads(old_value) if old_value else []) < len(new_value)):
                    merged[field] = json.dumps(new_value, ensure_ascii=False)
        else:
            # 普通字段：如果新数据有值，更新
            if new_value and new_value != old_value:
                merged[field] = new_value
    
    return merged


def update_movie(movie_id: int, movie_data: dict, merge: bool = True) -> bool:
    """
    更新影片信息
    - merge=True: 智能合并，与现有数据合并
    - merge=False: 完全替换
    """
    conn = get_db()
    cursor = conn.cursor()
    
    if merge:
        # 获取现有数据
        cursor.execute("SELECT * FROM movies WHERE id = ?", (movie_id,))
        row = cursor.fetchone()
        if row:
            existing = dict(row)
            movie_data = merge_movie_data(existing, movie_data)
    
    fields = []
    values = []
    
    for key, value in movie_data.items():
        if key not in ("id", "created_at"):
            if key in ("genres", "actors", "actors_male") and isinstance(value, list):
                value = json.dumps(value, ensure_ascii=False)
            fields.append(f"{key} = ?")
            values.append(value)
    
    if fields:
        fields.append("updated_at = ?")
        values.append(datetime.now().isoformat())
        values.append(movie_id)
        
        cursor.execute(
            f"UPDATE movies SET {', '.join(fields)} WHERE id = ?",
            values
        )
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        return affected > 0
    
    conn.close()
    return False


def upsert_movie(movie_data: dict) -> tuple:
    """
    upsert：存在则更新，不存在则创建
    返回: (movie_id, is_new)
    """
    code = movie_data.get("code")
    if not code:
        raise ValueError("影片编号不能为空")

    existing = get_movie_by_code(code)

    if existing:
        # 更新，智能合并
        update_movie(existing["id"], movie_data, merge=True)
        # 如果有 local_video_id，也更新关联
        if movie_data.get("local_video_id"):
            link_movie_to_local_video(existing["id"], movie_data["local_video_id"])
        return existing["id"], False
    else:
        # 创建
        movie_id = create_movie(movie_data)
        # 如果有 local_video_id，也建立关联
        if movie_data.get("local_video_id"):
            link_movie_to_local_video(movie_id, movie_data["local_video_id"])
        return movie_id, True


def delete_movie(movie_id: int) -> bool:
    """删除影片"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM movies WHERE id = ?", (movie_id,))
    conn.commit()
    affected = cursor.rowcount
    conn.close()

    return affected > 0


def get_local_video_by_code(code: str) -> Optional[dict]:
    """根据番号查找本地视频"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT v.*, s.path as source_path FROM local_videos v "
        "LEFT JOIN local_sources s ON v.source_id = s.id "
        "WHERE v.code = ? AND v.code IS NOT NULL AND v.code != ''",
        (code,)
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def link_movie_to_local_video(movie_id: int, local_video_id: int) -> bool:
    """将影片关联到本地视频"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE movies SET local_video_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (local_video_id, movie_id)
    )
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0


def row_to_movie_response(row: dict) -> dict:
    """将数据库行转换为响应格式"""
    if row.get("genres") and isinstance(row["genres"], str):
        row["genres"] = json.loads(row["genres"])
    if row.get("actors") and isinstance(row["actors"], str):
        row["actors"] = json.loads(row["actors"])
    if row.get("actors_male") and isinstance(row["actors_male"], str):
        row["actors_male"] = json.loads(row["actors_male"])
    return row


# ========== 本地视频源管理 ==========

def init_local_sources_table():
    """初始化本地视频源表"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS local_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT UNIQUE NOT NULL,
            name TEXT,
            enabled INTEGER DEFAULT 1,
            video_count INTEGER DEFAULT 0,
            last_scan_at TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


def init_local_videos_table():
    """初始化本地视频表"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS local_videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER,
            name TEXT NOT NULL,
            path TEXT UNIQUE NOT NULL,
            code TEXT,
            extension TEXT,
            file_size INTEGER DEFAULT 0,
            scraped INTEGER DEFAULT 0,
            movie_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (source_id) REFERENCES local_sources(id) ON DELETE CASCADE,
            FOREIGN KEY (movie_id) REFERENCES movies(id) ON DELETE SET NULL
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_local_videos_code ON local_videos(code)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_local_videos_source ON local_videos(source_id)")

    conn.commit()
    conn.close()


def init_all_tables():
    """初始化所有表"""
    init_db()
    init_local_sources_table()
    init_local_videos_table()


# 本地视频源 CRUD

def create_local_source(path: str, name: str = None) -> int:
    """添加本地视频源"""
    conn = get_db()
    cursor = conn.cursor()

    import os
    folder_name = name or os.path.basename(path.rstrip('\\/'))

    cursor.execute("""
        INSERT OR IGNORE INTO local_sources (path, name)
        VALUES (?, ?)
    """, (path, folder_name))

    conn.commit()

    # 获取已有记录的 id
    cursor.execute("SELECT id FROM local_sources WHERE path = ?", (path,))
    row = cursor.fetchone()
    source_id = row[0] if row else None

    conn.close()
    return source_id


def get_local_sources() -> list:
    """获取所有本地视频源"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, path, name, enabled, video_count, last_scan_at, created_at
        FROM local_sources
        ORDER BY created_at DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def delete_local_source(source_id: int) -> bool:
    """删除本地视频源（级联删除视频记录）"""
    conn = get_db()
    cursor = conn.cursor()

    # 先删除关联的视频
    cursor.execute("DELETE FROM local_videos WHERE source_id = ?", (source_id,))
    # 再删除源
    cursor.execute("DELETE FROM local_sources WHERE id = ?", (source_id,))

    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0


def update_local_source_scan(source_id: int, video_count: int):
    """更新扫描结果"""
    conn = get_db()
    cursor = conn.cursor()

    from datetime import datetime
    cursor.execute("""
        UPDATE local_sources
        SET video_count = ?, last_scan_at = ?
        WHERE id = ?
    """, (video_count, datetime.now().isoformat(), source_id))

    conn.commit()
    conn.close()


# 本地视频 CRUD

def upsert_local_video(video_data: dict) -> tuple:
    """
    upsert 本地视频记录（只保存有番号的视频）
    返回: (video_id, is_new)
    """
    path = video_data.get("path")
    if not path:
        raise ValueError("视频路径不能为空")
    # 不保存无番号的记录
    if not video_data.get("code"):
        return None, False

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT id, scraped, movie_id FROM local_videos WHERE path = ?", (path,))
    row = cursor.fetchone()

    if row:
        video_id, old_scraped, old_movie_id = row
        # 更新
        cursor.execute("""
            UPDATE local_videos
            SET name = ?, code = ?, extension = ?, file_size = ?,
                fanart_path = ?, poster_path = ?, thumb_path = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            video_data.get("name"),
            video_data.get("code"),
            video_data.get("extension"),
            video_data.get("file_size", 0),
            video_data.get("fanart_path"),
            video_data.get("poster_path"),
            video_data.get("thumb_path"),
            video_id
        ))
        conn.commit()
        conn.close()
        return video_id, False
    else:
        cursor.execute("""
            INSERT INTO local_videos (source_id, name, path, code, extension, file_size, fanart_path, poster_path, thumb_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            video_data.get("source_id"),
            video_data.get("name"),
            path,
            video_data.get("code"),
            video_data.get("extension"),
            video_data.get("file_size", 0),
            video_data.get("fanart_path"),
            video_data.get("poster_path"),
            video_data.get("thumb_path"),
        ))
        video_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return video_id, True


def get_local_videos(
    page: int = 1,
    page_size: int = 30,
    source_id: int = None,
    scraped: int = None,
    keyword: str = None
) -> tuple:
    """
    获取本地视频列表（分页）
    scraped: None=全部, 0=未刮削, 1=已刮削
    """
    conn = get_db()
    cursor = conn.cursor()

    where_clauses = []
    params = []

    if source_id is not None:
        where_clauses.append("v.source_id = ?")
        params.append(source_id)

    if scraped is not None:
        where_clauses.append("v.scraped = ?")
        params.append(scraped)

    if keyword:
        where_clauses.append("(v.name LIKE ? OR v.code LIKE ?)")
        params.extend([f"%{keyword}%", f"%{keyword}%"])

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    cursor.execute(f"SELECT COUNT(*) FROM local_videos v WHERE {where_sql}", params)
    total = cursor.fetchone()[0]

    offset = (page - 1) * page_size
    cursor.execute(f"""
        SELECT v.*, m.title, m.cover_url, m.local_cover_path, m.release_date, m.actors
        FROM local_videos v
        LEFT JOIN movies m ON v.movie_id = m.id
        WHERE {where_sql}
        ORDER BY v.updated_at DESC
        LIMIT ? OFFSET ?
    """, params + [page_size, offset])

    rows = cursor.fetchall()
    conn.close()

    result = []
    for row in rows:
        item = dict(row)
        # actors 可能是 JSON 字符串
        if item.get("actors") and isinstance(item["actors"], str):
            item["actors"] = json.loads(item["actors"])
        result.append(item)

    return total, result


def mark_video_scraped(video_id: int, movie_id: int):
    """标记视频已刮削并关联影片"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE local_videos
        SET scraped = 1, movie_id = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (movie_id, video_id))

    conn.commit()
    conn.close()


def delete_local_video(video_id: int) -> bool:
    """删除本地视频记录"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM local_videos WHERE id = ?", (video_id,))
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0


def get_unscraped_local_videos() -> list:
    """获取所有未刮削的本地视频"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT v.*, s.path as source_path
        FROM local_videos v
        LEFT JOIN local_sources s ON v.source_id = s.id
        WHERE v.scraped = 0 AND v.code IS NOT NULL AND v.code != ''
        ORDER BY v.id
    """)

    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def cleanup_videos_without_code():
    """删除所有无番号的本地视频记录"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM local_videos WHERE code IS NULL OR code = ''")
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted


def cleanup_invalid_codes():
    """
    清理本地视频库中无效的记录。
    使用与扫描相同的番号提取逻辑验证文件名，
    并检查文件是否在本地存在。
    删除：(1) 文件名无法提取有效番号的记录  (2) 文件本地不存在的记录
    返回: (deleted_count, list_of_deleted_info)
    """
    import os
    import re as _re

    # 复用 main.py 中扫描用的番号提取函数
    # （内部使用同一套正则规则和验证逻辑）
    try:
        from main import _extract_code_from_filename
    except ImportError:
        # 兜底：文件不存在则使用简单提取
        def _extract_code_from_filename(name):
            match = _re.search(r'([A-Z]{2,6})-(\d{2,5})', name.upper())
            return f"{match.group(1)}-{int(match.group(2))}" if match else None

    VIDEO_EXTS = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv',
                  '.webm', '.m4v', '.mpg', '.mpeg', '.ts', '.mts',
                  '.m2ts', '.vob', '.ogv'}

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT id, name, path FROM local_videos WHERE path IS NOT NULL AND path != ''")
    rows = cursor.fetchall()

    deleted_count = 0
    deleted_infos = []

    for row in rows:
        video_id = row['id']
        name = row['name']
        path = row['path']

        should_delete = False
        reason = ""

        # 步骤1：用扫描同款函数检查番号是否有效
        ext = _re.search(r'(\.[^.]+)$', name, _re.I)
        ext = ext.group(1) if ext else ""
        name_without_ext = name[:-len(ext)] if ext else name

        extracted = _extract_code_from_filename(name_without_ext)

        if extracted is None:
            should_delete = True
            reason = "番号无效"
        elif not os.path.exists(path):
            should_delete = True
            reason = "文件不存在"

        if should_delete:
            cursor.execute("DELETE FROM local_videos WHERE id = ?", (video_id,))
            deleted_count += 1
            deleted_infos.append(f"[{reason}] {name} ({path})")

    conn.commit()
    conn.close()

    return deleted_count, deleted_infos


def get_local_video_stats() -> dict:
    """获取本地视频统计"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN scraped = 1 THEN 1 ELSE 0 END) as scraped,
            SUM(CASE WHEN scraped = 0 THEN 1 ELSE 0 END) as unscraped
        FROM local_videos
        WHERE code IS NOT NULL AND code != ''
    """)
    row = cursor.fetchone()

    conn.close()
    return dict(row) if row else {"total": 0, "scraped": 0, "unscraped": 0}
