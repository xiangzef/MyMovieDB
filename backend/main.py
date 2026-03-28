"""
FastAPI 主入口
依赖库:
    - fastapi, uvicorn: Web 框架
    - beautifulsoup4 (bs4): HTML 解析
    - requests: HTTP 请求
    - python-dotenv: 环境变量管理
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from pathlib import Path
from typing import Optional, List
import logging
import threading
import re
import time

from models import (
    MovieResponse, MovieListResponse,
    ScrapeRequest, ScrapeResponse
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

# 挂载前端目录（让127.0.0.1:8000 直接打开前端页面）
if cfg.FRONTEND_DIR.exists():
    app.mount("/frontend", StaticFiles(directory=str(cfg.FRONTEND_DIR), html=True), name="frontend")


@app.get("/")
async def root():
    """API 根路径 - 重定向到前端页面"""
    frontend_index = cfg.FRONTEND_DIR / "index.html"
    if frontend_index.exists():
        from fastapi.responses import FileResponse
        return FileResponse(str(frontend_index))
    return {"message": "MyMovieDB API", "version": "1.0.0"}


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
    from scraper import scrape_movie

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
        if local_video:
            movie_data["local_video_id"] = local_video["id"]

        # 使用 upsert：存在则智能合并，不存在则创建
        movie_id, is_new = db.upsert_movie(movie_data)

        # 如果本地库有关联，同步更新本地视频记录
        if local_video:
            db.mark_video_scraped(local_video["id"], movie_id)
            db.link_movie_to_local_video(movie_id, local_video["id"])

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
    from scraper import scrape_movie
    import uuid

    job_id = str(uuid.uuid4())[:8]
    stop_event = threading.Event()
    with _scrape_lock:
        _scrape_stop_flags[job_id] = stop_event

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
            if existing and existing.get("scrape_status") == "complete":
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
                    
                    # 下载并裁切封面（如果启用）
                    if req.save_cover and movie_data.get("cover_url"):
                        from scraper import download_and_crop_cover
                        from pathlib import Path
                        covers_dir = Path(cfg.COVERS_DIR)
                        covers_dir.mkdir(parents=True, exist_ok=True)
                        crop_paths = download_and_crop_cover(
                            movie_data["cover_url"], code, covers_dir
                        )
                        if crop_paths:
                            movie_data.update(crop_paths)
                    
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
    """获取所有本地视频源"""
    sources = db.get_local_sources()
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
    扫描所有已添加的目录，查找视频文件
    
    功能:
        - 遍历每个已添加的视频源目录（递归所有子文件夹）
        - 识别有效 AV 番号的视频文件
        - 排除非 AV 文件（如普通电影、综艺节目等）
        - 排除网站前缀干扰（如 390JNT-114 -> JNT-114）
    
    依赖:
        - os.walk(): 递归遍历目录树
        - os.path.splitext(): 分离文件名和扩展名
        - _extract_code_from_filename(): 从文件名提取有效番号
    
    返回:
        dict: 扫描结果统计
    """
    import os
    import threading
    import time

    # 视频扩展名
    VIDEO_EXTENSIONS = {
        '.mp4', '.mkv', '.avi', '.wmv', '.mov',
        '.flv', '.webm', '.m4v', '.mpg', '.mpeg',
        '.ts', '.mts', '.m2ts', '.vob', '.ogv'
    }

    sources = db.get_local_sources()
    if not sources:
        return {"success": False, "message": "请先添加视频目录"}

    total_found = 0
    scan_results = []

    # 扫描前清理所有无效番号记录（NULL代码 + 不符合识别规则的代码）
    db.cleanup_invalid_codes()

    for source in sources:
        source_id = source["id"]
        base_path = source["path"]
        found_count = 0

        if not os.path.isdir(base_path):
            scan_results.append({"source_id": source_id, "path": base_path, "status": "目录不存在", "count": 0})
            continue

        # 遍历目录（递归扫描所有子文件夹）
        try:
            for root, dirs, files in os.walk(base_path):
                for filename in files:
                    ext = os.path.splitext(filename)[1].lower()

                    if ext not in VIDEO_EXTENSIONS:
                        continue

                    # 提取编号（使用增强的番号识别函数）
                    name_without_ext = os.path.splitext(filename)[0]
                    code = _extract_code_from_filename(name_without_ext)

                    # 只保存有番号的视频
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
                        # 提取同目录下的 fanart / poster / thumb 图片
                        "fanart_path": _find_image_path(root, code, "fanart"),
                        "poster_path": _find_image_path(root, code, "poster"),
                        "thumb_path": _find_image_path(root, code, "thumb"),
                    }

                    vid_id, is_new = db.upsert_local_video(video_data)
                    found_count += 1
                    total_found += 1

        except PermissionError:
            scan_results.append({"source_id": source_id, "path": base_path, "status": "权限不足", "count": found_count})
            continue

        # 更新源的视频数量
        db.update_local_source_scan(source_id, found_count)
        scan_results.append({"source_id": source_id, "path": base_path, "status": "完成", "count": found_count})

    return {
        "success": True,
        "total_found": total_found,
        "results": scan_results,
        "stats": db.get_local_video_stats()
    }


@app.post("/local-sources/scrape", tags=["本地视频"])
async def scrape_local_videos():
    """对扫描到的本地视频批量刮削（只刮削有编号的）"""
    from scraper import scrape_movie
    import threading
    import time

    unscraped = db.get_unscraped_local_videos()
    if not unscraped:
        return {"success": True, "message": "没有需要刮削的视频", "processed": 0, "success_count": 0}

    success_count = 0
    fail_count = 0
    skip_count = 0
    results = []

    for video in unscraped:
        code = video.get("code")
        video_id = video["id"]

        if not code:
            skip_count += 1
            results.append({"video_id": video_id, "code": None, "status": "skip", "message": "无编号"})
            continue

        try:
            movie_data = scrape_movie(code, save_cover=True)
            if not movie_data:
                fail_count += 1
                results.append({"video_id": video_id, "code": code, "status": "fail", "message": "未找到"})
                continue

            # upsert 影片
            movie_id, is_new = db.upsert_movie(movie_data)
            # 关联本地视频：local_videos.movie_id 和 movies.local_video_id 双向关联
            db.mark_video_scraped(video_id, movie_id)
            db.link_movie_to_local_video(movie_id, video_id)
            success_count += 1
            results.append({"video_id": video_id, "code": code, "status": "success", "title": movie_data.get("title")})

            # 避免请求过快
            time.sleep(0.5)

        except Exception as e:
            logger.error(f"刮削 {code} 失败: {e}")
            fail_count += 1
            results.append({"video_id": video_id, "code": code, "status": "error", "message": str(e)[:100]})

    return {
        "success": True,
        "processed": len(unscraped),
        "success_count": success_count,
        "fail_count": fail_count,
        "skip_count": skip_count,
        "results": results,
        "stats": db.get_local_video_stats()
    }


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


# 健康检查
@app.get("/health")
async def health_check():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
