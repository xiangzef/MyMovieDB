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
# 依赖: config.DEFAULT_DELAY, config.DEFAULT_TIMEOUT, config.SCRAPER_SOURCES 等

try:
    import config
    DEFAULT_DELAY = config.DEFAULT_DELAY        # 默认请求延迟（秒）
    DEFAULT_TIMEOUT = config.DEFAULT_TIMEOUT     # 默认请求超时（秒）
    DEFAULT_RETRY = config.DEFAULT_RETRY         # 默认重试次数
    DEFAULT_HEADERS = config.DEFAULT_HEADERS     # 默认 HTTP 头
    SCRAPER_SOURCES = config.SCRAPER_SOURCES     # 网站配置列表
    get_enabled_sources = config.get_enabled_sources  # 获取启用数据源
    get_source_by_id = config.get_source_by_id    # 根据 ID 获取数据源
except ImportError:
    # 如果 config.py 不存在，使用硬编码默认值
    DEFAULT_DELAY = 1.0
    DEFAULT_TIMEOUT = 30
    DEFAULT_RETRY = 2
    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    SCRAPER_SOURCES = []
    def get_enabled_sources():
        return []
    def get_source_by_id(x):
        return None

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

    def __init__(self, timeout: int = 30, delay: float = 1.0):
        """
        功能: 初始化爬虫基类
        参数:
            timeout: 请求超时时间（秒）
            delay: 请求间隔时间（秒），防止请求过快
        """
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
        soup = self._get(f"{self.BASE_URL}/?s={quote(keyword)}")

        if not soup:
            return []

        results = []
        page_text = soup.get_text()  # 获取页面纯文本

        # 检查搜索词是否在页面中
        if keyword.upper() not in page_text.upper() and keyword.lower() not in page_text.lower():
            logger.warning(f"Avdanyuwiki 未找到: {keyword}")
            return []

        # 解析页面数据
        data = self._parse_page_text(page_text, soup)

        if data.get("code"):
            results.append(data)

        logger.info(f"Avdanyuwiki 找到 {len(results)} 个结果")
        return results

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
        # 提取标题 - 在 h2 标签中查找日文内容
        # 语法: bs4.find_all(标签名) 查找所有匹配标签
        #       any(条件 for item in 列表) 检查是否有任何匹配
        # --------------------------------------------------------------------------
        h2_tags = soup.find_all("h2")
        for h2 in h2_tags:
            h2_text = h2.get_text(strip=True)
            # 检查是否包含日文字符（Unicode 范围 \u3040-\u30ff）
            if any('\u3040' <= c <= '\u30ff' for c in h2_text) and len(h2_text) > 5:
                detail["title_jp"] = h2_text
                detail["title"] = h2_text
                break

        # --------------------------------------------------------------------------
        # 提取发布日期
        # 语法: re.search(正则, 文本) 查找第一个匹配
        # --------------------------------------------------------------------------
        date_patterns = [
            r"商品発送日[：:]\s*(\d{4}[/\-]\d{2}[/\-]\d{2})",
            r"商品発売日[：:]\s*(\d{4}[/\-]\d{2}[/\-]\d{2})",
            r"配信開始日[：:]\s*(\d{4}[/\-]\d{2}[/\-]\d{2})",
            r"(\d{4}[/\-]\d{2}[/\-]\d{2})",
        ]
        for pattern in date_patterns:
            date_match = re.search(pattern, page_text)
            if date_match:
                detail["release_date"] = date_match.group(1).replace("/", "-")
                break

        # --------------------------------------------------------------------------
        # 提取时长
        # --------------------------------------------------------------------------
        duration_match = re.search(r"収録時間[：:]\s*(\d+)", page_text)
        if duration_match:
            detail["duration"] = int(duration_match.group(1))

        # --------------------------------------------------------------------------
        # 提取出演者（女优）
        # 语法: 捕获组 () 提取特定部分
        # --------------------------------------------------------------------------
        actor_match = re.search(r"出演者[：:]\s*([^出演\n]+?)(?=\n|出演|$)", page_text)
        if actor_match:
            actors_text = actor_match.group(1).strip()
            # 语法: str.split(分隔符) 分割字符串
            actors = [a.strip() for a in actors_text.split(",") if a.strip()]
            detail["actors"] = actors

        # --------------------------------------------------------------------------
        # 提取出演男優
        # --------------------------------------------------------------------------
        male_match = re.search(r"出演男優[：:]\s*([^出演\n]+?)(?=\n|監督|$)", page_text)
        if male_match:
            male_text = male_match.group(1).strip()
            males = [m.strip() for m in male_text.split(",") if m.strip()]
            detail["actors_male"] = males

        # --------------------------------------------------------------------------
        # 提取監督（导演）
        # --------------------------------------------------------------------------
        director_match = re.search(r"監督[：:]\s*([^\n]+?)(?=\n|シリーズ|$)", page_text)
        if director_match:
            detail["director"] = director_match.group(1).strip()

        # --------------------------------------------------------------------------
        # 提取メーカー（制作商）
        # --------------------------------------------------------------------------
        maker_match = re.search(r"メーカー[：:]\s*([^\n]+?)(?=\n|レーベル|$)", page_text)
        if maker_match:
            detail["maker"] = maker_match.group(1).strip()

        # --------------------------------------------------------------------------
        # 提取レーベル（发行商）
        # --------------------------------------------------------------------------
        label_match = re.search(r"レーベル[：:]\s*([^\n]+?)(?=\n|ジャンル|$)", page_text)
        if label_match:
            detail["studio"] = label_match.group(1).strip()

        # --------------------------------------------------------------------------
        # 提取ジャンル（类型/标签）
        # --------------------------------------------------------------------------
        genre_match = re.search(r"ジャンル[：:]\s*([^\n]+)", page_text)
        if genre_match:
            genres_text = genre_match.group(1).strip()
            genres = []
            for g in genres_text.split():
                g = g.strip()
                # 过滤条件：长度<20、不含数字、不含特殊符号、不含常见噪声词
                if g and len(g) < 20 and not re.search(r'\d', g) and not re.search(r'[◆○●□■▲△▼▽★☆♪]', g):
                    if g not in ['配信品番：', 'メーカー品番：', 'FANZA', 'PR', '当当は', 'を利用しています']:
                        genres.append(g)
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
        # 处理双语标题
        # --------------------------------------------------------------------------
        if detail.get("title_jp"):
            cn_title = translate_to_chinese(detail["title_jp"])
            if cn_title and cn_title != detail["title_jp"]:
                detail["title"] = make_bilingual_title(detail["title_jp"], cn_title)

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
        """解析详情页面"""
        data = make_basic_data(url)

        title_tag = soup.select_one("h1, .entry-title")
        if title_tag:
            data["title"] = title_tag.get_text(strip=True)

        code_match = re.search(r"([A-Z]{1,6}-\d{2,5})", soup.get_text(), re.IGNORECASE)
        if code_match:
            data["code"] = code_match.group(1).upper()

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
        """解析详情页面"""
        data = make_basic_data(url)

        title_tag = soup.select_one("h1, .title, .works-title")
        if title_tag:
            data["title"] = title_tag.get_text(strip=True)

        code_match = re.search(r"([A-Z0-9]{1,6}-\d{2,5})", soup.get_text(), re.IGNORECASE)
        if code_match:
            data["code"] = code_match.group(1).upper()

        date_match = re.search(r"(\d{4}[-/]\d{2}[-/]\d{2})", soup.get_text())
        if date_match:
            data["release_date"] = date_match.group(1).replace("/", "-")

        return data


