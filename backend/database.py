"""
SQLite 数据库模块
"""
import re
import sqlite3
from datetime import datetime
from typing import List, Optional
from pathlib import Path
import json

DATABASE_PATH = Path(__file__).resolve().parent.parent / "data" / "movies.db"


# ─────────────────────────────────────────────────────────────────────────────
# 番号标准化（统一去零格式）
# ─────────────────────────────────────────────────────────────────────────────
# 规则：去除番号数字部分的前导零
# 例: BEB-016 → BEB-16,  SSIS-037 → SSIS-37,  JNT-001 → JNT-1
# FC2-PPV 和 HEYDOUGA 特殊格式保持原样（数字段可能较长）
#
# 统一标准化意义：
#   - 现在 preserve leading zeros：ABC-012 保持为 ABC-012
#   - 这确保文件系统和数据库中的番号格式一致
# ─────────────────────────────────────────────────────────────────────────────
_FC2_RE = re.compile(r'^FC2-PPV-\d+$', re.IGNORECASE)
_HEYDOUGA_RE = re.compile(r'^HEYDOUGA-\d+-\d+$', re.IGNORECASE)


def normalize_code(code: str) -> str:
    """
    番号标准化：保持原始格式（包括前导零）。
    ABC-012 → ABC-012，ABC-12 → ABC-12
    FC2-PPV / HEYDOUGA 等长数字段特殊格式保持原样。
    """
    if not code:
        return code
    # 特殊格式不做标准化
    if _FC2_RE.match(code) or _HEYDOUGA_RE.match(code):
        return code.upper()
    return code.strip().upper()


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
        "scrape_status": "ALTER TABLE movies ADD COLUMN scrape_status TEXT DEFAULT 'partial'",  # complete/partial/empty
        "scrape_source": "ALTER TABLE movies ADD COLUMN scrape_source TEXT",  # 记录数据来源
        "title_cn": "ALTER TABLE movies ADD COLUMN title_cn TEXT",  # 中文标题
        "fanart_path": "ALTER TABLE movies ADD COLUMN fanart_path TEXT",  # Jellyfin/Kodi 背景
        "poster_path": "ALTER TABLE movies ADD COLUMN poster_path TEXT",  # Jellyfin/Kodi 海报
        "thumb_path": "ALTER TABLE movies ADD COLUMN thumb_path TEXT",  # Jellyfin/Kodi 缩略图
        "source": "ALTER TABLE movies ADD COLUMN source TEXT DEFAULT 'scraped'",  # 数据来源: scraped/jellyfin/manual
        "plot": "ALTER TABLE movies ADD COLUMN plot TEXT",  # 剧情简介
        "source_type": "ALTER TABLE movies ADD COLUMN source_type TEXT DEFAULT 'web'",  # 来源类型: web/jellyfin/local
        "video_path": "ALTER TABLE movies ADD COLUMN video_path TEXT",  # 本地视频文件路径
        "subtitle_type": "ALTER TABLE movies ADD COLUMN subtitle_type TEXT DEFAULT 'none'",  # 字幕类型: none/chinese/english/bilingual
        "last_organized_at": "ALTER TABLE movies ADD COLUMN last_organized_at TIMESTAMP",  # 最近整理时间
        "organized_path": "ALTER TABLE movies ADD COLUMN organized_path TEXT",  # 整理后存放路径
        "scrape_count": "ALTER TABLE movies ADD COLUMN scrape_count INTEGER DEFAULT 0",  # 刮削次数
        "last_scraped_at": "ALTER TABLE movies ADD COLUMN last_scraped_at TIMESTAMP",  # 最近一次刮削时间
        # Jellyfin 结构完整性状态（仅 source_type=jellyfin 的影片有意义）
        # complete: 视频文件 + poster 存在
        # partial:  视频存在但 poster/fanart 缺失
        # broken:   视频文件不存在（引用路径失效）
        # unknown:  未校验过
        "jellyfin_status": "ALTER TABLE movies ADD COLUMN jellyfin_status TEXT DEFAULT 'unknown'",
        # local_videos 表的来源标识（避免每次 JOIN local_sources 查询 is_jellyfin）
        # 在 init_local_videos_table() 里单独添加
    }
    for col_name, sql in new_columns.items():
        if col_name not in existing_columns:
            try:
                cursor.execute(sql)
            except Exception:
                pass  # 已存在则忽略
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_movies_code ON movies(code)")
    
    # 添加演员索引（JSON 数组字段无法直接索引，使用 LIKE 查询时会有性能损失）
    # 如需优化演员查询，可考虑单独建立 actors 表
    # cursor.execute("CREATE INDEX IF NOT EXISTS idx_movies_actors ON movies(actors)")
    
    # ========== 用户权限系统表（RBAC 模型） ==========
    
    # 用户表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            email TEXT,
            role TEXT NOT NULL DEFAULT 'guest',
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    """)
    
    # 角色权限映射表（简化版：直接在用户表存储角色，权限硬编码）
    # admin: 全部权限
    # premium: 刮削、查看、导出
    # guest: 仅查看
    
    # 创建默认 admin 账户
    cursor.execute("SELECT id FROM users WHERE username = 'admin'")
    if not cursor.fetchone():
        from hashlib import sha256
        password_hash = sha256("123".encode()).hexdigest()
        cursor.execute("""
            INSERT INTO users (username, password_hash, role, is_active)
            VALUES (?, ?, 'admin', 1)
        """, ('admin', password_hash))
        print("✅ 创建默认 admin 账户（密码: 123）")
    
    # 创建 tokens 表（Token 持久化）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tokens (
            token TEXT PRIMARY KEY,
            user_id INTEGER,
            username TEXT NOT NULL,
            role TEXT NOT NULL,
            email TEXT,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


# ========== Token 持久化函数 ==========

def create_token_db(token: str, user_data: dict, hours: int = 24) -> None:
    """将 Token 写入数据库"""
    from datetime import datetime, timedelta
    conn = get_db()
    cursor = conn.cursor()
    expires_at = (datetime.now() + timedelta(hours=hours)).isoformat()
    cursor.execute("""
        INSERT OR REPLACE INTO tokens (token, user_id, username, role, email, created_at, expires_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        token,
        user_data.get("id"),
        user_data.get("username"),
        user_data.get("role"),
        user_data.get("email"),
        datetime.now().isoformat(),
        expires_at,
    ))
    conn.commit()
    conn.close()


def verify_token_db(token: str) -> Optional[dict]:
    """从数据库验证 Token，返回用户信息或 None（已过期或不存在）"""
    from datetime import datetime
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT user_id, username, role, email, created_at, expires_at
        FROM tokens WHERE token = ?
    """, (token,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    # 检查是否过期
    if datetime.now() > datetime.fromisoformat(row["expires_at"]):
        # 过期自动清理
        conn2 = get_db()
        conn2.execute("DELETE FROM tokens WHERE token = ?", (token,))
        conn2.commit()
        conn2.close()
        return None
    return {
        "id": row["user_id"],
        "username": row["username"],
        "role": row["role"],
        "email": row["email"],
    }


def delete_token_db(token: str) -> bool:
    """从数据库删除指定 Token"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tokens WHERE token = ?", (token,))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def clean_expired_tokens_db() -> int:
    """清理所有已过期的 Token，返回清理数量"""
    from datetime import datetime
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tokens WHERE expires_at < ?", (datetime.now().isoformat(),))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected


