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
import json
from datetime import datetime, timedelta

from models import (
    MovieResponse, MovieListResponse,
    ScrapeRequest, ScrapeResponse,
    UserLogin, UserRegister, UserResponse, LoginResponse,
    ActorListResponse, SeriesListResponse, CategoryMoviesResponse,
    OrganizeRequest,  # Phase 0.5 整理功能
    # Phase 1 新增：统一响应模型
    ApiSuccess, ApiList, UserListResponse, MovieStatsResponse,
)
from pydantic import BaseModel, Field
import database as db
import config as cfg
import os

try:
    from translator import JapaneseVideoTranslator, WHISPER_AVAILABLE, TRANSLATOR_AVAILABLE
except ImportError:
    JapaneseVideoTranslator = None
    WHISPER_AVAILABLE = False
    TRANSLATOR_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 文件日志：只记录 ERROR 和 WARNING 级别，避免冗余
_LOG_FILE = Path(__file__).parent.parent / "logs" / "mymoviedb.log"
_LOG_FILE.parent.mkdir(exist_ok=True)
_file_handler = logging.FileHandler(_LOG_FILE, encoding="utf-8")
_file_handler.setLevel(logging.WARNING)
_file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
logging.getLogger().addHandler(_file_handler)

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
    'JBD', 'JB', 'JB5', 'JBR', 'JBS', 'JC', 'JD', 'JE', 'JFH', 'JHS', 'JIS', 'JK', 'JKT', 'JMK', 'JN', 'JNT', 'JPD', 'JPI', 'JPS', 'JR', 'JS', 'JUL', 'JUMP', 'JUX', 'JW',
    'K', 'KA', 'KAM', 'KB', 'KD', 'KGI', 'KM', 'KN', 'KO', 'KOK', 'KRD', 'KTK', 'KT', 'KU', 'KW', 'KZ',
    'LA', 'LB', 'LD', 'LEC', 'LG', 'LK', 'LL', 'LUXU', 'LX',
    'MA', 'MAD', 'MCS', 'MDB', 'ME', 'MFE', 'MGM', 'MI', 'MID', 'MIM', 'MJ', 'MK', 'ML', 'MM', 'MMB', 'MPL', 'MS', 'MST', 'MTA', 'MUGEN', 'MV', 'MX', 'MZ',
    'N', 'NAM', 'NB', 'NCT', 'ND', 'NE', 'NEW', 'NFA', 'NG', 'NH', 'NI', 'NK', 'NM', 'NN', 'NP', 'NPM', 'NR', 'NS', 'NSPS', 'NST', 'NT', 'NTR', 'NTT', 'NUK', 'NUM',
    'OB', 'OBA', 'OL', 'ONE', 'OOO', 'OP', 'ORE', 'OU',
    'P', 'P10', 'PAPA', 'PAR', 'PCD', 'PD', 'PE', 'PH', 'PJ', 'PK', 'PL', 'PP', 'PPV', 'PRESTIGE', 'PRED', 'PRIME', 'PU',
    'Q', 'QD', 'R', 'R18', 'RAC', 'RB', 'RCT', 'RD', 'REAL', 'RED', 'RE', 'RHEI', 'RHK', 'RID', 'RKI', 'RMC', 'RR', 'RS', 'RVS', 'RX',
    'S', 'S1', 'S2', 'S4U', 'SA', 'SACA', 'SAME', 'SAP', 'SAS', 'SC', 'SCO', 'SD', 'SDA', 'SDF', 'SDEN', 'SEN', 'SER', 'SF', 'SGA', 'SH', 'SHIN', 'SHK', 'SHL', 'SHP', 'SI', 'SIF', 'SKY', 'SL', 'SMA', 'SMDB', 'SML', 'SNC', 'SNIS', 'SOE', 'SOG', 'SOP', 'SOW', 'SP', 'SS', 'SSA', 'SSD', 'SSK', 'ST', 'STAR', 'STD', 'STON', 'STS', 'SUK', 'SW', 'SWAMP', 'SX',
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
    # 常见错误格式（OP/SS 已是有效 AV 前缀，不排除）
    'ED', 'OVA', 'EP', 'SP', 'CM', 'NC', 'PV',
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


@app.on_event("startup")
async def startup_event():
    """启动时同步数据 + 清理已过期的 Token"""
    # ① 同步 is_jellyfin 标识（防止数据库层面的来源不一致）
    try:
        sync_result = db.sync_local_videos_is_jellyfin()
        # 修复：只打印有实际修复的情况；0 表示已同步，无需提示
        has_actual_fix = (
            sync_result.get('lv_is_jellyfin_synced', 0) > 0 or
            sync_result.get('case_a_fixed', 0) > 0 or
            sync_result.get('case_b_fixed', 0) > 0
        )
        if has_actual_fix:
            print(f"[DataSync] is_jellyfin 同步: "
                  f"lv更新={sync_result.get('lv_is_jellyfin_synced', 0)} "
                  f"CaseA修复={sync_result.get('case_a_fixed', 0)} "
                  f"CaseB修复={sync_result.get('case_b_fixed', 0)}")
        else:
            print("[DataSync] is_jellyfin 数据已同步")
    except Exception as e:
        print(f"[DataSync] 启动时同步 is_jellyfin 失败: {e}")

    # ② 修复 is_jellyfin IS NULL 的孤立记录
    try:
        fix_result = db.fix_is_jellyfin_null_records()
        # 只在有修复或仍有残留时打印
        if fix_result.get('fixed', 0) > 0:
            print(f"[DataSync] is_jellyfin=NULL: {fix_result['message']}")
        elif fix_result.get('remaining_null', 0) > 0:
            print(f"[DataSync] is_jellyfin=NULL: {fix_result['message']}")
        else:
            print("[DataSync] is_jellyfin=NULL 无孤立记录")
    except Exception as e:
        print(f"[DataSync] 启动时修复孤立记录失败: {e}")

    try:
        cleaned = db.clean_expired_tokens_db()
        if cleaned > 0:
            print(f"[Auth] 清理了 {cleaned} 个过期 Token")
    except Exception as e:
        print(f"[Auth] 启动时清理 Token 失败: {e}")


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

# Token 内存缓存（写穿式，DB 为主存储）
active_tokens: dict = {}


