"""
FastAPI 主入口
依赖库:
    - fastapi, uvicorn: Web 框架
    - beautifulsoup4 (bs4): HTML 解析
    - requests: HTTP 请求
    - python-dotenv: 环境变量管理
"""

from fastapi import FastAPI, HTTPException, Query, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from pathlib import Path
from typing import Optional, List
import logging
import threading
import re
import time
import asyncio
from hashlib import sha256
import secrets
from datetime import datetime, timedelta

from models import (
    MovieResponse, MovieListResponse,
    ScrapeRequest, ScrapeResponse,
    UserLogin, UserRegister, UserResponse, LoginResponse
)
from pydantic import BaseModel, Field
import database as db
import config as cfg

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
# AV 番号识别配置
# 参考来源: JavSP (https://github.com/Yuukiy/JavSP)
# ============================================================

# AV厂商前缀列表（常见番号前缀，2-6位字母）
# 语法: List[str] - 存储有效厂商前缀的列表
AV_PREFIXES = {
    # 主流厂商 (按字母排序)
    'ABC', 'ABP', 'ADN', 'ADV', 'AOP', 'ATK', 'AYU',
    'BDA', 'BDC', 'BIJN', 'BIN', 'BOD', 'BT', 'BXX',
    'CA', 'CE', 'CH', 'CJ', 'CK', 'CL', 'CWP',
    'DADDY', 'DAH', 'DARK', 'DB', 'DDT', 'DE', 'DESU', 'DISM', 'DK', 'DM', 'DOC', 'DPM', 'DRC', 'DRG', 'DT',
    'EBOD', 'EC', 'EDD', 'EES', 'EN', 'EVO',
    'F8', 'FC', 'FC2', 'FCH', 'FD', 'FGA', 'FGO', 'FK', 'FP', 'FPW', 'FR', 'FS', 'FW', 'FX',
    'GAS', 'GD', 'GE', 'GF', 'GH', 'GIH', 'GIN', 'GK', 'GM', 'GNP', 'GQ', 'GQR', 'GRE', 'GS', 'GTA', 'GTO', 'GUG', 'GVS',
    'HA', 'HAB', 'HAME', 'HB', 'HERR', 'HEYDOUGA', 'HF', 'HHP', 'HIKARI', 'HIT', 'HJ', 'HND', 'HNI', 'HN', 'HO', 'HQ', 'HR', 'HS', 'HV', 'HX',
    'I' , 'IBW', 'IES', 'IP', 'IPZZ', 'IU', 'IV', 'IWF',
    'JBD', 'JB', 'JB5', 'JBD', 'JBR', 'JBS', 'JC', 'JD', 'JE', 'JFH', 'JHS', 'JIS', 'JK', 'JKT', 'JMK', 'JN', 'JNT', 'JPD', 'JPI', 'JPS', 'JR', 'JS', 'JUL', 'JUMP', 'JUX', 'JW',
    'K', 'KA', 'KAM', 'KB', 'KD', 'KGI', 'KM', 'KN', 'KO', 'KOK', 'KRD', 'KTK', 'KT', 'KU', 'KW', 'KZ',
    'LA', 'LB', 'LD', 'LEC', 'LG', 'LK', 'LL', 'LUXU', 'LX',
    'MA', 'MAD', 'MCS', 'MDB', 'ME', 'MFE', 'MGM', 'MI', 'MID', 'MIM', 'MJ', 'MK', 'ML', 'MM', 'MMB', 'MPL', 'MS', 'MST', 'MTA', 'MUGEN', 'MV', 'MX', 'MZ',
    'N', 'NAM', 'NB', 'NCT', 'ND', 'NE', 'NEW', 'NFA', 'NG', 'NH', 'NI', 'NK', 'NM', 'NN', 'NP', 'NPM', 'NR', 'NS', 'NSPS', 'NST', 'NT', 'NTR', 'NTT', 'NUK', 'NUM',
    'OB', 'OBA', 'OL', 'ONE', 'OOO', 'OP', 'ORE', 'OU',
    'P', 'P10', 'PAPA', 'PAR', 'PCD', 'PD', 'PE', 'PH', 'PJ', 'PK', 'PL', 'PP', 'PPV', 'PP', 'PRESTIGE', 'PRED', 'PRIME', 'PU', 'PRED',
    'Q', 'QD', 'R', 'R18', 'RAC', 'RB', 'RCT', 'RD', 'REAL', 'RED', 'RE', 'RHEI', 'RHK', 'RID', 'RKI', 'RMC', 'RR', 'RS', 'RVS', 'RX',
    'S', 'S1', 'S2', 'S4U', 'SA', 'SACA', 'SAME', 'SAP', 'SAS', 'SC', 'SCO', 'SD', 'SDA', 'SDF', 'SDEN', 'SEN', 'SER', 'SF', 'SGA', 'SH', 'SHIN', 'SHK', 'SHL', 'SHP', 'SI', 'SIF', 'SKY', 'SL', 'SL', 'SMA', 'SMDB', 'SML', 'SNC', 'SNIS', 'SOE', 'SOG', 'SOP', 'SOW', 'SP', 'SS', 'SSA', 'SSD', 'SSK', 'ST', 'STAR', 'STD', 'STON', 'STS', 'ST', 'SUK', 'SW', 'SWAMP', 'SX',
    'TAK', 'TBL', 'TBS', 'TC', 'TCE', 'TD', 'TEA', 'TEN', 'TGG', 'TH', 'TIGER', 'TK', 'TM', 'TN', 'TO', 'TOGE', 'TOKYO', 'TOS', 'TP', 'TR', 'TS', 'TSU', 'TT', 'TURBO', 'TV', 'TW', 'TX',
    'U', 'UDA', 'UFO', 'UK', 'UME', 'UMEMOTO', 'UQ', 'URC', 'URF', 'USAGI', 'USO', 'UTSUWA',
    'V', 'VAG', 'VAL', 'VENU', 'VH', 'VHS', 'VOSS', 'VQ', 'VR', 'VS',
    'WA', 'WAD', 'WAT', 'WIFI', 'WK', 'WN', 'WR', 'WS',
    'X', 'XA', 'XGG', 'XI', 'XR', 'XS', 'XXX',
    'YAD', 'YEQ', 'YMDB', 'YML', 'YP', 'YR', 'YS',
    'Z', 'ZEX', 'ZUK', 'ZUZU'
}

# 需要排除的前缀模式（网站前缀、常见错误前缀）
# 语法: Set[str] - 存储需要排除的字符串
EXCLUDE_PREFIXES = {
    # 数字前缀（可能与番号混合，如 390JNT-114）
    '390', '123', '456', '789',
    # 视频格式前缀
    'HD', 'SD', 'UHD', '4K', '1080', '720', '2160',
    # 媒体类型前缀
    'WEB', 'BD', 'DVD', 'CD', 'VCD', 'BR', 'BluRay',
    # 平台前缀
    'MAC', 'PC', 'WIN', 'IOS', 'ANDROID',
    # 成人标签（有时会出现在标题中）
    'XXX', 'SEX', 'PORN', 'ADULT',
    # 常见词汇
    'HARD', 'SOFT', 'FREE', 'HOT', 'NEW', 'LATEST',
    # 试看/预览标识
    'TEST', 'DEMO', 'SAMPLE', 'PREVIEW', 'TRAILER', 'TEASER',
    # 无意义单词
    'THE', 'AND', 'FOR', 'WITH', 'FROM', 'THIS', 'THAT',
    # 压制组/版本标识
    'TS', 'TC', 'R3', 'CAM', 'HDRIP', 'BRRIP', 'BLURAY', 'DUBBED', 'SUBBED',
    # 特殊处理标识
    'UNCEN', 'CEN', 'DECENSOR', 'UNCENSOR', 'RAW', 'SUB', 'DUB',
    # 常见错误格式
    'OP', 'ED', 'OVA', 'EP', 'SP', 'CM', 'NC', 'PV',
    # 其他网站标识
    'RARBG', 'FTP', 'PTP', 'HDS', 'NTB', 'SPARKS', 'FLUX',
}

# 需要排除的前缀模式（正则表达式）
# 用于排除如 WEBIPZZ、HDABC 等混合前缀
# 语法: List[str] - 存储正则表达式字符串
EXCLUDE_PREFIX_PATTERNS = [
    r'^(WEB|BD|720|1080|4K)[A-Z]{2,6}-',  # WEBIPZZ, HDABC 等
    r'^[A-Z]{2,3}\d{2,4}[A-Z]{2,6}-',     # 类似 390JNT 的情况
]

# ============================================================
# 番号识别正则表达式
# ============================================================

# 提取番号的正则表达式
# 语法: re.compile(正则, 标志)
#   - r'...' : raw string，避免转义字符问题
#   - (...) : 捕获组，提取需要的部分
#   - [A-Z]{2,6} : 2-6位大写字母
#   - -\d{2,5} : 短横线 + 2-5位数字
CODE_PATTERN = re.compile(r'([A-Z]{2,6})-(\d{2,5})')

# FC2/HEYDOUGA 等特殊番号正则（包含连字符）
# 匹配 FC2-PPV-123456, HEYDOUGA-1234-567 等
# 语法: re.compile(正则, 标志) - re.IGNORECASE 不区分大小写
SPECIAL_CODE_PATTERNS = [
    re.compile(r'(FC2-PPV-\d{5,7})', re.IGNORECASE),  # FC2-PPV-123456
    re.compile(r'(HEYDOUGA-\d{4}-\d{3,5})', re.IGNORECASE),  # HEYDOUGA-1234-567
]

