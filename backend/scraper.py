"""
================================================================================
爬虫模块 - 支持多个数据源，自动翻译标题
================================================================================
文件路径: F:\github\MyMovieDB\backend\scraper.py
功能说明: 影片刮削爬虫，支持从多个网站获取影片信息
主要类:
    - BaseScraper: 爬虫基类，提供通用 HTTP 请求和解析方法
    - AvdanyuwikiScraper: Avdanyuwiki 数据源（主要，推荐）
    - AvWikiScraper: AV-Wiki 数据源
    - AvbaseScraper: Avbase 数据源
    - JavcupScraper: Javcup 数据源
    - EnhancedMultiScraper: 多源聚合爬虫（综合所有可用数据源）
依赖库:
    - requests: HTTP 请求库，用于发送网络请求
    - bs4.BeautifulSoup: HTML/XML 解析库，用于提取网页数据
    - re: 正则表达式，用于匹配番号和文本模式
    - time: 时间控制，用于请求间隔
    - pathlib.Path: 路径处理，用于文件操作
    - urllib.parse: URL 处理，用于 URL 编码和拼接
    - typing: 类型提示，用于函数参数和返回值注解
    - logging: 日志记录，用于输出调试信息
可选依赖:
    - googletrans: Google 翻译 API，用于标题翻译
      安装命令: pip install googletrans==4.0.0-rc1
使用方法:
    from scraper import scrape_movie_enhanced, EnhancedMultiScraper
    result = scrape_movie_enhanced("IPZZ-792")
================================================================================
"""

# ===============================================================================
# 导入标准库和第三方库
# ===============================================================================

import requests                                  # HTTP 请求库
from bs4 import BeautifulSoup                   # HTML 解析库
import re                                        # 正则表达式
import time                                      # 时间控制（sleep）
from pathlib import Path                         # 路径处理
from urllib.parse import quote, urljoin, urlparse  # URL 处理
from typing import Optional, Dict, List          # 类型提示
import logging                                   # 日志记录
from io import BytesIO                           # 字节流处理

# ===============================================================================
# 可选依赖：PIL 图片处理
# ===============================================================================
# 功能: 下载封面并裁切为 fanart/poster/thumb 尺寸
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("警告: Pillow 未安装，将跳过封面裁切")

# ===============================================================================
# 可选依赖：Google 翻译
# ===============================================================================
# 功能: 将日文标题翻译为中文
# 安装: pip install googletrans==4.0.0-rc1
# 注意: Google 翻译 API 可能不稳定，已设置容错处理

try:
    from googletrans import Translator           # Google 翻译
    GOOGLE_TRANSLATE_AVAILABLE = True           # 标记翻译可用
except ImportError:
    GOOGLE_TRANSLATE_AVAILABLE = False          # 标记翻译不可用
    print("警告: googletrans 未安装，标题将不会翻译")

# ===============================================================================
# 导入配置文件
# ===============================================================================
# 功能: 从 config.py 读取网站配置和全局设置
# 依赖: config.DEFAULT_DELAY, config.DEFAULT_TIMEOUT, config.DEFAULT_RETRY,
#       config.DEFAULT_HEADERS, config.SCRAPER_SOURCES, config.get_enabled_sources,
#       config.get_source_by_id

import config

# ===============================================================================
# 日志配置
# ===============================================================================

logging.basicConfig(level=logging.INFO)          # 设置日志级别为 INFO
logger = logging.getLogger(__name__)             # 获取当前模块的日志记录器


# ===============================================================================
# 翻译相关函数
# ===============================================================================

def translate_to_chinese(text: str, retry: int = 2) -> str:
    """
    功能: 翻译日文文本到中文
    文件: scraper.py
    参数:
        text: 待翻译的日文文本
        retry: 失败重试次数（默认2次）
    返回: 翻译后的中文文本，失败时返回原文
    依赖: googletrans.Translator
    语法:
        result = translate_to_chinese("日文标题")
    """
    # 如果文本为空或翻译不可用，直接返回原文
    if not text or not GOOGLE_TRANSLATE_AVAILABLE:
        return text

    # 最多重试指定次数
    for i in range(retry):
        try:
            # 创建翻译器实例
            # 语法: Translator() 实例化
            translator = Translator()
            # 执行翻译
            # 语法: translator.translate(文本, src=源语言, dest=目标语言)
            result = translator.translate(text, src='ja', dest='zh-cn')
            if result and result.text:
                return result.text
        except Exception as e:
            logger.warning(f"翻译失败 (尝试 {i+1}/{retry}): {e}")
            if i < retry - 1:
                time.sleep(1)  # 等待1秒后重试

    return text  # 所有重试都失败，返回原文


# ===============================================================================
# 图片下载与裁切
# ===============================================================================

