"""
增强型刮削器 - 基于 JavSP 多源并发架构

核心设计：
1. 多源并发：同时发起多个源请求，最快返回的获胜
2. CloudFlare 绕过：cloudscraper + requests fallback + cookie injection
3. 配置驱动：从 config.ini 读取数据源 URL 和设置
4. 速率控制：每请求间隔 configurable delay
5. Cookie 支持：可注入浏览器 Cookie 通过 CloudFlare 检测

用法：
    from enhanced_scraper import EnhancedScraper
    scraper = EnhancedScraper()
    result = scraper.scrape('VENX-034')
    if result:
        print(result['title'], result['maker'], result['cover_url'])
"""

import re
import os
import sys
import time
import json
import logging
import requests
import threading
from typing import Optional, Dict, List
from dataclasses import dataclass, field
from pathlib import Path

import config

# cloudscraper 用于绕过 CloudFlare
try:
    import cloudscraper
    CLOUDSCRAPER_AVAILABLE = True
except ImportError:
    CLOUDSCRAPER_AVAILABLE = False
    print("警告: cloudscraper 未安装，将使用普通 requests（可能无法绕过 CloudFlare）")

logger = logging.getLogger(__name__)

# ─── 通用请求头 ────────────────────────────────────────
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}

# ─── 数据类 ────────────────────────────────────────────
@dataclass
class ScrapeResult:
    """单个源刮取结果"""
    source: str           # source id from config.ini
    success: bool
    url: str = ''
    title: str = ''
    title_jp: str = ''
    title_cn: str = ''
    code: str = ''
    maker: str = ''
    studio: str = ''
    director: str = ''
    release_date: str = ''
    duration: int = 0     # 分钟
    genres: List[str] = field(default_factory=list)
    actors: List[str] = field(default_factory=list)
    cover_url: str = ''
    fanart_url: str = ''
    plot: str = ''
    error: str = ''


def _build_config_from_ini() -> 'EnhancedConfig':
    """从 config.ini 构建增强刮削器配置"""
    # 从配置读取全局设置
    delay = config.getfloat("scrape", "default_delay", 1.5)
    timeout = config.getint("scrape", "timeout", 15)
    retry = config.getint("scrape", "default_retry", 2)
    cookie_file = config.get("scrape", "cookie_file", None)

    # 从 sources_json 解析各源 base_url
    sources = config.SCRAPER_SOURCES
    source_urls = {}
    for s in sources:
        sid = s.get("id", "")
        url = s.get("url", "")
        if sid and url:
            # 提取 base_url：去掉 {code} 及其后面的所有内容
            idx = url.find('{code}')
            if idx > 0:
                before = url[:idx]
                # 优先用 ? 之前（query string 开始）作为分割点
                q_pos = before.rfind('?')
                if q_pos != -1:
                    base = before[:q_pos].rstrip('/')
                else:
                    # 没有 ? 则用最后一个 /
                    slash_pos = before.rfind('/')
                    base = before[:slash_pos].rstrip('/') if slash_pos != -1 else before
            else:
                base = url.rstrip('/')
            source_urls[sid] = base

    return EnhancedConfig(
        request_delay=delay,
        timeout=timeout,
        retry=retry,
        parallel_timeout=20.0,
        cookie_file=cookie_file,
        _source_urls=source_urls,
    )


@dataclass
class EnhancedConfig:
    """刮削器配置"""
    # 请求间隔（秒），防止被封
    request_delay: float = 1.5
    # 请求超时（秒）
    timeout: int = 15
    # 重试次数
    retry: int = 2
    # 并发超时（秒），所有源竞争，最快返回的获胜
    parallel_timeout: float = 20.0
    # Cookie 文件路径（用于注入 CloudFlare clearance）
    cookie_file: Optional[str] = None
    # 内部：各数据源 base_url（从 config.ini 解析）
    _source_urls: Dict[str, str] = field(default_factory=dict)

    def get_source_url(self, source_id: str) -> str:
        """获取指定数据源的 base_url"""
        return self._source_urls.get(source_id, '')