# 解析番号的正则（用于搜索）
# 语法: re.IGNORECASE 标志表示不区分大小写
PARSE_CODE_PATTERN = re.compile(r'^([A-Za-z]{2,6})-(\d{2,5})$', re.IGNORECASE)


def _is_valid_av_code(prefix: str, number: str, full_match: str = "", filename: str = "") -> bool:
    """
    验证是否是有效的 AV 番号
    
    参数:
        prefix (str): 番号前缀，如 "IPZZ"
        number (str): 番号数字，如 "792"
        full_match (str): 完整匹配字符串，如 "IPZZ-792"（用于模式检查）
        filename (str): 原始文件名（用于检查前缀前的字符）
    
    返回:
        bool: 是否是有效的 AV 番号
    
    逻辑:
        1. 前缀不能全为数字
        2. 前缀不能是排除前缀
        3. 数字部分长度 >= 2
        4. 前缀必须是已知的 AV 厂商前缀 OR 不包含排除模式
        5. 检查匹配前是否有排除前缀（如 WEB, HD, 1080 等）
    """
    prefix = prefix.upper()
    number = number.lstrip('0')  # 去掉前导零进行比较
    
    # 前缀不能全是数字
    if prefix.isdigit():
        return False
    
    # 检查排除列表（精确匹配）
    if prefix in EXCLUDE_PREFIXES:
        return False
    
    # 数字部分至少2位（去掉前导零后）
    if len(number) < 2:
        return False
    
    # 检查排除模式（如 WEBIPZZ, HDABC 等混合前缀）
    if any(re.match(pat, full_match.upper()) for pat in EXCLUDE_PREFIX_PATTERNS):
        return False
    
    # 检查匹配前缀前是否有排除前缀
    # 例如 "WEBIPZZ-792" 中，WEB 是排除前缀，应该排除
    if filename:
        pos = filename.upper().find(full_match.upper())
        if pos > 0:
            prefix_part = filename[:pos].upper()
            # 检查是否以排除前缀结尾
            for exclude in ['WEB', 'HD', 'BD', '720', '1080', '4K', 'UHD']:
                if prefix_part.endswith(exclude):
                    return False
            # 检查是否以数字+字母组合结尾（如 390JNT 中的 390）
            mixed_prefix = re.search(r'(\d{2,4})[A-Z]{2,6}$', prefix_part)
            if mixed_prefix:
                return False
    
    # 前缀必须在已知厂商列表中 OR 不能是混合前缀
    # 排除明显不合理的字母组合
    # 如果前缀包含常见排除词的一部分（如 WEB, HD, BD, 720, 1080），则排除
    for exclude in ['WEB', 'HD', 'BD', '720', '1080', '4K', 'UHD', 'SD', 'HD']:
        if prefix.startswith(exclude) or prefix.endswith(exclude):
            # 但如果整个前缀就是排除词本身，可以接受（如 HD 本身）
            if prefix != exclude:
                return False
    
    # 排除以数字开头的组合（如 123ABC）
    if re.match(r'^\d', prefix):
        return False
    
    # 排除太短的前缀（除非是有效的单字母前缀）
    if len(prefix) < 2:
        return False
    
    return True


def _extract_code_from_filename(filename: str) -> Optional[str]:
    """
    从文件名中提取 AV 番号
    
    参数:
        filename (str): 文件名（不含扩展名）
    
    返回:
        str 或 None: 提取的番号，如 "JNT-114"，无效返回 None
    
    逻辑:
        1. 先检查特殊番号模式（FC2-PPV, HEYDOUGA 等）
        2. 再在文件名中搜索所有匹配正则的片段
        3. 逐一验证是否有效
        4. 返回第一个有效番号，或 None
    
    示例:
        "FC2-PPV-123456.mp4" -> "FC2-PPV-123456"
        "390JNT-114.mp4" -> "JNT-114"
        "WEBIPZZ-792.mp4" -> None (因为 WEBIPZZ 是无效前缀)
        "1080P XYZ-999.mp4" -> "XYZ-999" (有空格分隔，不是混合前缀)
        "IPZZ-792.mp4" -> "IPZZ-792"
    """
    # 1. 先检查特殊番号模式（FC2-PPV, HEYDOUGA 等）
    for pattern in SPECIAL_CODE_PATTERNS:
        match = pattern.search(filename.upper())
        if match:
            return match.group(1)
    
    # 排除前缀列表（用于检测混合前缀）
    MIXED_PREFIXES = ['WEB', 'HD', 'BD', '720', '1080', '4K', 'UHD', 'SD']
    
    # 2. 查找所有可能的番号（使用 finditer 获取位置信息）
    # 语法: re.finditer(正则, 字符串) - 返回所有匹配的位置迭代器
    for match in CODE_PATTERN.finditer(filename.upper()):
        prefix, number = match.groups()
        full_match = match.group(0)  # 完整匹配，如 "EBIPZZ-792"
        
        # 关键检查：如果匹配前面有排除前缀（如 WEB, HD, 1080），则跳过
        # 找到 full_match 在原始文件名中的位置
        orig_upper = filename.upper()
        match_upper = full_match.upper()
        pos = orig_upper.find(match_upper)
        
        if pos > 0:
            # 获取匹配前的字符
            before_match = orig_upper[:pos]
            
            # 如果前面有分隔符（空格、下划线、点），则不是混合前缀
            # 例如 "1080P XYZ-999" 中 "1080P " 和 "XYZ" 之间有空格
            if before_match[-1] in [' ', '_', '.', '-']:
                # 有分隔符，继续验证
                pass
            else:
                # 没有分隔符，检查是否是混合前缀
                # 对于 WEBIPZZ-792，before_match = 'W'，prefix = 'EBIPZZ'
                # combined = 'WEBIPZZ'
                combined = before_match + prefix
                skip = False
                for exclude in MIXED_PREFIXES:
                    # 检查 combined 是否以排除前缀开头
                    if combined.startswith(exclude):
                        skip = True
                        break
                if skip:
                    continue
        
        # 验证是否有效（传入完整文件名用于检查前缀）
        if _is_valid_av_code(prefix, number, full_match, filename):
            # 标准化输出：去掉数字部分的前导零
            normalized_number = str(int(number))
            return f"{prefix}-{normalized_number}"
    
    return None


# 初始化数据库
db.init_all_tables()

# 创建 FastAPI 应用
app = FastAPI(
    title="MyMovieDB API",
    description="本地影视库刮削器 API",
    version="1.0.0"
)

# 配置 CORS（允许前端访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if cfg.CORS_ORIGINS == "*" else [cfg.CORS_ORIGINS],
    allow_credentials=cfg.CORS_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件目录（封面图）
cfg.DATA_DIR.mkdir(parents=True, exist_ok=True)
cfg.COVERS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/covers", StaticFiles(directory=str(cfg.COVERS_DIR)), name="covers")

# 挂载前端目录到根路径（必须在所有路由之后挂载）
# 注意：静态文件挂载会在最后执行


# ========== 认证相关 API ==========

# 简单的 token 存储（生产环境应使用 Redis）
active_tokens = {}

def verify_token(token: str) -> dict:
    """验证 token 并返回用户信息"""
    if not token or token not in active_tokens:
        raise HTTPException(status_code=401, detail="未登录或 token 已过期")
    
    user_data = active_tokens[token]
    # 检查 token 是否过期（24小时）
    if datetime.now() - user_data['created_at'] > timedelta(hours=24):
        del active_tokens[token]
        raise HTTPException(status_code=401, detail="token 已过期，请重新登录")
    
    return user_data['user']


def get_current_user(token: str = Query(None, alias="token")):
    """FastAPI 依赖项：获取当前登录用户"""
    if not token:
        # 尝试从 header 获取
        from fastapi import Request
        raise HTTPException(status_code=401, detail="缺少 token")
    return verify_token(token)


@app.post("/auth/login", response_model=LoginResponse)
async def login(request: UserLogin):
    """用户登录"""
    conn = db.get_db()
    cursor = conn.cursor()
    
    # 查询用户
    password_hash = sha256(request.password.encode()).hexdigest()
    cursor.execute("""
        SELECT id, username, password_hash, role, email, created_at, last_login
        FROM users
        WHERE username = ? AND is_active = 1
    """, (request.username,))
    
    row = cursor.fetchone()
    if not row or row['password_hash'] != password_hash:
        conn.close()
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    
    # 生成 token
    token = secrets.token_urlsafe(32)
    user_data = {
        'id': row['id'],
        'username': row['username'],
        'role': row['role'],
        'email': row['email'],
        'created_at': row['created_at'],
        'last_login': row['last_login']
    }
    
    active_tokens[token] = {
        'user': user_data,
        'created_at': datetime.now()
    }
    
    # 更新最后登录时间
    cursor.execute("""
        UPDATE users SET last_login = ? WHERE id = ?
    """, (datetime.now().isoformat(), row['id']))
    conn.commit()
    conn.close()
    
    return {
        'token': token,
        'user': user_data
    }