def download_and_crop_cover(cover_url: str, code: str, save_dir: Path) -> Optional[Dict[str, str]]:
    """
    功能: 下载封面图并裁切为 fanart/poster/thumb 三种尺寸
    文件: scraper.py
    参数:
        cover_url: 封面图 URL
        code: 影片番号（用于命名文件）
        save_dir: 保存目录（基础目录，会在其中创建番号子文件夹）
    返回: {"fanart": path, "poster": path, "thumb": path, "folder": path} 或 None
    依赖: PIL.Image, requests
    说明:
        - fanart: 横向 1920x1080 (用于背景)
        - poster: 竖向 1000x1500 (从 fanart 右半边中间截取，展示女演员全身照)
        - thumb: 缩略图 300x450
        - 文件结构: {save_dir}/{code}/{code}-{type}.jpg
    """
    if not PIL_AVAILABLE or not cover_url:
        return None

    try:
        # 下载原图
        response = requests.get(cover_url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        if response.status_code != 200:
            logger.warning(f"封面下载失败: {cover_url}")
            return None

        # 打开图片
        img = Image.open(BytesIO(response.content))
        original_width, original_height = img.size

        # 创建番号子文件夹
        safe_code = re.sub(r'[<>:"/\\|?*]', '_', code)
        code_dir = save_dir / safe_code
        code_dir.mkdir(parents=True, exist_ok=True)

        paths = {}

        # 1. Fanart (横向 1920x1080) — 先生成 fanart
        fanart_path = code_dir / f"{safe_code}-fanart.jpg"
        if original_width > original_height:
            # 原图是横向
            fanart = img.copy()
            fanart.thumbnail((1920, 1080), Image.Resampling.LANCZOS)
        else:
            # 原图是竖向，裁切中间部分
            fanart = _crop_to_landscape(img, 1920, 1080)
        fanart = fanart.convert("RGB")
        fanart.save(fanart_path, "JPEG", quality=90)
        paths["fanart"] = str(fanart_path)

        # 2. Poster (竖向 1000x1500) — 从 fanart 右半边中间截取
        poster_path = code_dir / f"{safe_code}-poster.jpg"
        poster = _crop_poster_from_right(fanart, 1000, 1500)
        poster = poster.convert("RGB")
        poster.save(poster_path, "JPEG", quality=90)
        paths["poster"] = str(poster_path)

        # 3. Thumb (缩略图 300x450) — 从 poster 缩放
        thumb_path = code_dir / f"{safe_code}-thumb.jpg"
        thumb = poster.copy()
        thumb.thumbnail((300, 450), Image.Resampling.LANCZOS)
        thumb = thumb.convert("RGB")
        thumb.save(thumb_path, "JPEG", quality=85)
        paths["thumb"] = str(thumb_path)

        # 返回文件夹路径
        paths["folder"] = str(code_dir)

        logger.info(f"封面裁切成功: {code}")
        return paths

    except Exception as e:
        logger.error(f"封面处理失败 {code}: {e}")
        return None


def regenerate_poster_from_fanart(fanart_path: str, poster_path: str, thumb_path: str = None) -> bool:
    """
    功能: 从已有的 fanart 图片重新生成 poster（右半边中间截取）和 thumb
    文件: scraper.py
    参数:
        fanart_path: fanart 图片路径
        poster_path: 要保存的 poster 路径
        thumb_path: 要保存的 thumb 路径（可选）
    返回: True/False
    说明:
        - 从 fanart 右半边中间部分截取竖向 1000x1500 poster
        - poster 右半部分通常包含女演员全身照
    """
    if not PIL_AVAILABLE:
        return False

    try:
        fanart = Image.open(fanart_path)
        # 生成 poster：从 fanart 右半边中间截取
        poster = _crop_poster_from_right(fanart, 1000, 1500)
        poster = poster.convert("RGB")
        poster.save(poster_path, "JPEG", quality=90)

        # 生成 thumb：从 poster 缩放
        if thumb_path:
            thumb = poster.copy()
            thumb.thumbnail((300, 450), Image.Resampling.LANCZOS)
            thumb = thumb.convert("RGB")
            thumb.save(thumb_path, "JPEG", quality=85)

        logger.info(f"从 fanart 重新生成 poster: {poster_path}")
        return True

    except Exception as e:
        logger.error(f"重新生成 poster 失败: {e}")
        return False


# ===============================================================================
# 统一的刮削后处理函数（核心重构）
# ===============================================================================

def save_movie_assets(movie_data: dict, covers_dir: Path, local_video_path: str = None) -> dict:
    """
    功能: 统一的刮削后处理函数（下载封面 + 生成 NFO）
    文件: scraper.py
    参数:
        movie_data: 影片数据字典（必须包含 code 和 cover_url）
        covers_dir: 封面保存根目录
        local_video_path: 本地视频文件路径（可选）
    返回: 更新后的 movie_data（增加 fanart_path, poster_path, thumb_path）
    说明:
        - 这是唯一的刮削后处理入口
        - 所有刮削流程（手动/批量/修复）都应该调用此函数
        - 避免重复代码，确保一致性
    """
    code = movie_data.get("code", "")
    cover_url = movie_data.get("cover_url", "")

    if not code:
        return movie_data

    # 安全文件名
    safe_code = re.sub(r'[<>:"/\\|?*]', '_', code)
    code_dir = covers_dir / safe_code
    code_dir.mkdir(parents=True, exist_ok=True)

    # 1. 下载并裁切封面
    if cover_url and PIL_AVAILABLE:
        crop_paths = download_and_crop_cover(cover_url, code, covers_dir)
        if crop_paths:
            movie_data["fanart_path"] = crop_paths.get("fanart")
            movie_data["poster_path"] = crop_paths.get("poster")
            movie_data["thumb_path"] = crop_paths.get("thumb")
            logger.info(f"封面下载成功: {code}")

    # 2. 生成 NFO 文件
    nfo_path = code_dir / f"{safe_code}.nfo"
    if not nfo_path.exists():
        try:
            generate_nfo(movie_data, nfo_path, local_video_path)
            logger.info(f"NFO 生成成功: {code}")
        except Exception as e:
            logger.warning(f"NFO 生成失败 {code}: {e}")

    return movie_data


def _crop_poster_from_right(fanart: Image, target_width: int, target_height: int) -> Image:
    """
    功能: 从 fanart 图片的右半边中间截取竖向 poster
    说明:
        - fanart 是横向图（如 1920x1080）
        - poster 需要竖向比例（如 1000x1500, 比例 2:3）
        - 取 fanart 右半部分（x: width/2 ~ width），纵向居中裁切
        - 这样截取的区域包含封面图右侧的女演员全身照
        - 最后缩放到目标尺寸
    """
    width, height = fanart.size
    target_ratio = target_width / target_height  # 2:3 ≈ 0.667

    # 从右半边取区域
    right_half_width = width // 2
    left = width - right_half_width

    # 计算在右半边中能截取的最大竖向区域
    available_width = right_half_width
    available_height = height

    if available_width / available_height > target_ratio:
        # 右半边更宽，按高度填满，裁切宽度
        new_width = int(available_height * target_ratio)
        # 在右半边内水平居中（稍微偏右，因为人物可能更靠右边缘）
        offset_x = (available_width - new_width) // 2
        crop_left = left + offset_x
        poster = fanart.crop((crop_left, 0, crop_left + new_width, height))
    else:
        # 右半边更高（窄），按宽度填满，纵向居中裁切
        new_height = int(available_width / target_ratio)
        top = (height - new_height) // 2
        poster = fanart.crop((left, top, width, top + new_height))
    
    # 缩放到目标尺寸
    poster = poster.resize((target_width, target_height), Image.Resampling.LANCZOS)
    return poster


def generate_nfo(movie_data: dict, nfo_path: Path, local_video_path: str = None) -> bool:
    """
    功能: 生成 NFO 元数据文件（Kodi/Plex 兼容格式）
    文件: scraper.py
    参数:
        movie_data: 影片数据字典
        nfo_path: NFO 文件保存路径
        local_video_path: 本地视频文件路径（可选）
    返回: True/False
    说明:
        - NFO 格式兼容 Kodi、Plex、Emby 等媒体中心
        - 包含本地视频路径字段
    """
    try:
        # 安全处理 XML 特殊字符
        def escape_xml(text):
            if not text:
                return ""
            text = str(text)
            text = text.replace("&", "&amp;")
            text = text.replace("<", "&lt;")
            text = text.replace(">", "&gt;")
            text = text.replace('"', "&quot;")
            text = text.replace("'", "&apos;")
            return text

        # 构建 NFO 内容
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

        logger.info(f"NFO 文件生成成功: {nfo_path}")
        return True

    except Exception as e:
        logger.error(f"NFO 文件生成失败: {e}")
        return False


def _crop_to_portrait(img: Image, target_width: int, target_height: int) -> Image:
    """裁切为竖向比例"""
    width, height = img.size
    target_ratio = target_width / target_height
    current_ratio = width / height

    if current_ratio > target_ratio:
        # 原图更宽，裁切左右
        new_width = int(height * target_ratio)
        left = (width - new_width) // 2
        return img.crop((left, 0, left + new_width, height))
    else:
        # 原图更高，裁切上下
        new_height = int(width / target_ratio)
        top = (height - new_height) // 2
        return img.crop((0, top, width, top + new_height))


def _crop_to_landscape(img: Image, target_width: int, target_height: int) -> Image:
    """裁切为横向比例"""
    width, height = img.size
    target_ratio = target_width / target_height
    current_ratio = width / height

    if current_ratio > target_ratio:
        # 原图更宽，裁切左右
        new_width = int(height * target_ratio)
        left = (width - new_width) // 2
        return img.crop((left, 0, left + new_width, height))
    else:
        # 原图更高，裁切上下
        new_height = int(width / target_ratio)
        top = (height - new_height) // 2
        return img.crop((0, top, width, top + new_height))


def make_bilingual_title(jp_title: str, cn_title: str = None) -> str:
    """
    功能: 生成双语标题，格式为"中文标题\\n日文标题"
    文件: scraper.py
    参数:
        jp_title: 日文标题
        cn_title: 已翻译的中文标题（可选）
    返回: 双语标题字符串
    依赖: translate_to_chinese
    语法:
        title = make_bilingual_title("日本語のタイトル")
        title = make_bilingual_title("日本語のタイトル", "日文标题")
    """
    # 如果翻译不可用或日文标题为空，返回原文
    if not GOOGLE_TRANSLATE_AVAILABLE or not jp_title:
        return jp_title

    # 如果已提供中文标题，直接使用
    if cn_title:
        return f"{cn_title}\n{jp_title}"

    # 否则自动翻译
    cn_title = translate_to_chinese(jp_title)
    if cn_title and cn_title != jp_title:
        return f"{cn_title}\n{jp_title}"

    return jp_title


# ===============================================================================
# 爬虫基类 - 提供通用功能
# ===============================================================================

# 全局停止检查回调（由 main.py 设置）
_scrape_stop_check = None

def set_stop_check(check_func):
    """设置停止检查回调函数"""
    global _scrape_stop_check
    _scrape_stop_check = check_func

def should_stop():
    """检查是否应该停止刮削"""
    if _scrape_stop_check:
        return _scrape_stop_check()
    return False


class BaseScraper:
    """
    功能: 爬虫基类，所有具体爬虫的父类
    文件: scraper.py
    提供:
        - HTTP 请求封装（带重试）
        - 通用搜索接口（需子类实现）
        - 通用详情获取接口（需子类实现）
        - 影片刮削流程
    依赖: requests.Session, bs4.BeautifulSoup, time.sleep
    """

    def __init__(self, timeout: int = None, delay: float = None):
        """
        功能: 初始化爬虫基类
        参数:
            timeout: 请求超时时间（秒），默认从 config 读取
            delay: 请求间隔时间（秒），默认从 config 读取
        """
        timeout = timeout if timeout is not None else config.SCRAPE_TIMEOUT
        delay = delay if delay is not None else config.DEFAULT_DELAY
        self.timeout = timeout
        self.delay = delay
        # 创建持久的 HTTP Session
        # 语法: requests.Session() 保持连接，提高效率
        self.session = requests.Session()
        # 设置默认请求头
        # 语法: session.headers.update(dict) 更新请求头
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,ja;q=0.7",
            "Connection": "keep-alive",
        })

    def _get(self, url: str, retry: int = 2) -> Optional[BeautifulSoup]:
        """
        功能: 发送 GET 请求并解析 HTML
        文件: scraper.py
        参数:
            url: 目标 URL
            retry: 失败重试次数
        返回: BeautifulSoup 解析后的对象，失败返回 None
        依赖: requests.Session.get, bs4.BeautifulSoup, time.sleep
        语法:
            soup = self._get("https://example.com")
        """
        for i in range(retry):
            # 检查停止信号
            if should_stop():
                logger.info("收到停止信号，中断请求")
                return None

            try:
                # 请求前等待（防止请求过快）
                time.sleep(self.delay)
                # 发送 GET 请求
                # 语法: session.get(url, timeout=超时时间)
                response = self.session.get(url, timeout=self.timeout)

                # 处理 403 禁止访问错误
                if response.status_code == 403:
                    logger.warning(f"403 禁止访问 (尝试 {i+1}/{retry}): {url}")
                    if i < retry - 1:
                        time.sleep(3)  # 等待更长时间后重试
                        continue
                    return None

                # 检查 HTTP 错误
                response.raise_for_status()
                # 解析 HTML 为 BeautifulSoup 对象
                # 语法: BeautifulSoup(html内容, 解析器)
                return BeautifulSoup(response.content, "lxml")

            except requests.exceptions.RequestException as e:
                logger.warning(f"请求失败 (尝试 {i+1}/{retry}): {url}, 错误: {e}")
                if i < retry - 1:
                    time.sleep(2)
                    continue
                return None

        return None

    def search(self, keyword: str) -> List[Dict]:
        """
        功能: 搜索影片（子类必须实现）
        文件: scraper.py
        参数:
            keyword: 搜索关键词（通常是番号）
        返回: 搜索结果列表，每项包含 code, title, cover_url, detail_url 等
        注意: 子类必须重写此方法
        """
        raise NotImplementedError

    def get_detail(self, detail_url: str) -> Optional[Dict]:
        """
        功能: 获取影片详情（子类必须实现）
        文件: scraper.py
        参数:
            detail_url: 影片详情页 URL
        返回: 影片详情字典
        注意: 子类必须重写此方法
        """
        raise NotImplementedError

    def scrape(self, keyword: str) -> Optional[Dict]:
        """
        功能: 刮削影片（搜索 + 获取详情）
        文件: scraper.py
        参数:
            keyword: 搜索关键词
        返回: 影片完整信息字典
        依赖: search(), get_detail()
        语法:
            result = scraper.scrape("IPZZ-792")
        """
        results = self.search(keyword)
        if not results:
            return None

        # 找到精确匹配的影片
        target = None
        # 清理关键词用于匹配
        # 语法: re.sub(正则, 替换, 字符串) 移除非字母数字字符
        keyword_clean = re.sub(r'[^a-zA-Z0-9]', '', keyword.upper())

        for item in results:
            code_clean = re.sub(r'[^a-zA-Z0-9]', '', item.get("code", "").upper())
            # 检查是否匹配
            if keyword_clean in code_clean or code_clean in keyword_clean:
                target = item
                break

        # 如果没有精确匹配，使用第一个结果
        if not target:
            target = results[0]

        # 获取详情页信息
        if target.get("detail_url"):
            detail = self.get_detail(target["detail_url"])
            if detail:
                return detail

        return target