def create_movie(movie_data: dict) -> int:
    """创建新影片"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO movies (
            code, title, title_jp, title_cn, release_date, duration,
            studio, maker, director, cover_url, preview_url,
            detail_url, genres, actors, actors_male, local_cover_path, local_video_id,
            scrape_status, scrape_source, fanart_path, poster_path, thumb_path,
            subtitle_type, organized_path
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        movie_data.get("code"),
        movie_data.get("title"),
        movie_data.get("title_jp"),
        movie_data.get("title_cn"),
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
        movie_data.get("scrape_status", "partial"),
        movie_data.get("scrape_source"),
        movie_data.get("fanart_path"),
        movie_data.get("poster_path"),
        movie_data.get("thumb_path"),
        movie_data.get("subtitle_type", "none"),
        movie_data.get("organized_path"),
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
    
    # 额外取关联的 local_videos 的图片路径和视频路径
    local_video_id = result.get("local_video_id")
    if local_video_id:
        cursor.execute(
            "SELECT fanart_path, poster_path, thumb_path, path FROM local_videos WHERE id = ?",
            (local_video_id,)
        )
        lv_row = cursor.fetchone()
        if lv_row:
            lv_dict = dict(lv_row)
            # 把 path 重命名为 local_video_path，避免与 movies.path 冲突
            if 'path' in lv_dict:
                result['local_video_path'] = lv_dict.pop('path')
            # 只用 local_videos 的图片路径覆盖 movies 的，如果 movies 已有值则保留
            for key in ('fanart_path', 'poster_path', 'thumb_path'):
                if key in lv_dict and lv_dict[key] is not None:
                    result[key] = lv_dict[key]
    
    # 查询所有关联的本地视频（一对多）
    code = result.get("code")
    if code:
        cursor.execute(
            "SELECT id, path, file_size, scraped FROM local_videos WHERE code = ?",
            (code,)
        )
        local_video_rows = cursor.fetchall()
        if local_video_rows:
            result['local_videos'] = [
                {'id': row[0], 'path': row[1], 'size': row[2], 'is_scraped': row[3]}
                for row in local_video_rows
            ]
    
    conn.close()
    return result


def get_all_movies(page: int = 1, page_size: int = 20) -> tuple:
    """获取所有影片（分页）
    排序规则：
    1. 有封面有信息的最前
    2. 信息缺失的其次（无论是否有封面）
    3. 无封面的最后
    同组内按番号字母数字排序
    """
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM movies")
    total = cursor.fetchone()[0]

    offset = (page - 1) * page_size
    cursor.execute("""
        SELECT m.*, lv.fanart_path, lv.poster_path, lv.thumb_path
        FROM movies m
        LEFT JOIN local_videos lv ON m.local_video_id = lv.id
        ORDER BY
            CASE WHEN m.actors IS NOT NULL AND m.actors != '' AND m.title IS NOT NULL AND m.title != '' THEN 0 ELSE 1 END,
            CASE WHEN (m.local_cover_path IS NOT NULL AND m.local_cover_path != ''
                       OR m.cover_url IS NOT NULL AND m.cover_url != ''
                       OR lv.fanart_path IS NOT NULL AND lv.fanart_path != ''
                       OR lv.poster_path IS NOT NULL AND lv.poster_path != '') THEN 0 ELSE 1 END,
            m.code ASC
        LIMIT ? OFFSET ?
    """, (page_size, offset))

    rows = cursor.fetchall()
    conn.close()

    return total, [dict(row) for row in rows]


def get_all_movies_no_paging() -> list:
    """获取所有影片（不分页，用于检查和修复）"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT m.*, lv.fanart_path, lv.poster_path, lv.thumb_path
        FROM movies m
        LEFT JOIN local_videos lv ON m.local_video_id = lv.id
        ORDER BY m.id
    """)

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_local_video_by_id(video_id: int) -> Optional[dict]:
    """根据ID获取本地视频记录"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM local_videos WHERE id = ?", (video_id,))
    row = cursor.fetchone()
    conn.close()

    return dict(row) if row else None


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
    - 保护本地关联字段：source_type, video_path, local_video_id 不被网络刮削覆盖
    """
    merged = existing.copy()
    
    # 需要比较和更新的字段
    updatable_fields = [
        "title", "title_jp", "title_cn", "release_date", "duration",
        "studio", "maker", "director", "cover_url",
        "preview_url", "detail_url", "genres", "actors",
        "actors_male", "local_cover_path",
        "scrape_source", "fanart_path", "poster_path", "thumb_path"
    ]
    
    for field in updatable_fields:
        new_value = new_data.get(field)
        old_value = existing.get(field)
        
        # 处理列表字段（genres, actors, actors_male）
        if field in ("genres", "actors", "actors_male"):
            # 如果新数据有值而旧数据为空或不同，更新
            if new_value and isinstance(new_value, list) and len(new_value) > 0:
                try:
                    old_list_len = len(json.loads(old_value)) if isinstance(old_value, str) else 0
                except (json.JSONDecodeError, TypeError):
                    old_list_len = 0
                if not old_value or old_list_len < len(new_value):
                    merged[field] = json.dumps(new_value, ensure_ascii=False)
        else:
            # 普通字段：如果新数据有值，更新
            if new_value and new_value != old_value:
                merged[field] = new_value
    
    # ========== 保护本地关联字段 ==========
    # local_video_id: 如果已有值，不覆盖（保留本地视频关联）
    if existing.get("local_video_id") and not new_data.get("local_video_id"):
        merged["local_video_id"] = existing["local_video_id"]
    elif new_data.get("local_video_id"):
        merged["local_video_id"] = new_data["local_video_id"]
    
    # source_type: 如果已有值且不是 web，不覆盖（保留 Jellyfin/本地来源）
    if existing.get("source_type") and existing["source_type"] != "web":
        merged["source_type"] = existing["source_type"]
    elif new_data.get("source_type"):
        merged["source_type"] = new_data["source_type"]
    
    # video_path: 如果已有值，不覆盖（保留本地视频路径）
    if existing.get("video_path") and not new_data.get("video_path"):
        merged["video_path"] = existing["video_path"]
    elif new_data.get("video_path"):
        merged["video_path"] = new_data["video_path"]
    
    # 重新计算削刮状态
    merged["scrape_status"] = calculate_scrape_status(merged)
    
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


def upsert_movie(movie_data: dict, force_source_type: str = None) -> tuple:
    """
    upsert：存在则更新，不存在则创建
    返回: (movie_id, is_new)

    参数:
        force_source_type: 强制设置 source_type（用于 Jellyfin 补全刮削，保留 'jellyfin' 来源）
                          仅当 force_source_type='jellyfin' 且 existing movie 存在时，
                          强制将 source_type 改为 'jellyfin'（覆盖 'web' 等污染值）

    注意：存储前统一标准化 code（去零），与 _extract_code_from_filename 保持一致。

    自动关联：每次 upsert_movie 成功后，自动查找所有 code 匹配的 local_videos，
    并更新其 movie_id。从此不再出现"刮削后 movies 有数据但 local_videos 未关联"的孤立记录。
    """
    code = movie_data.get("code")
    if not code:
        raise ValueError("影片编号不能为空")
    # ── 标准化：去零（与 local_videos.code 格式对齐）──────────────
    code = normalize_code(code)
    movie_data["code"] = code

    # 计算削刮状态
    movie_data["scrape_status"] = calculate_scrape_status(movie_data)
    # 每次刮削更新时间和次数（由调用方传入，若未传则在 upsert 时自动处理）
    movie_data["last_scraped_at"] = datetime.now().isoformat()

    existing = get_movie_by_code(code)

    if existing:
        # 更新，智能合并（会保护 source_type/video_path/local_video_id）
        # 刮削次数递增
        movie_data["scrape_count"] = (existing.get("scrape_count") or 0) + 1
        # Jellyfin 补全刮削：强制保留 source_type='jellyfin'
        if force_source_type == 'jellyfin' and existing.get("source_type") != 'jellyfin':
            movie_data["source_type"] = 'jellyfin'
        update_movie(existing["id"], movie_data, merge=True)
        # 如果有 local_video_id，也更新关联
        if movie_data.get("local_video_id"):
            link_movie_to_local_video(existing["id"], movie_data["local_video_id"])
        movie_id = existing["id"]
    else:
        # 创建新记录时才设置默认 source_type
        if "source_type" not in movie_data:
            movie_data["source_type"] = "web"
        movie_data.setdefault("scrape_count", 1)  # 首次刮削
        movie_id = create_movie(movie_data)
        # 如果有 local_video_id，也建立关联
        if movie_data.get("local_video_id"):
            link_movie_to_local_video(movie_id, movie_data["local_video_id"])

    # ── 自动关联：查找所有 code 匹配的 local_videos 并更新 movie_id ──
    _auto_link_local_videos(movie_id, code)

    return movie_id, False if existing else True


def _auto_link_local_videos(movie_id: int, code: str) -> int:
    """
    查找所有 code 匹配的 local_videos（movie_id IS NULL），
    自动更新其 movie_id = 当前 movie_id，并设 scraped=1。

    同时同步 is_jellyfin（从 local_sources.is_jellyfin 获取），
    确保 local_videos.is_jellyfin 与目录来源一致。

    返回更新的记录数。
    """
    try:
        conn = get_db()
        cursor = conn.cursor()
        # 同时更新 movie_id, scraped, is_jellyfin
        cursor.execute("""
            UPDATE local_videos
            SET movie_id = ?,
                scraped = 1,
                is_jellyfin = (
                    SELECT COALESCE(ls.is_jellyfin, 0)
                    FROM local_sources ls
                    WHERE ls.id = local_videos.source_id
                ),
                updated_at = CURRENT_TIMESTAMP
            WHERE code = ? AND (movie_id IS NULL OR movie_id != ?)
        """, (movie_id, code, movie_id))
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected
    except Exception:
        return 0


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
    if row is None:
        return {}
    if row.get("genres") and isinstance(row["genres"], str):
        row["genres"] = json.loads(row["genres"])
    else:
        row["genres"] = None
    if row.get("actors") and isinstance(row["actors"], str):
        row["actors"] = json.loads(row["actors"])
    else:
        row["actors"] = None
    if row.get("actors_male") and isinstance(row["actors_male"], str):
        row["actors_male"] = json.loads(row["actors_male"])
    else:
        row["actors_male"] = None
    # 动态计算刮削状态
    if not row.get("scrape_status"):
        row["scrape_status"] = calculate_scrape_status(row)
    return row


def calculate_scrape_status(movie_data: dict) -> str:
    """
    计算削刮完整度状态
    complete: 有标题 + 有发布日期 + 有制作商 + 有女演员 + 有封面 + 有 NFO 文件
    partial: 部分字段有值
    empty: 仅番号，无其他信息
    
    注意：Jellyfin 视频的封面可能在远程服务器，不检查本地文件
    """
    # 判断是否是 Jellyfin 来源
    source_type = movie_data.get("source_type") or movie_data.get("source")
    is_jellyfin = source_type == "jellyfin"
    
    # 必填字段：title, release_date, maker, actors
    has_title = bool(movie_data.get("title"))
    has_release_date = bool(movie_data.get("release_date"))
    has_maker = bool(movie_data.get("maker"))  # 制作商
    
    # 演员字段特殊处理（可能是列表或JSON字符串）
    actors = movie_data.get("actors")
    has_actors = False
    if actors:
        if isinstance(actors, list) and len(actors) > 0:
            has_actors = True
        elif isinstance(actors, str) and actors.strip() not in ("", "[]"):
            try:
                parsed = json.loads(actors)
                has_actors = isinstance(parsed, list) and len(parsed) > 0
            except:
                pass
    
    # 检查封面
    has_cover = False
    poster_path = movie_data.get("poster_path")
    cover_url = movie_data.get("cover_url")
    if poster_path:
        if is_jellyfin:
            # Jellyfin 视频：只要有 poster_path 就认为有封面（可能是远程 URL 或本地路径）
            has_cover = True
        else:
            # 网络刮削视频：检查本地文件是否存在
            try:
                has_cover = Path(poster_path).exists()
            except:
                pass
    elif is_jellyfin and cover_url:
        # Jellyfin 视频：cover_url（DMM远程图）也算有封面
        has_cover = True
    
    # 检查 NFO 文件（仅非 Jellyfin 来源）
    has_nfo = False
    if not is_jellyfin:
        code = movie_data.get("code")
        if code:
            safe_code = re.sub(r'[<>:"/\\|?*]', '_', str(code))
            nfo_path = DATABASE_PATH.parent / "covers" / safe_code / f"{safe_code}.nfo"
            try:
                has_nfo = nfo_path.exists()
            except Exception:
                pass
    
    # Jellyfin 视频：封面由 Jellyfin 服务器远程提供，不检查本地 poster_path
    # 只要有标题就算 metadata 完整（发布日期/制作商/演员可能为空）
    if is_jellyfin:
        if has_title:
            return "complete"
        elif has_actors or has_cover:
            return "partial"
        else:
            return "empty"
    
    # 网络刮削视频：判断完整度 - 必须同时满足6个条件（含 NFO）
    if has_title and has_release_date and has_maker and has_actors and has_cover and has_nfo:
        return "complete"
    elif has_title or has_release_date or has_maker or has_actors or has_cover or has_nfo:
        return "partial"
    else:
        return "empty"


def update_movie_scrape_status(movie_id: int):
    """更新影片的削刮状态（重新计算）"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM movies WHERE id = ?", (movie_id,))
    row = cursor.fetchone()
    
    if row:
        movie_data = dict(row)
        status = calculate_scrape_status(movie_data)
        cursor.execute(
            "UPDATE movies SET scrape_status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, movie_id)
        )
        conn.commit()
    
    conn.close()