# ─── 基础爬虫类 ────────────────────────────────────────
class BaseCrawler:
    """
    爬虫基类，封装通用请求逻辑
    CloudFlare 绕过策略（JavSP 架构）：
    1. 优先使用 cloudscraper（能绕过 CloudFlare）
    2. cloudscraper 失败时 fallback 到普通 requests
    3. 支持从文件注入浏览器 Cookie
    """

    def __init__(self, config: EnhancedConfig = None):
        self.config = config or _build_config_from_ini()
        self.session = self._create_session()
        self._last_request_time = 0

    def _create_session(self):
        """创建请求会话，优先 cloudscraper（CloudFlare 绕过），失败则 fallback"""
        session = requests.Session()
        session.headers.update(DEFAULT_HEADERS)

        if CLOUDSCRAPER_AVAILABLE:
            try:
                scraper = cloudscraper.create_scraper(
                    browser={
                        'browser': 'chrome',
                        'platform': 'windows',
                        'mobile': False,
                    },
                )
                # 复用 headers
                scraper.headers.update(DEFAULT_HEADERS)
                return scraper
            except Exception as e:
                logger.warning(f"cloudscraper 初始化失败，使用普通 requests: {e}")

        return session

    def _rate_limit(self):
        """速率限制：确保两次请求之间有足够间隔"""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.config.request_delay:
            time.sleep(self.config.request_delay - elapsed)
        self._last_request_time = time.time()

    def _get(self, url: str, **kwargs) -> requests.Response:
        """带速率控制的 GET 请求"""
        self._rate_limit()
        kwargs.setdefault('timeout', self.config.timeout)
        kwargs.setdefault('headers', DEFAULT_HEADERS)
        return self.session.get(url, **kwargs)

    def _load_cookies_from_file(self, cookie_file: str = None):
        """从 JSON 文件加载 Cookie（用于手动注入 CloudFlare clearance）"""
        cookie_file = cookie_file or self.config.cookie_file
        if not cookie_file or not os.path.exists(cookie_file):
            return
        try:
            with open(cookie_file, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
            for domain, cookie_list in cookies.items():
                for cookie_dict in cookie_list:
                    self.session.cookies.set(**cookie_dict)
            logger.info(f"已加载 Cookie: {cookie_file}")
        except Exception as e:
            logger.warning(f"Cookie 加载失败: {e}")

    def get(self, url: str, use_cookie: bool = False) -> Optional[requests.Response]:
        """
        发送 GET 请求，失败时自动重试
        策略：cloudscraper 失败 → 普通 requests 重试
        """
        if use_cookie:
            self._load_cookies_from_file()

        last_error = None
        for attempt in range(self.config.retry):
            try:
                resp = self._get(url)
                if resp.status_code == 200:
                    return resp
                elif resp.status_code == 403:
                    last_error = f'HTTP 403 Forbidden (可能遇到 CloudFlare)'
                    # 403 时等久一点再重试
                    if attempt < self.config.retry - 1:
                        time.sleep(3)
                elif resp.status_code == 404:
                    last_error = f'HTTP 404 Not Found'
                    break  # 不重试 404
                else:
                    last_error = f'HTTP {resp.status_code}'
            except requests.exceptions.RequestException as e:
                last_error = str(e)
                if 'cloudscraper' in str(type(e).__name__.lower()):
                    # cloudscraper 特定错误，尝试普通 requests
                    logger.debug(f"cloudscraper 失败，切换普通请求: {e}")

        logger.debug(f"[{self.__class__.__name__}] 请求失败 ({url}): {last_error}")
        return None


# ─── 动态源爬虫（基于 config.ini 配置）─────────────────
class ConfigSourceScraper(BaseCrawler):
    """
    动态数据源爬虫 - 从 config.ini 读取 URL 和配置
    支持所有在 scraper.py 中定义的数据源（Avdanyuwiki/Av-Wiki/Avbase/Fanza/Javcup）
    使用 cloudscraper + requests fallback + cookie injection 反爬策略
    """

    def __init__(self, source_config: dict, config: EnhancedConfig = None):
        """
        参数:
            source_config: config.ini 中单个数据源配置 dict
                {
                    "id": "avdanyuwiki",
                    "name": "Avdanyuwiki",
                    "enabled": true,
                    "priority": 1,
                    "url": "https://avdanyuwiki.com/?s={code}",
                    "anti_bot": false
                }
            config: 全局增强配置
        """
        self.source_config = source_config
        self.source_id = source_config.get("id", "")
        self.source_name = source_config.get("name", self.source_id)
        self.base_url = source_config.get("url", "").split("{code}")[0].rstrip("/")
        self.anti_bot = source_config.get("anti_bot", False)
        super().__init__(config)

        # 反爬站点增加延迟
        if self.anti_bot:
            self.config.request_delay = max(self.config.request_delay, 3.0)

        # 复用 scraper.py 的爬虫类来执行实际刮取
        self._init_legacy_scraper()

    def _init_legacy_scraper(self):
        """初始化 scraper.py 中的 LegacyScraper（封装现有爬虫逻辑）"""
        self._legacy = LegacyScraperWrapper(self.source_config, self.config)

    def scrape(self, code: str) -> Optional[ScrapeResult]:
        """使用 legacy scraper 执行刮取"""
        # 清理番号
        code = code.strip().upper()
        code = re.sub(r'\s+', '', code)

        result = self._legacy.scrape(code)
        if not result:
            return None

        # 转换为 ScrapeResult
        sr = ScrapeResult(
            source=self.source_id,
            success=bool(result.get("code")),
            url=result.get("detail_url", ""),
            title=result.get("title", ""),
            title_jp=result.get("title_jp", ""),
            title_cn=result.get("title_cn", ""),
            code=result.get("code", code),
            maker=result.get("maker", ""),
            studio=result.get("studio", ""),
            director=result.get("director", ""),
            release_date=result.get("release_date", ""),
            duration=result.get("duration", 0) or 0,
            genres=result.get("genres", []) or [],
            actors=result.get("actors", []) or [],
            cover_url=result.get("cover_url", ""),
            fanart_url=result.get("fanart_path", ""),
            plot=result.get("plot", ""),
        )
        return sr


# ─── Legacy 爬虫封装器（复用 scraper.py 的成熟逻辑）────
from scraper import (
    AvdanyuwikiScraper, AvWikiScraper, AvbaseScraper,
    FanzaScraper, JavcupScraper, JavDBScraper,
    JavSeeScraper, Jav321Scraper, AvSoxScraper, AvMooScraper,
    EnhancedMultiScraper, translate_to_chinese,
)

# 源 ID → 爬虫类映射
_SOURCE_CLASS_MAP = {
    "avdanyuwiki": AvdanyuwikiScraper,
    "av-wiki": AvWikiScraper,
    "avbase": AvbaseScraper,
    "fanza": FanzaScraper,
    "javcup": JavcupScraper,
    "javdb": JavDBScraper,
    "javsee": JavSeeScraper,
    "jav321": Jav321Scraper,
    "avsox": AvSoxScraper,
    "avmoo": AvMooScraper,
}


class LegacyScraperWrapper:
    """
    封装 scraper.py 中的各数据源爬虫
    提供统一的接口，集成 cloudscraper 反爬策略
    """

    def __init__(self, source_config: dict, config: EnhancedConfig = None):
        self.source_config = source_config
        self.source_id = source_config.get("id", "")
        self._scraper_class = _SOURCE_CLASS_MAP.get(self.source_id)
        self._config = config or _build_config_from_ini()

        # 为每个源创建独立的 session（带 cloudscraper）
        self._session = None
        self._init_session()

    def _init_session(self):
        """初始化 cloudscraper session"""
        if CLOUDSCRAPER_AVAILABLE:
            try:
                self._session = cloudscraper.create_scraper(
                    browser={
                        'browser': 'chrome',
                        'platform': 'windows',
                        'mobile': False,
                    },
                )
                # cloudscraper 已自带浏览器指纹，不要覆盖 headers
                # 只额外添加 Accept-Language（追加，不覆盖）
                self._session.headers['Accept-Language'] = 'zh-CN,zh;q=0.9,en;q=0.8'
                self._session.headers['Referer'] = self.source_config.get('url', '').split('{code}')[0].rstrip('/') or 'https://example.com'
            except Exception:
                import requests as _req
                self._session = _req.Session()
        else:
            import requests as _req
            self._session = _req.Session()

    def _get_session(self):
        """获取 session（每次请求前确保 CloudFlare clearance 有效）"""
        return self._session

    def scrape(self, code: str) -> Optional[Dict]:
        """执行刮取，返回 movie_data 字典"""
        if not self._scraper_class:
            logger.warning(f"未知数据源: {self.source_id}")
            return None

        scraper = self._scraper_class(delay=self._config.request_delay)
        scraper.session = self._session  # 注入 cloudscraper session

        try:
            result = scraper.scrape(code)
            if result and result.get("code"):
                # 处理双语标题
                if result.get("title_jp") and not result.get("title_cn"):
                    cn = translate_to_chinese(result["title_jp"])
                    if cn and cn != result["title_jp"]:
                        result["title_cn"] = cn
                        result["title"] = f"{cn}\n{result['title_jp']}"
                return result
        except Exception as e:
            logger.debug(f"[{self.source_id}] 刮取异常: {e}")

        return None


# ─── 增强型刮削器 ──────────────────────────────────────
class EnhancedScraper:
    """
    多源并发刮削器（参考 JavSP 架构）

    核心策略：
    1. 从 config.ini 读取所有启用的数据源
    2. 按 priority 排序后，并发发起所有源的请求
    3. 最快返回有效结果的源获胜
    4. cloudscraper + requests fallback + cookie injection 反爬

    使用方式：
        scraper = EnhancedScraper()
        result = scraper.scrape('VENX-034')
        if result:
            print(result.title, result.maker)
    """

    def __init__(self, config: EnhancedConfig = None):
        self.config = config or _build_config_from_ini()
        self._lock = threading.Lock()
        self._scrapers: Dict[str, ConfigSourceScraper] = {}
        self._init_scrapers()

    def _init_scrapers(self):
        """从 config.ini 初始化所有启用的数据源爬虫"""
        sources = config.get_enabled_sources()
        for source in sources:
            sid = source.get("id", "")
            if sid in _SOURCE_CLASS_MAP:  # 只初始化有对应爬虫类的源
                self._scrapers[sid] = ConfigSourceScraper(source, self.config)
                logger.info(f"[EnhancedScraper] 初始化数据源: {sid} ({source.get('name', '')})")

        if not self._scrapers:
            logger.warning("[EnhancedScraper] 没有可用的数据源，请检查 config.ini 配置")

    def scrape(self, code: str) -> Optional[ScrapeResult]:
        """
        多源并发刮取，返回最快成功的源的结果

        策略（JavSP 架构）：
        1. 同时启动所有启用的数据源爬虫
        2. 竞争谁先返回完整数据
        3. 第一个成功的源返回结果
        4. 所有源都失败返回 None
        """
        code = code.strip().upper()
        code = re.sub(r'\s+', '', code)

        results: Dict[str, ScrapeResult] = {}
        results_event = threading.Event()
        start_time = time.time()
        active_sources = list(self._scrapers.keys())
        print(f"[EnhancedScraper] 🚀 开始刮削 {code}，共 {len(active_sources)} 个源: {active_sources}", flush=True)

        _BAD_COVER_PATTERNS = ('netcdn.space', 'file.netcdn.space', '5561yurd')

        def try_source(source_id: str, scraper: ConfigSourceScraper):
            try:
                src_start = time.time()
                result = scraper.scrape(code)
                elapsed = int((time.time() - src_start) * 1000)
                # 质量检查：cover URL 是占位符（JS 渲染站特征）时视为失败
                if result and result.success and result.cover_url:
                    if any(bad in result.cover_url for bad in _BAD_COVER_PATTERNS):
                        result = None  # 降级为失败，等其他源
                with self._lock:
                    results[source_id] = result
                if result and result.success:
                    print(f"[EnhancedScraper]   ✅ {source_id} 成功 ({elapsed}ms): {result.title[:40] if result.title else code}", flush=True)
                    results_event.set()
                else:
                    print(f"[EnhancedScraper]   ❌ {source_id} 未命中 ({elapsed}ms)", flush=True)
            except Exception as e:
                print(f"[EnhancedScraper]   💥 {source_id} 异常: {e}", flush=True)

        # 并发启动所有源爬虫
        threads = []
        for source_id, scraper in self._scrapers.items():
            t = threading.Thread(target=try_source, args=(source_id, scraper), name=source_id)
            threads.append(t)
            t.start()

        # 等待第一个源成功返回，或者全部超时
        first_success = results_event.wait(timeout=self.config.parallel_timeout)
        total_elapsed = int((time.time() - start_time) * 1000)

        if first_success:
            # 找到第一个成功的
            for source_id, result in results.items():
                if result and result.success:
                    total = result.title or code
                    print(f"[EnhancedScraper] 🏆 {code} → {source_id} 获胜！总耗时 {total_elapsed}ms", flush=True)
                    # 等待其他线程结束
                    for t in threads:
                        t.join(timeout=1)
                    return result

        # 所有源都完成但都没成功
        winners = [r.source for r in results.values() if r and r.success]
        print(f"[EnhancedScraper] ❌ {code} 全部 {len(active_sources)} 个源均失败（耗时 {total_elapsed}ms）", flush=True)
        for result in results.values():
            if result:
                return result
        return None

        return None

    def scrape_to_movie_data(self, code: str) -> Optional[Dict]:
        """
        刮取并返回适合写入数据库的 movie_data 字典

        返回：
            {
                'code': 'VENX-034',
                'title': '...',
                'title_jp': '...',
                'maker': '...',
                'studio': '...',
                'director': '...',
                'release_date': '2021-05-07',
                'duration': 150,
                'genres': [...],
                'actors': [...],
                'cover_url': 'https://...',
                'plot': '...',
                'source': 'avdanyuwiki'
            }
        """
        result = self.scrape(code)
        if not result or not result.success:
            return None

        # ─── 结果校验：番号必须匹配 ─────────────────────────────────────────
        # 当源返回空番号（avmoo/avsox 等 JS 渲染站常见）时，
        # legacy scraper 会用请求番号填充，但覆盖 URL 可能仍是占位符。
        # 通过比较正规化后的番号来检测不匹配情况。
        normalized = lambda c: re.sub(r'[^A-Z0-9]', '', c.upper())
        req_norm = normalized(code)
        res_norm = normalized(result.code) if result.code else ''
        if res_norm and res_norm != req_norm:
            print(f"[EnhancedScraper] ❌ 番号不匹配: 请求={code}, 返回={result.code} → 拒绝该结果", flush=True)
            return None

        # ─── 数据质量校验已移除 ──────────────────────────────────────────────
        # 注意：不再以 genres/actors/plot 全空为由拒绝结果。
        # 理由：并发 scrape() 已选择第一个成功源，DMM/fanza 常返回空 genres 但封面正确。
        # 若过滤掉 DMM 会导致后续源全部被拒绝，最终 scrape_to_movie_data 返回 None，
        # 数据库得不到 DMM 的正确封面。质量筛选应在 scrape() 并发层做，而非在此。

        # 始终使用请求的 code 而非 result.code（后者来自数据源，可能丢失前导零）
        # 例如：请求 ABW-086，源站可能返回 ABW-86
        return {
            'code': code,
            'title': result.title or code,
            'title_jp': result.title_jp or result.title or '',
            'maker': result.maker or '',
            'studio': result.studio or '',
            'director': result.director or '',
            'release_date': result.release_date or '',
            'duration': result.duration or 0,
            'genres': result.genres or [],
            'actors': result.actors or [],
            'cover_url': result.cover_url or '',
            'plot': result.plot or '',
            'source': result.source,
        }


# ─── 测试入口 ─────────────────────────────────────────
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

    scraper = EnhancedScraper()

    test_codes = ['VENX-034', 'JAC-104', 'MIUM-655']
    for code in test_codes:
        print(f'\n{"="*50}')
        print(f'刮取: {code}')
        result = scraper.scrape(code)
        if result and result.success:
            print(f'  来源: {result.source}')
            print(f'  标题: {result.title}')
            print(f'  片商: {result.maker}')
            print(f'  系列: {result.studio}')
            print(f'  女优: {result.actors}')
            print(f'  发行: {result.release_date}')
            print(f'  时长: {result.duration}分钟')
            print(f'  封面: {result.cover_url[:60]}...' if len(result.cover_url) > 60 else f'  封面: {result.cover_url}')
        else:
            print(f'  刮取失败')
            if result:
                print(f'  错误: {result.error}')