# ===============================================================================
# Avdanyuwiki 爬虫 - 主要数据源
# ===============================================================================

class AvdanyuwikiScraper(BaseScraper):
    """
    功能: Avdanyuwiki 数据源爬虫
    文件: scraper.py
    网站: https://avdanyuwiki.com
    成功率: 4/4 (100%)
    特点: 信息全面，数据完整
    依赖: BaseScraper
    """

    BASE_URL = "https://avdanyuwiki.com"  # 网站基础 URL

    def __init__(self, **kwargs):
        """初始化 Avdanyuwiki 爬虫"""
        super().__init__(**kwargs)
        # 优先发送日语 Accept-Language
        self.session.headers.update({
            "Accept-Language": "ja,en;q=0.7",
        })

    def search(self, keyword: str) -> List[Dict]:
        """
        功能: 搜索 Avdanyuwiki
        文件: scraper.py
        参数:
            keyword: 番号（如 "IPZZ-792"）
        返回: 搜索结果列表
        依赖: _get(), _parse_page_text()
        URL 格式: https://avdanyuwiki.com/?s=KEYWORD
        """
        # 生成多种搜索格式（Avdanyuwiki 可能使用不同格式）
        search_variants = self._generate_search_variants(keyword)
        
        for search_term in search_variants:
            soup = self._get(f"{self.BASE_URL}/?s={quote(search_term)}")

            if not soup:
                continue

            results = []
            page_text = soup.get_text()  # 获取页面纯文本

            # 检查搜索词是否在页面中
            if search_term.upper() not in page_text.upper() and search_term.lower() not in page_text.lower():
                # 检查原始番号是否在页面中
                if keyword.upper() not in page_text.upper():
                    continue

            # 解析页面数据
            data = self._parse_page_text(page_text, soup)

            if data.get("code"):
                results.append(data)
                logger.info(f"Avdanyuwiki 找到 {len(results)} 个结果 (使用格式: {search_term})")
                return results

        logger.warning(f"Avdanyuwiki 未找到: {keyword}")
        return []

    def _generate_search_variants(self, keyword: str) -> List[str]:
        """
        功能: 生成多种搜索格式变体
        文件: scraper.py
        参数:
            keyword: 原始番号（如 "SSIS-254"）
        返回: 搜索变体列表
        说明:
            - SSIS-254 → ["SSIS 254", "SSIS00254", "SSIS254"]
            - 横线替换为空格，补零到5位，去掉横线
        """
        variants = []
        
        # 提取前缀和数字
        match = re.match(r'([A-Z]+)-(\d+)', keyword.upper())
        if match:
            prefix, number = match.groups()
            
            # 1. 横线替换为空格（SSIS 254）
            variants.append(f"{prefix} {number}")
            
            # 2. 补零到5位（SSIS00254）
            if len(number) < 5:
                padded = number.zfill(5)
                variants.append(f"{prefix}{padded}")
            
            # 3. 去掉横线（SSIS254）
            variants.append(f"{prefix}{number}")
            
            # 4. 补零到3位
            if len(number) < 3:
                padded = number.zfill(3)
                variants.append(f"{prefix}{padded}")
        else:
            # 如果没有横线，直接使用
            variants.append(keyword.upper())
        
        return variants

    def _parse_page_text(self, page_text: str, soup: BeautifulSoup) -> Dict:
        """
        功能: 从页面解析影片详细信息
        文件: scraper.py
        参数:
            page_text: 页面纯文本（用于正则匹配）
            soup: BeautifulSoup 对象（用于 DOM 选择器）
        返回: 影片信息字典
        依赖: re.findall, re.search, bs4.select, translate_to_chinese
        """
        detail = {
            "code": "",                    # 影片番号
            "title": "",                   # 标题（含翻译）
            "title_jp": "",                # 日文标题
            "release_date": "",             # 发布日期
            "duration": None,              # 时长（分钟）
            "studio": "",                   # 发行商/レーベル
            "maker": "",                   # 制作商/メーカー
            "director": "",                # 导演/監督
            "cover_url": "",               # 封面图 URL
            "genres": [],                  # 类型/ジャンル
            "actors": [],                  # 女优/出演者
            "actors_male": [],             # 男优/出演男優
            "detail_url": "",              # 详情页 URL
        }

        # --------------------------------------------------------------------------
        # 提取影片番号
        # 语法: re.compile(正则, 标志) 编译正则表达式
        #       re.findall(正则, 文本) 查找所有匹配
        # --------------------------------------------------------------------------
        code_pattern = re.compile(r"([A-Z]{2,10}-\d{2,})", re.IGNORECASE)
        code_matches = code_pattern.findall(page_text)
        if code_matches:
            detail["code"] = code_matches[0].upper()

        # --------------------------------------------------------------------------
        # 提取标题 - 新格式：番号后紧跟标题
        # 格式："SSIS00254"
        #       激イキ109回！痙攣3900回！イキ潮2000cc超え！...
        # --------------------------------------------------------------------------
        # 方法1：查找番号后的第一行日文标题
        lines = page_text.split('\n')
        for i, line in enumerate(lines):
            line = line.strip()
            # 找到包含番号的行
            if detail["code"] and detail["code"].replace("-", "") in line.replace("-", "").upper():
                # 后面几行找标题
                for j in range(i+1, min(i+5, len(lines))):
                    next_line = lines[j].strip()
                    # 标题特征：包含日文且长度>10
                    if len(next_line) > 10 and any('\u3040' <= c <= '\u30ff' for c in next_line):
                        # 排除"出演AV男優"等非标题行
                        if "出演" not in next_line and "ジャンル" not in next_line:
                            detail["title_jp"] = next_line
                            detail["title"] = next_line
                            break
                break

        # 方法2：查找 h1 标签
        if not detail["title_jp"]:
            h1 = soup.find("h1")
            if h1:
                h1_text = h1.get_text(strip=True)
                if len(h1_text) > 10 and any('\u3040' <= c <= '\u30ff' for c in h1_text):
                    detail["title_jp"] = h1_text
                    detail["title"] = h1_text

        # 方法3：查找 h2 标签中的日文内容
        if not detail["title_jp"]:
            h2_tags = soup.find_all("h2")
            for h2 in h2_tags:
                h2_text = h2.get_text(strip=True)
                if any('\u3040' <= c <= '\u30ff' for c in h2_text) and len(h2_text) > 5:
                    detail["title_jp"] = h2_text
                    detail["title"] = h2_text
                    break

        # --------------------------------------------------------------------------
        # 提取发布日期 - 新格式：配信開始日：	2021/11/19
        # --------------------------------------------------------------------------
        date_patterns = [
            r"配信開始日[：:]\s*(\d{4}[/\-]\d{2}[/\-]\d{2})",
            r"商品発売日[：:]\s*(\d{4}[/\-]\d{2}[/\-]\d{2})",
            r"商品発送日[：:]\s*(\d{4}[/\-]\d{2}[/\-]\d{2})",
            r"(\d{4}[/\-]\d{2}[/\-]\d{2})",
        ]
        for pattern in date_patterns:
            date_match = re.search(pattern, page_text)
            if date_match:
                detail["release_date"] = date_match.group(1).replace("/", "-")
                break

        # --------------------------------------------------------------------------
        # 提取时长 - 新格式：収録時間：	120分
        # --------------------------------------------------------------------------
        duration_match = re.search(r"収録時間[：:]\s*(\d+)\s*分", page_text)
        if duration_match:
            detail["duration"] = int(duration_match.group(1))

        # --------------------------------------------------------------------------
        # 提取出演者（女优）- 新格式：出演者：	楓ふうあ
        # --------------------------------------------------------------------------
        actor_match = re.search(r"出演者[：:]\s*([^\n]+?)(?=\n|出演男優|監督|$)", page_text)
        if actor_match:
            actors_text = actor_match.group(1).strip()
            # 按空格或逗号分割
            actors = re.split(r'[,\s、]+', actors_text)
            actors = [a.strip() for a in actors if a.strip() and len(a.strip()) > 1]
            detail["actors"] = actors

        # --------------------------------------------------------------------------
        # 提取出演男優 - 新格式：出演男優： 貞松大輔 , イセドン内村...
        # --------------------------------------------------------------------------
        male_match = re.search(r"出演男優[：:]\s*([^\n]+?)(?=\n|監督|$)", page_text)
        if male_match:
            male_text = male_match.group(1).strip()
            males = re.split(r'[,\s、]+', male_text)
            males = [m.strip() for m in males if m.strip() and len(m.strip()) > 1]
            detail["actors_male"] = males

        # --------------------------------------------------------------------------
        # 提取監督（导演）- 新格式：監督：	嵐山みちる
        # --------------------------------------------------------------------------
        director_match = re.search(r"監督[：:]\s*([^\n]+)", page_text)
        if director_match:
            director = director_match.group(1).strip()
            if director:
                detail["director"] = director

        # --------------------------------------------------------------------------
        # 提取メーカー（制作商）- 新格式：メーカー：	エスワン ナンバーワンスタイル
        # --------------------------------------------------------------------------
        maker_match = re.search(r"メーカー[：:]\s*([^\n]+?)(?=\n|レーベル|$)", page_text)
        if maker_match:
            detail["maker"] = maker_match.group(1).strip()

        # --------------------------------------------------------------------------
        # 提取レーベル（发行商）- 新格式：レーベル：	S1 NO.1 STYLE
        # --------------------------------------------------------------------------
        label_match = re.search(r"レーベル[：:]\s*([^\n]+?)(?=\n|ジャンル|$)", page_text)
        if label_match:
            detail["studio"] = label_match.group(1).strip()

        # --------------------------------------------------------------------------
        # 提取ジャンル（类型）- 新格式：ジャンル：	ハイビジョン  独占配信...
        # --------------------------------------------------------------------------
        genre_match = re.search(r"ジャンル[：:]\s*([^\n]+?)(?=\n|品番|$)", page_text)
        if genre_match:
            genre_text = genre_match.group(1).strip()
            # 按空格分割
            genres = re.split(r'\s+', genre_text)
            genres = [g.strip() for g in genres if g.strip()]
            detail["genres"] = genres

        # --------------------------------------------------------------------------
        # 提取封面图 - 优先 DMM.co.jp 的图片
        # 语法: img.get(属性名, 默认值) 获取标签属性
        # --------------------------------------------------------------------------
        imgs = soup.find_all("img")
        for img in imgs:
            src = img.get("src") or img.get("data-src", "")
            # 查找包含 pics.dmm.co.jp 且有 pl 的图片
            if src and ("pics.dmm.co.jp" in src or "dmm.co.jp" in src) and "pl" in src:
                detail["cover_url"] = src
                break

        # --------------------------------------------------------------------------
        # 处理双语标题 + 提取中文标题
        # --------------------------------------------------------------------------
        if detail.get("title_jp"):
            cn_title = translate_to_chinese(detail["title_jp"])
            if cn_title and cn_title != detail["title_jp"]:
                detail["title_cn"] = cn_title
                detail["title"] = f"{cn_title}\n{detail['title_jp']}"
            else:
                detail["title_cn"] = ""
                detail["title"] = detail["title_jp"]

        return detail

    def get_detail(self, detail_url: str) -> Optional[Dict]:
        """
        功能: 获取详情（Avdanyuwiki 通常没有独立详情页）
        文件: scraper.py
        返回: None（使用搜索结果作为详情）
        """
        return None