@app.post("/auth/register")
async def register(request: UserRegister):
    """用户注册（默认为 guest 角色）"""
    conn = db.get_db()
    cursor = conn.cursor()
    
    # 检查用户名是否已存在
    cursor.execute("SELECT id FROM users WHERE username = ?", (request.username,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="用户名已存在")
    
    # 创建用户
    password_hash = sha256(request.password.encode()).hexdigest()
    cursor.execute("""
        INSERT INTO users (username, password_hash, email, role, is_active)
        VALUES (?, ?, ?, 'guest', 1)
    """, (request.username, password_hash, request.email))
    
    conn.commit()
    conn.close()
    
    return {"success": True, "message": "注册成功"}


@app.get("/auth/me")
async def get_current_user_info(token: str = Query(None)):
    """获取当前用户信息"""
    user = get_current_user(token)
    return user


@app.post("/auth/logout")
async def logout(token: str = Query(None)):
    """用户登出"""
    if token and token in active_tokens:
        del active_tokens[token]
    return {"success": True, "message": "已登出"}


# ========== 管理员 API ==========

class UserUpdateRequest(BaseModel):
    role: Optional[str] = Field(None, description="用户角色")
    is_active: Optional[int] = Field(None, description="是否激活")


@app.get("/admin/users")
async def get_all_users(token: str = Query(None)):
    """获取所有用户列表（仅管理员）"""
    user = get_current_user(token)
    if user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="权限不足")
    
    conn = db.get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, username, email, role, is_active, created_at, last_login
        FROM users
        ORDER BY created_at DESC
    """)
    
    users = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return {"users": users}


@app.put("/admin/users/{user_id}")
async def update_user(user_id: int, request: UserUpdateRequest, token: str = Query(None)):
    """更新用户信息（仅管理员）"""
    user = get_current_user(token)
    if user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="权限不足")
    
    conn = db.get_db()
    cursor = conn.cursor()
    
    # 检查用户是否存在
    cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 更新用户信息
    updates = []
    params = []
    if request.role is not None:
        updates.append("role = ?")
        params.append(request.role)
    if request.is_active is not None:
        updates.append("is_active = ?")
        params.append(request.is_active)
    
    if updates:
        params.append(user_id)
        cursor.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
    
    conn.close()
    
    return {"success": True, "message": "更新成功"}


@app.delete("/admin/users/{user_id}")
async def delete_user(user_id: int, token: str = Query(None)):
    """删除用户（仅管理员）"""
    user = get_current_user(token)
    if user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="权限不足")
    
    conn = db.get_db()
    cursor = conn.cursor()
    
    # 不能删除自己
    if user_id == user['id']:
        conn.close()
        raise HTTPException(status_code=400, detail="不能删除自己的账户")
    
    # 检查用户是否存在
    cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="用户不存在")
    
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    
    return {"success": True, "message": "删除成功"}


# ========== 前端页面路由 ==========




@app.get("/movies", response_model=MovieListResponse)
async def get_movies(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量")
):
    """获取影片列表"""
    total, movies = db.get_all_movies(page, page_size)

    items = []
    errors = []
    for movie in movies:
        try:
            movie = db.row_to_movie_response(movie)
            items.append(MovieResponse(**movie))
        except Exception as e:
            errors.append((movie.get('id'), movie.get('code'), str(e)[:80]))

    # 如果有失败项，记录但不阻断响应
    if errors:
        import logging
        logging.warning(f"[get_movies] {len(errors)} 条记录转换失败: {errors}")

    return MovieListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items
    )


@app.get("/movies/{movie_id}", response_model=MovieResponse)
async def get_movie(movie_id: int):
    """获取单个影片详情"""
    movie = db.get_movie_by_id(movie_id)

    if not movie:
        raise HTTPException(status_code=404, detail="影片不存在")

    movie = db.row_to_movie_response(movie)
    try:
        return MovieResponse(**movie)
    except Exception as e:
        logging.error(f"[get_movie] Pydantic 验证失败 id={movie_id}: {e}")
        raise HTTPException(status_code=500, detail=f"影片数据格式错误 (id={movie_id}): {str(e)[:100]}")


@app.get("/movies/code/{code}", response_model=MovieResponse)
async def get_movie_by_code(code: str):
    """根据编号获取影片"""
    movie = db.get_movie_by_code(code)

    if not movie:
        raise HTTPException(status_code=404, detail="影片不存在")

    movie = db.row_to_movie_response(movie)
    try:
        return MovieResponse(**movie)
    except Exception as e:
        logging.error(f"[get_movie_by_code] Pydantic 验证失败 code={code}: {e}")
        raise HTTPException(status_code=500, detail=f"影片数据格式错误 ({code}): {str(e)[:100]}")



@app.get("/open-folder")
async def open_folder(path: str = Query(..., description="要打开的文件夹路径")):
    """打开本地文件夹（Windows 资源管理器）"""
    import subprocess
    import os

    # 安全检查：路径必须存在于本地视频库或已注册目录下
    is_allowed = False

    # 1. 精确匹配本地视频库中的文件路径
    conn = db.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT path FROM local_videos WHERE path = ?", (path,))
    if cursor.fetchone():
        is_allowed = True

    # 2. 检查是否在已注册目录下
    if not is_allowed:
        sources = db.get_all_sources()
        norm_path = os.path.normpath(path)
        for s in sources:
            if s.get("path") and norm_path.startswith(os.path.normpath(s["path"])):
                is_allowed = True
                break

    # 3. 检查是否是某条本地视频记录所在目录
    if not is_allowed:
        folder = os.path.normpath(os.path.dirname(path))
        cursor.execute("SELECT DISTINCT path FROM local_videos", ())
        for row in cursor.fetchall():
            existing_folder = os.path.normpath(os.path.dirname(row[0]))
            if folder == existing_folder:
                is_allowed = True
                break

    conn.close()

    if not is_allowed:
        raise HTTPException(status_code=403, detail="路径不在允许访问的范围内")

    # 打开文件夹
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="路径不存在")

    try:
        folder = os.path.dirname(path) if os.path.isfile(path) else path
        subprocess.Popen(f'explorer "{folder}"')
        return {"success": True, "message": f"已打开文件夹: {folder}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"打开失败: {str(e)}")


@app.get("/play-video")
async def play_video(path: str = Query(..., description="要播放的视频文件路径")):
    """用迅雷播放器打开本地视频"""
    import subprocess
    import os

    # 安全检查（与 open-folder 相同）
    is_allowed = False
    conn = db.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT path FROM local_videos WHERE path = ?", (path,))
    if cursor.fetchone():
        is_allowed = True

    if not is_allowed:
        sources = db.get_all_sources()
        norm_path = os.path.normpath(path)
        for s in sources:
            if s.get("path") and norm_path.startswith(os.path.normpath(s["path"])):
                is_allowed = True
                break

    conn.close()

    if not is_allowed:
        raise HTTPException(status_code=403, detail="路径不在允许访问的范围内")

    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="文件不存在")

    try:
        # 迅雷播放器桌面快捷方式路径
        xmp_path = r"C:\Program Files (x86)\Thunder Network\Xmp\program\xmp.exe"
        
        if os.path.exists(xmp_path):
            # 使用迅雷播放器桌面图标方式启动
            subprocess.Popen([xmp_path, "-StartType:DesktopIcon", path])
            return {"success": True, "message": "正在用迅雷播放器打开"}
        else:
            # 回退：用系统默认程序打开
            os.startfile(path)
            return {"success": True, "message": "迅雷播放器未安装，已用默认程序打开"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"播放失败: {str(e)}")


@app.get("/search")
async def search_movies(
    q: str = Query(..., description="搜索关键词"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量")
):
    """搜索影片"""
    total, movies = db.search_movies(q, page, page_size)

    items = []
    for movie in movies:
        try:
            movie = db.row_to_movie_response(movie)
            items.append(MovieResponse(**movie))
        except Exception as e:
            logging.warning(f"[search] 记录转换失败 id={movie.get('id')}: {str(e)[:60]}")

    return MovieListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items
    )


@app.post("/scrape", response_model=ScrapeResponse)
async def scrape_movie_endpoint(request: ScrapeRequest):
    """刮削影片信息（智能合并）"""
    from scraper import scrape_movie, save_movie_assets

    try:
        # 调用爬虫
        movie_data = scrape_movie(request.keyword, request.save_cover)

        if not movie_data:
            return ScrapeResponse(
                success=False,
                message=f"未找到影片: {request.keyword}"
            )

        # 检查本地库是否有该番号的视频
        local_video = db.get_local_video_by_code(request.keyword.strip())
        local_video_path = local_video["path"] if local_video else None

        # 统一后处理：下载封面 + 生成 NFO
        if request.save_cover:
            covers_dir = Path(cfg.COVERS_DIR)
            covers_dir.mkdir(parents=True, exist_ok=True)
            movie_data = save_movie_assets(movie_data, covers_dir, local_video_path)

        if local_video:
            movie_data["local_video_id"] = local_video["id"]

        # 使用 upsert：存在则智能合并，不存在则创建
        movie_id, is_new = db.upsert_movie(movie_data)

        # 如果本地库有关联，同步更新本地视频记录
        if local_video:
            db.mark_video_scraped(local_video["id"], movie_id)
            db.link_movie_to_local_video(movie_id, local_video["id"])
        else:
            # 即使前端没有指定本地视频，也尝试自动匹配
            auto_match = db.get_local_video_by_code(request.keyword.strip())
            if auto_match:
                db.mark_video_scraped(auto_match["id"], movie_id)
                db.link_movie_to_local_video(movie_id, auto_match["id"])
                local_video = auto_match

        movie = db.get_movie_by_id(movie_id)
        movie = db.row_to_movie_response(movie)

        if is_new:
            message = "刮削成功，新建记录"
        else:
            message = "影片已存在，智能更新完成"

        if local_video:
            message += f"（已关联本地: {local_video['name']}）"

        return ScrapeResponse(
            success=True,
            message=message,
            movie=MovieResponse(**movie)
        )

    except Exception as e:
        logger.error(f"刮削失败: {e}")
        return ScrapeResponse(
            success=False,
            message=f"刮削失败: {str(e)}"
        )


@app.delete("/movies/{movie_id}")
async def delete_movie(movie_id: int):
    """删除影片"""
    success = db.delete_movie(movie_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="影片不存在")
    
    return {"message": "删除成功"}


# ========== 本地视频源管理 API ==========

# 全局刮削停止标志（job_id -> stop_event）
_scrape_stop_flags: dict = {}
_scrape_lock = threading.Lock()


class LocalSourceCreate(BaseModel):
    path: str = Field(..., description="目录路径")
    name: Optional[str] = Field(None, description="显示名称")


class LocalVideoListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[dict]


# 番号解析正则：严格匹配 2-6位字母-2-5位数字
_PARSE_CODE_PATTERN = re.compile(r'^([A-Za-z]{2,6})-(\d{2,5})$', re.IGNORECASE)


def _parse_codes(raw: str) -> list:
    """
    解析输入文本，返回有效番号列表（去重，保持顺序）
    
    参数:
        raw (str): 原始输入文本，可能包含多个番号（逗号/空格/换行/分号分隔）
    
    返回:
        list: 有效番号列表，如 ["IPZZ-792", "GQN-011"]
    
    依赖:
        - re.split(): 按分隔符分割字符串
        - _parse_code(): 验证番号有效性
    """
    raw = raw.strip()
    if not raw:
        return []
    # 支持逗号、空格、换行、分号、中英文逗号
    # 语法: re.split(正则, 字符串) - 按正则分割字符串
    parts = re.split(r'[,，\s\n;；]+', raw)
    seen = set()
    codes = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        # 尝试直接作为番号使用（严格验证）
        # 语法: re.match(正则, 字符串) - 从字符串开头匹配
        m = _PARSE_CODE_PATTERN.match(p.upper())
        if m:
            prefix, number = m.groups()
            # 使用验证函数检查是否有效
            if _is_valid_av_code(prefix, number):
                code = f"{prefix}-{number}"
                if code not in seen:
                    seen.add(code)
                    codes.append(code)
    return codes


def _send_sse(data: dict) -> str:
    """生成 SSE data 行"""
    import json
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/scrape/batch", tags=["刮削"])
async def scrape_batch(req: ScrapeRequest):
    """
    批量刮削接口（支持 SSE 实时进度）
    请求体: { "keyword": "ABC-123, XYZ-456\nDEF-789", "save_cover": true }
    keyword 支持多番号，用逗号/空格/换行/分号分隔
    """
    from scraper import scrape_movie, set_stop_check
    import uuid

    job_id = str(uuid.uuid4())[:8]
    stop_event = threading.Event()
    with _scrape_lock:
        _scrape_stop_flags[job_id] = stop_event

    # 设置停止检查回调
    set_stop_check(lambda: stop_event.is_set())

    codes = _parse_codes(req.keyword)
    if not codes:
        with _scrape_lock:
            _scrape_stop_flags.pop(job_id, None)
        return {"success": False, "message": "未识别到有效番号"}

    total = len(codes)

    def generate():
        success_count = 0
        fail_count = 0
        local_link_count = 0
        skipped_count = 0

        for i, code in enumerate(codes):
            # 检查停止标志
            if stop_event.is_set():
                yield _send_sse({
                    "type": "stopped",
                    "code": code,
                    "index": i + 1,
                    "total": total,
                    "message": "用户停止了刮削"
                })
                break

            # 发送当前处理信息
            yield _send_sse({
                "type": "scraping",
                "job_id": job_id,
                "code": code,
                "title": f"正在刮削 {code} ({i+1}/{total})...",
                "index": i + 1,
                "total": total,
                "pct": int((i / total) * 100)
            })

            # 检查是否已有完整削刮记录
            existing = db.get_movie_by_code(code)
            
            # 跳过 Jellyfin 来源的影片
            if existing and existing.get("source") == "jellyfin":
                skipped_count += 1
                yield _send_sse({
                    "type": "skipped",
                    "job_id": job_id,
                    "code": code,
                    "title": existing.get("title", ""),
                    "message": "📁 Jellyfin 导入，跳过刮削",
                    "index": i + 1,
                    "total": total,
                    "pct": int(((i + 1) / total) * 100)
                })
                continue
            
            if existing and existing.get("scrape_status") == "complete":
                # 即使跳过刮削，也要检查是否需要关联本地视频
                if local_video_id and not existing.get("local_video_id"):
                    db.mark_video_scraped(local_video_id, existing["id"])
                    db.link_movie_to_local_video(existing["id"], local_video_id)
                    local_link_count += 1
                skipped_count += 1
                yield _send_sse({
                    "type": "skipped",
                    "job_id": job_id,
                    "code": code,
                    "title": existing.get("title", ""),
                    "message": "已有完整削刮记录，跳过",
                    "index": i + 1,
                    "total": total,
                    "pct": int(((i + 1) / total) * 100)
                })
                continue

            # 检查本地库是否有该番号的视频
            local_video = db.get_local_video_by_code(code)
            local_video_id = local_video["id"] if local_video else None
            local_path = local_video.get("path") if local_video else None

            try:
                movie_data = scrape_movie(code, req.save_cover)
                if movie_data:
                    # 注入本地视频关联
                    if local_video_id:
                        movie_data["local_video_id"] = local_video_id

                    # 统一后处理：下载封面 + 生成 NFO
                    if req.save_cover:
                        from scraper import save_movie_assets
                        covers_dir = Path(cfg.COVERS_DIR)
                        covers_dir.mkdir(parents=True, exist_ok=True)
                        movie_data = save_movie_assets(movie_data, covers_dir, local_path)

                    movie_id, is_new = db.upsert_movie(movie_data)
                    # 标记本地视频已刮削
                    if local_video_id:
                        db.mark_video_scraped(local_video_id, movie_id)
                        local_link_count += 1

                    yield _send_sse({
                        "type": "success",
                        "job_id": job_id,
                        "code": code,
                        "title": movie_data.get("title", ""),
                        "local_path": local_path,
                        "is_new": is_new,
                        "index": i + 1,
                        "total": total,
                        "pct": int(((i + 1) / total) * 100)
                    })
                    success_count += 1
                else:
                    yield _send_sse({
                        "type": "fail",
                        "job_id": job_id,
                        "code": code,
                        "message": "未找到影片信息",
                        "index": i + 1,
                        "total": total,
                        "pct": int(((i + 1) / total) * 100)
                    })
                    fail_count += 1

            except Exception as e:
                logger.error(f"刮削 {code} 失败: {e}")
                yield _send_sse({
                    "type": "error",
                    "job_id": job_id,
                    "code": code,
                    "message": str(e)[:100],
                    "index": i + 1,
                    "total": total,
                    "pct": int(((i + 1) / total) * 100)
                })
                fail_count += 1

            # 请求间隔
            time.sleep(0.5)

        # 完成
        yield _send_sse({
            "type": "done",
            "job_id": job_id,
            "processed": success_count + fail_count + skipped_count,
            "success_count": success_count,
            "fail_count": fail_count,
            "skipped_count": skipped_count,
            "local_link_count": local_link_count,
            "total": total
        })

        # 清理
        with _scrape_lock:
            _scrape_stop_flags.pop(job_id, None)

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no"
    }
    return StreamingResponse(generate(), media_type="text/event-stream", headers=headers)


@app.post("/scrape/stop", tags=["刮削"])
async def stop_scrape(req: dict = None):
    """停止指定 job_id 的刮削任务"""
    job_id = (req or {}).get("job_id") if req else None
    with _scrape_lock:
        if job_id and job_id in _scrape_stop_flags:
            _scrape_stop_flags[job_id].set()
            return {"success": True, "message": f"已发送停止信号: {job_id}"}
        elif job_id:
            return {"success": False, "message": f"任务不存在: {job_id}"}
        else:
            # 停止所有任务
            for ev in _scrape_stop_flags.values():
                ev.set()
            return {"success": True, "message": "已停止所有刮削任务"}


@app.post("/local-sources", tags=["本地视频"])
async def add_local_source(req: LocalSourceCreate):
    """添加本地视频源目录"""
    import os
    path = req.path.strip().rstrip('\\').rstrip('/')

    # 验证路径是否存在
    if not os.path.isdir(path):
        raise HTTPException(status_code=400, detail=f"路径不存在或不是有效目录: {path}")

    source_id = db.create_local_source(path, req.name)
    if source_id is None:
        raise HTTPException(status_code=400, detail="该目录已添加")

    sources = db.get_local_sources()
    added = next((s for s in sources if s["id"] == source_id), None)
    return {"success": True, "source": added}


@app.get("/local-sources", tags=["本地视频"])
async def list_local_sources():
    """获取所有本地视频源（包含 Jellyfin 标记）"""
    sources = db.get_local_sources_with_jellyfin()
    stats = db.get_local_video_stats()
    return {"sources": sources, "stats": stats}


@app.delete("/local-sources/{source_id}", tags=["本地视频"])
async def remove_local_source(source_id: int):
    """删除本地视频源"""
    success = db.delete_local_source(source_id)
    if not success:
        raise HTTPException(status_code=404, detail="视频源不存在")
    return {"success": True, "message": "已删除"}


def _find_image_path(directory: str, code: str, image_type: str) -> Optional[str]:
    """
    在指定目录查找 {code}-{type}.jpg 图片文件
    例如: SSIS-254-fanart.jpg, ABP-875-poster.jpg
    """
    import os
    filename = f"{code}-{image_type}.jpg"
    path = os.path.join(directory, filename)
    return path if os.path.isfile(path) else None


@app.post("/local-sources/scan", tags=["本地视频"])
async def scan_local_sources():
    """
    扫描所有已添加的目录，查找视频文件（SSE 实时进度）
    
    功能:
        - 遍历每个已添加的视频源目录（递归所有子文件夹）
        - 识别有效 AV 番号的视频文件
        - 排除非 AV 文件（如普通电影、综艺节目等）
        - 排除网站前缀干扰（如 390JNT-114 -> JNT-114）
        - 实时推送扫描进度（目录数、文件数、当前文件名）
    
    返回:
        SSE 流: 实时扫描进度
    """
    import os
    import time
    
    def _send_sse(data: dict):
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
    
    def generate():
        VIDEO_EXTENSIONS = {
            '.mp4', '.mkv', '.avi', '.wmv', '.mov',
            '.flv', '.webm', '.m4v', '.mpg', '.mpeg',
            '.ts', '.mts', '.m2ts', '.vob', '.ogv'
        }
        
        sources = db.get_local_sources()
        if not sources:
            yield _send_sse({"type": "error", "message": "请先添加视频目录"})
            return
        
        # 扫描前清理无效记录
        db.cleanup_invalid_codes()
        
        total_sources = len(sources)
        total_found = 0
        scan_results = []
        
        # 阶段1: 开始扫描
        yield _send_sse({
            "type": "start",
            "total_sources": total_sources,
            "message": f"开始扫描 {total_sources} 个目录..."
        })
        
        for s_idx, source in enumerate(sources, 1):
            source_id = source["id"]
            base_path = source["path"]
            found_count = 0
            
            # 阶段2: 扫描目录
            yield _send_sse({
                "type": "source_start",
                "source_index": s_idx,
                "total_sources": total_sources,
                "path": base_path,
                "message": f"[{s_idx}/{total_sources}] 扫描: {base_path}"
            })
            
            if not os.path.isdir(base_path):
                scan_results.append({"source_id": source_id, "path": base_path, "status": "目录不存在", "count": 0})
                yield _send_sse({
                    "type": "source_done",
                    "source_index": s_idx,
                    "total_sources": total_sources,
                    "found": 0,
                    "status": "目录不存在"
                })
                continue
            
            # 先统计文件总数（用于进度百分比）
            file_count = 0
            try:
                for root, dirs, files in os.walk(base_path):
                    file_count += len([f for f in files if os.path.splitext(f)[1].lower() in VIDEO_EXTENSIONS])
            except PermissionError:
                scan_results.append({"source_id": source_id, "path": base_path, "status": "权限不足", "count": 0})
                yield _send_sse({
                    "type": "source_done",
                    "source_index": s_idx,
                    "total_sources": total_sources,
                    "found": 0,
                    "status": "权限不足"
                })
                continue
            
            # 阶段3: 扫描文件
            processed_files = 0
            try:
                for root, dirs, files in os.walk(base_path):
                    for filename in files:
                        ext = os.path.splitext(filename)[1].lower()
                        
                        if ext not in VIDEO_EXTENSIONS:
                            continue
                        
                        processed_files += 1
                        
                        # 提取番号
                        name_without_ext = os.path.splitext(filename)[0]
                        code = _extract_code_from_filename(name_without_ext)
                        
                        # 每 10 个文件推送一次进度
                        if processed_files % 10 == 0 or processed_files == file_count:
                            yield _send_sse({
                                "type": "progress",
                                "source_index": s_idx,
                                "total_sources": total_sources,
                                "processed": processed_files,
                                "total_files": file_count,
                                "pct": int((processed_files / file_count) * 100) if file_count > 0 else 0,
                                "found": found_count,
                                "current_file": filename,
                                "message": f"[{s_idx}/{total_sources}] {processed_files}/{file_count} 文件 ({int((processed_files/file_count)*100)}%) - 已找到 {found_count} 个"
                            })
                        
                        if not code:
                            continue
                        
                        file_path = os.path.join(root, filename)
                        
                        try:
                            file_size = os.path.getsize(file_path)
                        except OSError:
                            file_size = 0
                        
                        video_data = {
                            "source_id": source_id,
                            "name": filename,
                            "path": file_path,
                            "code": code,
                            "extension": ext,
                            "file_size": file_size,
                            "fanart_path": _find_image_path(root, code, "fanart"),
                            "poster_path": _find_image_path(root, code, "poster"),
                            "thumb_path": _find_image_path(root, code, "thumb"),
                        }
                        
                        vid_id, is_new = db.upsert_local_video(video_data)
                        found_count += 1
                        total_found += 1
                        
            except PermissionError:
                scan_results.append({"source_id": source_id, "path": base_path, "status": "权限不足", "count": found_count})
                yield _send_sse({
                    "type": "source_done",
                    "source_index": s_idx,
                    "total_sources": total_sources,
                    "found": found_count,
                    "status": "权限不足"
                })
                continue
            
            # 更新源的视频数量
            db.update_local_source_scan(source_id, found_count)
            scan_results.append({"source_id": source_id, "path": base_path, "status": "完成", "count": found_count})
            
            yield _send_sse({
                "type": "source_done",
                "source_index": s_idx,
                "total_sources": total_sources,
                "found": found_count,
                "status": "完成",
                "message": f"[{s_idx}/{total_sources}] 完成 - 找到 {found_count} 个视频"
            })
        
        # 阶段4: 全部完成
        yield _send_sse({
            "type": "done",
            "total_found": total_found,
            "results": scan_results,
            "stats": db.get_local_video_stats()
        })
    
    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no"
    }
    return StreamingResponse(generate(), media_type="text/event-stream", headers=headers)


@app.post("/local-sources/scrape", tags=["本地视频"])
async def scrape_local_videos():
    """
    对扫描到的本地视频批量刮削（支持 SSE 实时进度）
    只刮削有编号的视频，返回 SSE 流
    """
    from scraper import scrape_movie, set_stop_check
    import uuid

    job_id = str(uuid.uuid4())[:8]
    stop_event = threading.Event()
    with _scrape_lock:
        _scrape_stop_flags[job_id] = stop_event

    # 设置停止检查回调
    set_stop_check(lambda: stop_event.is_set())

    unscraped = db.get_unscraped_local_videos()
    if not unscraped:
        with _scrape_lock:
            _scrape_stop_flags.pop(job_id, None)
        return {"success": True, "message": "没有需要刮削的视频", "processed": 0}

    total = len(unscraped)

    def generate():
        success_count = 0
        fail_count = 0
        skip_count = 0
        last_pct = -1  # 上次推送的百分比，用于减少重复推送

        for i, video in enumerate(unscraped):
            # 检查停止标志
            if stop_event.is_set():
                yield _send_sse({
                    "type": "stopped",
                    "job_id": job_id,
                    "code": video.get("code"),
                    "index": i + 1,
                    "total": total,
                    "message": "用户停止了刮削"
                })
                break

            code = video.get("code")
            video_id = video["id"]
            current_pct = int(((i + 1) / total) * 100)

            if not code:
                skip_count += 1
                # 只在百分比变化时推送
                if current_pct != last_pct:
                    yield _send_sse({
                        "type": "progress",
                        "job_id": job_id,
                        "index": i + 1,
                        "total": total,
                        "pct": current_pct,
                        "stats": {"success": success_count, "fail": fail_count, "skip": skip_count}
                    })
                    last_pct = current_pct
                continue

            # 检查是否已有完整刮削记录
            existing = db.get_movie_by_code(code)

            # 跳过 Jellyfin 来源的影片
            if existing and existing.get("source_type") == "jellyfin":
                skip_count += 1
                if current_pct != last_pct:
                    yield _send_sse({
                        "type": "progress",
                        "job_id": job_id,
                        "index": i + 1,
                        "total": total,
                        "pct": current_pct,
                        "stats": {"success": success_count, "fail": fail_count, "skip": skip_count}
                    })
                    last_pct = current_pct
                continue

            if existing and existing.get("scrape_status") == "complete":
                # 已完整刮削，跳过
                if video_id and not existing.get("local_video_id"):
                    db.mark_video_scraped(video_id, existing["id"])
                    db.link_movie_to_local_video(existing["id"], video_id)
                skip_count += 1
                if current_pct != last_pct:
                    yield _send_sse({
                        "type": "progress",
                        "job_id": job_id,
                        "index": i + 1,
                        "total": total,
                        "pct": current_pct,
                        "stats": {"success": success_count, "fail": fail_count, "skip": skip_count}
                    })
                    last_pct = current_pct
                continue

            # 发送当前处理信息（重要事件，总是推送）
            yield _send_sse({
                "type": "scraping",
                "job_id": job_id,
                "code": code,
                "title": f"正在刮削 {code}",
                "index": i + 1,
                "total": total,
                "pct": current_pct
            })

            try:
                movie_data = scrape_movie(code, save_cover=True)
                if not movie_data:
                    fail_count += 1
                    # 失败事件总是推送
                    yield _send_sse({
                        "type": "fail",
                        "job_id": job_id,
                        "code": code,
                        "message": "未找到",
                        "index": i + 1,
                        "total": total,
                        "pct": current_pct,
                        "stats": {"success": success_count, "fail": fail_count, "skip": skip_count}
                    })
                    last_pct = current_pct
                    continue

                # 统一后处理：下载封面 + 生成 NFO
                from scraper import save_movie_assets
                covers_dir = Path(cfg.COVERS_DIR)
                covers_dir.mkdir(parents=True, exist_ok=True)
                movie_data = save_movie_assets(movie_data, covers_dir, video.get("path"))

                # upsert 影片
                movie_id, is_new = db.upsert_movie(movie_data)
                # 关联本地视频
                db.mark_video_scraped(video_id, movie_id)
                db.link_movie_to_local_video(movie_id, video_id)
                success_count += 1

                # 成功事件总是推送
                yield _send_sse({
                    "type": "success",
                    "job_id": job_id,
                    "code": code,
                    "title": movie_data.get("title", ""),
                    "index": i + 1,
                    "total": total,
                    "pct": current_pct,
                    "stats": {"success": success_count, "fail": fail_count, "skip": skip_count}
                })
                last_pct = current_pct

                # 避免请求过快
                time.sleep(0.8)
                time.sleep(0.5)

            except Exception as e:
                logger.error(f"刮削 {code} 失败: {e}")
                fail_count += 1
                yield _send_sse({
                    "type": "error",
                    "job_id": job_id,
                    "code": code,
                    "message": str(e)[:100],
                    "index": i + 1,
                    "total": total,
                    "pct": int(((i + 1) / total) * 100)
                })

        # 发送完成消息
        yield _send_sse({
            "type": "done",
            "job_id": job_id,
            "processed": total,
            "success_count": success_count,
            "fail_count": fail_count,
            "skip_count": skip_count
        })

        # 清理停止标志
        with _scrape_lock:
            _scrape_stop_flags.pop(job_id, None)

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/local-videos", response_model=LocalVideoListResponse, tags=["本地视频"])
async def get_local_videos(
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    source_id: int = Query(None, description="按视频源筛选"),
    scraped: int = Query(None, description="刮削状态: 0=未刮, 1=已刮"),
    keyword: str = Query(None, description="搜索文件名或编号")
):
    """获取本地视频列表"""
    total, items = db.get_local_videos(
        page=page,
        page_size=page_size,
        source_id=source_id,
        scraped=scraped,
        keyword=keyword
    )

    return LocalVideoListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items
    )


@app.get("/local-videos/stats", tags=["本地视频"])
async def get_local_video_stats():
    """获取本地视频统计"""
    return db.get_local_video_stats()


@app.post("/local-videos/cleanup", tags=["本地视频"])
async def cleanup_invalid_local_videos():
    """
    清理本地视频库中的无效记录。
    使用与扫描相同的番号提取逻辑验证文件名，
    并检查文件是否在本地存在。
    删除：(1) 文件名无法提取有效番号的记录  (2) 文件本地不存在的记录
    """
    deleted_count, deleted_infos = db.cleanup_invalid_codes()
    return {
        "success": True,
        "deleted_count": deleted_count,
        "deleted_items": deleted_infos
    }


@app.delete("/local-videos/{video_id}", tags=["本地视频"])
async def delete_local_video(video_id: int):
    """删除本地视频记录"""
    success = db.delete_local_video(video_id)
    if not success:
        raise HTTPException(status_code=404, detail="视频不存在")
    return {"success": True}
async def get_cover(filename: str):
    """获取封面图"""
    cover_path = covers_dir / filename
    
    if not cover_path.exists():
        raise HTTPException(status_code=404, detail="封面不存在")
    
    return {"url": f"/covers/{filename}"}


# 批量重新生成所有 poster（从 fanart 右半边截取）
@app.post("/regenerate-posters", tags=["封面图"])
async def regenerate_all_posters():
    """
    从已有的 fanart 图片重新生成所有 poster 和 thumb
    poster 从 fanart 右半边中间截取（展示女演员全身照）
    """
    try:
        from PIL import Image
    except ImportError:
        raise HTTPException(status_code=500, detail="Pillow 未安装，无法处理图片")

    from scraper import regenerate_poster_from_fanart
    from pathlib import Path

    covers_base = Path(cfg.COVERS_DIR)
    if not covers_base.exists():
        return {"success": False, "message": "封面目录不存在"}

    regenerated = 0
    failed = 0

    # 遍历每个番号文件夹
    for code_dir in sorted(covers_base.iterdir()):
        if not code_dir.is_dir():
            continue

        fanart_file = None
        for f in code_dir.iterdir():
            if f.stem.endswith("-fanart") and f.suffix.lower() in (".jpg", ".jpeg", ".png"):
                fanart_file = f
                break

        if not fanart_file:
            continue

        poster_file = code_dir / f"{fanart_file.stem.replace('-fanart', '')}-poster.jpg"
        thumb_file = code_dir / f"{fanart_file.stem.replace('-fanart', '')}-thumb.jpg"

        try:
            ok = regenerate_poster_from_fanart(
                str(fanart_file),
                str(poster_file),
                str(thumb_file)
            )
            if ok:
                regenerated += 1
            else:
                failed += 1
        except Exception as e:
            logger.error(f"重新生成 poster 失败 {code_dir.name}: {e}")
            failed += 1

    return {
        "success": True,
        "regenerated": regenerated,
        "failed": failed,
        "message": f"重新生成 {regenerated} 个 poster，{failed} 个失败"
    }


# ============================================================
# 刮削结果检查和修复 API
# ============================================================

class ScrapeCheckResult(BaseModel):
    """单个影片的刮削检查结果"""
    movie_id: int
    code: str
    title: Optional[str] = None
    scrape_status: str
    issues: List[str] = []
    has_poster: bool = False
    has_fanart: bool = False
    has_thumb: bool = False
    has_nfo: bool = False


class ScrapeCheckResponse(BaseModel):
    """刮削检查结果响应"""
    total: int
    complete: int
    incomplete: int
    issues: List[ScrapeCheckResult]


@app.get("/scrape/check", tags=["刮削"], response_model=ScrapeCheckResponse)
async def check_scrape_results():
    """
    检查所有影片的刮削完整性

    检查项目：
    1. title（标题）
    2. release_date（发布日期）
    3. maker（制作商）
    4. actors（女演员）
    5. poster_path 文件存在
    6. fanart_path 文件存在
    7. NFO 文件存在
    """
    from pathlib import Path

    movies = db.get_all_movies_no_paging()
    covers_dir = Path(cfg.COVERS_DIR)

    result = ScrapeCheckResponse(total=len(movies), complete=0, incomplete=0, issues=[])

    for m in movies:
        issues = []
        movie_id = m.get("id")
        code = m.get("code", "")

        # 判断是否是 Jellyfin 来源
        source_type = m.get("source_type") or m.get("source")
        is_jellyfin = source_type == "jellyfin"

        # Jellyfin 视频不参与修复检查（它们有自己的元数据系统）
        if is_jellyfin:
            result.complete += 1
            continue

        # 检查必填字段
        if not m.get("title"):
            issues.append("缺少标题")
        if not m.get("release_date"):
            issues.append("缺少发布日期")
        if not m.get("maker"):
            issues.append("缺少制作商")
        if not m.get("actors"):
            issues.append("缺少女演员")

        # 检查封面文件
        has_poster = False
        has_fanart = False
        has_thumb = False
        has_nfo = False

        poster_path = m.get("poster_path")
        if poster_path:
            try:
                has_poster = Path(poster_path).exists()
                if not has_poster:
                    issues.append("poster 文件不存在")
            except:
                issues.append("poster 路径无效")

        fanart_path = m.get("fanart_path")
        if fanart_path:
            try:
                has_fanart = Path(fanart_path).exists()
                if not has_fanart:
                    issues.append("fanart 文件不存在")
            except:
                pass

        thumb_path = m.get("thumb_path")
        if thumb_path:
            try:
                has_thumb = Path(thumb_path).exists()
            except:
                pass

        # 检查 NFO 文件
        safe_code = re.sub(r'[<>:"/\\|?*]', '_', code)
        nfo_path = covers_dir / safe_code / f"{safe_code}.nfo"
        if nfo_path.exists():
            has_nfo = True
        else:
            issues.append("缺少 NFO 文件")

        # 计算状态
        scrape_status = m.get("scrape_status", "empty")

        item = ScrapeCheckResult(
            movie_id=movie_id,
            code=code,
            title=m.get("title"),
            scrape_status=scrape_status,
            issues=issues,
            has_poster=has_poster,
            has_fanart=has_fanart,
            has_thumb=has_thumb,
            has_nfo=has_nfo
        )

        if issues:
            result.incomplete += 1
            result.issues.append(item)
        else:
            result.complete += 1

    return result


class FixScrapeRequest(BaseModel):
    """修复刮削请求"""
    movie_ids: Optional[List[int]] = None  # 指定影片ID，为空则修复所有


class FixScrapeResult(BaseModel):
    """单个影片的修复结果"""
    movie_id: int
    code: str
    fixed: bool
    message: str


class FixScrapeResponse(BaseModel):
    """修复刮削响应"""
    total: int
    fixed: int
    failed: int
    results: List[FixScrapeResult]


@app.post("/scrape/fix", tags=["刮削"])
async def fix_scrape_results(request: FixScrapeRequest = None):
    """
    修复不完整的刮削结果（SSE 实时进度）

    修复操作：
    1. 重新刮削缺失元数据的影片
    2. 重新下载缺失的封面图片
    3. 重新生成 NFO 文件
    """
    from scraper import scrape_movie, save_movie_assets
    import uuid

    job_id = str(uuid.uuid4())[:8]
    
    # 注册停止事件
    stop_event = threading.Event()
    with _scrape_lock:
        _scrape_stop_flags[job_id] = stop_event

    covers_dir = Path(cfg.COVERS_DIR)
    covers_dir.mkdir(parents=True, exist_ok=True)

    # 获取需要修复的影片
    if request and request.movie_ids:
        movies = [db.get_movie_by_id(mid) for mid in request.movie_ids if db.get_movie_by_id(mid)]
    else:
        # 检查所有影片，筛选有问题的
        try:
            check_result = await check_scrape_results()
            movie_ids = [item.movie_id for item in check_result.issues]
            movies = [db.get_movie_by_id(mid) for mid in movie_ids if db.get_movie_by_id(mid)]
            logger.info(f"[fix_scrape] check_result.issues count: {len(check_result.issues)}, movies count: {len(movies)}")
        except Exception as e:
            logger.error(f"检查刮削结果失败: {e}", exc_info=True)
            movies = []

    total = len(movies)
    logger.info(f"[fix_scrape] total movies to fix: {total}")

    def generate():
        fixed_count = 0
        failed_count = 0

        # 发送开始事件（包含 job_id，让前端可以停止）
        yield _send_sse({
            "type": "start",
            "job_id": job_id,
            "total": total,
            "message": f"开始修复 {total} 部影片..."
        })

        for i, m in enumerate(movies):
            # 检查停止信号
            if stop_event.is_set():
                yield _send_sse({
                    "type": "stopped",
                    "job_id": job_id,
                    "message": "用户已停止修复"
                })
                # 清理停止标志
                with _scrape_lock:
                    _scrape_stop_flags.pop(job_id, None)
                return  # 使用 return 而不是 break，直接结束生成器
            
            movie_id = m.get("id")
            code = m.get("code", "")
            fixed = False
            message = ""

            # 跳过 Jellyfin 来源的影片
            if m.get("source") == "jellyfin" or m.get("source_type") == "jellyfin":
                yield _send_sse({
                    "type": "skipped",
                    "job_id": job_id,
                    "code": code,
                    "message": "📁 Jellyfin 导入，跳过修复"
                })
                continue

            try:
                # 获取本地视频路径
                local_video_path = None
                if m.get("local_video_id"):
                    lv = db.get_local_video_by_id(m.get("local_video_id"))
                    if lv:
                        local_video_path = lv.get("path")

                # 检查是否缺少元数据（需要重新刮削）
                need_metadata = (
                    not m.get("title") or
                    not m.get("release_date") or
                    not m.get("maker") or
                    not m.get("actors")
                )

                if need_metadata and code:
                    # 重新刮削元数据
                    yield _send_sse({
                        "type": "scraping",
                        "job_id": job_id,
                        "code": code,
                        "index": i + 1,
                        "total": total,
                        "pct": int(((i + 1) / total) * 100)
                    })

                    result = scrape_movie(code, save_cover=True, local_video_path=local_video_path)
                    if result:
                        # 更新数据库
                        update_data = {k: v for k, v in result.items() if v}
                        db.update_movie(movie_id, update_data)
                        fixed = True
                        message += "已重新刮削元数据; "

                        # 下载封面
                        if result.get("cover_url"):
                            updated = save_movie_assets(result, covers_dir, local_video_path)
                            if updated.get("poster_path"):
                                db.update_movie(movie_id, {
                                    "fanart_path": updated.get("fanart_path"),
                                    "poster_path": updated.get("poster_path"),
                                    "thumb_path": updated.get("thumb_path")
                                })
                                message += "已下载封面; "
                    else:
                        message = "重新刮削失败"
                        failed_count += 1
                        yield _send_sse({
                            "type": "error",
                            "job_id": job_id,
                            "code": code,
                            "message": message,
                            "index": i + 1,
                            "total": total,
                            "pct": int(((i + 1) / total) * 100)
                        })
                        continue
                else:
                    # 只检查封面和 NFO
                    need_cover = m.get("cover_url") and (
                        not m.get("poster_path") or not Path(m.get("poster_path", "")).exists()
                    )
                    safe_code = re.sub(r'[<>:"/\\|?*]', '_', code)
                    code_dir = covers_dir / safe_code
                    nfo_path = code_dir / f"{safe_code}.nfo"
                    need_nfo = not nfo_path.exists()

                    if need_cover or need_nfo:
                        updated = save_movie_assets(m, covers_dir, local_video_path)

                        if need_cover and updated.get("poster_path"):
                            db.update_movie(movie_id, {
                                "fanart_path": updated.get("fanart_path"),
                                "poster_path": updated.get("poster_path"),
                                "thumb_path": updated.get("thumb_path")
                            })
                            fixed = True
                            message += "已下载封面; "

                        if need_nfo and nfo_path.exists():
                            fixed = True
                            message += "已生成 NFO; "

                if fixed:
                    fixed_count += 1
                    yield _send_sse({
                        "type": "success",
                        "job_id": job_id,
                        "code": code,
                        "title": m.get("title", ""),
                        "message": message,
                        "index": i + 1,
                        "total": total,
                        "pct": int(((i + 1) / total) * 100)
                    })
                else:
                    failed_count += 1
                    yield _send_sse({
                        "type": "skipped",
                        "job_id": job_id,
                        "code": code,
                        "message": "无需修复",
                        "index": i + 1,
                        "total": total,
                        "pct": int(((i + 1) / total) * 100)
                    })

            except Exception as e:
                logger.error(f"修复影片 {code} 失败: {e}")
                message = f"修复失败: {str(e)}"
                failed_count += 1
                yield _send_sse({
                    "type": "error",
                    "job_id": job_id,
                    "code": code,
                    "message": message,
                    "index": i + 1,
                    "total": total,
                    "pct": int(((i + 1) / total) * 100)
                })

        # 完成
        yield _send_sse({
            "type": "done",
            "job_id": job_id,
            "success_count": fixed_count,
            "fail_count": failed_count,
            "message": f"修复完成：成功 {fixed_count}，失败 {failed_count}"
        })
        
        # 清理停止标志
        with _scrape_lock:
            _scrape_stop_flags.pop(job_id, None)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


# 单个影片的检查和修复
@app.get("/movies/{movie_id}/check", tags=["刮削"])
async def check_movie_scrape(movie_id: int):
    """检查单个影片的刮削完整性"""
    m = db.get_movie_by_id(movie_id)
    if not m:
        raise HTTPException(status_code=404, detail="影片不存在")

    from pathlib import Path
    covers_dir = Path(cfg.COVERS_DIR)

    issues = []
    code = m.get("code", "")

    # 判断是否是 Jellyfin 来源
    source_type = m.get("source_type") or m.get("source")
    is_jellyfin = source_type == "jellyfin"

    # Jellyfin 视频直接返回完整状态
    if is_jellyfin:
        return {
            "movie_id": movie_id,
            "code": code,
            "title": m.get("title"),
            "scrape_status": m.get("scrape_status"),
            "issues": [],
            "has_poster": bool(m.get("poster_path")),
            "has_fanart": bool(m.get("fanart_path")),
            "has_thumb": bool(m.get("thumb_path")),
            "has_nfo": True,
            "is_complete": True
        }

    # 检查必填字段
    if not m.get("title"):
        issues.append("缺少标题")
    if not m.get("release_date"):
        issues.append("缺少发布日期")
    if not m.get("maker"):
        issues.append("缺少制作商")
    if not m.get("actors"):
        issues.append("缺少女演员")

    # 检查封面文件
    has_poster = False
    has_fanart = False
    has_thumb = False
    has_nfo = False

    poster_path = m.get("poster_path")
    if poster_path:
        try:
            has_poster = Path(poster_path).exists()
            if not has_poster:
                issues.append("poster 文件不存在")
        except:
            issues.append("poster 路径无效")

    fanart_path = m.get("fanart_path")
    if fanart_path:
        try:
            has_fanart = Path(fanart_path).exists()
        except:
            pass

    thumb_path = m.get("thumb_path")
    if thumb_path:
        try:
            has_thumb = Path(thumb_path).exists()
        except:
            pass

    # 检查 NFO
    safe_code = re.sub(r'[<>:"/\\|?*]', '_', code)
    nfo_path = covers_dir / safe_code / f"{safe_code}.nfo"
    has_nfo = nfo_path.exists()
    if not has_nfo:
        issues.append("缺少 NFO 文件")

    return {
        "movie_id": movie_id,
        "code": code,
        "title": m.get("title"),
        "scrape_status": m.get("scrape_status"),
        "issues": issues,
        "has_poster": has_poster,
        "has_fanart": has_fanart,
        "has_thumb": has_thumb,
        "has_nfo": has_nfo,
        "is_complete": len(issues) == 0
    }


@app.post("/movies/{movie_id}/fix", tags=["刮削"])
async def fix_movie_scrape(movie_id: int):
    """修复单个影片的刮削结果"""
    m = db.get_movie_by_id(movie_id)
    if not m:
        raise HTTPException(status_code=404, detail="影片不存在")

    from scraper import save_movie_assets

    covers_dir = Path(cfg.COVERS_DIR)
    code = m.get("code", "")
    safe_code = re.sub(r'[<>:"/\\|?*]', '_', code)
    code_dir = covers_dir / safe_code

    fixed = []
    errors = []

    # 获取本地视频路径
    local_video_path = None
    if m.get("local_video_id"):
        lv = db.get_local_video_by_id(m.get("local_video_id"))
        if lv:
            local_video_path = lv.get("path")

    # 检查是否需要下载封面
    need_cover = m.get("cover_url") and (
        not m.get("poster_path") or not Path(m.get("poster_path", "")).exists()
    )
    # 检查是否需要生成 NFO
    nfo_path = code_dir / f"{safe_code}.nfo"
    need_nfo = not nfo_path.exists()

    if need_cover or need_nfo:
        try:
            # 统一后处理
            updated = save_movie_assets(m, covers_dir, local_video_path)

            # 更新数据库（封面路径）
            if need_cover and updated.get("poster_path"):
                db.update_movie(movie_id, {
                    "fanart_path": updated.get("fanart_path"),
                    "poster_path": updated.get("poster_path"),
                    "thumb_path": updated.get("thumb_path")
                })
                fixed.append("已下载封面")

            if need_nfo and nfo_path.exists():
                fixed.append("已生成 NFO")

        except Exception as e:
            errors.append(f"修复失败: {e}")

    return {
        "movie_id": movie_id,
        "code": code,
        "fixed": fixed,
        "errors": errors,
        "success": len(fixed) > 0 or len(errors) == 0
    }


# 健康检查
@app.get("/health")
async def health_check():
    return {"status": "ok"}


# ===============================================================================
# Jellyfin 导入 API
# ===============================================================================

@app.get("/jellyfin/stats", tags=["Jellyfin"])
async def jellyfin_stats():
    """获取 Jellyfin 导入统计"""
    count = db.get_jellyfin_count()
    return {
        "total_imported": count,
        "status": "ok"
    }


@app.post("/jellyfin/scan", tags=["Jellyfin"])
async def jellyfin_scan(request: Request):
    """
    扫描 Jellyfin 格式影视库（SSE 流式响应）
    
    请求体: { "directory": "Z:\\\\影视库" }
    
    目录结构期望：
    根目录/
    ├── 女星名称/
    │   ├── SSIS-001/
    │   │   ├── SSIS-001.mp4
    │   │   ├── SSIS-001.nfo
    │   │   ├── SSIS-001-poster.jpg
    │   │   └── SSIS-001-fanart.jpg
    │   └── ...
    └── ...
    """
    from jellyfin import scan_jellyfin_directory
    
    body = await request.json()
    directory = body.get("directory", "Z:\\影视库")
    
    # 调试日志
    print(f"[Jellyfin] 接收到的 directory: {repr(directory)}")
    
    async def generate():
        # 发送开始事件
        yield _send_sse({
            "type": "start",
            "directory": directory
        })
        
        # 扫描目录
        try:
            results = scan_jellyfin_directory(directory)
        except Exception as e:
            yield _send_sse({
                "type": "error",
                "message": f"扫描目录失败: {str(e)}"
            })
            return
        
        total = len(results)
        
        if total == 0:
            yield _send_sse({
                "type": "complete",
                "imported": 0,
                "skipped": 0,
                "errors": ["未找到有效内容"]
            })
            return
        
        imported = 0
        skipped = 0
        errors = []
        
        for i, item in enumerate(results):
            code = item['code']
            
            # 发送进度
            yield _send_sse({
                "type": "progress",
                "current": i + 1,
                "total": total,
                "code": code,
                "pct": int((i + 1) / total * 100),
                "title": f"正在导入 {code} ({i+1}/{total})..."
            })
            
            # 导入数据库
            print(f"[Jellyfin] 开始导入 {code}: video={item['video_path']}, poster={item.get('poster_file')}")
            try:
                movie_id = db.import_jellyfin_movie(
                    code=code,
                    metadata=item['metadata'],
                    video_path=item['video_path'],
                    poster_file=item.get('poster_file'),
                    fanart_file=item.get('fanart_file'),
                    thumb_file=item.get('thumb_file'),
                )
                print(f"[Jellyfin] 导入结果 {code}: movie_id={movie_id}")
            except Exception as e:
                print(f"[Jellyfin] 导入异常 {code}: {e}")
                import traceback
                traceback.print_exc()
                movie_id = -1
            
            if movie_id > 0:
                imported += 1
                yield _send_sse({
                    "type": "imported",
                    "code": code,
                    "movie_id": movie_id,
                    "title": item['metadata'].get('title', code)
                })
            elif movie_id == 0:
                skipped += 1
                yield _send_sse({
                    "type": "skipped",
                    "code": code,
                    "message": "已存在"
                })
            else:
                errors.append(code)
                yield _send_sse({
                    "type": "error",
                    "code": code,
                    "message": "导入失败"
                })
        
        # 标记目录为 Jellyfin 格式，并更新视频数量
        db.mark_source_as_jellyfin(directory, video_count=imported + skipped)
        
        # 完成
        yield _send_sse({
            "type": "complete",
            "imported": imported,
            "skipped": skipped,
            "errors": errors
        })
    
    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/jellyfin/mark-directory", tags=["Jellyfin"])
async def mark_directory_as_jellyfin(request: Request):
    """标记本地目录为 Jellyfin 格式"""
    body = await request.json()
    directory = body.get("directory")
    
    if not directory:
        return {"success": False, "error": "目录路径不能为空"}
    
    success = db.mark_source_as_jellyfin(directory)
    return {"success": success}


@app.get("/local-image", tags=["本地文件"])
async def get_local_image(path: str = Query(..., description="本地图片路径")):
    """
    安全访问本地图片文件（仅限已注册目录下的图片）
    
    用于 Jellyfin 导入的影片，封面存储在原目录而非 data/covers/
    """
    from fastapi.responses import FileResponse
    import os
    
    if not path:
        raise HTTPException(status_code=400, detail="路径不能为空")
    
    # 安全检查：必须是绝对路径
    if not os.path.isabs(path):
        raise HTTPException(status_code=400, detail="必须是绝对路径")
    
    # 安全检查：路径规范化，防止 .. 跳转
    path = os.path.normpath(path)
    
    # 安全检查：只允许图片文件
    ext = os.path.splitext(path)[1].lower()
    if ext not in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
        raise HTTPException(status_code=400, detail="只允许访问图片文件")
    
    # 安全检查：必须在已注册的目录下
    sources = db.get_local_sources_with_jellyfin()
    allowed_dirs = [s['path'] for s in sources]
    
    # 同时允许 data/covers 目录
    allowed_dirs.append(str(cfg.COVERS_DIR))
    allowed_dirs.append(str(cfg.DATA_DIR))
    
    # 规范化路径（统一使用系统分隔符）
    norm_path = os.path.normpath(path)
    
    # 调试：打印路径比较
    # print(f"[local-image] 请求路径: {norm_path}")
    
    in_allowed_dir = False
    for allowed in allowed_dirs:
        norm_allowed = os.path.normpath(allowed)
        # 检查是否匹配（支持子目录）
        if norm_path.startswith(norm_allowed + os.sep) or norm_path == norm_allowed:
            in_allowed_dir = True
            break
    
    if not in_allowed_dir:
        # 尝试更宽松的匹配：忽略盘符大小写
        for allowed in allowed_dirs:
            if norm_path.lower().startswith(os.path.normpath(allowed).lower() + os.sep):
                in_allowed_dir = True
                print(f"[local-image] 宽松匹配成功: {allowed}")
                break
    
    if not in_allowed_dir:
        print(f"[local-image] 拒绝访问: {path} (不在允许目录列表中)")
        print(f"[local-image] 允许的目录: {allowed_dirs}")
        raise HTTPException(status_code=403, detail="只能访问已注册目录下的文件")
    
    # 检查文件是否存在
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="文件不存在")
    
    # 返回文件
    return FileResponse(
        path,
        media_type=f"image/{ext[1:]}" if ext != '.jpg' else "image/jpeg",
        filename=os.path.basename(path)
    )


# 挂载前端静态文件（必须在所有路由定义之后）
if cfg.FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(cfg.FRONTEND_DIR), html=True), name="static")


@app.get("/local-sources/stats", tags=["本地目录"])
async def get_local_sources_stats():
    """获取本地视频统计信息（包含 Jellyfin 导入数量）"""
    stats = db.get_local_video_stats()
    jellyfin_count = db.get_jellyfin_count()
    
    return {
        "total": stats.get("total", 0),
        "scraped": stats.get("scraped", 0),
        "pending": stats.get("unscraped", 0),
        "jellyfin_imported": jellyfin_count
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