def verify_token(token: str) -> dict:
    """验证 token 并返回用户信息（优先查缓存，fallback DB）"""
    if not token:
        raise HTTPException(status_code=401, detail="未登录或 token 已过期")

    # 缓存命中
    if token in active_tokens:
        user_data = active_tokens[token]
        if datetime.now() - user_data["created_at"] <= timedelta(hours=24):
            return user_data["user"]
        # 缓存过期，删除
        active_tokens.pop(token, None)

    # 缓存未命中，查数据库
    user = db.verify_token_db(token)
    if not user:
        raise HTTPException(status_code=401, detail="token 已过期，请重新登录")

    # 回填缓存
    active_tokens[token] = {
        "user": user,
        "created_at": datetime.now(),
    }
    return user


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

    # 持久化到 DB（同时写穿缓存）
    db.create_token_db(token, user_data)
    active_tokens[token] = {
        'user': user_data,
        'created_at': datetime.now(),
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


@app.post("/auth/register", response_model=ApiSuccess)
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
    
    return ApiSuccess(success=True, message="注册成功")


@app.get("/auth/me")
async def get_current_user_info(token: str = Query(None)):
    """获取当前用户信息"""
    user = get_current_user(token)
    return user


@app.post("/auth/logout", response_model=ApiSuccess)
async def logout(token: str = Query(None)):
    """用户登出（同时删除 DB 和缓存中的 Token）"""
    if token:
        active_tokens.pop(token, None)
        db.delete_token_db(token)
    return ApiSuccess(success=True, message="已登出")


# ========== 管理员 API ==========

class UserUpdateRequest(BaseModel):
    role: Optional[str] = Field(None, description="用户角色")
    is_active: Optional[int] = Field(None, description="是否激活")


@app.get("/admin/users", response_model=UserListResponse)
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

    return UserListResponse(users=users)


@app.put("/admin/users/{user_id}", response_model=ApiSuccess)
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
    
    return ApiSuccess(success=True, message="更新成功")


@app.delete("/admin/users/{user_id}", response_model=ApiSuccess)
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

    return ApiSuccess(success=True, message="删除成功")


# ========== 数据工具 API ==========

def _audit_database() -> dict:
    """审计数据库健康度"""
    conn = db.get_db()
    cursor = conn.cursor()
    results = {
        "total_movies": 0, "total_videos": 0,
        "complete": 0, "scraped_only": 0, "orphan": 0, "stale": 0,
        "missing_cover": 0, "actors_without_avatar": 0,
    }
    cursor.execute("SELECT COUNT(*) FROM movies")
    results["total_movies"] = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM local_videos")
    results["total_videos"] = cursor.fetchone()[0]
    cursor.execute("""
        SELECT id, code, title, actors, cover_url, local_cover_path,
               poster_path, fanart_path, thumb_path,
               (SELECT COUNT(*) FROM local_videos WHERE movie_id = movies.id) as video_count
        FROM movies
    """)
    movies = cursor.fetchall()
    cursor.execute("SELECT DISTINCT movie_id FROM local_videos WHERE movie_id IS NOT NULL")
    movies_with_videos = set(row[0] for row in cursor.fetchall())
    cursor.execute("SELECT actors FROM movies WHERE actors IS NOT NULL AND actors != ''")
    all_actors = set()
    for row in cursor.fetchall():
        if row[0]:
            for actor in row[0].split(","):
                actor = actor.strip()
                if actor:
                    all_actors.add(actor)
    avatar_dir = db.DATABASE_PATH.parent / "avatars"
    actors_with_avatar = set()
    if avatar_dir.exists():
        for f in avatar_dir.iterdir():
            if f.is_file():
                actors_with_avatar.add(f.stem)
    results["actors_without_avatar"] = len(all_actors - actors_with_avatar)
    for movie in movies:
        movie_id, code, title, actors = movie[0], movie[1], movie[2], movie[3]
        local_cover_path, cover_url = movie[5], movie[4]
        video_count = movie[9]
        has_actors = bool(actors and actors.strip())
        has_title = bool(title and title.strip())
        if video_count > 0:
            results["complete" if (has_actors and has_title) else "stale"] += 1
        else:
            results["scraped_only" if (has_actors or has_title) else "orphan"] += 1
        if not local_cover_path and not cover_url:
            results["missing_cover"] += 1
    conn.close()
    total = results["total_movies"]
    if total > 0:
        for key in ["complete", "scraped_only", "orphan", "stale"]:
            results[f"{key}_pct"] = round(results[key] / total * 100, 1)
    return results


@app.get("/api/admin/audit")
async def admin_audit():
    """数据库健康度审计"""
    return _audit_database()


@app.get("/api/admin/check")
async def admin_check(type: str = Query(...)):
    """数据质量检查"""
    conn = db.get_db()
    cursor = conn.cursor()
    result = {}
    if type == "orphans":
        cursor.execute("""
            SELECT id, code, title, actors, created_at FROM movies
            WHERE (SELECT COUNT(*) FROM local_videos WHERE movie_id = movies.id) = 0
            AND (actors IS NULL OR actors = '') AND (title IS NULL OR title = '')
        """)
        result["orphans"] = [dict(zip(['id','code','title','actors','created_at'], row)) for row in cursor.fetchall()]
    elif type == "duplicates":
        cursor.execute("""
            SELECT code, COUNT(*) as cnt, GROUP_CONCAT(id) as ids FROM movies
            WHERE code IS NOT NULL AND code != '' GROUP BY code HAVING cnt > 1
        """)
        result["duplicates"] = [{"code": r[0], "count": r[1], "ids": r[2].split(",")} for r in cursor.fetchall()]
    elif type == "missing_videos":
        cursor.execute("""
            SELECT id, code, title, actors FROM movies
            WHERE (SELECT COUNT(*) FROM local_videos WHERE movie_id = movies.id) = 0
            AND actors IS NOT NULL AND actors != ''
        """)
        result["missing_videos"] = [dict(zip(['id','code','title','actors'], row)) for row in cursor.fetchall()]
    elif type == "missing_covers":
        cursor.execute("""
            SELECT DISTINCT m.id, m.code, m.title FROM movies m
            INNER JOIN local_videos lv ON lv.movie_id = m.id
            WHERE (m.local_cover_path IS NULL OR m.local_cover_path = '')
            AND (m.cover_url IS NULL OR m.cover_url = '')
        """)
        result["missing_covers"] = [dict(zip(['id','code','title'], row)) for row in cursor.fetchall()]
    elif type == "invalid_codes":
        cursor.execute("SELECT id, code, title FROM movies WHERE code IS NOT NULL")
        invalid = []
        for row in cursor.fetchall():
            code = row[1] or ""
            if " " in code or any(c in code for c in ['(', ')', '[', ']', '（', '）']):
                invalid.append({"id": row[0], "code": row[1], "title": row[2]})
        result["invalid_codes"] = invalid
    elif type == "video_path_status":
        import shutil
        cursor.execute("""
            SELECT lv.id, lv.movie_id, lv.path, lv.name, lv.extension,
                   m.code, m.title, m.actors, m.organized_path
            FROM local_videos lv
            LEFT JOIN movies m ON lv.movie_id = m.id
        """)
        videos = cursor.fetchall()
        cursor.execute("SELECT path FROM local_sources WHERE is_jellyfin = 1")
        jellyfin_sources = [str(r[0]).replace("\\", "/").rstrip("/") for r in cursor.fetchall() if r[0]]
        valid, missing, jellyfin_moved = [], [], []
        for video in videos:
            video_id, movie_id, path, name = video[0], video[1], video[2], video[3]
            extension = video[4]
            code, title, actors, organized_path = video[5], video[6], video[7], video[8]
            path_str = str(path) if path else ""
            if path_str and Path(path_str).exists():
                valid.append({"video_id": video_id, "movie_id": movie_id, "code": code, "title": title, "path": path_str})
            elif path_str:
                found = False
                if code and jellyfin_sources:
                    for jf_src in jellyfin_sources:
                        jf_path = Path(jf_src)
                        if jf_path.exists():
                            possible = [jf_path / "jellyfin" / (actors or "未知演员") / code / f"{code}{extension}"]
                            for p in possible:
                                if p.exists():
                                    jellyfin_moved.append({"video_id": video_id, "movie_id": movie_id, "code": code, "title": title, "actors": actors, "old_path": path_str, "new_path": str(p)})
                                    found = True
                                    break
                if not found:
                    missing.append({"video_id": video_id, "movie_id": movie_id, "code": code, "title": title, "actors": actors, "old_path": path_str, "organized_path": organized_path})
        result["video_path_status"] = {"valid": valid[:50], "missing": missing[:50], "jellyfin_moved": jellyfin_moved[:50]}
    conn.close()
    return result


@app.get("/api/admin/video-path-status")
async def admin_video_path_status():
    """检查 local_videos 表中视频路径的有效性"""
    import shutil
    conn = db.get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT lv.id, lv.movie_id, lv.path, lv.name, lv.extension,
               m.code, m.title, m.actors, m.organized_path
        FROM local_videos lv
        LEFT JOIN movies m ON lv.movie_id = m.id
    """)
    videos = cursor.fetchall()
    cursor.execute("SELECT path FROM local_sources WHERE is_jellyfin = 1")
    jellyfin_sources = [str(r[0]).replace("\\", "/").rstrip("/") for r in cursor.fetchall() if r[0]]
    conn.close()

    valid, missing, jellyfin_moved = [], [], []
    for video in videos:
        video_id, movie_id, path, name = video[0], video[1], video[2], video[3]
        extension = video[4]
        code, title, actors, organized_path = video[5], video[6], video[7], video[8]
        path_str = str(path) if path else ""

        if path_str and Path(path_str).exists():
            valid.append({"video_id": video_id, "movie_id": movie_id, "code": code, "title": title, "path": path_str})
        elif path_str:
            found = False
            if code and jellyfin_sources:
                for jf_src in jellyfin_sources:
                    jf_path = Path(jf_src)
                    if jf_path.exists():
                        possible = [
                            jf_path / "jellyfin" / (actors or "未知演员") / code / f"{code}{extension}",
                        ]
                        for p in possible:
                            if p.exists():
                                jellyfin_moved.append({
                                    "video_id": video_id, "movie_id": movie_id, "code": code,
                                    "title": title, "actors": actors, "old_path": path_str, "new_path": str(p)
                                })
                                found = True
                                break
            if not found:
                missing.append({
                    "video_id": video_id, "movie_id": movie_id, "code": code,
                    "title": title, "actors": actors, "old_path": path_str,
                    "organized_path": organized_path
                })

    return {"valid_count": len(valid), "missing_count": len(missing), "jellyfin_moved_count": len(jellyfin_moved),
            "missing": missing[:50], "jellyfin_moved": jellyfin_moved[:50]}


@app.get("/api/admin/no-video-movies")
async def admin_no_video_movies():
    """查找无视频的影片（分孤儿和待整理）"""
    conn = db.get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, code, title, title_cn, actors, release_date, created_at
        FROM movies
        WHERE (SELECT COUNT(*) FROM local_videos WHERE movie_id = movies.id) = 0
        ORDER BY created_at DESC
    """)
    scraped_only = []
    orphan = []
    for row in cursor.fetchall():
        item = dict(zip(['id','code','title','title_cn','actors','release_date','created_at'], row))
        has_info = bool((item.get('title') and item['title'].strip()) or
                        (item.get('title_cn') and item['title_cn'].strip()) or
                        (item.get('actors') and item['actors'].strip()))
        if has_info:
            scraped_only.append(item)
        else:
            orphan.append(item)
    conn.close()
    return {"scraped_only": scraped_only, "orphan": orphan}