# ===============================================================================
# AV-Wiki 爬虫
# ===============================================================================

class AvWikiScraper(BaseScraper):
    """
    功能: AV-Wiki 数据源爬虫
    文件: scraper.py
    网站: https://av-wiki.net
    成功率: 2/4 (50%)
    特点: WordPress 结构，需要点击"阅读全文"
    依赖: BaseScraper
    """

    BASE_URL = "https://av-wiki.net"

    def search(self, keyword: str) -> List[Dict]:
        """
        功能: 搜索 AV-Wiki
        文件: scraper.py
        URL 格式: https://av-wiki.net/?s=KEYWORD&post_type=product
        """
        results = []
        url = f"{self.BASE_URL}/?s={quote(keyword)}&post_type=product"
        soup = self._get(url)

        if not soup:
            return results

        # AV-Wiki 使用 WordPress 结构，查找"続きを読む"链接
        more_links = soup.select('a.more-link, a[href*="/' + keyword.lower() + '/"]')
        for link in more_links:
            href = link.get("href", "")
            # 只保留包含番号的详情链接
            if href and self.BASE_URL in href and keyword.upper() in href.upper():
                # 获取详情页
                detail_soup = self._get(href)
                if detail_soup:
                    # 提取标题
                    title_tag = detail_soup.select_one("h1, .entry-title")
                    title = title_tag.get_text(strip=True) if title_tag else ""

                    # 提取番号
                    code_match = re.search(r"([A-Z]{1,6}-\d{2,5})", detail_soup.get_text(), re.IGNORECASE)
                    code = code_match.group(1).upper() if code_match else keyword.upper()

                    # 提取封面
                    img = detail_soup.select_one("img")
                    cover = img.get("src", "") if img else ""

                    results.append({
                        "code": code,
                        "title": title,
                        "detail_url": href,
                        "cover_url": cover,
                        "source": "av-wiki",
                    })
                    break

        logger.info(f"AV-Wiki 找到 {len(results)} 个结果")
        return results

    def get_detail(self, detail_url: str) -> Optional[Dict]:
        """获取影片详情"""
        soup = self._get(detail_url)
        if not soup:
            return None

        data = self._parse_detail_page(soup, detail_url)
        data["source"] = "av-wiki"
        return data

    def _parse_detail_page(self, soup: BeautifulSoup, url: str) -> Dict:
        """
        功能: 解析 AV-Wiki 详情页面
        文件: scraper.py
        优化: 2026-03-28 - 增强信息提取
        """
        data = make_basic_data(url)

        # 提取标题
        title_tag = soup.select_one("h1, .entry-title")
        if title_tag:
            data["title"] = title_tag.get_text(strip=True)
            data["title_jp"] = data["title"]

        # 提取番号
        code_match = re.search(r"([A-Z]{1,6}-\d{2,5})", soup.get_text(), re.IGNORECASE)
        if code_match:
            data["code"] = code_match.group(1).upper()

        # 查找文章内容
        article = soup.select_one("article, .entry-content, .post-content")
        if article:
            article_text = article.get_text()

            # 提取日期
            date_match = re.search(r"(\d{4}[-/]\d{2}[-/]\d{2})", article_text)
            if date_match:
                data["release_date"] = date_match.group(1).replace("/", "-")

            # 提取演员
            actor_match = re.search(r'出演[：:]\s*([^\n]+)', article_text)
            if actor_match:
                actors_text = actor_match.group(1).strip()
                actors = re.split(r'[,\s、]+', actors_text)
                actors = [a for a in actors if a and len(a) > 1]
                if actors:
                    data["actors"] = actors

            # 提取男优
            male_match = re.search(r'男優[：:]\s*([^\n]+)', article_text)
            if male_match:
                males_text = male_match.group(1).strip()
                males = re.split(r'[,\s、]+', males_text)
                males = [m for m in males if m and len(m) > 1]
                if males:
                    data["actors_male"] = males

            # 提取导演
            director_match = re.search(r'監督[：:]\s*([^\n]+)', article_text)
            if director_match:
                data["director"] = director_match.group(1).strip()

            # 提取制作商
            maker_match = re.search(r'メーカー[：:]\s*([^\n]+)', article_text)
            if maker_match:
                data["maker"] = maker_match.group(1).strip()

            # 提取发行商
            label_match = re.search(r'レーベル[：:]\s*([^\n]+)', article_text)
            if label_match:
                data["studio"] = label_match.group(1).strip()

            # 提取类型
            genre_match = re.search(r'ジャンル[：:]\s*([^\n]+)', article_text)
            if genre_match:
                genre_text = genre_match.group(1).strip()
                genres = re.split(r'[,\s、]+', genre_text)
                genres = [g for g in genres if g and len(g) > 1]
                if genres:
                    data["genres"] = genres

            # 提取时长
            duration_match = re.search(r'(\d+)\s*分', article_text)
            if duration_match:
                data["duration"] = int(duration_match.group(1))

        # 提取封面
        imgs = soup.find_all("img")
        for img in imgs:
            src = img.get("src", "") or img.get("data-src", "")
            # 跳过延迟加载的占位图和 logo
            if src and "data:image" not in src and "favicon" not in src and "logo" not in src:
                # 优先选择 DMM 图片
                if "dmm" in src.lower():
                    data["cover_url"] = src
                    break
                elif not data["cover_url"]:
                    data["cover_url"] = src

        return data