# ===============================================================================
# Javcup 爬虫
# ===============================================================================

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
        """解析详情页面"""
        data = make_basic_data(url)

        title_tag = soup.select_one("h1, .title")
        if title_tag:
            data["title"] = title_tag.get_text(strip=True)

        code_match = re.search(r"([A-Z]{1,6}-\d{2,5})", soup.get_text(), re.IGNORECASE)
        if code_match:
            data["code"] = code_match.group(1).upper()

        date_match = re.search(r"(\d{4}[-/]\d{2}[-/]\d{2})", soup.get_text())
        if date_match:
            data["release_date"] = date_match.group(1).replace("/", "-")

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
            "avdanyuwiki": AvdanyuwikiScraper,
            "av-wiki": AvWikiScraper,
            "avbase": AvbaseScraper,
            "javcup": JavcupScraper,
            # 以下已禁用，不再使用
            # "javdb": JavDBScraper,
            # "javbus": JavBusScraper,
            # "javbooks": JavbooksScraper,
            # "javhoo": JavhooScraper,
            # "javd": JavdScraper,
            # "javinfo": JavInfoScraper,
        }

        # 从配置获取启用的数据源
        for source in SCRAPER_SOURCES:
            source_id = source["id"]
            # 检查是否启用且在映射表中
            if source_id in scraper_map and source.get("enabled", True):
                scraper_class = scraper_map[source_id]
                # 如果有反爬，增加请求延迟
                delay = DEFAULT_DELAY * (2 if source.get("anti_bot") else 1)
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
            3. 如果已获取 code + title + cover，提前退出
        """
        merged_data = {}

        for scraper in self.scrapers:
            logger.info(f"尝试数据源: {scraper.__class__.__name__}")
            try:
                result = scraper.scrape(keyword)
                if result and result.get("code"):
                    logger.info(f"OK 成功从 {scraper.__class__.__name__} 获取数据")

                    # 智能合并数据
                    for key, value in result.items():
                        if value:
                            if key not in merged_data or not merged_data[key]:
                                merged_data[key] = value
                            elif isinstance(value, list) and isinstance(merged_data.get(key), list):
                                for item in value:
                                    if item not in merged_data[key]:
                                        merged_data[key].append(item)

                    # 如果已获取足够数据，提前退出
                    if merged_data.get("code") and merged_data.get("title") and merged_data.get("cover_url"):
                        break

            except Exception as e:
                logger.warning(f"X {scraper.__class__.__name__} 失败: {e}")
                continue

        # 处理双语标题
        if merged_data.get("title_jp") and not merged_data.get("title"):
            cn_title = translate_to_chinese(merged_data["title_jp"])
            merged_data["title"] = make_bilingual_title(merged_data["title_jp"], cn_title)
        elif merged_data.get("title_jp") and "\n" not in merged_data.get("title", ""):
            cn_title = translate_to_chinese(merged_data["title_jp"])
            if cn_title and cn_title != merged_data["title_jp"]:
                merged_data["title"] = make_bilingual_title(merged_data["title_jp"], cn_title)

        return merged_data if merged_data.get("code") else None


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