@app.get("/api/admin/cleanup")
async def admin_cleanup_preview(mode: str = Query("preview")):
    """预览或执行孤儿记录清理"""
    conn = db.get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, code, title, actors FROM movies
        WHERE (SELECT COUNT(*) FROM local_videos WHERE movie_id = movies.id) = 0
        AND (actors IS NULL OR actors = '') AND (title IS NULL OR title = '')
    """)
    orphans = [{"id": r[0], "code": r[1], "title": r[2]} for r in cursor.fetchall()]
    conn.close()
    if mode == "preview":
        return {"dry_run": True, "count": len(orphans), "ids": [o["id"] for o in orphans]}
    # execute
    if not orphans:
        return {"dry_run": False, "deleted": 0}
    conn = db.get_db()
    cursor = conn.cursor()
    ids = [o["id"] for o in orphans]
    placeholders = ",".join("?" * len(ids))
    cursor.execute(f"DELETE FROM movies WHERE id IN ({placeholders})", ids)
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return {"dry_run": False, "deleted": deleted}


@app.post("/api/admin/fix-codes")
async def admin_fix_codes():
    """修复番号格式（去除空格和特殊字符）"""
    conn = db.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, code FROM movies WHERE code IS NOT NULL")
    updated = 0
    for row in cursor.fetchall():
        code_id, code = row[0], row[1]
        if code and (" " in code or any(c in code for c in ['(', ')', '[', ']', '（', '）'])):
            new_code = re.sub(r'[\s()（）\[\]]+', '', code)
            cursor.execute("UPDATE movies SET code = ? WHERE id = ?", (new_code, code_id))
            updated += 1
    conn.commit()
    conn.close()
    return {"updated": updated}


@app.get("/api/admin/export-missing-videos")
async def admin_export_missing_videos():
    """导出有刮削但无视频的记录"""
    conn = db.get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, code, title, title_cn, actors, release_date, created_at
        FROM movies
        WHERE (SELECT COUNT(*) FROM local_videos WHERE movie_id = movies.id) = 0
        AND (actors IS NOT NULL AND actors != '')
        ORDER BY created_at DESC
    """)
    result = [dict(zip(['id','code','title','title_cn','actors','release_date','created_at'], row)) for row in cursor.fetchall()]
    conn.close()
    return result


class SqlRequest(BaseModel):
    query: str


@app.post("/api/admin/sql")
async def admin_sql(req: SqlRequest):
    """执行只读 SQL 查询"""
    q = req.query.strip().upper()
    if not q.startswith("SELECT"):
        return {"error": "只支持 SELECT 查询"}
    try:
        conn = db.get_db()
        cursor = conn.cursor()
        cursor.execute(req.query)
        columns = [d[0] for d in cursor.description] if cursor.description else []
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        conn.close()
        return {"columns": columns, "rows": rows}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/admin/logs")
async def get_logs(lines: int = Query(50, ge=10, le=500)):
    """读取系统日志（仅 ERROR/WARNING）"""
    log_path = Path(__file__).parent.parent / "logs" / "mymoviedb.log"
    if not log_path.exists():
        return {"logs": [], "total": 0}
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
        recent = all_lines[-lines:] if len(all_lines) > lines else all_lines
        return {"logs": [l.strip() for l in recent if l.strip()], "total": len(all_lines)}
    except Exception as e:
        return {"logs": [], "total": 0, "error": str(e)}