# ===============================================================================
# Avbase 爬虫
# ===============================================================================

class AvbaseScraper(BaseScraper):
    """
    功能: Avbase 数据源爬虫
    文件: scraper.py
    网站: https://www.avbase.net
    成功率: 4/4 (100%)
    特点: 搜索使用 ?q= 参数格式
    依赖: BaseScraper
    URL 格式: https://www.avbase.net/works?q=KEYWORD
    """

    BASE_URL = "https://www.avbase.net"

    def search(self, keyword: str) -> List[Dict]:
        """
        功能: 搜索 Avbase
        文件: scraper.py
        URL 格式: https://www.avbase.net/works?q=KEYWORD
        """
        results = []

        # 使用搜索 URL 格式（不是 /works/CODE）
        search_url = f"{self.BASE_URL}/works?q={quote(keyword)}"
        soup = self._get(search_url)

        if not soup:
            return results

        # 查找搜索结果中的影片链接
        items = soup.select(".item, .movie-item, .works-item, a[href*='/works/']")

        for item in items[:5]:
            # 获取链接
            link = item if item.name == 'a' else item.select_one("a")
            if not link:
                continue

            href = link.get("href", "")
            if not href or "/works/" not in href:
                continue

            # 补全 URL
            if not href.startswith("http"):
                href = self.BASE_URL + href

            # 检查是否包含目标番号
            if keyword.upper() not in href.upper():
                continue

            # 获取详情页
            detail_soup = self._get(href)
            if not detail_soup:
                continue

            # 提取标题
            title_tag = detail_soup.select_one("h1, .title, .works-title")
            title = title_tag.get_text(strip=True) if title_tag else ""

            # 提取番号
            code_match = re.search(r"([A-Z0-9]{1,6}-\d{2,5})", detail_soup.get_text(), re.IGNORECASE)
            code = code_match.group(1).upper() if code_match else keyword.upper()

            # 提取封面
            imgs = detail_soup.select("img")
            cover = ""
            for img in imgs:
                src = img.get("src", "") or img.get("data-src", "")
                if src and "favicon" not in src.lower() and "logo" not in src.lower():
                    cover = src
                    break

            results.append({
                "code": code,
                "title": title,
                "detail_url": href,
                "cover_url": cover,
                "source": "avbase",
            })
            break

        logger.info(f"Avbase 找到 {len(results)} 个结果")
        return results

    def get_detail(self, detail_url: str) -> Optional[Dict]:
        """获取影片详情"""
        soup = self._get(detail_url)
        if not soup:
            return None

        data = self._parse_detail_page(soup, detail_url)
        data["source"] = "avbase"
        return data

    def _parse_detail_page(self, soup: BeautifulSoup, url: str) -> Dict:
        """
        功能: 解析 Avbase 详情页面
        文件: scraper.py
        优化: 2026-03-28 - 增强信息提取，正确提取演员/时长/导演
        """
        data = make_basic_data(url)
        page_text = soup.get_text()

        # 提取标题
        title_tag = soup.select_one("h1, .title, .works-title")
        if title_tag:
            data["title"] = title_tag.get_text(strip=True)
            data["title_jp"] = data["title"]

        # 提取番号
        code_match = re.search(r"([A-Z0-9]{1,6}-\d{2,5})", page_text, re.IGNORECASE)
        if code_match:
            data["code"] = code_match.group(1).upper()

        # 提取日期
        date_match = re.search(r"(\d{4}[-/]\d{2}[-/]\d{2})", page_text)
        if date_match:
            data["release_date"] = date_match.group(1).replace("/", "-")

        # 提取封面（优先 DMM 图片）
        imgs = soup.find_all("img")
        for img in imgs:
            src = img.get("src", "") or img.get("data-src", "")
            if src and "dmm" in src.lower() and "pl" in src:
                data["cover_url"] = src
                break

        # 提取演员 - 从 /talents/ 链接中提取
        actor_links = soup.select('a[href*="/talents/"]')
        if actor_links:
            actors = [link.get_text(strip=True) for link in actor_links if link.get_text(strip=True)]
            if actors:
                # 去重（保持顺序）
                seen = set()
                unique_actors = []
                for actor in actors:
                    if actor not in seen:
                        seen.add(actor)
                        unique_actors.append(actor)
                data["actors"] = unique_actors

        # 提取时长 - 从页面文本中提取 "収録分数120"
        duration_match = re.search(r"収録分数\s*(\d+)", page_text)
        if duration_match:
            data["duration"] = int(duration_match.group(1))

        # 提取制作商 - 从页面文本中提取 "メーカー..."
        # 查找 "メーカー" 关键词后的文本
        lines = page_text.split('\n')
        for i, line in enumerate(lines):
            line = line.strip()
            if line == "メーカー" and i+1 < len(lines):
                # 下一行是制作商名称
                maker = lines[i+1].strip()
                if maker and len(maker) < 50:
                    data["maker"] = maker
                    break
            elif line.startswith("メーカー"):
                # 同一行包含制作商名称
                maker = line.replace("メーカー", "").strip()
                if maker and len(maker) < 50:
                    data["maker"] = maker
                    break

        # 提取发行商 - 从页面文本中提取 "レーベル..."
        for i, line in enumerate(lines):
            line = line.strip()
            if line == "レーベル" and i+1 < len(lines):
                label = lines[i+1].strip()
                if label and len(label) < 50:
                    data["studio"] = label
                    break
            elif line.startswith("レーベル"):
                label = line.replace("レーベル", "").strip()
                if label and len(label) < 50:
                    data["studio"] = label
                    break

        # 提取导演 - 从页面文本中提取 "監督..."
        for i, line in enumerate(lines):
            line = line.strip()
            if line == "監督" and i+1 < len(lines):
                director = lines[i+1].strip()
                if director and len(director) < 30:
                    data["director"] = director
                    break
            elif line.startswith("監督"):
                director = line.replace("監督", "").strip()
                if director and len(director) < 30:
                    data["director"] = director
                    break

        # 提取类型 - 从 "タグ" 后面的关键词提取
        tag_keywords = ["ギリモザ", "単体作品", "3P・4P", "淫乱・ハード系", "潮吹き", "独占配信"]
        genres = []
        for keyword in tag_keywords:
            if keyword in page_text:
                genres.append(keyword)
        if genres:
            data["genres"] = genres

        return data