def check_and_fix_scrape_status(code: str) -> dict:
    """
    轻量级单片预检：根据当前数据库字段重新计算 scrape_status，
    若与已存标志不一致则原地修正，无需任何网络请求。

    返回:
        {
          "exists": bool,          # 数据库中是否存在此番号
          "old_status": str|None,  # 修正前的标志
          "new_status": str|None,  # 修正后的标志（不变则与 old_status 相同）
          "fixed": bool,           # 是否做了修正写入
          "should_scrape": bool,   # 修正后是否仍需刮削（new_status != 'complete'）
          "last_scraped_at": str|None,
          "scrape_count": int,
        }
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM movies WHERE code = ?", (code,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return {
            "exists": False,
            "old_status": None,
            "new_status": None,
            "fixed": False,
            "should_scrape": True,
            "last_scraped_at": None,
            "scrape_count": 0,
        }

    movie_data = dict(row)
    old_status = movie_data.get("scrape_status")
    new_status = calculate_scrape_status(movie_data)
    fixed = False

    # 只有状态真正变化时才写库，避免无意义的 UPDATE
    if new_status != old_status:
        cursor.execute(
            "UPDATE movies SET scrape_status = ?, updated_at = CURRENT_TIMESTAMP WHERE code = ?",
            (new_status, code)
        )
        conn.commit()
        fixed = True

    conn.close()
    return {
        "exists": True,
        "old_status": old_status,
        "new_status": new_status,
        "fixed": fixed,
        "should_scrape": new_status != "complete",
        "last_scraped_at": movie_data.get("last_scraped_at"),
        "scrape_count": movie_data.get("scrape_count") or 0,
    }


def batch_verify_scrape_status(limit: int = 0) -> dict:
    """
    批量校验并修正全库 scrape_status 标志位。
    不做网络请求，只根据当前字段重新计算并写库。

    Args:
        limit: 最多处理多少条，0 = 全部

    Returns:
        {"total": int, "fixed": int, "complete": int, "partial": int, "empty": int}
    """
    conn = get_db()
    cursor = conn.cursor()

    sql = "SELECT * FROM movies ORDER BY id"
    if limit > 0:
        sql += f" LIMIT {limit}"
    cursor.execute(sql)
    rows = cursor.fetchall()

    stats = {"total": 0, "fixed": 0, "complete": 0, "partial": 0, "empty": 0}
    updates = []

    for row in rows:
        movie_data = dict(row)
        old_status = movie_data.get("scrape_status")
        new_status = calculate_scrape_status(movie_data)
        stats["total"] += 1
        stats[new_status] = stats.get(new_status, 0) + 1
        if new_status != old_status:
            updates.append((new_status, movie_data["id"]))

    if updates:
        cursor.executemany(
            "UPDATE movies SET scrape_status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            updates
        )
        conn.commit()
        stats["fixed"] = len(updates)

    conn.close()
    return stats


# ========== Jellyfin 结构完整性 ==========

def calculate_jellyfin_status(movie_id: int, video_path: str, poster_path: str = None,
                               fanart_path: str = None) -> str:
    """
    计算 Jellyfin 影片的结构完整性状态（仅 source_type=jellyfin 的影片有意义）。

    完整性判断：
      complete: video 存在 + poster 存在（核心）
      partial:  video 存在，但 poster/fanart 至少缺一样
      broken:   video 文件不存在（引用路径失效）
      unknown:  无法判断（无 video_path）

    注意：NFO 由 Jellyfin 自身管理，MyMovieDB 不强制要求。
    """
    from pathlib import Path

    if not video_path:
        return "unknown"

    video_exists = Path(video_path).exists()
    if not video_exists:
        return "broken"

    # 至少要有 poster（核心封面）
    poster_exists = bool(poster_path and Path(poster_path).exists())
    # fanart 是可选的
    fanart_exists = bool(fanart_path and Path(fanart_path).exists())

    if poster_exists:
        return "complete"
    else:
        return "partial"


def verify_jellyfin_status(movie_id: int) -> dict:
    """
    对单部 Jellyfin 影片重新校验结构完整性，不写库，只返回校验结果。
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT v.id, v.path, m.poster_path, m.fanart_path, m.jellyfin_status
        FROM local_videos v
        JOIN movies m ON v.movie_id = m.id
        WHERE v.movie_id = ? AND m.source_type = 'jellyfin'
        LIMIT 1
    """, (movie_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    lv_id, video_path, poster_path, fanart_path, old_status = row
    new_status = calculate_jellyfin_status(movie_id, video_path, poster_path, fanart_path)
    return {
        "movie_id": movie_id,
        "video_exists": Path(video_path).exists() if video_path else False,
        "poster_exists": Path(poster_path).exists() if poster_path else False,
        "fanart_exists": Path(fanart_path).exists() if fanart_path else False,
        "old_status": old_status,
        "new_status": new_status,
        "changed": old_status != new_status,
    }


def update_jellyfin_status(movie_id: int, video_path: str, poster_path: str = None,
                            fanart_path: str = None) -> str:
    """
    计算并写入 jellyfin_status 列（增量：仅当状态变化时才写库）。
    返回计算后的状态值。
    """
    from pathlib import Path

    new_status = calculate_jellyfin_status(movie_id, video_path, poster_path, fanart_path)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT jellyfin_status FROM movies WHERE id = ?",
        (movie_id,)
    )
    row = cursor.fetchone()
    if row and row[0] == new_status:
        conn.close()
        return new_status  # 无需更新

    cursor.execute(
        "UPDATE movies SET jellyfin_status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (new_status, movie_id)
    )
    conn.commit()
    conn.close()
    return new_status


def batch_verify_jellyfin_status(limit: int = 0) -> dict:
    """
    批量校验 Jellyfin 影片的 jellyfin_status，并修正数据库。

    Returns:
        stats = {
            "total": N,          # 总 Jellyfin 影片数
            "complete": N,       # 结构完整（video + poster）
            "partial": N,        # video 存在但封面缺失
            "broken": N,         # video 文件不存在
            "unknown": N,        # 无 video_path
            "fixed": N,          # 本次修正的记录数
        }
    """
    from pathlib import Path

    conn = get_db()
    cursor = conn.cursor()

    query = """
        SELECT v.id as lv_id, v.path, v.movie_id,
               m.poster_path, m.fanart_path, m.jellyfin_status, m.id as m_id
        FROM local_videos v
        JOIN movies m ON v.movie_id = m.id
        WHERE m.source_type = 'jellyfin'
    """
    if limit > 0:
        query += f" LIMIT {limit}"
    cursor.execute(query)

    stats = {"total": 0, "complete": 0, "partial": 0, "broken": 0, "unknown": 0, "fixed": 0}
    updates = []

    for row in cursor.fetchall():
        lv_id, video_path, movie_id, poster_path, fanart_path, old_status, m_id = row
        new_status = calculate_jellyfin_status(m_id, video_path, poster_path, fanart_path)
        stats["total"] += 1
        stats[new_status] = stats.get(new_status, 0) + 1
        if old_status != new_status:
            updates.append((new_status, m_id))

    if updates:
        cursor.executemany(
            "UPDATE movies SET jellyfin_status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            updates
        )
        conn.commit()
        stats["fixed"] = len(updates)

    conn.close()
    return stats


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
            is_jellyfin INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 添加 is_jellyfin 字段（向后兼容）
    existing_columns = [col[1] for col in cursor.execute("PRAGMA table_info(local_sources)")]
    if "is_jellyfin" not in existing_columns:
        try:
            cursor.execute("ALTER TABLE local_sources ADD COLUMN is_jellyfin INTEGER DEFAULT 0")
        except Exception:
            pass

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

    # 添加 is_jellyfin 列（denormalize，避免每次 JOIN local_sources 查询）
    # 解决：get_unscraped_local_videos SQL 过滤依赖 JOIN 结果，但 JOIN 结果与
    #       movies.source_type 不同步，导致 Jellyfin 目录视频混入批量刮削
    existing_lv_cols = [col[1] for col in cursor.execute("PRAGMA table_info(local_videos)")]
    if 'is_jellyfin' not in existing_lv_cols:
        try:
            cursor.execute("ALTER TABLE local_videos ADD COLUMN is_jellyfin INTEGER DEFAULT 0")
            print("  + local_videos.is_jellyfin 列已添加")
        except Exception:
            pass  # 已存在则忽略

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_local_videos_code ON local_videos(code)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_local_videos_source ON local_videos(source_id)")

    conn.commit()
    conn.close()


def sync_local_videos_is_jellyfin():
    """
    将 local_videos.is_jellyfin 与 local_sources.is_jellyfin 同步。

    背景：
    - local_videos.is_jellyfin 是 denormalize 列，避免每次 JOIN 查询
    - 当 local_sources.is_jellyfin 发生变化（如新增 Jellyfin 目录），
      或 local_videos 移动/复制到新目录后，调用此函数同步
    - 同时将 movies.source_type 与 is_jellyfin 目录的影片同步

    同步规则：
    - is_jellyfin=1 目录的视频 → local_videos.is_jellyfin=1, movies.source_type='jellyfin'
    - is_jellyfin=0 目录的视频 → local_videos.is_jellyfin=0（source_type 不强制覆盖）
    - Case B: is_jellyfin=0 但 source_type='jellyfin' → 强制改 source_type='web'
    """
    conn = get_db()
    cursor = conn.cursor()

    # Step 1: 同步 local_videos.is_jellyfin
    # 正确做法：JOIN local_sources，只更新值真正不同的行（SQLite 3.21 兼容写法）
    # 避免 IS NOT (subquery) 在找不到匹配行时把孤立记录也纳入更新（rowcount 虚高到 401）
    cursor.execute("""
        UPDATE local_videos
        SET is_jellyfin = (
            SELECT COALESCE(ls.is_jellyfin, 0)
            FROM local_sources ls
            WHERE ls.id = local_videos.source_id
        )
        WHERE source_id IS NOT NULL
          AND source_id IN (SELECT id FROM local_sources)
          AND COALESCE(is_jellyfin, -1) != (
              SELECT COALESCE(ls.is_jellyfin, 0)
              FROM local_sources ls
              WHERE ls.id = local_videos.source_id
          )
    """)
    lv_updated = cursor.rowcount

    # Step 2: Case B 修复 - is_jellyfin=0 但 source_type='jellyfin' 的影片
    # 关键修复：排除同时在 Jellyfin 目录中存在的电影（双目录情形）
    # 如果一部电影同时存在于 Jellyfin 目录（is_jellyfin=1）和普通目录（is_jellyfin=0），
    # source_type 应保持 'jellyfin'，CaseB 不应覆盖 CaseA 的结果。
    cursor.execute("""
        UPDATE movies
        SET source_type = 'web'
        WHERE id IN (
            SELECT lv.movie_id
            FROM local_videos lv
            JOIN local_sources ls ON lv.source_id = ls.id
            WHERE ls.is_jellyfin = 0
              AND lv.is_jellyfin = 0
              AND lv.movie_id IS NOT NULL
        )
        AND source_type = 'jellyfin'
        AND id NOT IN (
            -- 排除同时在 Jellyfin 目录里存在记录的电影
            SELECT DISTINCT lv2.movie_id
            FROM local_videos lv2
            JOIN local_sources ls2 ON lv2.source_id = ls2.id
            WHERE ls2.is_jellyfin = 1
              AND lv2.is_jellyfin = 1
              AND lv2.movie_id IS NOT NULL
        )
    """)
    case_b_fixed = cursor.rowcount

    # Step 3: Case A 修复 - is_jellyfin=1 但 source_type='web' 的影片
    # 修复：移除 subquery 中对外层 movies 表的引用（SQLite 不支持该语法，会导致全表扫描）
    cursor.execute("""
        UPDATE movies
        SET source_type = 'jellyfin'
        WHERE id IN (
            SELECT lv.movie_id
            FROM local_videos lv
            JOIN local_sources ls ON lv.source_id = ls.id
            WHERE ls.is_jellyfin = 1
              AND lv.is_jellyfin = 1
              AND lv.movie_id IS NOT NULL
        )
        AND source_type = 'web'
    """)
    case_a_fixed = cursor.rowcount

    conn.commit()
    conn.close()

    return {
        'lv_is_jellyfin_synced': lv_updated,
        'case_a_fixed': case_a_fixed,
        'case_b_fixed': case_b_fixed,
    }


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


def get_local_source_by_id(source_id: int) -> Optional[dict]:
    """根据 ID 获取单个本地视频源"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, path, name, enabled, video_count, last_scan_at, created_at
        FROM local_sources WHERE id = ?
    """, (source_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


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

    注意：存储前统一标准化 code（去零），与 movies.code 保持一致。
    """
    path = video_data.get("path")
    if not path:
        raise ValueError("视频路径不能为空")
    # 不保存无番号的记录
    if not video_data.get("code"):
        return None, False
    # ── 标准化：去零（与 movies.code 格式对齐）──────────────────
    raw_code = video_data.get("code")
    video_data["code"] = normalize_code(raw_code)

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
                is_jellyfin = COALESCE(?, is_jellyfin),
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
            video_data.get("is_jellyfin", 0),
            video_id
        ))
        conn.commit()
        conn.close()
        return video_id, False
    else:
        cursor.execute("""
            INSERT INTO local_videos (source_id, name, path, code, extension, file_size, fanart_path, poster_path, thumb_path, is_jellyfin)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, 0))
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
            video_data.get("is_jellyfin", 0),
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
    scrape_status: str = None,
    keyword: str = None
) -> tuple:
    """
    获取本地视频列表（分页）
    scraped: None=全部, 0=未刮削, 1=已刮削（按 local_videos.scraped 字段）
    scrape_status: None=全部, 'complete'=完整, 'partial'=部分, 'empty'=空, 'not_complete'=不完整(partial+empty+NULL)
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

    if scrape_status is not None:
        if scrape_status == "not_complete":
            where_clauses.append("(m.scrape_status IS NULL OR m.scrape_status != 'complete')")
        else:
            where_clauses.append("m.scrape_status = ?")
            params.append(scrape_status)

    if keyword:
        where_clauses.append("(v.name LIKE ? OR v.code LIKE ?)")
        params.extend([f"%{keyword}%", f"%{keyword}%"])

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    cursor.execute(f"""
        SELECT COUNT(*) FROM local_videos v
        LEFT JOIN movies m ON v.movie_id = m.id
        WHERE {where_sql}
    """, params)
    total = cursor.fetchone()[0]

    offset = (page - 1) * page_size
    # 注意：local_videos 和 movies 都有 poster_path/thumb_path 字段
    # 优先使用 movies 表的封面（刮削后的），若为 NULL 则用 local_videos 的
    cursor.execute(f"""
        SELECT v.id, v.source_id, v.name, v.path, v.code, v.extension, v.file_size,
               v.scraped, v.movie_id, v.created_at, v.updated_at,
               v.fanart_path AS local_fanart, v.poster_path AS local_poster, v.thumb_path AS local_thumb,
               m.title, m.cover_url, m.local_cover_path, m.release_date, m.actors,
               m.maker, m.scrape_status,
               COALESCE(m.poster_path, v.poster_path) AS poster_path,
               COALESCE(m.thumb_path, v.thumb_path) AS thumb_path,
               COALESCE(m.fanart_path, v.fanart_path) AS fanart_path
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
        # 封面路径转换：本地路径 → API 路径
        # 本地视频库列表用缩略图（thumb_path），节省带宽和加载速度
        if item.get("thumb_path"):
            item["cover_url_display"] = item["thumb_path"]
        elif item.get("poster_path"):
            item["cover_url_display"] = item["poster_path"]
        elif item.get("local_cover_path"):
            item["cover_url_display"] = item["local_cover_path"]
        elif item.get("cover_url"):
            # 外部 URL 直接用
            item["cover_url_display"] = item["cover_url"]
        else:
            item["cover_url_display"] = None
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
    """
    获取所有需要刮削的本地视频。

    业务逻辑（两步走，避免大量无意义刮削）：

    Step-1（SQL层过滤）：
      - 只取 code 非空、scrape_status != 'complete' 的视频
      - 排除 source_type = 'jellyfin' 的影片（Jellyfin 来源不走网络刮削）

    Step-2（Python层轻量预检）：
      - 对每条视频调用 check_and_fix_scrape_status()
      - 若实际数据已满足 complete 要求（标志位只是还没更新），
        则原地修正标志并跳过，不加入待刮削列表
      - 防止已有完整数据的影片因标志位滞后而被重复刮削
    """
    conn = get_db()
    cursor = conn.cursor()

    # Step-1：SQL 层粗过滤
    # 关键修复：用 v.is_jellyfin = 0 替代 m.source_type != 'jellyfin'
    # 原因：movies.source_type 会被批量刮削污染（is_jellyfin=1 但 source_type='web'）
    #       而 local_videos.is_jellyfin 由 sync_local_videos_is_jellyfin() 维护，
    #       是可靠的来源标识
    # 同步处理：is_jellyfin IS NULL 的孤立记录也纳入待刮削范围（fix_is_jellyfin_null_records 会清理，
    #           但 startup 之前可能仍有残留，保守纳入统计）
    cursor.execute("""
        SELECT v.*, s.path as source_path,
               m.scrape_status, m.source_type AS movie_source_type,
               m.last_scraped_at, m.scrape_count
        FROM local_videos v
        LEFT JOIN local_sources s ON v.source_id = s.id
        LEFT JOIN movies m ON v.movie_id = m.id
        WHERE v.code IS NOT NULL AND v.code != ''
          AND (v.is_jellyfin = 0 OR v.is_jellyfin IS NULL)
          AND (m.scrape_status IS NULL OR m.scrape_status != 'complete')
        ORDER BY v.id
    """)

    rows = cursor.fetchall()
    conn.close()

    # Step-2：Python 层精确预检（只校验标志位，无网络请求）
    result = []
    for row in rows:
        video = dict(row)
        code = video.get("code")
        if not code:
            continue

        # 预检：重新计算当前字段是否已满足 complete
        check = check_and_fix_scrape_status(code)

        if check["exists"] and not check["should_scrape"]:
            # 标志位已修正为 complete，不需要再刮削
            # 当 movie_id 为 NULL 时，通过 code 查 movie 并建立关联
            if not video.get("movie_id"):
                movie = get_movie_by_code(code)
                if movie:
                    _mark_video_scraped_silent(video["id"], movie["id"])
            elif not video.get("scraped"):
                _mark_video_scraped_silent(video["id"], video["movie_id"])
            continue

        # 把预检结果附到 video dict 上，供调用方参考
        video["scrape_count"] = check.get("scrape_count", 0)
        video["last_scraped_at"] = check.get("last_scraped_at")
        result.append(video)

    return result


def _mark_video_scraped_silent(video_id: int, movie_id: int):
    """标记视频为已刮削（内部静默调用，不抛异常）"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE local_videos SET scraped = 1, movie_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (movie_id, video_id)
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


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
    """
    获取本地视频统计。

    统计口径（与 get_unscraped_local_videos() 的预检验证逻辑对齐）：
    - total:       所有有番号的本地视频（含 Jellyfin）
    - scraped:     非 Jellyfin + scrape_status='complete'（真正完整刮削）
    - unscraped:   非 Jellyfin + 实际需要网络刮削的数量
                   = partial（movie 存在但数据不完整）+ exists_false（无 movie 记录）
                   → 与 get_unscraped_local_videos() 返回的影片数完全一致
    - complete_unlabeled: 非 Jellyfin + 已有完整数据（经 check_and_fix 验证）
                         但 scrape_status != 'complete' 的数量
                         → 预检时会跳过并自动修正标志
    - jellyfin:    Jellyfin 来源视频数（metadata 由 Jellyfin 提供，不走网络刮削）
    - is_null:     is_jellyfin IS NULL 的孤立记录（需要清理）

    scraped 直接用 SQL COUNT 得出，不依赖公式反推，确保数字一致。
    """
    conn = get_db()
    cursor = conn.cursor()

    # ① 总视频数
    cursor.execute("""
        SELECT COUNT(*) FROM local_videos
        WHERE code IS NOT NULL AND code != ''
    """)
    total = cursor.fetchone()[0]

    # ② Jellyfin 视频数（优先用 movies.source_type，fallback 到 is_jellyfin 标记）
    #    is_jellyfin 标记在 cleanup 后已无有效数据，改用 movies 表作为权威来源
    cursor.execute("""
        SELECT COUNT(*) FROM movies WHERE source_type = 'jellyfin'
    """)
    jellyfin = cursor.fetchone()[0]

    # ③ is_jellyfin IS NULL 的孤立记录数（需修复）
    cursor.execute("""
        SELECT COUNT(*) FROM local_videos v
        WHERE v.code IS NOT NULL AND v.code != ''
          AND v.is_jellyfin IS NULL
    """)
    is_null = cursor.fetchone()[0]

    # ④ scraped: 所有有完整刮削数据的本地视频（非 Jellyfin + 刮削完成）
    cursor.execute("""
        SELECT COUNT(*) FROM local_videos v
        LEFT JOIN movies m ON v.movie_id = m.id
        WHERE v.code IS NOT NULL AND v.code != ''
          AND (v.is_jellyfin = 0 OR v.is_jellyfin IS NULL)
          AND (m.id IS NOT NULL AND m.scrape_status = 'complete')
    """)
    scraped = cursor.fetchone()[0]

    # ⑤ unscraped: 非 Jellyfin 来源的本地视频中需要刮削的数量
    #   与 get_unscraped_local_videos() 的过滤口径保持一致
    #   scraped + unscraped = is_jellyfin=0/ISNULL 的总数
    cursor.execute("""
        SELECT COUNT(*) FROM local_videos v
        LEFT JOIN movies m ON v.movie_id = m.id
        WHERE v.code IS NOT NULL AND v.code != ''
          AND (v.is_jellyfin = 0 OR v.is_jellyfin IS NULL)
          AND (m.id IS NULL OR m.scrape_status != 'complete')
    """)
    unscraped = cursor.fetchone()[0]

    complete_unlabeled = 0

    conn.close()
    return {
        'total': total,
        'scraped': scraped,
        'unscraped': unscraped,
        'complete_unlabeled': complete_unlabeled,
        'jellyfin': jellyfin,
        'is_null': is_null,  # 新增：孤立记录数
    }


def fix_is_jellyfin_null_records() -> dict:
    """
    修复所有 is_jellyfin IS NULL 的孤立记录。

    根因：这些 local_videos 的 source_id 指向已删除的 local_sources，
          导致 is_jellyfin 字段为 NULL。

    修复策略：
    1. 将所有 is_jellyfin IS NULL 设为 is_jellyfin = 0
       （无来源记录 = 非 Jellyfin 视频，按正常刮削处理）
    2. 不删除 movies 记录（可能还有价值）
    3. 返回修复统计
    """
    conn = get_db()
    cursor = conn.cursor()

    # 修复前数量
    cursor.execute("""
        SELECT COUNT(*) FROM local_videos
        WHERE code IS NOT NULL AND code != ''
          AND is_jellyfin IS NULL
    """)
    before = cursor.fetchone()[0]

    # 修复 UPDATE
    cursor.execute("""
        UPDATE local_videos
        SET is_jellyfin = 0,
            scraped = COALESCE(scraped, 0),
            updated_at = CURRENT_TIMESTAMP
        WHERE is_jellyfin IS NULL
          AND code IS NOT NULL AND code != ''
    """)
    fixed = cursor.rowcount
    conn.commit()

    # 提交后再查询（SQLite 自动开始新事务）
    cursor.execute("""
        SELECT COUNT(*) FROM local_videos
        WHERE code IS NOT NULL AND code != ''
          AND is_jellyfin IS NULL
    """)
    after = cursor.fetchone()[0]
    conn.close()
    return {
        'fixed': fixed,
        'remaining_null': after,
        'message': f'已修复 {fixed} 条孤立记录' + (f'，剩余 {after} 条' if after else '，全部修复完毕'),
    }


def import_jellyfin_movie(code: str, metadata: dict, video_path: str, 
                          poster_file: str = None, fanart_file: str = None,
                          thumb_file: str = None) -> int:
    """
    导入 Jellyfin 格式影片到数据库
    
    Args:
        code: 番号
        metadata: NFO 元数据字典
        video_path: 视频文件路径
        poster_file: 海报图片路径（本地文件）
        fanart_file: 背景图路径（本地文件）
        thumb_file: 缩略图路径（本地文件）
    
    Returns:
        movie_id 或 -1（失败）、0（跳过）

    注意：存储前统一标准化 code（去零），与 _extract_code_from_filename 保持一致。
    """
    import os
    # ── 标准化：去零（与 local_videos.code 格式对齐）───────────
    code = normalize_code(code)

    conn = get_db()
    cursor = conn.cursor()

    try:
        # 检查是否已存在（同时查 source 和 source_type）
        cursor.execute("SELECT id, source, source_type FROM movies WHERE code = ?", (code,))
        existing = cursor.fetchone()

        if existing:
            movie_id = existing['id']
            existing_st = existing['source_type']

            # 如果已经是 Jellyfin 来源，跳过（用 source_type 判断，统一口径）
            # source_type='jellyfin' 意味着该记录已由 Jellyfin NFO 完全填充
            if existing_st == 'jellyfin':
                conn.close()
                return 0  # 跳过
            
            # source_type != 'jellyfin'（如 'web'）：Jellyfin NFO 数据有更高权威
            # → 强制覆盖所有字段（包括已填写的 web 数据），彻底替换为 Jellyfin 来源
            update_fields = ["source = ?", "source_type = ?", "video_path = ?",
                             "scrape_status = ?"]
            update_values = ['jellyfin', 'jellyfin', video_path, 'complete']

            for field in ['title', 'title_jp', 'plot', 'release_date', 'studio',
                          'maker', 'director']:
                val = metadata.get(field)
                update_fields.append(f"{field} = ?")
                update_values.append(val if val else None)

            # 演员/genres 强制覆盖（JSON）
            update_fields.append("actors = ?")
            update_values.append(json.dumps(metadata.get('actors') or [], ensure_ascii=False))
            update_fields.append("actors_male = ?")
            update_values.append(json.dumps(metadata.get('actors_male') or [], ensure_ascii=False))
            update_fields.append("genres = ?")
            update_values.append(json.dumps(metadata.get('genres') or [], ensure_ascii=False))

            # 本地图片路径强制覆盖
            update_fields.append("poster_path = ?")
            update_values.append(poster_file)
            update_fields.append("fanart_path = ?")
            update_values.append(fanart_file)
            update_fields.append("thumb_path = ?")
            update_values.append(thumb_file)

            update_values.append(movie_id)
            cursor.execute(f"""
                UPDATE movies SET {', '.join(update_fields)} WHERE id = ?
            """, update_values)
        else:
            # 插入新记录
            cursor.execute("""
                INSERT INTO movies (code, title, title_jp, plot, release_date, 
                                    studio, maker, director, actors, actors_male, 
                                    genres, poster_path, fanart_path, thumb_path, 
                                    source, source_type, video_path, scrape_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'jellyfin', 'jellyfin', ?, 'complete')
            """, (
                code,
                metadata.get('title') or code,
                metadata.get('title_jp'),
                metadata.get('plot'),
                metadata.get('release_date'),
                metadata.get('studio'),
                metadata.get('maker'),
                metadata.get('director'),
                json.dumps(metadata.get('actors', []), ensure_ascii=False) if metadata.get('actors') else None,
                json.dumps(metadata.get('actors_male', []), ensure_ascii=False) if metadata.get('actors_male') else None,
                json.dumps(metadata.get('genres', []), ensure_ascii=False) if metadata.get('genres') else None,
                poster_file,
                fanart_file,
                thumb_file,
                video_path,
            ))
            movie_id = cursor.lastrowid
            
            # 同时插入 local_videos 记录（source_id 需从 video_path 反查）
            file_size = os.path.getsize(video_path) if os.path.exists(video_path) else 0
            video_dir = os.path.dirname(video_path)
            # 查找对应的 source_id（Jellyfin 扫描时 source_id 由调用方传入，这里简化处理）
            cursor.execute("""
                INSERT OR IGNORE INTO local_videos
                (path, name, file_size, code, movie_id, scraped, is_jellyfin)
                VALUES (?, ?, ?, ?, ?, 1, 1)
            """, (video_path, os.path.basename(video_path), file_size, code, movie_id))

        # 更新关联的 local_videos 记录的 is_jellyfin=1（如果已有记录）
        # 查找该 movie_id 对应的 local_videos
        cursor.execute(
            "SELECT id FROM local_videos WHERE movie_id = ? AND path = ?",
            (movie_id, video_path)
        )
        lv = cursor.fetchone()
        if lv:
            cursor.execute(
                "UPDATE local_videos SET is_jellyfin = 1 WHERE id = ?",
                (lv['id'],)
            )
        
        conn.commit()
        return movie_id
    
    except Exception as e:
        conn.rollback()
        print(f"[Database] 导入失败: {e}")
        return -1
    finally:
        conn.close()


def get_jellyfin_count() -> int:
    """获取 Jellyfin 导入的影片数量"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM movies WHERE source = 'jellyfin'")
    count = cursor.fetchone()[0]
    conn.close()
    return count


def get_jellyfin_incomplete_codes() -> list:
    """
    获取 Jellyfin 来源但元数据不完整的影片番号。
    判断标准：有 video_path（能找到 NFO）+ 缺 maker 或缺 actors。
    用于批量补全功能。
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT m.code, m.title, m.maker, m.actors, m.video_path,
               v.path as local_video_path
        FROM movies m
        LEFT JOIN local_videos v ON v.movie_id = m.id AND v.is_jellyfin = 1
        WHERE m.source_type = 'jellyfin'
          AND (m.maker IS NULL OR m.maker = ''
               OR m.actors IS NULL OR m.actors = '[]' OR m.actors = '[\"[]\"]')
        ORDER BY m.code
    """)
    rows = cursor.fetchall()
    conn.close()
    result = []
    for r in rows:
        result.append({
            'code': r[0],
            'title': r[1],
            'maker': r[2],
            'actors': r[3],
            'video_path': r[4],
            'local_video_path': r[5],
        })
    return result


def enrich_jellyfin_movie_from_nfo(code: str) -> dict:
    """
    从 Jellyfin NFO 文件补全 movies 表缺失的元数据字段。

    查找逻辑：
    1. 优先使用 movies.video_path（来自 Jellyfin 导入的路径）
    2. 备选：local_videos.path（但 is_jellyfin=1 的记录）
    3. 基础番号推断：去除 -C/-U/-UC/-4K 等后缀，查找同名 .nfo

    返回: {
        'success': bool,
        'nfo_found': bool,
        'nfo_path': str,
        'fields_updated': list[str],   # 本次更新的字段名
        'message': str,
    }
    """
    import os, re as _re
    from jellyfin import parse_jellyfin_nfo

    conn = get_db()
    cursor = conn.cursor()

    # 查找 movie
    cursor.execute("SELECT id, video_path, maker, actors, title FROM movies WHERE code = ?", (code,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return {'success': False, 'nfo_found': False, 'nfo_path': None,
                'fields_updated': [], 'message': 'movies 表无此番号'}

    movie_id, video_path, existing_maker, existing_actors, title = row

    # 推断 NFO 路径
    nfo_path = None
    search_paths = []

    # ① 直接替换扩展名
    if video_path:
        for ext in ['.mp4', '.mkv', '.avi', '.wmv', '.mov']:
            candidate = video_path.replace(ext, '.nfo')
            if candidate != video_path and os.path.exists(candidate):
                nfo_path = candidate
                break

    # ② 基础番号 + 同目录 .nfo（去除 -C/-U/-UC/-4K 后缀）
    if not nfo_path and video_path:
        video_dir = os.path.dirname(video_path)
        base_code = _re.sub(r'[-_](C|U|UC|4K|HD|KT|TT)$', '', code, flags=_re.IGNORECASE)
        for fname in os.listdir(video_dir) if os.path.isdir(video_dir) else []:
            if fname.endswith('.nfo'):
                stem = os.path.splitext(fname)[0]
                if stem.upper() == base_code.upper() or stem.upper() == code.upper():
                    nfo_path = os.path.join(video_dir, fname)
                    break

    # ③ 备选：从 local_videos 查找 is_jellyfin=1 的视频路径
    if not nfo_path:
        cursor.execute("""
            SELECT path FROM local_videos
            WHERE movie_id = ? AND is_jellyfin = 1
            LIMIT 1
        """, (movie_id,))
        lv_row = cursor.fetchone()
        if lv_row and lv_row[0]:
            lv_path = lv_row[0]
            for ext in ['.mp4', '.mkv', '.avi']:
                candidate = lv_path.replace(ext, '.nfo')
                if candidate != lv_path and os.path.exists(candidate):
                    nfo_path = candidate
                    break
            if not nfo_path:
                lv_dir = os.path.dirname(lv_path)
                for fname in os.listdir(lv_dir) if os.path.isdir(lv_dir) else []:
                    if fname.endswith('.nfo'):
                        nfo_path = os.path.join(lv_dir, fname)
                        break

    # ④ 标准路径：data/covers/{code}/{code}.nfo（Jellyfin 刮削输出目录）
    if not nfo_path:
        import pathlib as _pathlib
        nfo_candidate = _pathlib.Path('data/covers') / code / f'{code}.nfo'
        if nfo_candidate.exists():
            nfo_path = str(nfo_candidate)

    if not nfo_path:
        conn.close()
        return {'success': False, 'nfo_found': False, 'nfo_path': None,
                'fields_updated': [], 'message': '未找到 NFO 文件'}

    # 安全检查：验证文件大小（防止 AVI/MP4 被误当 NFO，如 EBOD-054.AVI → .nfo）
    try:
        fsize = os.path.getsize(nfo_path)
        if fsize > 10 * 1024 * 1024:  # > 10MB 不是正常 NFO
            conn.close()
            return {'success': False, 'nfo_found': True, 'nfo_path': nfo_path,
                    'fields_updated': [],
                    'message': f'文件过大({fsize//1024//1024}MB)，非NFO，跳过'}
    except Exception:
        pass

    # 解析 NFO
    try:
        nfo_data = parse_jellyfin_nfo(nfo_path)
    except Exception as e:
        conn.close()
        return {'success': False, 'nfo_found': True, 'nfo_path': nfo_path,
                'fields_updated': [], 'message': f'NFO 解析失败: {e}'}

    if not nfo_data:
        conn.close()
        return {'success': False, 'nfo_found': True, 'nfo_path': nfo_path,
                'fields_updated': [], 'message': 'NFO 解析结果为空'}

    # 对比现有数据，确定哪些字段需要补充
    update_fields = []
    update_values = []

    # maker/studio
    if nfo_data.get('maker') and not existing_maker:
        update_fields.append("maker = ?")
        update_values.append(nfo_data['maker'])
    if nfo_data.get('studio') and not existing_maker:
        update_fields.append("studio = ?")
        update_values.append(nfo_data['studio'])

    # actors（JSON）
    nfo_actors = nfo_data.get('actors') or []
    has_existing_actors = existing_actors and existing_actors not in ('[]', '[\"[]\"]', '')
    if nfo_actors and not has_existing_actors:
        update_fields.append("actors = ?")
        update_values.append(json.dumps(nfo_actors, ensure_ascii=False))

    # genres
    if nfo_data.get('genres'):
        update_fields.append("genres = ?")
        update_values.append(json.dumps(nfo_data['genres'], ensure_ascii=False))

    # poster/fanart 路径
    if nfo_data.get('poster_path') and not nfo_data['poster_path'].startswith('http'):
        update_fields.append("poster_path = ?")
        update_values.append(nfo_data['poster_path'])
    if nfo_data.get('fanart_path') and not nfo_data['fanart_path'].startswith('http'):
        update_fields.append("fanart_path = ?")
        update_values.append(nfo_data['fanart_path'])

    if update_fields:
        update_fields.append("updated_at = ?")
        update_values.append(datetime.now().isoformat())
        update_values.append(movie_id)
        cursor.execute(f"""
            UPDATE movies SET {', '.join(update_fields)} WHERE id = ?
        """, update_values)
        conn.commit()

    field_names = [f.split(' = ')[0] for f in update_fields if 'updated_at' not in f]
    conn.close()

    return {
        'success': True,
        'nfo_found': True,
        'nfo_path': nfo_path,
        'fields_updated': field_names,
        'message': f"更新了 {len(field_names)} 个字段: {', '.join(field_names)}" if field_names else '无字段需要补充',
    }


def mark_source_as_jellyfin(source_path: str, video_count: int = 0) -> bool:
    """标记本地目录为 Jellyfin 格式（如果不存在则创建）"""
    import os
    
    # 规范化路径（统一使用系统分隔符）
    source_path = os.path.normpath(source_path)
    
    conn = get_db()
    cursor = conn.cursor()
    
    # 先尝试更新已存在的记录（支持不同斜杠格式）
    cursor.execute("""
        UPDATE local_sources SET is_jellyfin = 1, video_count = ? WHERE path = ?
    """, (video_count, source_path))
    
    if cursor.rowcount == 0:
        # 记录不存在，插入新记录
        cursor.execute("""
            INSERT INTO local_sources (path, is_jellyfin, enabled, video_count)
            VALUES (?, 1, 1, ?)
        """, (source_path, video_count))
    
    conn.commit()
    conn.close()
    return True


def get_local_sources_with_jellyfin() -> list:
    """获取本地目录列表，包含 Jellyfin 标记"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, path, name, enabled, video_count, last_scan_at, is_jellyfin, created_at
        FROM local_sources
        ORDER BY created_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


# ===============================================================================
# 类别统计相关函数
# ===============================================================================

def get_actor_stats(page: int = 1, page_size: int = 48, keyword: str = None) -> tuple:
    """
    获取女演员统计列表（按出现次数降序）
    返回: (total, items=[{name, count, has_avatar}])
    与 get_actors_without_avatars() 使用相同的批量头像索引逻辑，保证一致性。
    """
    import hashlib
    from pathlib import Path
    from urllib.parse import quote

    # ── 1. 一次性扫描头像目录构建索引（O(1) 查询） ──
    try:
        avatar_dir = Path(__file__).resolve().parent.parent / "data" / "avatars"
        if avatar_dir.exists():
            cached_files = {p.stem for p in avatar_dir.iterdir() if p.suffix.lower() in (".jpg", ".png")}
        else:
            cached_files = set()
    except Exception:
        cached_files = set()

    def _safe_filename(name: str):
        """将演员姓名转换为安全文件名（直接用真实名字，去除非法字符和方括号）"""
        if not name or name == "佚名":
            return None
        # 去除方括号和引号
        name = name.strip().strip('[]"\' ')
        illegal = r'\/:*?"<>|'
        result = name
        for ch in illegal:
            result = result.replace(ch, '_')
        return result.strip() or None

    def _clean_actor_name(name: str) -> str | None:
        """清洗演员姓名：去除 []\" 等残留符号，返回干净姓名或 None"""
        if not name or not isinstance(name, str):
            return None
        raw = name.strip()
        # 跳过明显无效值
        if raw in ("", "[]", "佚名", "null", "None"):
            return None
        # 去除首尾的 [] " ' 空白字符
        cleaned = raw.strip().strip("'\"").strip()
        # 如果清洗后是 [] 或空，跳过
        if cleaned in ("", "[]"):
            return None
        # 去除所有残留的 [ ] " 字符
        cleaned = cleaned.replace("[", "").replace("]", "").replace('"', "").replace("'", "")
        cleaned = cleaned.strip()
        if not cleaned or cleaned in ("[]", "佚名"):
            return None
        return cleaned

    def _has_avatar(name: str) -> bool:
        """O(1) 判断演员是否有本地头像（直接文件名匹配）"""
        safe_name = _safe_filename(name)
        return bool(safe_name and safe_name in cached_files)

    def _local_url(name: str):
        """返回头像 URL（直接文件名匹配）"""
        safe_name = _safe_filename(name)
        if safe_name and safe_name in cached_files:
            return f"/avatars/{quote(safe_name, safe='')}.jpg"
        return None

    conn = get_db()
    cursor = conn.cursor()

    # 统计每名演员的出现次数
    cursor.execute("""
        SELECT code, actors FROM movies
        WHERE actors IS NOT NULL AND actors != '[]' AND actors != ''
    """)
    rows = cursor.fetchall()

    actor_count = {}
    for code, actors_str in rows:
        try:
            actors = json.loads(actors_str)
            for raw_name in actors:
                name = _clean_actor_name(raw_name)
                if name:
                    actor_count[name] = actor_count.get(name, 0) + 1
        except Exception:
            pass

    # 过滤关键词
    if keyword:
        # 过滤时同时用干净名字和原始名字匹配
        filtered = {
            k: v for k, v in actor_count.items()
            if keyword.lower() in k.lower()
        }
    else:
        filtered = actor_count

    total = len(filtered)
    # 排序：有头像的在前，没头像的在后，同组内按名字字母序
    sorted_actors = sorted(
        filtered.items(),
        key=lambda x: (-_has_avatar(x[0]), x[0])
    )

    # 分页
    offset = (page - 1) * page_size
    page_actors = sorted_actors[offset:offset + page_size]

    items = [
        {
            "name": name,
            "count": cnt,
            "has_avatar": _has_avatar(name),
            "local_url": _local_url(name),
        }
        for name, cnt in page_actors
    ]

    conn.close()
    return total, items


def get_actors_without_avatars(page: int = 1, page_size: int = None) -> tuple:
    """
    高效获取无头像女演员列表。
    一次性扫描头像目录构建索引，再批量判断（避免逐个演员查磁盘）。
    page_size=None 时返回全部无头像演员（用于批量下载）。
    返回: (total, items=[{name, count, has_avatar, local_url}])
    """
    import hashlib
    from pathlib import Path
    from urllib.parse import quote

    # ── 1. 一次性扫描所有已缓存的头像文件名，构建索引集合 ──
    try:
        avatar_dir = Path(__file__).resolve().parent.parent / "data" / "avatars"
        if avatar_dir.exists():
            cached_files = {p.stem for p in avatar_dir.iterdir() if p.suffix.lower() in (".jpg", ".png")}
        else:
            cached_files = set()
    except Exception:
        cached_files = set()

    def _safe_filename(name: str):
        """将演员姓名转换为安全文件名（直接用真实名字，去除非法字符）"""
        if not name or name == "佚名":
            return None
        illegal = r'\/:*?"<>|'
        result = name
        for ch in illegal:
            result = result.replace(ch, '_')
        return result.strip() or None

    def _clean_actor_name(name: str) -> str | None:
        """清洗演员姓名：去除 []\" 等残留符号，返回干净姓名或 None"""
        if not name or not isinstance(name, str):
            return None
        raw = name.strip()
        if raw in ("", "[]", "佚名", "null", "None"):
            return None
        cleaned = raw.strip().strip("'\"").strip()
        if cleaned in ("", "[]"):
            return None
        cleaned = cleaned.replace("[", "").replace("]", "").replace('"', "").replace("'", "").strip()
        if not cleaned or cleaned in ("[]", "佚名"):
            return None
        return cleaned

    def _has_avatar(name: str):
        """O(1) 判断演员是否有本地头像"""
        # 1) 真实名字格式（当前格式）
        safe_name = _safe_filename(name)
        if safe_name and safe_name in cached_files:
            return True
        # 2) MD5 兜底（早期文件兼容）
        h = hashlib.md5(name.encode("utf-8")).hexdigest()[12:-12]
        if h in cached_files:
            return True
        return False

    def _local_url(name: str):
        """返回头像 URL（无则为 None）"""
        safe_name = _safe_filename(name)
        if safe_name and safe_name in cached_files:
            return f"/avatars/{quote(safe_name, safe='')}.jpg"
        h = hashlib.md5(name.encode("utf-8")).hexdigest()[12:-12]
        if h in cached_files:
            return f"/avatars/{h}.jpg"
        return None

    # ── 2. 从数据库获取所有演员（无头像过滤，最小化数据传输） ──
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT code, actors FROM movies
        WHERE actors IS NOT NULL AND actors != '[]' AND actors != ''
    """)
    rows = cursor.fetchall()

    actor_count = {}
    for code, actors_str in rows:
        try:
            actors = json.loads(actors_str)
            for raw_name in actors:
                name = _clean_actor_name(raw_name)
                if name:
                    actor_count[name] = actor_count.get(name, 0) + 1
        except Exception:
            pass
    conn.close()

    # ── 3. 过滤无头像演员 ──
    no_avatar_actors = [(name, cnt) for name, cnt in actor_count.items() if not _has_avatar(name)]
    total = len(no_avatar_actors)
    no_avatar_actors.sort(key=lambda x: -x[1])  # 按出现次数降序

    # ── 4. 分页（page_size=None 时返回全部） ──
    if page_size is not None:
        offset = (page - 1) * page_size
        page_actors = no_avatar_actors[offset:offset + page_size]
    else:
        page_actors = no_avatar_actors
    items = [
        {"name": name, "count": cnt, "has_avatar": False, "local_url": _local_url(name)}
        for name, cnt in page_actors
    ]
    return total, items


def get_series_stats(page: int = 1, page_size: int = 48, keyword: str = None) -> tuple:
    """
    获取番号系列统计列表（按影片数量降序）
    返回: (total, items=[{prefix, count}])
    """
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT code FROM movies
        WHERE code IS NOT NULL AND code != ''
    """)
    rows = cursor.fetchall()

    prefixes = {}
    for (code,) in rows:
        if code and '-' in code:
            # 特殊番号处理
            if code.startswith("FC2-PPV-"):
                prefix = "FC2-PPV"
            elif code.startswith("HEYDOUGA-"):
                prefix = "HEYDOUGA"
            elif code.startswith("WEBIP-"):
                prefix = "WEBIP"
            elif code.startswith("ABC-"):
                prefix = "ABC"
            elif code.startswith("1080P-"):
                prefix = "1080P"
            elif code.startswith("390JNT-"):
                prefix = "JNT"
            else:
                parts = code.split("-")
                prefix = parts[0] if parts else code
            prefixes[prefix] = prefixes.get(prefix, 0) + 1
        else:
            prefixes["OTHER"] = prefixes.get("OTHER", 0) + 1

    # 过滤关键词
    if keyword:
        filtered = {k: v for k, v in prefixes.items() if keyword.upper() in k.upper()}
    else:
        filtered = prefixes

    total = len(filtered)
    sorted_series = sorted(filtered.items(), key=lambda x: -x[1])

    # 分页
    offset = (page - 1) * page_size
    page_series = sorted_series[offset:offset + page_size]

    items = [
        {"prefix": prefix, "count": cnt}
        for prefix, cnt in page_series
    ]

    conn.close()
    return total, items


def get_movies_by_actor(actor_name: str, page: int = 1, page_size: int = 48) -> tuple:
    """
    获取某女演员的所有影片
    返回: (total, items=[MovieResponse])
    """
    conn = get_db()
    cursor = conn.cursor()

    # 搜索包含该演员的影片
    cursor.execute("""
        SELECT m.*, lv.fanart_path, lv.poster_path, lv.thumb_path
        FROM movies m
        LEFT JOIN local_videos lv ON m.local_video_id = lv.id
        WHERE m.actors IS NOT NULL AND m.actors != '[]' AND m.actors != ''
        ORDER BY m.release_date DESC, m.id DESC
    """)
    rows = cursor.fetchall()

    matched = []
    for row in rows:
        try:
            actors = json.loads(row["actors"]) if isinstance(row["actors"], str) else row["actors"]
            if actor_name in actors:
                matched.append(dict(row))
        except:
            pass

    total = len(matched)

    # 分页
    offset = (page - 1) * page_size
    page_movies = matched[offset:offset + page_size]

    # 转换为 MovieResponse
    results = [row_to_movie_response(m) for m in page_movies]

    conn.close()
    return total, results


def get_movies_by_series(prefix: str, page: int = 1, page_size: int = 48) -> tuple:
    """
    获取某番号系列的所有影片
    返回: (total, items=[MovieResponse])
    """
    conn = get_db()
    cursor = conn.cursor()

    # 构建 prefix 匹配条件（处理特殊番号）
    if prefix == "FC2-PPV":
        code_pattern = "FC2-PPV-%"
    elif prefix == "HEYDOUGA":
        code_pattern = "HEYDOUGA-%"
    elif prefix == "WEBIP":
        code_pattern = "WEBIP-%"
    elif prefix == "ABC":
        code_pattern = "ABC-%"
    elif prefix == "1080P":
        code_pattern = "1080P-%"
    elif prefix == "JNT":
        code_pattern = "JNT-%"
    else:
        code_pattern = f"{prefix}-%"

    cursor.execute(f"""
        SELECT m.*, lv.fanart_path, lv.poster_path, lv.thumb_path
        FROM movies m
        LEFT JOIN local_videos lv ON m.local_video_id = lv.id
        WHERE m.code LIKE ?
        ORDER BY m.release_date DESC, m.id DESC
    """, (code_pattern,))

    rows = cursor.fetchall()

    total = len(rows)
    offset = (page - 1) * page_size
    page_rows = rows[offset:offset + page_size]
    results = [row_to_movie_response(dict(r)) for r in page_rows]

    conn.close()
    return total, results


# ========== 整理功能（Phase 0.5）============

def update_movie_organize_info(movie_id: int, subtitle_type: str, organized_path: str):
    """
    更新影片的整理信息（整理功能专用）
    - subtitle_type: none / chinese / english / bilingual
    - organized_path: 整理后的目标文件夹路径
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE movies
        SET subtitle_type = ?, organized_path = ?,
            last_organized_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (subtitle_type, organized_path, movie_id))
    conn.commit()
    conn.close()


def sync_local_video_after_organize(
    movie_id: int,
    new_video_path: str,
    new_code: str,
    new_name: str,
    new_extension: str
) -> int:
    """
    整理完成后，同步 local_videos 记录。

    整理（复制/移动）文件到 Jellyfin 目录后：
      - 如果已有该 movie_id 的 local_videos → 更新 path/code/name/extension
      - 如果没有 → 新建一条 local_videos
      - 同时更新 movies.source_type='jellyfin' 和 local_videos.is_jellyfin=1
      - 通过 new_video_path 查找对应 local_sources 的 source_id 来设置 is_jellyfin

    这样 Jellyfin 扫描时不会再重复创建记录。

    返回: local_videos id
    """
    import os as _os
    conn = get_db()
    cursor = conn.cursor()
    new_code_norm = normalize_code(new_code)
    new_dir = _os.path.dirname(new_video_path)

    # 查找 new_video_path 对应的 source_id（Jellyfin 目录）
    cursor.execute(
        "SELECT id, is_jellyfin FROM local_sources WHERE path = ?",
        (new_dir,)
    )
    src_row = cursor.fetchone()
    if src_row:
        new_source_id = src_row['id']
        new_is_jellyfin = src_row['is_jellyfin']
    else:
        new_source_id = None
        new_is_jellyfin = 0

    cursor.execute(
        "SELECT id FROM local_videos WHERE movie_id = ? LIMIT 1",
        (movie_id,)
    )
    existing_any = cursor.fetchone()

    if existing_any:
        # 已有记录 → 更新路径和 is_jellyfin
        cursor.execute("""
            UPDATE local_videos
            SET path = ?, code = ?, name = ?, extension = ?,
                source_id = ?, is_jellyfin = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (new_video_path, new_code_norm, new_name, new_extension,
              new_source_id, new_is_jellyfin, existing_any['id']))
        vid_id = existing_any['id']
    else:
        # 真没有任何记录 → 新建
        cursor.execute("""
            INSERT INTO local_videos
            (code, name, path, extension, movie_id, scraped, source_id, is_jellyfin)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?)
        """, (new_code_norm, new_name, new_video_path, new_extension,
              movie_id, new_source_id, new_is_jellyfin))
        vid_id = cursor.lastrowid

    # 同步 movies.source_type（如果整理到 Jellyfin 目录）
    if new_is_jellyfin:
        cursor.execute(
            "UPDATE movies SET source_type = 'jellyfin' WHERE id = ?",
            (movie_id,)
        )

    conn.commit()
    conn.close()
    return vid_id