@app.post("/api/admin/logs/clear")
async def clear_logs():
    """清空日志文件"""
    log_path = Path(__file__).parent.parent / "logs" / "mymoviedb.log"
    if log_path.exists():
        log_path.write_text("", encoding="utf-8")
    return {"success": True, "message": "日志已清空"}


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
        logging.error(f"[get_movie] Pydantic 验证失败 id={movie_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="影片数据加载失败，请检查数据完整性")


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
        logging.error(f"[get_movie_by_code] Pydantic 验证失败 code={code}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="影片数据加载失败，请检查数据完整性")



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
        logging.error(f"[open_folder] 打开文件夹失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="打开文件夹失败")


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
        logging.error(f"[play_video] 播放失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="播放视频失败")


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
        set_stop_check(None)  # 清理全局停止回调，防止影响后续单片刮削
        return {"success": False, "message": "未识别到有效番号"}

    total = len(codes)

    def generate():
        import time as _time
        success_count = 0
        fail_count = 0
        local_link_count = 0
        skipped_count = 0
        start_time = _time.time()

        for i, code in enumerate(codes):
            elapsed = _time.time() - start_time
            processed = success_count + fail_count + skipped_count
            speed = processed / elapsed if elapsed > 0 else 0
            eta = int((total - processed) / speed) if speed > 0 else -1

            def _speed_eta(extra: int = 0) -> dict:
                """生成 speed/eta 字段"""
                p = processed + extra
                e = elapsed + 0.001
                spd = p / e
                eta_val = int((total - p) / spd) if spd > 0 else -1
                return {"speed": round(spd, 2), "eta": eta_val}
            # 检查停止标志
            if stop_event.is_set():
                yield _send_sse({
                    "type": "stopped",
                    "code": code,
                    "index": i + 1,
                    "total": total,
                    "message": "用户停止了刮削",
                    "elapsed": round(_time.time() - start_time, 1),
                })
                break

            # 发送当前处理信息
            _se = _speed_eta()
            yield _send_sse({
                "type": "scraping",
                "job_id": job_id,
                "code": code,
                "title": f"正在刮削 {code} ({i+1}/{total})...",
                "index": i + 1,
                "total": total,
                "pct": int((i / total) * 100),
                "speed": _se["speed"],
                "eta": _se["eta"],
            })

            # ── 预检标志位（轻量，无网络请求）────────────────────────────
            # 先用 check_and_fix_scrape_status() 校验并原地修正标志位：
            # 1. 若字段已满足 complete 要求但标志位滞后 → 修正后跳过
            # 2. 若确实 partial/empty → 继续刮削
            # 3. 若数据库不存在 → 继续刮削
            check = db.check_and_fix_scrape_status(code)
            existing = db.get_movie_by_code(code)  # 取完整记录（供后续关联用）

            # 检查本地库是否有该番号的视频（提前查询，避免在后续分支中引用时未定义）
            local_video = db.get_local_video_by_code(code)
            local_video_id = local_video["id"] if local_video else None
            local_path = local_video.get("path") if local_video else None

            # 跳过 Jellyfin 来源的影片（Jellyfin 有自己的元数据管理，不走网络刮削）
            if existing and existing.get("source") in ("jellyfin",) or \
               existing and existing.get("source_type") == "jellyfin":
                skipped_count += 1
                _se = _speed_eta()
                yield _send_sse({
                    "type": "skipped",
                    "job_id": job_id,
                    "code": code,
                    "title": existing.get("title", ""),
                    "message": "📁 Jellyfin 导入，跳过刮削",
                    "index": i + 1,
                    "total": total,
                    "pct": int(((i + 1) / total) * 100),
                    "speed": _se["speed"],
                    "eta": _se["eta"],
                })
                continue

            # 标志位校验：complete（含刚修正的情况）→ 跳过，补关联即可
            if not check["should_scrape"]:
                # 补全本地视频关联（防止历史数据缺关联）
                if local_video_id and existing and not existing.get("local_video_id"):
                    db.mark_video_scraped(local_video_id, existing["id"])
                    db.link_movie_to_local_video(existing["id"], local_video_id)
                    local_link_count += 1
                skipped_count += 1
                _se = _speed_eta()
                # 区分"已是complete"和"刚被修正为complete"两种情况给用户不同提示
                fixed_msg = "🔧 标志位已修正为完整，跳过" if check["fixed"] else "已有完整削刮记录，跳过"
                yield _send_sse({
                    "type": "skipped",
                    "job_id": job_id,
                    "code": code,
                    "title": existing.get("title", "") if existing else "",
                    "message": fixed_msg,
                    "scrape_count": check["scrape_count"],
                    "last_scraped_at": check["last_scraped_at"],
                    "index": i + 1,
                    "total": total,
                    "pct": int(((i + 1) / total) * 100),
                    "speed": _se["speed"],
                    "eta": _se["eta"],
                })
                continue

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

                    success_count += 1
                    # ── 刮削后验证：确认数据完整性 ───────────────────────
                    after = db.check_and_fix_scrape_status(code)
                    if after["exists"] and after["should_scrape"]:
                        # 刮削不完整：缺 maker/actors/cover 等字段
                        success_count -= 1  # 不计入 success
                        missing_fields = []
                        movie = db.get_movie_by_code(code)
                        if movie:
                            if not movie.get("maker") and not movie.get("studio"):
                                missing_fields.append("制作商")
                            if not movie.get("actors"):
                                missing_fields.append("演员")
                            if not movie.get("local_cover_path") and not movie.get("cover_url"):
                                missing_fields.append("封面")
                            if not movie.get("release_date"):
                                missing_fields.append("发布日期")
                        _se = _speed_eta()
                        yield _send_sse({
                            "type": "partial",
                            "job_id": job_id,
                            "code": code,
                            "title": movie_data.get("title", "") if movie_data else "",
                            "message": "⚠️ 刮削不完整（" + "、".join(missing_fields) + "缺失）",
                            "missing_fields": missing_fields,
                            "scrape_count": after.get("scrape_count", 0),
                            "index": i + 1,
                            "total": total,
                            "pct": int(((i + 1) / total) * 100),
                            "speed": _se["speed"],
                            "eta": _se["eta"],
                        })
                        continue

                    _se = _speed_eta()
                    yield _send_sse({
                        "type": "success",
                        "job_id": job_id,
                        "code": code,
                        "title": movie_data.get("title", ""),
                        "local_path": local_path,
                        "is_new": is_new,
                        "index": i + 1,
                        "total": total,
                        "pct": int(((i + 1) / total) * 100),
                        "speed": _se["speed"],
                        "eta": _se["eta"],
                    })
                else:
                    fail_count += 1
                    _se = _speed_eta()
                    yield _send_sse({
                        "type": "fail",
                        "job_id": job_id,
                        "code": code,
                        "message": "未找到影片信息",
                        "index": i + 1,
                        "total": total,
                        "pct": int(((i + 1) / total) * 100),
                        "speed": _se["speed"],
                        "eta": _se["eta"],
                    })

            except Exception as e:
                logger.error(f"刮削 {code} 失败: {e}")
                fail_count += 1
                _se = _speed_eta()
                yield _send_sse({
                    "type": "error",
                    "job_id": job_id,
                    "code": code,
                    "message": str(e)[:100],
                    "index": i + 1,
                    "total": total,
                    "pct": int(((i + 1) / total) * 100),
                    "speed": _se["speed"],
                    "eta": _se["eta"],
                })

            # 请求间隔
            time.sleep(0.5)

        # 完成
        total_elapsed = _time.time() - start_time
        total_processed = success_count + fail_count + skipped_count
        final_speed = total_processed / total_elapsed if total_elapsed > 0 else 0
        yield _send_sse({
            "type": "done",
            "job_id": job_id,
            "processed": total_processed,
            "success_count": success_count,
            "fail_count": fail_count,
            "skipped_count": skipped_count,
            "local_link_count": local_link_count,
            "total": total,
            "elapsed": round(total_elapsed, 1),
            "avg_speed": round(final_speed, 2),
        })

        # 清理
        with _scrape_lock:
            _scrape_stop_flags.pop(job_id, None)
        set_stop_check(None)  # 重置全局停止回调，避免污染后续的单片刮削

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
                        
                        # 每 50 个文件推送一次进度（降低频率防止前端卡顿）
                        if processed_files % 50 == 0 or processed_files == file_count:
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


@app.post("/local-sources/{source_id}/scan", tags=["本地视频"])
async def scan_single_source(source_id: int):
    """
    扫描指定目录，查找视频文件（单个目录的重新扫描）
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

        source = db.get_local_source_by_id(source_id)
        if not source:
            yield _send_sse({"type": "error", "message": f"目录不存在 (id={source_id})"})
            return

        base_path = source["path"]

        # 阶段1: 开始
        yield _send_sse({
            "type": "start",
            "total_sources": 1,
            "message": f"重新扫描: {base_path}"
        })

        yield _send_sse({
            "type": "source_start",
            "source_index": 1,
            "total_sources": 1,
            "path": base_path,
            "message": f"扫描: {base_path}"
        })

        if not os.path.isdir(base_path):
            yield _send_sse({
                "type": "source_done",
                "source_index": 1,
                "total_sources": 1,
                "found": 0,
                "status": "目录不存在"
            })
            yield _send_sse({
                "type": "done",
                "total_found": 0,
                "results": [{"source_id": source_id, "path": base_path, "status": "目录不存在", "count": 0}]
            })
            return

        # 统计文件数
        file_count = 0
        try:
            for root, dirs, files in os.walk(base_path):
                file_count += len([f for f in files if os.path.splitext(f)[1].lower() in VIDEO_EXTENSIONS])
        except PermissionError:
            pass

        processed_files = 0
        found_count = 0

        try:
            for root, dirs, files in os.walk(base_path):
                for filename in files:
                    ext = os.path.splitext(filename)[1].lower()
                    if ext not in VIDEO_EXTENSIONS:
                        continue

                    processed_files += 1
                    name_without_ext = os.path.splitext(filename)[0]
                    code = _extract_code_from_filename(name_without_ext)

                    # 每 50 个文件推送一次进度
                    if processed_files % 50 == 0 or processed_files == file_count:
                        yield _send_sse({
                            "type": "progress",
                            "source_index": 1,
                            "total_sources": 1,
                            "processed": processed_files,
                            "total_files": file_count,
                            "pct": int((processed_files / file_count) * 100) if file_count > 0 else 0,
                            "found": found_count,
                            "current_file": filename
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

        except PermissionError:
            pass

        db.update_local_source_scan(source_id, found_count)

        yield _send_sse({
            "type": "source_done",
            "source_index": 1,
            "total_sources": 1,
            "found": found_count,
            "status": "完成",
            "message": f"完成 - 找到 {found_count} 个视频"
        })

        yield _send_sse({
            "type": "done",
            "total_found": found_count,
            "results": [{"source_id": source_id, "path": base_path, "status": "完成", "count": found_count}]
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
        set_stop_check(None)  # 清理全局停止回调，防止影响后续单片刮削
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

            # ── 预检标志位（轻量，无网络请求）────────────────────────────
            # check_and_fix_scrape_status() 会重新计算字段完整性并原地修正标志：
            # - 数据已完整但标志滞后 → 修正后跳过（避免重复刮削）
            # - 确实 partial/empty → 继续刮削
            check = db.check_and_fix_scrape_status(code)
            existing = db.get_movie_by_code(code)

            # 跳过 Jellyfin 来源的影片（双保险：is_jellyfin 字段 + source_type 判断）
            if video.get("is_jellyfin") == 1 or (existing and existing.get("source_type") == "jellyfin"):
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

            # 标志位校验通过（complete，含刚修正的情况）→ 跳过
            if not check["should_scrape"]:
                if video_id and existing and not existing.get("local_video_id"):
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

                # 避免请求过快（保留0.8s，原0.5s为重复遗留bug，已删除）
                time.sleep(0.8)

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
        set_stop_check(None)  # 重置全局停止回调，避免污染后续的单片刮削

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/local-videos", response_model=LocalVideoListResponse, tags=["本地视频"])
async def get_local_videos(
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    source_id: int = Query(None, description="按视频源筛选"),
    scraped: int = Query(None, description="刮削状态: 0=未刮, 1=已刮"),
    scrape_status: str = Query(None, description="刮削完整度: complete/partial/empty/not_complete"),
    keyword: str = Query(None, description="搜索文件名或编号")
):
    """获取本地视频列表"""
    total, items = db.get_local_videos(
        page=page,
        page_size=page_size,
        source_id=source_id,
        scraped=scraped,
        scrape_status=scrape_status,
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


@app.post("/scrape/verify-status", tags=["刮削"])
async def verify_scrape_status(limit: int = Query(0, description="最多校验条数，0=全部")):
    """
    批量校验并修正 scrape_status 标志位（无网络请求，纯本地字段校验）

    - 遍历全库（或指定 limit 条）影片
    - 重新计算每部影片的 scrape_status（基于字段完整性）
    - 若与存储值不一致则原地修正
    - 返回统计：总数 / 修正数 / complete 数 / partial 数 / empty 数

    使用场景：
    1. 刮削后 UI 显示状态不一致时手动触发
    2. 批量刮削前先运行，过滤掉实际已完整的影片
    3. 定期维护时清理历史脏数据
    """
    try:
        stats = db.batch_verify_scrape_status(limit=limit)
        return {
            "success": True,
            "message": f"校验完成：共 {stats['total']} 部，修正 {stats['fixed']} 部（complete={stats['complete']}, partial={stats['partial']}, empty={stats['empty']}）",
            "stats": stats,
        }
    except Exception as e:
        logger.error("batch_verify_scrape_status 失败", exc_info=True)
        raise HTTPException(status_code=500, detail="校验失败，请查看服务器日志")


@app.post("/scrape/jellyfin-verify", tags=["刮削"])
async def verify_jellyfin_status():
    """
    校验 Jellyfin 来源影片的刮削状态。

    - 统计 Jellyfin 视频的 complete/partial/empty 分布
    - 统计 Jellyfin 结构完整性 jellyfin_status 分布（complete/partial/broken/unknown）
    - 对 scrape_status != 'complete' 的影片尝试修正（重算标志位）
    - 返回统计和需要关注的影片列表
    """
    try:
        conn = db.get_db()
        cursor = conn.cursor()

        # 统计 Jellyfin 视频各状态数量（scrape_status）
        cursor.execute("""
            SELECT COALESCE(m.scrape_status, 'NULL') as status, COUNT(*) as cnt
            FROM local_videos v
            JOIN movies m ON v.movie_id = m.id
            WHERE v.code IS NOT NULL AND v.code != ''
              AND m.source_type = 'jellyfin'
            GROUP BY m.scrape_status
        """)
        status_dist = {row["status"]: row["cnt"] for row in cursor.fetchall()}

        # 统计 Jellyfin 结构完整性分布（jellyfin_status）
        cursor.execute("""
            SELECT COALESCE(m.jellyfin_status, 'unknown') as js, COUNT(*) as cnt
            FROM local_videos v
            JOIN movies m ON v.movie_id = m.id
            WHERE m.source_type = 'jellyfin'
            GROUP BY m.jellyfin_status
        """)
        jellyfin_struct_dist = {row["js"]: row["cnt"] for row in cursor.fetchall()}

        # 检查是否有 Jellyfin 视频的 scrape_status 不是 complete
        cursor.execute("""
            SELECT v.id, v.code, m.title, m.scrape_status, m.release_date,
                   m.maker, m.poster_path
            FROM local_videos v
            JOIN movies m ON v.movie_id = m.id
            WHERE v.code IS NOT NULL AND v.code != ''
              AND m.source_type = 'jellyfin'
              AND m.scrape_status != 'complete'
            LIMIT 50
        """)
        issues = [dict(row) for row in cursor.fetchall()]

        # 同时检查 Jellyfin 视频中有多少实际上没有本地 poster 封面文件
        cursor.execute("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN m.poster_path IS NULL OR m.poster_path = '' THEN 1 ELSE 0 END) as no_poster
            FROM local_videos v
            JOIN movies m ON v.movie_id = m.id
            WHERE v.code IS NOT NULL AND v.code != ''
              AND m.source_type = 'jellyfin'
        """)
        poster_stats = dict(cursor.fetchone())

        # 有 jellyfin_status=broken 或 unknown 的影片（需要关注）
        cursor.execute("""
            SELECT v.code, m.title, v.path, m.poster_path, m.jellyfin_status
            FROM local_videos v
            JOIN movies m ON v.movie_id = m.id
            WHERE m.source_type = 'jellyfin'
              AND m.jellyfin_status IN ('broken', 'unknown', 'partial')
            LIMIT 50
        """)
        struct_issues = [dict(row) for row in cursor.fetchall()]

        conn.close()

        return {
            "success": True,
            "status_distribution": status_dist,
            "jellyfin_struct_distribution": jellyfin_struct_dist,
            "issues": issues,
            "struct_issues": struct_issues,
            "poster_stats": poster_stats,
            "message": (
                f"Jellyfin 视频 {status_dist.get('complete', 0)} 部完整，"
                f"{status_dist.get('partial', 0)} 部部分，"
                f"{status_dist.get('empty', 0)} 部为空；"
                f"结构完整 {jellyfin_struct_dist.get('complete', 0)} 部，"
                f"缺失封面 {jellyfin_struct_dist.get('partial', 0)} 部，"
                f"文件失效 {jellyfin_struct_dist.get('broken', 0)} 部"
            ),
        }
    except Exception as e:
        logger.error("verify_jellyfin_status 失败", exc_info=True)
        raise HTTPException(status_code=500, detail="Jellyfin 校验失败")


@app.post("/scrape/jellyfin-refresh-status", tags=["刮削"])
async def refresh_jellyfin_status():
    """
    重新扫描所有 Jellyfin 影片的文件结构，计算并更新 jellyfin_status 列。
    仅对 source_type='jellyfin' 的记录有效，批量操作，无网络请求。
    """
    try:
        stats = db.batch_verify_jellyfin_status()
        return {
            "success": True,
            **stats,
            "message": (
                f"Jellyfin 结构扫描完成：共 {stats['total']} 部，"
                f"完整 {stats['complete']} 部，缺失封面 {stats['partial']} 部，"
                f"文件失效 {stats['broken']} 部，未知 {stats['unknown']} 部，"
                f"本次修正 {stats['fixed']} 部"
            ),
        }
    except Exception as e:
        logger.error("refresh_jellyfin_status 失败", exc_info=True)
        raise HTTPException(status_code=500, detail="刷新 Jellyfin 结构状态失败")


@app.post("/scrape/jellyfin-scrape-missing", tags=["刮削"])
async def scrape_jellyfin_missing():
    """
    Jellyfin 影片补全刮削：联网补充缺失的元数据（厂商/演员等）。

    与批量刮削的区别：
    - 批量刮削（/local-sources/scrape）：处理 is_jellyfin=0 的独立视频库
    - Jellyfin 补全刮削：处理 is_jellyfin=1 的 Jellyfin 影片，
      联网刮削后强制保留 source_type='jellyfin'（不污染来源）

    数据流：
    1. 查询 is_jellyfin=1 且 scrape_status != 'complete' 的 Jellyfin 影片
    2. 对每部联网刮削，upsert_movie(force_source_type='jellyfin')
    3. 刮削完成后更新 jellyfin_status

    返回 SSE 流式进度。
    """
    from scraper import scrape_movie, save_movie_assets, set_stop_check
    import uuid
    import time

    job_id = str(uuid.uuid4())[:8]
    stop_event = threading.Event()
    with _scrape_lock:
        _scrape_stop_flags[job_id] = stop_event
    set_stop_check(lambda: stop_event.is_set())

    # 查询 Jellyfin 待刮削影片（is_jellyfin=1 且 scrape_status != 'complete'）
    conn = db.get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT v.id, v.code, v.path, v.movie_id,
               m.title, m.maker, m.actors, m.scrape_status
        FROM local_videos v
        JOIN movies m ON v.movie_id = m.id
        WHERE v.is_jellyfin = 1
          AND v.code IS NOT NULL AND v.code != ''
          AND m.scrape_status != 'complete'
        ORDER BY v.id
    """)
    jellyfin_videos = [dict(row) for row in cursor.fetchall()]
    conn.close()

    if not jellyfin_videos:
        with _scrape_lock:
            _scrape_stop_flags.pop(job_id, None)
        set_stop_check(None)
        return {"success": True, "message": "所有 Jellyfin 影片数据已完整，无需补全", "processed": 0}

    total = len(jellyfin_videos)

    def generate():
        success_count = 0
        fail_count = 0
        last_pct = -1

        for i, video in enumerate(jellyfin_videos):
            if stop_event.is_set():
                yield _send_sse({
                    "type": "stopped", "job_id": job_id,
                    "code": video.get("code"), "index": i + 1,
                    "total": total, "message": "用户停止了 Jellyfin 补全刮削"
                })
                break

            code = video.get("code")
            movie_id = video["movie_id"]
            video_id = video["id"]
            current_pct = int(((i + 1) / total) * 100)

            # 跳过已完整
            check = db.check_and_fix_scrape_status(code)
            if not check["should_scrape"]:
                if current_pct != last_pct:
                    yield _send_sse({
                        "type": "progress", "job_id": job_id,
                        "index": i + 1, "total": total, "pct": current_pct,
                        "stats": {"success": success_count, "fail": fail_count}
                    })
                    last_pct = current_pct
                continue

            yield _send_sse({
                "type": "scraping", "job_id": job_id,
                "code": code,
                "title": f"[Jellyfin] 正在刮削 {code}",
                "index": i + 1, "total": total, "pct": current_pct
            })

            try:
                movie_data = scrape_movie(code, save_cover=True)
                if movie_data and movie_data.get("title"):
                    covers_dir = Path(cfg.COVERS_DIR)
                    covers_dir.mkdir(parents=True, exist_ok=True)
                    movie_data = save_movie_assets(movie_data, covers_dir, video.get("path"))
                    # 关键：force_source_type='jellyfin' 保留来源标识
                    mid, is_new = db.upsert_movie(movie_data, force_source_type='jellyfin')
                    db.mark_video_scraped(mid, video_id)
                    db.link_movie_to_local_video(mid, video_id)
                    # 更新 jellyfin_status（校验文件完整性）
                    db.update_jellyfin_status(mid)
                    success_count += 1
                    yield _send_sse({
                        "type": "success", "job_id": job_id,
                        "code": code, "title": movie_data.get("title", ""),
                        "index": i + 1, "total": total, "pct": current_pct,
                        "stats": {"success": success_count, "fail": fail_count}
                    })
                else:
                    fail_count += 1
                    yield _send_sse({
                        "type": "fail", "job_id": job_id,
                        "code": code, "message": "未找到数据",
                        "index": i + 1, "total": total, "pct": current_pct,
                        "stats": {"success": success_count, "fail": fail_count}
                    })
            except Exception as e:
                fail_count += 1
                logger.warning(f"Jellyfin 补全刮削失败 {code}: {e}")
                yield _send_sse({
                    "type": "fail", "job_id": job_id,
                    "code": code, "message": str(e),
                    "index": i + 1, "total": total, "pct": current_pct,
                    "stats": {"success": success_count, "fail": fail_count}
                })

            time.sleep(0.8)

        # 完成
        with _scrape_lock:
            _scrape_stop_flags.pop(job_id, None)
        set_stop_check(None)
        yield _send_sse({
            "type": "done", "job_id": job_id,
            "total": total,
            "stats": {"success": success_count, "fail": fail_count},
            "message": f"Jellyfin 补全刮削完成：成功 {success_count} 部，失败 {fail_count} 部"
        })

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


@app.get("/scrape/jellyfin-missing-count", tags=["刮削"])
async def get_jellyfin_missing_count():
    """
    返回 Jellyfin 影片中缺失数据的数量（用于前台显示按钮 badge）。
    """
    try:
        conn = db.get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*)
            FROM local_videos v
            JOIN movies m ON v.movie_id = m.id
            WHERE v.is_jellyfin = 1
              AND v.code IS NOT NULL AND v.code != ''
              AND m.scrape_status != 'complete'
        """)
        count = cursor.fetchone()[0]
        conn.close()
        return {"success": True, "count": count}
    except Exception as e:
        logger.error(f"get_jellyfin_missing_count 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/scrape/jellyfin-incomplete", tags=["刮削"])
async def get_jellyfin_incomplete():
    """
    获取 Jellyfin 来源但元数据不完整的影片列表（缺 maker 或 actors）。
    返回：{incomplete: [{code, title, maker, actors, video_path, local_video_path}]}
    """
    try:
        items = db.get_jellyfin_incomplete_codes()
        return {"success": True, "count": len(items), "items": items}
    except Exception as e:
        logger.error(f"get_jellyfin_incomplete 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/scrape/jellyfin-enrich-nfo", tags=["刮削"])
async def enrich_jellyfin_from_nfo(request: Request):
    """
    从 Jellyfin NFO 文件批量补全 movies 表缺失的元数据。

    请求体（可选）: { "codes": ["ABP-454", "SSNI-730"] }  // 不传则处理全部

    流程：
    1. 找到每个番号对应的 NFO 文件（支持 -C/-U/-UC/-4K 后缀变体）
    2. 解析 NFO，提取 maker/studio/actors/genres/poster_path/fanart_path
    3. 仅补充空字段（不覆盖已有数据）
    4. 重算 scrape_status

    返回 SSE 流式进度：enrich_progress / enrich_done
    """
    body = await request.json() if request.body else {}
    target_codes = body.get("codes", None)  # None = 处理全部

    # 获取待处理列表
    if target_codes:
        all_incomplete = db.get_jellyfin_incomplete_codes()
        items = [it for it in all_incomplete if it['code'] in target_codes]
    else:
        items = db.get_jellyfin_incomplete_codes()

    total = len(items)

    async def generate():
        if total == 0:
            yield _send_sse({
                "type": "enrich_done",
                "total": 0,
                "nfo_found": 0,
                "nfo_missing": 0,
                "fields_updated": 0,
                "message": "没有需要补全的 Jellyfin 影片"
            })
            return

        nfo_found_count = 0
        nfo_missing_count = 0
        fields_updated_total = 0

        for i, item in enumerate(items):
            code = item['code']
            yield _send_sse({
                "type": "enrich_progress",
                "code": code,
                "index": i + 1,
                "total": total,
                "pct": int((i / total) * 100),
                "message": f"正在补全 {code}..."
            })

            result = db.enrich_jellyfin_movie_from_nfo(code)

            if result['success']:
                if result['nfo_found']:
                    nfo_found_count += 1
                    fields_updated_total += len(result.get('fields_updated', []))
                    yield _send_sse({
                        "type": "enrich_success",
                        "code": code,
                        "nfo_path": result.get('nfo_path', ''),
                        "fields_updated": result.get('fields_updated', []),
                        "message": result['message'],
                        "index": i + 1,
                        "total": total,
                    })
                else:
                    nfo_missing_count += 1
                    yield _send_sse({
                        "type": "enrich_no_nfo",
                        "code": code,
                        "message": result['message'],
                        "index": i + 1,
                        "total": total,
                    })
            else:
                nfo_missing_count += 1
                yield _send_sse({
                    "type": "enrich_error",
                    "code": code,
                    "message": result['message'],
                    "index": i + 1,
                    "total": total,
                })

        # 更新 scrape_status
        for item in items:
            db.check_and_fix_scrape_status(item['code'])

        yield _send_sse({
            "type": "enrich_done",
            "total": total,
            "nfo_found": nfo_found_count,
            "nfo_missing": nfo_missing_count,
            "fields_updated": fields_updated_total,
            "message": (f"NFO 补全完成：找到 {nfo_found_count} 部 NFO，"
                       f"缺失 {nfo_missing_count} 部，更新了 {fields_updated_total} 个字段")
        })

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@app.get("/local-sources/jellyfin-folders", tags=["本地视频"])
async def get_jellyfin_folder_issues():
    """
    扫描 Jellyfin 来源目录，识别：

    1. 空子文件夹（无视频文件 + 无 .nfo/.jpg 等元数据）
       → 可能表示视频文件实际不在此路径（Jellyfin 库指向了其他位置）

    2. 有元数据但无视频文件的子文件夹
       → 元数据存在但视频文件缺失，需要用户确认是否需要修复路径

    返回每个 Jellyfin 源目录的扫描结果。
    """
    import os
    from pathlib import Path

    try:
        conn = db.get_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, path, name FROM local_sources WHERE is_jellyfin = 1
        """)
        sources = [dict(row) for row in cursor.fetchall()]
        conn.close()

        results = []
        video_exts = {".mp4", ".mkv", ".avi", ".wmv", ".mov", ".webm", ".m4v", ".ts", ".flv", ".mpg", ".mpeg"}
        meta_exts = {".nfo", ".jpg", ".jpeg", ".png", ".tbn", ".xml"}

        for source in sources:
            root = source["path"]
            if not os.path.exists(root):
                results.append({
                    "source_id": source["id"],
                    "path": root,
                    "status": "path_missing",
                    "message": "路径不存在",
                    "empty_folders": [],
                    "meta_only_folders": [],
                })
                continue

            empty_folders = []
            meta_only_folders = []
            total_subfolders = 0
            total_videos = 0

            try:
                for subfolder in os.listdir(root):
                    subpath = os.path.join(root, subfolder)
                    if not os.path.isdir(subpath):
                        continue
                    total_subfolders += 1
                    files = os.listdir(subpath)
                    video_files = [f for f in files if Path(f).suffix.lower() in video_exts]
                    meta_files = [f for f in files if Path(f).suffix.lower() in meta_exts]

                    if len(files) == 0:
                        # 完全空的文件夹
                        empty_folders.append({
                            "name": subfolder,
                            "path": subpath,
                            "reason": "完全空（无任何文件）",
                        })
                    elif len(video_files) == 0 and len(meta_files) > 0:
                        # 有元数据但无视频
                        meta_only_folders.append({
                            "name": subfolder,
                            "path": subpath,
                            "files": files[:20],  # 最多显示20个
                            "file_count": len(files),
                        })
                        total_videos += 0  # 无视频文件
                    elif len(video_files) > 0:
                        total_videos += len(video_files)
            except PermissionError:
                results.append({
                    "source_id": source["id"],
                    "path": root,
                    "status": "permission_error",
                    "message": "无访问权限",
                    "empty_folders": [],
                    "meta_only_folders": [],
                })
                continue

            results.append({
                "source_id": source["id"],
                "path": root,
                "status": "ok" if not empty_folders and not meta_only_folders else "needs_attention",
                "total_subfolders": total_subfolders,
                "total_videos": total_videos,
                "empty_folders": empty_folders,
                "meta_only_folders": meta_only_folders,
                "message": (
                    f"共 {total_subfolders} 个子文件夹，{total_videos} 个视频，"
                    f"{len(empty_folders)} 个空文件夹，{len(meta_only_folders)} 个仅元数据"
                ),
            })

        return {"success": True, "results": results}

    except Exception as e:
        logger.error("get_jellyfin_folder_issues 失败", exc_info=True)
        raise HTTPException(status_code=500, detail="目录扫描失败")


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


# ===============================================================================
# 日语语音翻译 API - 从视频中提取日语语音并翻译成中文
# ===============================================================================

@app.post("/translate/video", tags=["语音翻译"])
async def translate_video(request: Request):
    """
    处理视频文件，提取日语语音并翻译成中文

    请求体: { "video_path": "Z:\\视频\\movie.mp4", "translate": true }
    """
    body = await request.json()
    video_path = body.get("video_path")
    do_translate = body.get("translate", True)

    if not video_path:
        raise HTTPException(status_code=400, detail="视频路径不能为空")

    if not os.path.isfile(video_path):
        raise HTTPException(status_code=404, detail=f"视频文件不存在: {video_path}")

    def run_translation():
        try:
            translator = JapaneseVideoTranslator(model_size="base")
            result = translator.process_video(video_path, translate=do_translate)
            return result
        except Exception as e:
            logger.error(f"[translate_video] 翻译失败: {str(e)}", exc_info=True)
            return {
                "success": False,
                "video_path": video_path,
                "original_text": "",
                "translated_text": "",
                "segments": [],
                "error": str(e)
            }

    result = await asyncio.to_thread(run_translation)
    return result


@app.post("/translate/batch", tags=["语音翻译"])
async def translate_batch(request: Request):
    """
    批量处理多个视频文件（SSE 实时进度）

    请求体: { "video_paths": ["Z:\\视频\\1.mp4", "Z:\\视频\\2.mp4"], "translate": true }
    """
    body = await request.json()
    video_paths = body.get("video_paths", [])
    do_translate = body.get("translate", True)

    if not video_paths:
        raise HTTPException(status_code=400, detail="视频路径列表不能为空")

    async def generate():
        total = len(video_paths)
        translator = JapaneseVideoTranslator(model_size="base")

        for i, video_path in enumerate(video_paths):
            yield _send_sse({
                "type": "progress",
                "current": i + 1,
                "total": total,
                "video_path": video_path,
                "pct": int((i + 1) / total * 100),
                "status": f"正在处理 {i+1}/{total}..."
            })

            try:
                if not os.path.isfile(video_path):
                    yield _send_sse({
                        "type": "error",
                        "video_path": video_path,
                        "message": "文件不存在"
                    })
                    continue

                result = translator.process_video(video_path, translate=do_translate)
                yield _send_sse({
                    "type": "result",
                    "video_path": video_path,
                    "success": result['success'],
                    "original_length": len(result.get('original_text', '')),
                    "translated_length": len(result.get('translated_text', '')),
                    "error": result.get('error')
                })
            except Exception as e:
                logger.error(f"[translate_batch] 处理失败 {video_path}: {str(e)}")
                yield _send_sse({
                    "type": "error",
                    "video_path": video_path,
                    "message": str(e)
                })

        yield _send_sse({
            "type": "complete",
            "total": total
        })

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/translate/check-tools", tags=["语音翻译"])
async def check_translation_tools():
    """
    检查翻译工具的可用性

    返回: { "whisper": true, "ffmpeg": true, "translator": true }
    """
    import shutil

    result = {
        "whisper": WHISPER_AVAILABLE,
        "ffmpeg": shutil.which("ffmpeg") is not None,
        "translator": TRANSLATOR_AVAILABLE
    }

    missing = []
    if not result["whisper"]:
        missing.append("openai-whisper")
    if not result["ffmpeg"]:
        missing.append("ffmpeg")
    if not result["translator"]:
        missing.append("deep-translator")

    result["ready"] = len(missing) == 0
    result["missing"] = missing

    return result


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



# ===============================================================================
# 类别展示 API（必须在 app.mount("/") 之前注册，否则被静态文件拦截）
# ===============================================================================

@app.get("/categories/actors", response_model=ActorListResponse, tags=["类别"])
async def get_actors(
    page: int = Query(1, ge=1),
    page_size: int = Query(48, ge=1, le=200),
    keyword: str = Query(None)
):
    """获取女演员列表（按作品数量降序）"""
    try:
        total, items = db.get_actor_stats(page=page, page_size=page_size, keyword=keyword)
    except Exception as e:
        logger.error(f"[get_actors] 加载女演员列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"加载女演员列表失败: {e}")
    return ActorListResponse(total=total, page=page, page_size=page_size, items=items)


@app.get("/categories/series", response_model=SeriesListResponse, tags=["类别"])
async def get_series(
    page: int = Query(1, ge=1),
    page_size: int = Query(48, ge=1, le=200),
    keyword: str = Query(None)
):
    """获取番号系列列表（按影片数量降序）"""
    total, items = db.get_series_stats(page=page, page_size=page_size, keyword=keyword)
    return SeriesListResponse(total=total, page=page, page_size=page_size, items=items)


@app.get("/categories/actors/{actor_name}/movies", response_model=CategoryMoviesResponse, tags=["类别"])
async def get_movies_by_actor(
    actor_name: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(48, ge=1, le=200)
):
    """获取某女演员的所有影片"""
    from urllib.parse import unquote
    actor_name = unquote(actor_name)
    total, items = db.get_movies_by_actor(actor_name=actor_name, page=page, page_size=page_size)
    return CategoryMoviesResponse(total=total, page=page, page_size=page_size, items=items)


@app.get("/categories/series/{prefix}/movies", response_model=CategoryMoviesResponse, tags=["类别"])
async def get_movies_by_series(
    prefix: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(48, ge=1, le=200)
):
    """获取某番号系列的所有影片"""
    total, items = db.get_movies_by_series(prefix=prefix, page=page, page_size=page_size)
    return CategoryMoviesResponse(total=total, page=page, page_size=page_size, items=items)


@app.get("/categories/stats", tags=["类别"])
async def get_categories_stats():
    """获取类别统计概览"""
    try:
        from gfriends import AVATAR_DIR

        _, all_actors = db.get_actor_stats(page=1, page_size=10000)
        total_actors = len(all_actors)
        total_known = sum(1 for a in all_actors if a["has_avatar"])

        total_series, _ = db.get_series_stats(page=1, page_size=10000)

        cached_avatars = 0
        if AVATAR_DIR.exists():
            cached_avatars = len(list(AVATAR_DIR.glob("*.jpg"))) + len(list(AVATAR_DIR.glob("*.png")))

        return {
            "actors": {
                "total": total_actors,
                "known": total_known,
                "anonymous": total_actors - total_known,
            },
            "series": {"total": total_series},
            "avatars": {"cached": cached_avatars}
        }
    except Exception as e:
        logger.error(f"[get_categories_stats] 获取类别统计失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取类别统计失败: {e}")


@app.get("/actors/not-in-repo", tags=["女演员"])
async def get_actors_not_in_repo(
    page: int = Query(1, ge=1),
    page_size: int = Query(48, ge=1, le=200)
):
    """
    获取佚女演员列表（本地无头像的女演员，用于点击"佚名"聚合卡后展示）。
    使用高效批量头像索引，避免逐演员查磁盘。
    """
    total, items = db.get_actors_without_avatars(page=page, page_size=page_size)
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items
    }


@app.get("/actors/lookup/{actor_name}", tags=["女演员"])
async def lookup_actor(actor_name: str):
    """查询女演员是否为真实 AV 女优（gfriends 收录）"""
    from urllib.parse import unquote
    actor_name = unquote(actor_name)
    from gfriends import lookup_actor as gfriends_lookup, get_local_avatar_url
    result = gfriends_lookup(actor_name)
    result["local_url"] = get_local_avatar_url(actor_name)
    return result


@app.post("/actors/download-avatars", tags=["女演员"])
async def download_actor_avatars(keyword: str = Query(...)):
    """批量下载女演员头像（SSE 实时进度流）"""
    from gfriends import search_avatar_url, download_avatar, get_local_avatar_path
    import asyncio

    if keyword == "all":
        _, nameless_actors = db.get_actors_without_avatars()
        names = [a["name"] for a in nameless_actors]
    else:
        names = [n.strip() for n in keyword.replace(",", " ").split() if n.strip()]

    async def generate():
        # 先 yield 一次空行，确保 headers 尽早发送（解决 CORS StreamingResponse 问题）
        await asyncio.sleep(0)

        if not names:
            yield f"data: {json.dumps({'type': 'complete', 'message': '没有需要下载的演员', 'total': 0, 'success': 0, 'fail': 0})}\n\n"
            return

        total = len(names)
        success_count = 0
        fail_count = 0

        # 发送开始事件
        job_id = f"avatar-{int(__import__('time').time())}"
        yield f"data: {json.dumps({'type': 'start', 'job_id': job_id, 'total': total})}\n\n"

        for i, name in enumerate(names):
            pct = int((i / total) * 100)
            yield f"data: {json.dumps({'type': 'progress', 'current': i+1, 'total': total, 'pct': pct, 'name': name})}\n\n"

            # 在线程池中执行下载（网络请求可能较慢，不阻塞主线程）
            def do_download(n=name):
                local = get_local_avatar_path(n)
                if local and local.exists():
                    return ("skip", n)
                urls = search_avatar_url(n)
                if not urls:
                    return ("fail", n)
                url = urls[0]["url"]
                ok = download_avatar(n, url)
                return ("success" if ok else "fail", n)

            loop = asyncio.get_event_loop()
            status, _ = await loop.run_in_executor(None, do_download)

            if status == "success":
                success_count += 1
                yield f"data: {json.dumps({'type': 'item', 'status': 'success', 'name': name, 'pct': pct})}\n\n"
            elif status == "skip":
                success_count += 1
                yield f"data: {json.dumps({'type': 'item', 'status': 'skip', 'name': name, 'pct': pct})}\n\n"
            else:
                fail_count += 1
                yield f"data: {json.dumps({'type': 'item', 'status': 'fail', 'name': name, 'pct': pct})}\n\n"

        yield f"data: {json.dumps({'type': 'complete', 'total': total, 'success': success_count, 'fail': fail_count, 'pct': 100, 'message': f'下载完成：{success_count}/{total} 成功'})}\n\n"

    # SSE 专用 headers，防止代理/浏览器缓冲导致流式推送失效
    headers = {
        "X-Accel-Buffering": "no",
        "Cache-Control": "no-cache",
    }
    return StreamingResponse(generate(), media_type="text/event-stream", headers=headers)


# ===============================================================================
# 整理功能路由（Phase 0.5）
# ===============================================================================

@app.post("/organize/preview", tags=["整理"])
async def organize_preview(req: OrganizeRequest):
    """
    预览整理计划（不实际移动文件）
    返回 SSE 流式事件:
        - scan_start: 开始扫描
        - found: 找到的每个文件（逐文件实时推送）
        - summary: 汇总统计
        - error: 发生错误

    设计原则：不设超时，让目录扫描自然完成。
    大网络目录可能耗时较长，但用户会看到实时文件列表，而不是无响应的 spinner。
    """
    import asyncio
    from organizer import organize_files_sync, OrganizeMode

    async def generate():
        await asyncio.sleep(0)

        loop = asyncio.get_running_loop()

        def make_sse(event_type: str, data: dict) -> str:
            return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

        # 先发送 scan_start，让前端立即显示"正在扫描..."
        yield make_sse("scan_start", {"message": "正在扫描文件..."})

        def progress_handler(progress):
            data = progress.model_dump(exclude_none=True)
            event_name = data.pop("event", "message")
            # 用 queue 传递给 asyncio loop
            q.put_nowait((event_name, data))

        # 用 queue 把 generator 的 yield 事件传回 asyncio
        q = asyncio.Queue()

        def run_sync():
            try:
                organize_files_sync(
                    source_paths=req.source_paths,
                    target_root=req.target_root,
                    mode=OrganizeMode.PREVIEW,
                    auto_scrape=False,
                    progress_callback=progress_handler,
                )
            finally:
                q.put_nowait((None, None))  # 结束信号

        # 在线程池中运行（不影响主 asyncio loop）
        executor_future = loop.run_in_executor(None, run_sync)

        try:
            while True:
                # 不设超时：扫描多久等多久，目录越大越能看到实时进度
                event_name, data = await q.get()
                if event_name is None:
                    break
                yield make_sse(event_name, data)
        except asyncio.CancelledError:
            executor_future.cancel()
            raise
        except Exception as e:
            logger.error(f"[Organize] 预览失败: {e}", exc_info=True)
            yield make_sse("error", {"message": str(e)})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache",
        }
    )


@app.post("/organize/execute", tags=["整理"])
async def organize_execute(req: OrganizeRequest):
    """
    执行整理（复制或移动文件）
    请求体:
        source_paths: 源目录列表
        target_root:  目标根目录
        mode: preview | copy | move
    返回 SSE 流式事件:
        - copied/moved/skipped/error: 每文件进度
        - done: 汇总结果
        - error: 发生错误
    """
    import asyncio
    from organizer import organize_files_sync, OrganizeMode

    async def generate():
        await asyncio.sleep(0)

        loop = asyncio.get_running_loop()

        def make_sse(event_type: str, data: dict) -> str:
            return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

        q: asyncio.Queue = asyncio.Queue()

        def progress_handler(progress):
            data = progress.model_dump(exclude_none=True)
            event_name = data.pop("event", "message")
            q.put_nowait((event_name, data))

        def run_sync():
            try:
                organize_files_sync(
                    source_paths=req.source_paths,
                    target_root=req.target_root,
                    mode=OrganizeMode(req.mode.value),
                    auto_scrape=req.auto_scrape,
                    progress_callback=progress_handler,
                )
            except Exception as e:
                logger.error(f"[Organize] 执行出错: {e}", exc_info=True)
                q.put_nowait(("error", {"message": str(e)}))
            finally:
                q.put_nowait((None, None))

        executor_future = loop.run_in_executor(None, run_sync)

        try:
            while True:
                # 不设超时：文件复制/移动耗时取决于文件大小和网络，大文件慢慢等
                # 实时看到每个 copied/moved/skipped 事件，胜于超时放弃
                event_name, data = await q.get()
                if event_name is None:
                    break
                yield make_sse(event_name, data)
        except asyncio.CancelledError:
            executor_future.cancel()
            raise
        except Exception as e:
            logger.error(f"[Organize] 执行失败: {e}", exc_info=True)
            yield make_sse("error", {"message": str(e)})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache",
        }
    )


@app.post("/organize/stop", tags=["整理"])
async def organize_stop():
    """中止正在进行的整理操作"""
    from organizer import abort_organize
    abort_organize()
    return {"message": "整理操作已请求中止"}


# ===============================================================================
# 静态文件挂载（必须最后，在所有 API 路由之后）
# ===============================================================================

# 挂载头像静态文件（必须在 "/" 之前）
from gfriends import get_avatar_dir
AVATAR_DIR = get_avatar_dir()
if AVATAR_DIR.exists():
    app.mount("/avatars", StaticFiles(directory=str(AVATAR_DIR), html=False), name="avatars")

# 挂载前端静态文件（最后挂载，会拦截所有未匹配路由）
if cfg.FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(cfg.FRONTEND_DIR), html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    import socket

    # 从 config.ini 读取端口
    server_port = cfg.PORT
    host = cfg.HOST

    # 预检查端口是否可用
    def is_port_available(port: int) -> bool:
        import errno as _errno
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("0.0.0.0", port))
                return True
        except OSError as e:
            # WSAEACCES (10013): 系统级权限拒绝（如 Hyper-V/Docker 保留端口段）
            # 此情况下所有端口都会返回拒绝，直接用 localhost 绑定尝试
            if e.errno == 10013:
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s2:
                        s2.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                        s2.bind(("127.0.0.1", port))
                        return True
                except OSError:
                    return False
            return False

    # 如果首选端口不可用，尝试递增端口
    actual_port = server_port
    if not is_port_available(actual_port):
        print(f"[WARNING] 端口 {actual_port} 已被占用，尝试其他端口...")
        for port in range(actual_port + 1, actual_port + 20):
            if is_port_available(port):
                actual_port = port
                print(f"[INFO] 找到可用端口: {port}")
                break
        else:
            print(f"[ERROR] 无法找到可用端口（{actual_port}~{actual_port+19} 均被占用），请先关闭占用进程。")
            exit(1)

    print(f"=" * 50)
    print(f"启动 MyMovieDB 后端服务")
    print(f"端口: {actual_port}")
    print(f"API文档: http://localhost:{actual_port}/docs")
    print(f"前端页面: http://localhost:{actual_port}/")
    print(f"=" * 50)

    try:
        uvicorn.run("main:app", host=host, port=actual_port, reload=False)
    except OSError as e:
        if e.errno == 10013:
            print(f"[ERROR] 端口 {actual_port} 被占用（权限不足或端口已被占用）。")
            print(f"[ERROR] 请关闭占用该端口的进程后重试，或修改 config.ini 中的 port 值。")
        else:
            print(f"[ERROR] 启动失败: {e}")
        exit(1)