# ===============================================================================
# Javcup 爬虫
# ===============================================================================

class FanzaScraper(BaseScraper):
    """
    功能: Fanza (DMM) 数据源爬虫
    文件: scraper.py
    网站: https://www.dmm.co.jp
    特点: DMM 官方站点，数据最全最准
    URL 格式: https://www.dmm.co.jp/mono/dvd/-/detail/=/cid=CODE/
    说明: 需要将番号转换为 DMM 格式（SSIS-254 → ssis254）
          需要设置年龄验证 Cookie
    """

    BASE_URL = "https://www.dmm.co.jp"

    def __init__(self, **kwargs):
        """初始化 Fanza 爬虫"""
        super().__init__(**kwargs)
        # 设置年龄验证 Cookie
        self.session.cookies.set("age_check_done", "1", domain=".dmm.co.jp")

    def search(self, keyword: str) -> List[Dict]:
        """
        功能: 搜索 Fanza (DMM)
        文件: scraper.py
        URL 格式: https://www.dmm.co.jp/mono/dvd/-/detail/=/cid=ssis254/
        优化: 直接访问失败时，使用搜索页面兜底查找
        """
        results = []

        # ========== 第一步：直接按 CID 格式尝试访问 ==========
        # 转换番号格式：SSIS-254 → ssis254
        code_dmm = keyword.upper().replace("-", "").lower()

        # 尝试补零（SSIS254 → ssis00254）
        match = re.match(r'([a-z]+)(\d+)', code_dmm)
        if match:
            prefix, number = match.groups()

            # DMM 格式：补零到 3-5 位，尝试多种格式
            variants = []

            # 1. 原格式
            variants.append(code_dmm)

            # 2. 补零到 3 位
            if len(number) < 3:
                variants.append(f"{prefix}{number.zfill(3)}")

            # 3. 补零到 5 位
            if len(number) < 5:
                variants.append(f"{prefix}{number.zfill(5)}")

            # 遍历尝试
            for variant in variants:
                url = f"{self.BASE_URL}/mono/dvd/-/detail/=/cid={variant}/"
                soup = self._get(url)

                if soup and self._is_valid_page(soup, keyword):
                    # 直接解析详情页，不再返回 search 结果
                    detail = self._parse_detail_page(soup, url)
                    detail["code"] = keyword.upper()
                    detail["source"] = "fanza"
                    logger.info(f"Fanza 找到结果: {url}")
                    return [detail]  # 返回包含完整信息的列表

        # ========== 第二步：搜索页面兜底 ==========
        logger.info(f"Fanza 直接访问未找到，尝试搜索: {keyword}")
        search_result = self._search_via_search_page(keyword)
        if search_result:
            return [search_result]

        logger.warning(f"Fanza 未找到: {keyword}")
        return results

    def _search_via_search_page(self, keyword: str) -> Optional[Dict]:
        """
        功能: 通过 Fanza 搜索页面查找番号
        文件: scraper.py
        说明: 当直接按 CID 访问失败时（如 JERA-16 实际 CID 是 1jera016），
              使用搜索页面找到正确的详情链接
        """
        search_url = f"{self.BASE_URL}/mono/-/search/=/searchstr={keyword}/"
        soup = self._get(search_url)

        if not soup:
            return None

        # 找搜索结果中的详情链接（只看 mono/dvd 或 mono/blu-ray）
        links = soup.select('a[href*="/detail/"]')
        detail_links = []
        for link in links:
            href = link.get('href', '')
            if '/mono/dvd/' in href or '/mono/blu-ray/' in href:
                detail_links.append(href)

        if not detail_links:
            return None

        # 取第一个结果，跳过 DOD（数字发行版）等变体
        target_url = None
        for href in detail_links:
            # 跳过 DOD 版本
            if 'dod' in href.lower():
                continue
            target_url = href
            break

        # 如果只有 DOD 版本，也用
        if not target_url and detail_links:
            target_url = detail_links[0]

        if not target_url:
            return None

        logger.info(f"Fanza 搜索找到链接: {target_url}")

        # 访问详情页
        detail_soup = self._get(target_url)
        if not detail_soup:
            return None

        data = self._parse_detail_page(detail_soup, target_url)
        data["code"] = keyword.upper()
        data["source"] = "fanza"
        data["detail_url"] = target_url
        return data

    def _is_valid_page(self, soup: BeautifulSoup, keyword: str) -> bool:
        """检查页面是否有效（避免 404 或空页面）"""
        page_text = soup.get_text()
        # 检查是否包含番号关键词
        return keyword.upper() in page_text.upper() or keyword.upper().replace("-", "") in page_text.upper()

    def scrape(self, keyword: str) -> Optional[Dict]:
        """
        功能: 刮削影片（覆盖父类方法，直接返回详情）
        文件: scraper.py
        """
        results = self.search(keyword)
        if results:
            return results[0]  # search() 已返回完整详情
        return None

    def get_detail(self, detail_url: str) -> Optional[Dict]:
        """获取影片详情"""
        soup = self._get(detail_url)
        if not soup:
            return None

        data = self._parse_detail_page(soup, detail_url)
        data["source"] = "fanza"
        return data

    def _parse_detail_page(self, soup: BeautifulSoup, url: str) -> Dict:
        """
        功能: 解析 Fanza 详情页面
        文件: scraper.py
        优化: 2026-03-28 - 提取完整信息
        """
        data = make_basic_data(url)
        page_text = soup.get_text()

        # 提取标题
        title_tag = soup.select_one("h1, #title")
        if title_tag:
            title = title_tag.get_text(strip=True)
            data["title"] = title
            data["title_jp"] = title

        # 提取番号
        code_match = re.search(r"([A-Z]{2,6}-\d{2,5})", page_text, re.IGNORECASE)
        if code_match:
            data["code"] = code_match.group(1).upper()

        # 提取日期 - 尝试多种格式
        date_patterns = [
            r"(\d{4}年\d{2}月\d{2}日)",  # 2021年11月19日
            r"発売日[：:]\s*(\d{4}/\d{2}/\d{2})",  # 発売日：2021/11/19
            r"(\d{4}/\d{2}/\d{2})",  # 2021/11/19
        ]
        for pattern in date_patterns:
            date_match = re.search(pattern, page_text)
            if date_match:
                date_str = date_match.group(1)
                # 转换格式：2021年11月19日 → 2021-11-19
                date_str = re.sub(r'[年月]', '-', date_str).replace('日', '').replace('/', '-')
                data["release_date"] = date_str
                break

        # 提取时长
        duration_match = re.search(r"(\d+)\s*分", page_text)
        if duration_match:
            data["duration"] = int(duration_match.group(1))

        # 提取女演员（出演者）
        actor_links = soup.select('a[href*="article=actress"], a[href*="actress"]')
        if actor_links:
            actors = []
            for link in actor_links:
                text = link.get_text(strip=True)
                # 过滤干扰项
                if text and text not in ["AV女優一覧", "AV女優", "女優一覧", "一覧"]:
                    actors.append(text)
            if actors:
                # 去重（保持顺序）
                seen = set()
                unique_actors = []
                for actor in actors:
                    if actor not in seen:
                        seen.add(actor)
                        unique_actors.append(actor)
                data["actors"] = unique_actors

        # 提取男演员（出演男優）- 从页面文本提取
        male_actor_match = re.search(r"出演男優[：:]\s*([^\n]+)", page_text)
        if male_actor_match:
            male_actors_text = male_actor_match.group(1).strip()
            # 按斜杠或逗号分割
            male_actors = [a.strip() for a in re.split(r'[/、,，]', male_actors_text) if a.strip()]
            if male_actors:
                data["actors_male"] = male_actors

        # 提取制作商（メーカー）
        maker_link = soup.select_one('a[href*="article=maker"]')
        if maker_link:
            data["maker"] = maker_link.get_text(strip=True)

        # 提取发行商（レーベル）
        label_link = soup.select_one('a[href*="article=label"]')
        if label_link:
            data["studio"] = label_link.get_text(strip=True)

        # 提取导演（監督）
        director_link = soup.select_one('a[href*="article=director"]')
        if director_link:
            director = director_link.get_text(strip=True)
            # 排除干扰项
            if director and director not in ["Blu-ray商品", "DVD商品", "商品一覧"]:
                data["director"] = director

        # 如果链接没找到，从页面文本提取
        if not data.get("director"):
            director_match = re.search(r"監督[：:]\s*([^\n]+)", page_text)
            if director_match:
                director = director_match.group(1).strip()
                if director:
                    data["director"] = director

        # 提取类型
        genre_links = soup.select('a[href*="article=genre"]')
        if genre_links:
            genres = [link.get_text(strip=True) for link in genre_links if link.get_text(strip=True)]
            if genres:
                data["genres"] = genres

        # 提取封面
        img = soup.select_one('img[src*="pics.dmm"]')
        if img:
            src = img.get("src", "") or img.get("data-src", "")
            # 替换为高清封面
            if src and "ps.jpg" in src:
                src = src.replace("ps.jpg", "pl.jpg")
            data["cover_url"] = src

        return data