def get_organized_movies_without_info() -> list:
    """
    获取已整理但缺少刮削信息的电影（organized_path 非空，但 title/actors 为空）
    用于批量刮削这些迁移后丢失信息的电影
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, code, title, title_jp, actors, organized_path
        FROM movies
        WHERE organized_path IS NOT NULL 
          AND organized_path != ''
          AND (title IS NULL OR title = ''
               OR title_jp IS NULL OR title_jp = ''
               OR actors IS NULL OR actors = '[]' OR actors = '')
        ORDER BY id DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    
    if rows:
        return [dict(row) for row in rows]
    return []


def get_movies_by_codes(codes: list) -> dict:
    """
    批量根据番号查询影片（整理功能扫描时使用）
    返回: { "IPZZ-792": {id, actors, title, ...}, ... }

    注意：传入的 code 会被标准化后查询（与 upsert_movie 存储格式对齐）。
    返回字典的 key 统一使用标准化格式（如 IPZZ-792 而非 IPZZ-00792）。
    """
    if not codes:
        return {}
    # 标准化后去重（防止同一标准化格式出现多次）
    normalized = {normalize_code(c): c for c in codes}  # normalized → original
    codes_to_query = list(normalized.keys())
    placeholders = ",".join(["?"] * len(codes_to_query))
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        f"SELECT * FROM movies WHERE code IN ({placeholders})",
        codes_to_query
    )
    rows = cursor.fetchall()
    conn.close()
    # 返回字典的 key 统一用标准化格式（与 _extract_code_from_filename 输出对齐）
    return {normalize_code(dict(r)["code"]): dict(r) for r in rows}