class JavcupScraper(BaseScraper):
    """
    功能: Javcup 数据源爬虫
    文件: scraper.py
    网站: https://javcup.com
    成功率: 2/4 (50%)
    特点: 备用数据源
    依赖: BaseScraper
    URL 格式: https://javcup.com/search?q=KEYWORD
    """

    BASE_URL = "https://javcup.com"

    def search(self, keyword: str) -> List[Dict]:
        """
        功能: 搜索 Javcup
        文件: scraper.py
        URL 格式: https://javcup.com/search?q=KEYWORD
        """
        results = []

        url = f"{self.BASE_URL}/search?q={quote(keyword)}"
        soup = self._get(url)

        if not soup:
            return results

        # 找电影链接
        links = soup.select('a[href*="/movie/"]')
        for link in links:
            href = link.get("href", "")
            if href:
                # 补全URL
                if not href.startswith("http"):
                    href = self.BASE_URL + href

                # 获取详情页
                detail_soup = self._get(href)
                if detail_soup:
                    title_tag = detail_soup.select_one("h1, .title")
                    title = title_tag.get_text(strip=True) if title_tag else ""

                    code_match = re.search(r"([A-Z]{1,6}-\d{2,5})", detail_soup.get_text(), re.IGNORECASE)
                    code = code_match.group(1).upper() if code_match else keyword.upper()

                    img = detail_soup.select_one("img")
                    cover = img.get("src", "") if img else ""

                    results.append({
                        "code": code,
                        "title": title,
                        "detail_url": href,
                        "cover_url": cover,
                        "source": "javcup",
                    })
                    break

        logger.info(f"Javcup 找到 {len(results)} 个结果")
        return results

    def get_detail(self, detail_url: str) -> Optional[Dict]:
        """获取影片详情"""
        soup = self._get(detail_url)
        if not soup:
            return None

        data = self._parse_detail_page(soup, detail_url)
        data["source"] = "javcup"
        return data

    def _parse_detail_page(self, soup: BeautifulSoup, url: str) -> Dict:
        """
        功能: 解析 Javcup 详情页面
        文件: scraper.py
        优化: 2026-03-28 - 修复封面路径，增强信息提取
        """
        data = make_basic_data(url)

        # 提取标题
        title_tag = soup.select_one("h1, .title")
        if title_tag:
            title = title_tag.get_text(strip=True)
            # 去除番号前缀（如 "SSIS-254 标题..."）
            if title and "-" in title:
                parts = title.split(None, 1)
                if len(parts) > 1 and re.match(r'^[A-Z]+-\d+', parts[0]):
                    title = parts[1]
            data["title"] = title
            data["title_jp"] = title

        # 提取番号
        code_match = re.search(r"([A-Z]{1,6}-\d{2,5})", soup.get_text(), re.IGNORECASE)
        if code_match:
            data["code"] = code_match.group(1).upper()

        # 提取日期
        date_match = re.search(r"(\d{4}[-/]\d{2}[-/]\d{2})", soup.get_text())
        if date_match:
            data["release_date"] = date_match.group(1).replace("/", "-")

        # 提取演员
        actor_tags = soup.select(".actress, .actor, .performer")
        if actor_tags:
            actors = [tag.get_text(strip=True) for tag in actor_tags if tag.get_text(strip=True)]
            if actors:
                data["actors"] = actors

        # 提取封面（修复相对路径）
        imgs = soup.find_all("img")
        for img in imgs:
            src = img.get("src", "") or img.get("data-src", "")
            if src and "favicon" not in src and "logo" not in src and "javcup.png" not in src:
                # 修复相对路径
                if src.startswith("/"):
                    src = self.BASE_URL + src
                data["cover_url"] = src
                break

        return data


# ===============================================================================
# 辅助函数
# ===============================================================================

def make_basic_data(url: str) -> Dict:
    """
    功能: 生成影片基础数据结构
    文件: scraper.py
    参数:
        url: 详情页 URL
    返回: 包含所有字段的字典
    用途: 统一数据格式，便于合并来自不同数据源的信息
    """
    return {
        "code": "",
        "title": "",
        "title_jp": "",
        "release_date": "",
        "duration": None,
        "studio": "",
        "maker": "",
        "director": "",
        "cover_url": "",
        "genres": [],
        "actors": [],
        "actors_male": [],
        "detail_url": url,
    }


# ===============================================================================
# 已禁用的爬虫（代码保留，暂不使用）
# ===============================================================================

class JavDBScraper(BaseScraper):
    """
    功能: JavDB 数据源爬虫（已禁用）
    文件: scraper.py
    状态: 已禁用 - 403 禁止访问
    依赖: BaseScraper
    未来: 等待更好的反反爬虫方案
    """
    # ... 代码保留，用于未来参考


class JavBusScraper(BaseScraper):
    """
    功能: JavBus 数据源爬虫（已禁用）
    文件: scraper.py
    状态: 已禁用 - 域名失效
    """
    pass


class JavbooksScraper(BaseScraper):
    """
    功能: Javbooks 数据源爬虫（已禁用）
    文件: scraper.py
    状态: 已禁用 - 站点失效
    """
    pass


class JavhooScraper(BaseScraper):
    """
    功能: Javhoo 数据源爬虫（已禁用）
    文件: scraper.py
    状态: 已禁用 - 404 Not Found
    """
    pass


class JavdScraper(BaseScraper):
    """
    功能: Javd 数据源爬虫（已禁用）
    文件: scraper.py
    状态: 已禁用 - 404 Not Found
    """
    pass


class JavInfoScraper(BaseScraper):
    """
    功能: Jav情报站数据源爬虫（已禁用）
    文件: scraper.py
    状态: 已禁用 - 需要 hash 验证
    """
    pass


class MultiScraper:
    """
    功能: 旧版多数据源爬虫（已弃用）
    文件: scraper.py
    替代: EnhancedMultiScraper
    """
    pass


# ===============================================================================
# 增强型多源爬虫
# ===============================================================================

class EnhancedMultiScraper:
    """
    功能: 增强型多数据源爬虫 - 综合所有启用的数据源
    文件: scraper.py
    特点: 
        - 从 config.py 读取启用的数据源
        - 按优先级顺序尝试
        - 智能合并来自不同源的数据
    依赖: config.get_enabled_sources, 各具体爬虫类
    使用语法:
        scraper = EnhancedMultiScraper()
        result = scraper.scrape("IPZZ-792")
    """

    def __init__(self):
        """初始化爬虫，从配置加载启用的数据源"""
        self.scrapers = []
        self._init_scrapers()

    def _init_scrapers(self):
        """
        功能: 根据配置初始化爬虫实例
        文件: scraper.py
        依赖: config.get_enabled_sources, scraper_map
        """
        # 爬虫类映射表
        scraper_map = {
            "fanza": FanzaScraper,
            "avbase": AvbaseScraper,
            "av-wiki": AvWikiScraper,
            "javcup": JavcupScraper,
            "avdanyuwiki": AvdanyuwikiScraper,
        }

        # 从配置获取启用的数据源（按 priority 排序）
        for source in config.get_enabled_sources():
            source_id = source["id"]
            # 检查是否在爬虫映射表中
            if source_id in scraper_map:
                scraper_class = scraper_map[source_id]
                # 如果有反爬，增加请求延迟
                delay = config.DEFAULT_DELAY * (2 if source.get("anti_bot") else 1)
                self.scrapers.append(scraper_class(delay=delay))

    def scrape(self, keyword: str) -> Optional[Dict]:
        """
        功能: 尝试多个数据源刮削
        文件: scraper.py
        参数:
            keyword: 搜索关键词（番号）
        返回: 影片信息字典，全部失败返回 None
        算法:
            1. 按优先级遍历所有启用的爬虫
            2. 第一个成功的爬虫返回结果
            3. 只使用第一个成功的数据源，不再合并多个源
        """
        for scraper in self.scrapers:
            logger.info(f"尝试数据源: {scraper.__class__.__name__}")
            try:
                result = scraper.scrape(keyword)
                if result and result.get("code"):
                    logger.info(f"OK 成功从 {scraper.__class__.__name__} 获取数据")

                    # 处理双语标题 + 提取中文标题
                    if result.get("title_jp") and not result.get("title"):
                        cn_title = translate_to_chinese(result["title_jp"])
                        if cn_title and cn_title != result["title_jp"]:
                            result["title_cn"] = cn_title
                            result["title"] = f"{cn_title}\n{result['title_jp']}"
                        else:
                            result["title_cn"] = ""
                            result["title"] = result["title_jp"]
                    elif result.get("title_jp") and "\n" not in result.get("title", ""):
                        cn_title = translate_to_chinese(result["title_jp"])
                        if cn_title and cn_title != result["title_jp"]:
                            result["title_cn"] = cn_title
                            result["title"] = f"{cn_title}\n{result['title_jp']}"

                    # 如果没有提取到标题，用 code 作为兜底标题（避免数据库 NOT NULL 约束报错）
                    if result.get("code") and not result.get("title"):
                        result["title"] = f"[{result['code']}]（标题待补充）"
                        result["title_cn"] = ""

                    return result

            except Exception as e:
                logger.warning(f"X {scraper.__class__.__name__} 失败: {e}")
                continue

        return None


# ===============================================================================
# 便捷函数
# ===============================================================================

def scrape_movie_enhanced(keyword: str, save_cover: bool = True) -> Optional[Dict]:
    """
    功能: 增强版刮削函数（推荐使用）
    文件: scraper.py
    参数:
        keyword: 搜索关键词（番号）
        save_cover: 是否保存封面到本地
    返回: 影片信息字典
    依赖: EnhancedMultiScraper
    使用语法:
        result = scrape_movie_enhanced("IPZZ-792")
        if result:
            print(result["title"])
    """
    scraper = EnhancedMultiScraper()
    return scraper.scrape(keyword)


# 兼容性别名（main.py 中的旧代码导入 scrape_movie）
scrape_movie = scrape_movie_enhanced


# ===============================================================================
# 爬虫测试函数
# ===============================================================================

def test_all_scrapers(keyword: str = "ABC-123") -> Dict:
    """
    功能: 测试所有爬虫的可用性
    文件: scraper.py
    参数:
        keyword: 测试用关键词
    返回: 各爬虫测试结果字典
    使用:
        python scraper.py
    """
    results = {}
    scrapers = [
        ("Avdanyuwiki", AvdanyuwikiScraper),
        ("AvWiki", AvWikiScraper),
        ("Avbase", AvbaseScraper),
        ("Javcup", JavcupScraper),
    ]

    print(f"\n{'='*50}")
    print(f"测试爬虫可用性 - 关键词: {keyword}")
    print(f"{'='*50}\n")

    for name, scraper_class in scrapers:
        try:
            scraper = scraper_class(delay=0.5)
            print(f"测试 {name}...", end=" ")
            result = scraper.search(keyword)
            if result:
                print(f"OK 找到 {len(result)} 个结果")
                results[name] = {"status": "可用", "count": len(result), "sample": result[0]}
            else:
                print(f"X 无结果")
                results[name] = {"status": "无可用数据", "count": 0}
        except Exception as e:
            print(f"X 错误: {str(e)[:50]}")
            results[name] = {"status": f"错误: {str(e)[:30]}", "count": 0, "error": str(e)}

    print(f"\n{'='*50}")
    print("测试完成")
    print(f"{'='*50}\n")

    return results


if __name__ == "__main__":
    # 直接运行此文件测试所有爬虫
    test_all_scrapers("ABC-123")
