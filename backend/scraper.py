"""
爬虫模块 - 支持多个数据源，自动翻译标题
支持网站: Avdanyuwiki, AV-Wiki, JavDB, Avbase, Javbus, Javbooks, Javhoo, Javd, Jav情报站, Javcup
"""
import requests
from bs4 import BeautifulSoup
import re
import time
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse
from typing import Optional, Dict, List
import logging

try:
    from googletrans import Translator
    GOOGLE_TRANSLATE_AVAILABLE = True
except ImportError:
    GOOGLE_TRANSLATE_AVAILABLE = False
    print("警告: googletrans 未安装，标题将不会翻译")

# 导入配置
try:
    import config
    DEFAULT_DELAY = config.DEFAULT_DELAY
    DEFAULT_TIMEOUT = config.DEFAULT_TIMEOUT
    DEFAULT_RETRY = config.DEFAULT_RETRY
    DEFAULT_HEADERS = config.DEFAULT_HEADERS
    SCRAPER_SOURCES = config.SCRAPER_SOURCES
    get_enabled_sources = config.get_enabled_sources
    get_source_by_id = config.get_source_by_id
except ImportError:
    # 如果 config.py 不存在，使用默认值
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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def translate_to_chinese(text: str, retry: int = 2) -> str:
    """翻译日文到中文，带重试"""
    if not text or not GOOGLE_TRANSLATE_AVAILABLE:
        return text

    for i in range(retry):
        try:
            translator = Translator()
            result = translator.translate(text, src='ja', dest='zh-cn')
            if result and result.text:
                return result.text
        except Exception as e:
            logger.warning(f"翻译失败 (尝试 {i+1}/{retry}): {e}")
            if i < retry - 1:
                time.sleep(1)

    return text


def make_bilingual_title(jp_title: str, cn_title: str = None) -> str:
    """生成双语标题"""
    if not GOOGLE_TRANSLATE_AVAILABLE or not jp_title:
        return jp_title

    if cn_title:
        return f"{cn_title}\n{jp_title}"

    cn_title = translate_to_chinese(jp_title)
    if cn_title and cn_title != jp_title:
        return f"{cn_title}\n{jp_title}"

    return jp_title


class BaseScraper:
    """爬虫基类"""

    def __init__(self, timeout: int = 30, delay: float = 1.0):
        self.timeout = timeout
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,ja;q=0.7",
            "Connection": "keep-alive",
        })

    def _get(self, url: str, retry: int = 2) -> Optional[BeautifulSoup]:
        """发送 GET 请求并解析 HTML，带重试"""
        for i in range(retry):
            try:
                time.sleep(self.delay)
                response = self.session.get(url, timeout=self.timeout)

                # 处理 403 等错误
                if response.status_code == 403:
                    logger.warning(f"403 禁止访问 (尝试 {i+1}/{retry}): {url}")
                    if i < retry - 1:
                        time.sleep(3)
                        continue
                    return None

                response.raise_for_status()
                return BeautifulSoup(response.content, "lxml")
            except requests.exceptions.RequestException as e:
                logger.warning(f"请求失败 (尝试 {i+1}/{retry}): {url}, 错误: {e}")
                if i < retry - 1:
                    time.sleep(2)
                    continue
                return None

        return None

    def search(self, keyword: str) -> List[Dict]:
        """搜索影片"""
        raise NotImplementedError

    def get_detail(self, detail_url: str) -> Optional[Dict]:
        """获取影片详情"""
        raise NotImplementedError

    def scrape(self, keyword: str) -> Optional[Dict]:
        """刮削影片"""
        results = self.search(keyword)
        if not results:
            return None

        # 找到匹配的影片
        target = None
        keyword_clean = re.sub(r'[^a-zA-Z0-9]', '', keyword.upper())

        for item in results:
            code_clean = re.sub(r'[^a-zA-Z0-9]', '', item.get("code", "").upper())
            if keyword_clean in code_clean or code_clean in keyword_clean:
                target = item
                break

        if not target:
            target = results[0]

        if target.get("detail_url"):
            detail = self.get_detail(target["detail_url"])
            if detail:
                return detail

        return target


class JavDBScraper(BaseScraper):
    """JavDB 数据源 - 尝试多个域名"""

    DOMAINS = [
        "javdb565.com",
        "javdb564.com",
        "javdb33.com",
        "javdb3.com",
        "javdb32.com",
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.base_url = None
        for domain in self.DOMAINS:
            self.base_url = f"https://{domain}"
            break

    def search(self, keyword: str) -> List[Dict]:
        """搜索影片"""
        results = []

        # 尝试每个域名
        for domain in self.DOMAINS:
            url = f"https://{domain}/search?q={quote(keyword)}&f=all"
            logger.info(f"尝试 JavDB: {url}")

            soup = self._get(url)
            if not soup:
                continue

            # JavDB 的搜索结果结构
            movie_items = soup.select(".movie-item, .movie-box, .grid-item")

            if movie_items:
                self.base_url = f"https://{domain}"

                for item in movie_items:
                    try:
                        link_tag = item.select_one("a")
                        if not link_tag:
                            continue

                        href = link_tag.get("href", "")
                        detail_url = urljoin(self.base_url, href)

                        # 获取影片编号
                        code = ""
                        code_tag = item.select_one(".uid, [class*='uid']")
                        if code_tag:
                            code = code_tag.get_text(strip=True)

                        if not code:
                            code_match = re.search(r"([A-Z]{2,10}-\d+)", href)
                            if code_match:
                                code = code_match.group(1)

                        # 获取标题
                        title_tag = item.select_one(".video-title, strong, .title")
                        title = title_tag.get_text(strip=True) if title_tag else ""

                        # 获取封面
                        img_tag = item.select_one("img")
                        cover = img_tag.get("src") or img_tag.get("data-src", "") if img_tag else ""

                        if code or title:
                            results.append({
                                "code": code,
                                "title": title,
                                "detail_url": detail_url,
                                "cover_url": cover,
                            })
                    except Exception as e:
                        logger.warning(f"解析 JavDB 结果失败: {e}")
                        continue

                if results:
                    logger.info(f"JavDB ({domain}) 找到 {len(results)} 个结果")
                    break

        if not results:
            logger.warning("所有 JavDB 域名均无法访问")

        return results

    def get_detail(self, detail_url: str) -> Optional[Dict]:
        """获取影片详情"""
        soup = self._get(detail_url)
        if not soup:
            return None

        return self._parse_detail_page(soup, detail_url)

    def _parse_detail_page(self, soup: BeautifulSoup, url: str) -> Dict:
        """解析详情页面"""
        data = {
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
            "detail_url": url,
        }

        # 影片编号
        uid_tag = soup.select_one(".video-uid, .uid, [class*='uid']")
        if uid_tag:
            code_match = re.search(r"([A-Z]{2,10}-\d+)", uid_tag.get_text())
            if code_match:
                data["code"] = code_match.group(1)

        if not data["code"]:
            code_match = re.search(r"([A-Z]{2,10}-\d+)", soup.get_text())
            if code_match:
                data["code"] = code_match.group(1)

        # 标题
        title_tag = soup.select_one("h2.title, .title h2, .video-title")
        if title_tag:
            full_title = title_tag.get_text(strip=True)
            data["title_jp"] = full_title

            cn_title = translate_to_chinese(full_title)
            if cn_title and cn_title != full_title:
                data["title"] = make_bilingual_title(full_title, cn_title)
            else:
                data["title"] = full_title

        # 封面图
        cover_tag = soup.select_one(".cover-container img, .movie-cover img, img[data-origin]")
        if cover_tag:
            src = cover_tag.get("src") or cover_tag.get("data-origin", "")
            if src:
                data["cover_url"] = src

        # 元数据
        meta_panels = soup.select(".meta-panel, .video-meta, .column")

        for panel in meta_panels:
            panel_text = panel.get_text()

            # 日期
            if any(k in panel_text for k in ["發布", "發行", "Release", "release"]):
                date_tag = panel.select_one("span, a")
                if date_tag:
                    date_text = date_tag.get_text(strip=True)
                    date_match = re.search(r"\d{4}-\d{2}-\d{2}", date_text)
                    if date_match:
                        data["release_date"] = date_match.group(0)

            # 时长
            if any(k in panel_text for k in ["時長", "时长", "Duration"]):
                duration_tag = panel.select_one("span")
                if duration_tag:
                    duration_match = re.search(r"(\d+)", duration_tag.get_text())
                    if duration_match:
                        data["duration"] = int(duration_match.group(1))

            # 片商
            if "片商" in panel_text or "Maker" in panel_text:
                maker_tag = panel.select_one("a")
                if maker_tag:
                    data["maker"] = maker_tag.get_text(strip=True)

            # 导演
            if any(k in panel_text for k in ["導演", "导演", "Director"]):
                director_tag = panel.select_one("a")
                if director_tag:
                    data["director"] = director_tag.get_text(strip=True)

        # 演员
        actor_section = soup.select(".actor-section a, .performer-section a")
        for a in actor_section:
            actor_name = a.get_text(strip=True)
            if actor_name and "♀" not in actor_name and "♂" not in actor_name:
                data["actors"].append(actor_name)

        # 类别/标签
        genre_tags = soup.select(".genre-list a, .tag-list a")
        for tag in genre_tags:
            tag_text = tag.get_text(strip=True)
            if tag_text and len(tag_text) < 30:
                data["genres"].append(tag_text)

        return data


class AvdanyuwikiScraper(BaseScraper):
    """Avdanyuwiki 数据源 - 主要数据源"""

    BASE_URL = "https://avdanyuwiki.com"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.session.headers.update({
            "Accept-Language": "ja,en;q=0.7",
        })

    def search(self, keyword: str) -> List[Dict]:
        """搜索影片"""
        soup = self._get(f"{self.BASE_URL}/?s={quote(keyword)}")

        if not soup:
            return []

        results = []

        # 获取页面文本
        page_text = soup.get_text()

        # 检查是否找到搜索词
        if keyword.upper() not in page_text.upper() and keyword.lower() not in page_text.lower():
            logger.warning(f"Avdanyuwiki 未找到: {keyword}")
            return []

        # 从页面文本提取数据
        data = self._parse_page_text(page_text, soup)

        if data.get("code"):
            results.append(data)

        logger.info(f"Avdanyuwiki 找到 {len(results)} 个结果")
        return results

    def _parse_page_text(self, page_text: str, soup: BeautifulSoup) -> Dict:
        """从页面文本解析影片数据"""
        detail = {
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
            "actors_male": [],  # 男优
            "detail_url": "",
        }

        # 提取影片编号
        code_pattern = re.compile(r"([A-Z]{2,10}-\d{2,})", re.IGNORECASE)
        code_matches = code_pattern.findall(page_text)
        if code_matches:
            detail["code"] = code_matches[0].upper()

        # 提取标题 (在 h2 标签中)
        h2_tags = soup.find_all("h2")
        for h2 in h2_tags:
            h2_text = h2.get_text(strip=True)
            # 标题通常包含日文字符
            if any('\u3040' <= c <= '\u30ff' for c in h2_text) and len(h2_text) > 5:
                detail["title_jp"] = h2_text
                detail["title"] = h2_text
                break

        # 提取发布日期 (商品発売日)
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

        # 提取时长
        duration_match = re.search(r"収録時間[：:]\s*(\d+)", page_text)
        if duration_match:
            detail["duration"] = int(duration_match.group(1))

        # 提取出演者
        actor_match = re.search(r"出演者[：:]\s*([^出演\n]+?)(?=\n|出演|$)", page_text)
        if actor_match:
            actors_text = actor_match.group(1).strip()
            actors = [a.strip() for a in actors_text.split(",") if a.strip()]
            detail["actors"] = actors

        # 提取出演男優
        male_match = re.search(r"出演男優[：:]\s*([^出演\n]+?)(?=\n|監督|$)", page_text)
        if male_match:
            male_text = male_match.group(1).strip()
            males = [m.strip() for m in male_text.split(",") if m.strip()]
            detail["actors_male"] = males

        # 提取監督
        director_match = re.search(r"監督[：:]\s*([^\n]+?)(?=\n|シリーズ|$)", page_text)
        if director_match:
            detail["director"] = director_match.group(1).strip()

        # 提取メーカー (片商)
        maker_match = re.search(r"メーカー[：:]\s*([^\n]+?)(?=\n|レーベル|$)", page_text)
        if maker_match:
            detail["maker"] = maker_match.group(1).strip()

        # 提取レーベル
        label_match = re.search(r"レーベル[：:]\s*([^\n]+?)(?=\n|ジャンル|$)", page_text)
        if label_match:
            detail["studio"] = label_match.group(1).strip()

        # 提取ジャンル (类别) - 只提取ジャンル标签后的内容，遇到换行或特殊字符停止
        genre_match = re.search(r"ジャンル[：:]\s*([^\n]+)", page_text)
        if genre_match:
            genres_text = genre_match.group(1).strip()
            # 分割并清理，过滤掉太长的和包含特殊字符的
            genres = []
            for g in genres_text.split():
                g = g.strip()
                # 过滤掉太长的、包含数字的、包含特殊符号的
                if g and len(g) < 20 and not re.search(r'\d', g) and not re.search(r'[◆○●□■▲△▼▽★☆♪]', g):
                    # 过滤掉常见的非类别词
                    if g not in ['配信品番：', 'メーカー品番：', 'FANZA', 'PR', '当当は', 'を利用しています']:
                        genres.append(g)
            detail["genres"] = genres

        # 提取封面图
        imgs = soup.find_all("img")
        for img in imgs:
            src = img.get("src") or img.get("data-src", "")
            if src and ("pics.dmm.co.jp" in src or "dmm.co.jp" in src) and "pl" in src:
                detail["cover_url"] = src
                break

        # 处理双语标题
        if detail.get("title_jp"):
            cn_title = translate_to_chinese(detail["title_jp"])
            if cn_title and cn_title != detail["title_jp"]:
                detail["title"] = make_bilingual_title(detail["title_jp"], cn_title)

        return detail

    def get_detail(self, detail_url: str) -> Optional[Dict]:
        """Avdanyuwiki 通常没有独立详情页，直接返回搜索结果"""
        return None


class JavBusScraper(BaseScraper):
    """JavBus 数据源 - 备用"""

    DOMAINS = [
        "www.javbus.com",
        "javbus.net",
    ]

    def search(self, keyword: str) -> List[Dict]:
        """搜索影片"""
        results = []

        for domain in self.DOMAINS:
            url = f"https://{domain}/search?keyword={quote(keyword)}"
            soup = self._get(url)
            if not soup:
                continue

            items = soup.select(".item, .movie-item")
            if items:
                for item in items:
                    link = item.select_one("a")
                    if not link:
                        continue

                    href = link.get("href", "")
                    img = item.select_one("img")
                    title = img.get("title", "") if img else ""

                    code_match = re.search(r"([A-Z]{2,10}-\d+)", title)
                    code = code_match.group(1) if code_match else ""

                    if code or title:
                        results.append({
                            "code": code,
                            "title": title,
                            "detail_url": urljoin(f"https://{domain}", href),
                            "cover_url": img.get("src", "") if img else "",
                        })

                if results:
                    break

        return results

    def get_detail(self, detail_url: str) -> Optional[Dict]:
        return None


class MultiScraper:
    """多数据源爬虫"""

    def __init__(self):
        self.scrapers = [
            AvdanyuwikiScraper(delay=1.0),  # 主数据源
            JavDBScraper(delay=1.5),  # 备用
            JavBusScraper(delay=1.0),  # 备用
        ]

    def scrape(self, keyword: str) -> Optional[Dict]:
        """尝试多个数据源刮削"""
        merged_data = {}

        for scraper in self.scrapers:
            logger.info(f"尝试数据源: {scraper.__class__.__name__}")
            try:
                result = scraper.scrape(keyword)
                if result and result.get("code"):
                    logger.info(f"成功从 {scraper.__class__.__name__} 获取数据")

                    # 智能合并数据
                    for key, value in result.items():
                        if value:  # 只合并有值的字段
                            if key not in merged_data or not merged_data[key]:
                                merged_data[key] = value
                            # 对于列表字段，合并去重
                            elif isinstance(value, list) and isinstance(merged_data.get(key), list):
                                for item in value:
                                    if item not in merged_data[key]:
                                        merged_data[key].append(item)

                    # 如果已获取足够数据，可以提前退出
                    if merged_data.get("code") and merged_data.get("title") and merged_data.get("cover_url"):
                        break

            except Exception as e:
                logger.warning(f"{scraper.__class__.__name__} 失败: {e}")
                continue

        # 处理双语标题（如果还没有）
        if merged_data.get("title_jp") and not merged_data.get("title"):
            cn_title = translate_to_chinese(merged_data["title_jp"])
            merged_data["title"] = make_bilingual_title(merged_data["title_jp"], cn_title)
        elif merged_data.get("title_jp") and "\n" not in merged_data.get("title", ""):
            cn_title = translate_to_chinese(merged_data["title_jp"])
            if cn_title and cn_title != merged_data["title_jp"]:
                merged_data["title"] = make_bilingual_title(merged_data["title_jp"], cn_title)

        return merged_data if merged_data.get("code") else None


def scrape_movie(keyword: str, save_cover: bool = True) -> Optional[Dict]:
    """便捷函数：刮削单个影片（多数据源）"""
    scraper = MultiScraper()
    movie_data = scraper.scrape(keyword)

    if movie_data and save_cover and movie_data.get("cover_url"):
        covers_dir = Path(__file__).parent.parent / "data" / "covers"
        covers_dir.mkdir(parents=True, exist_ok=True)

        try:
            session = requests.Session()
            session.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            response = session.get(movie_data["cover_url"], timeout=30)
            response.raise_for_status()

            code = movie_data.get("code", "unknown")
            ext = Path(movie_data["cover_url"]).suffix or ".jpg"
            save_path = covers_dir / f"{code}{ext}"

            with open(save_path, "wb") as f:
                f.write(response.content)

            movie_data["local_cover_path"] = str(save_path)
            logger.info(f"封面已保存: {save_path}")
        except Exception as e:
            logger.error(f"下载封面失败: {e}")

    return movie_data


# ==================== 新的网站爬虫 ====================


class AvWikiScraper(BaseScraper):
    """AV-Wiki 数据源"""

    BASE_URL = "https://av-wiki.net"

    def search(self, keyword: str) -> List[Dict]:
        """搜索影片"""
        results = []
        url = f"{self.BASE_URL}/?s={quote(keyword)}&post_type=product"
        soup = self._get(url)

        if not soup:
            return results

        # AV-Wiki 使用 WordPress 结构，需要找"続きを読む"链接
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
                    break  # 只取第一个匹配

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

        # 尝试提取标题
        title_tag = soup.select_one("h1, .entry-title")
        if title_tag:
            data["title"] = title_tag.get_text(strip=True)

        # 提取番号
        code_match = re.search(r"([A-Z]{1,6}-\d{2,5})", soup.get_text(), re.IGNORECASE)
        if code_match:
            data["code"] = code_match.group(1).upper()

        return data


class AvbaseScraper(BaseScraper):
    """Avbase 数据源"""

    BASE_URL = "https://www.avbase.net"

    def search(self, keyword: str) -> List[Dict]:
        """搜索影片 - Avbase 详情页格式: /works/CODE"""
        results = []

        # 直接访问详情页
        detail_url = f"{self.BASE_URL}/works/{quote(keyword)}"
        soup = self._get(detail_url)

        if not soup:
            return results

        # 提取标题
        title_tag = soup.select_one("h1, .title, .works-title")
        title = title_tag.get_text(strip=True) if title_tag else ""

        # 提取番号
        code_match = re.search(r"([A-Z0-9]{1,6}-\d{2,5})", soup.get_text(), re.IGNORECASE)
        code = code_match.group(1).upper() if code_match else keyword.upper()

        # 提取封面
        imgs = soup.select("img")
        cover = ""
        for img in imgs:
            src = img.get("src", "") or img.get("data-src", "")
            if src and "favicon" not in src and "logo" not in src.lower():
                cover = src
                break

        results.append({
            "code": code,
            "title": title,
            "detail_url": detail_url,
            "cover_url": cover,
            "source": "avbase",
        })

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

        # 提取番号
        code_match = re.search(r"([A-Z0-9]{1,6}-\d{2,5})", soup.get_text(), re.IGNORECASE)
        if code_match:
            data["code"] = code_match.group(1).upper()

        # 提取发布日期
        date_match = re.search(r"(\d{4}[-/]\d{2}[-/]\d{2})", soup.get_text())
        if date_match:
            data["release_date"] = date_match.group(1).replace("/", "-")

        return data


class JavhooScraper(BaseScraper):
    """Javhoo 数据源"""

    BASE_URL = "https://www.javhoo.com"

    def search(self, keyword: str) -> List[Dict]:
        """搜索影片"""
        results = []
        url = f"{self.BASE_URL}/search?q={quote(keyword)}"
        soup = self._get(url)

        if not soup:
            return results

        items = soup.select(".movie-box, .item, .video-item")
        for item in items:
            link = item.select_one("a")
            if not link:
                continue

            href = link.get("href", "")
            img = item.select_one("img")
            title = img.get("title", "") if img else ""

            code_match = re.search(r"([A-Z]{1,6}-\d{2,5})", title, re.IGNORECASE)
            code = code_match.group(1).upper() if code_match else ""

            results.append({
                "code": code,
                "title": title,
                "detail_url": urljoin(self.BASE_URL, href),
                "cover_url": img.get("src", "") if img else "",
                "source": "javhoo",
            })

        logger.info(f"Javhoo 找到 {len(results)} 个结果")
        return results

    def get_detail(self, detail_url: str) -> Optional[Dict]:
        """获取影片详情"""
        soup = self._get(detail_url)
        if not soup:
            return None

        data = self._parse_detail_page(soup, detail_url)
        data["source"] = "javhoo"
        return data

    def _parse_detail_page(self, soup: BeautifulSoup, url: str) -> Dict:
        """解析详情页面"""
        data = make_basic_data(url)

        title_tag = soup.select_one("h1, .movie-title")
        if title_tag:
            data["title"] = title_tag.get_text(strip=True)

        return data


class JavdScraper(BaseScraper):
    """Javd 数据源"""

    BASE_URL = "https://javd.me"

    def search(self, keyword: str) -> List[Dict]:
        """搜索影片 - Javd 详情页格式: /movie/HASH/CODE"""
        results = []

        # 搜索并重定向
        search_url = f"{self.BASE_URL}/search?q={quote(keyword)}"
        resp = self.session.get(search_url, timeout=self.timeout)
        final_url = resp.url

        # 从 URL 中提取详情页信息
        if "/movie/" in final_url:
            detail_url = final_url
        else:
            # 解析搜索页找链接
            soup = BeautifulSoup(resp.content, "lxml")
            links = soup.select('a[href*="/movie/"]')
            for link in links:
                href = link.get("href", "")
                if href and keyword.upper() in href.upper():
                    detail_url = urljoin(self.BASE_URL, href)
                    break
            else:
                # 尝试直接访问
                detail_url = f"{self.BASE_URL}/movie/unknown/{keyword.upper()}"

        # 获取详情页
        detail_soup = self._get(detail_url)
        if detail_soup:
            title_tag = detail_soup.select_one("h1, h2")
            title = title_tag.get_text(strip=True) if title_tag else ""

            code_match = re.search(r"([A-Z]{1,6}-\d{2,5})", detail_soup.get_text(), re.IGNORECASE)
            code = code_match.group(1).upper() if code_match else keyword.upper()

            # 提取封面
            imgs = detail_soup.select("img")
            cover = ""
            for img in imgs:
                src = img.get("src", "") or img.get("data-src", "")
                if src and "cover" in src.lower() or "poster" in src.lower():
                    cover = src
                    break

            results.append({
                "code": code,
                "title": title,
                "detail_url": detail_url,
                "cover_url": cover,
                "source": "javd",
            })

        logger.info(f"Javd 找到 {len(results)} 个结果")
        return results

    def get_detail(self, detail_url: str) -> Optional[Dict]:
        """获取影片详情"""
        soup = self._get(detail_url)
        if not soup:
            return None

        data = self._parse_detail_page(soup, detail_url)
        data["source"] = "javd"
        return data

    def _parse_detail_page(self, soup: BeautifulSoup, url: str) -> Dict:
        """解析详情页面"""
        data = make_basic_data(url)

        title_tag = soup.select_one("h1, h2")
        if title_tag:
            data["title"] = title_tag.get_text(strip=True)

        # 提取番号
        code_match = re.search(r"([A-Z]{1,6}-\d{2,5})", soup.get_text(), re.IGNORECASE)
        if code_match:
            data["code"] = code_match.group(1).upper()

        return data


class JavInfoScraper(BaseScraper):
    """Jav情报站 数据源 - 需要先获取hash"""

    BASE_URL = "https://pc5.top"

    def search(self, keyword: str) -> List[Dict]:
        """搜索影片 - Jav情报站需要先获取hash"""
        results = []

        try:
            # 先获取搜索页面获取hash
            search_page_url = f"{self.BASE_URL}/search.php"
            resp = self.session.get(search_page_url, timeout=self.timeout)
            soup = BeautifulSoup(resp.content, "lxml")

            # 提取hash和code
            hash_input = soup.select_one('input[name="hash"]')
            code_input = soup.select_one('input[name="code"]')
            hash_val = hash_input.get("value", "") if hash_input else ""
            code_val = code_input.get("value", "") if code_input else ""

            if hash_val and code_val:
                # 发送搜索请求
                search_url = f"{self.BASE_URL}/search.php?s={quote(keyword)}&code={code_val}&hash={hash_val}"
                soup2 = self._get(search_url)

                if soup2:
                    # 找结果链接
                    links = soup2.select('a[href*="/article/"]')
                    for link in links[:3]:
                        href = link.get("href", "")
                        if href:
                            if not href.startswith("http"):
                                href = self.BASE_URL + href

                            # 获取详情页
                            detail_soup = self._get(href)
                            if detail_soup:
                                title_tag = detail_soup.select_one("h1, .title")
                                title = title_tag.get_text(strip=True) if title_tag else ""

                                code_match = re.search(r"([A-Z]{1,6}-\d{2,5})", detail_soup.get_text(), re.IGNORECASE)
                                code = code_match.group(1).upper() if code_match else keyword.upper()

                                results.append({
                                    "code": code,
                                    "title": title,
                                    "detail_url": href,
                                    "cover_url": "",
                                    "source": "javinfo",
                                })
                                break  # 取第一个

        except Exception as e:
            logger.warning(f"Jav情报站 搜索失败: {e}")

        logger.info(f"Jav情报站 找到 {len(results)} 个结果")
        return results

    def get_detail(self, detail_url: str) -> Optional[Dict]:
        """获取影片详情"""
        soup = self._get(detail_url)
        if not soup:
            return None

        data = self._parse_detail_page(soup, detail_url)
        data["source"] = "javinfo"
        return data

    def _parse_detail_page(self, soup: BeautifulSoup, url: str) -> Dict:
        """解析详情页面"""
        data = make_basic_data(url)

        title_tag = soup.select_one("h1, .title")
        if title_tag:
            data["title"] = title_tag.get_text(strip=True)

        # 提取番号
        code_match = re.search(r"([A-Z]{1,6}-\d{2,5})", soup.get_text(), re.IGNORECASE)
        if code_match:
            data["code"] = code_match.group(1).upper()

        return data


class JavcupScraper(BaseScraper):
    """Javcup 数据源"""

    BASE_URL = "https://javcup.com"

    def search(self, keyword: str) -> List[Dict]:
        """搜索影片 - Javcup 详情页格式: /movie/CODE"""
        results = []

        # 搜索
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

                    # 提取封面
                    img = detail_soup.select_one("img")
                    cover = img.get("src", "") if img else ""

                    results.append({
                        "code": code,
                        "title": title,
                        "detail_url": href,
                        "cover_url": cover,
                        "source": "javcup",
                    })
                    break  # 取第一个

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

        # 提取番号
        code_match = re.search(r"([A-Z]{1,6}-\d{2,5})", soup.get_text(), re.IGNORECASE)
        if code_match:
            data["code"] = code_match.group(1).upper()

        # 提取发布日期
        date_match = re.search(r"(\d{4}[-/]\d{2}[-/]\d{2})", soup.get_text())
        if date_match:
            data["release_date"] = date_match.group(1).replace("/", "-")

        return data


class JavbooksScraper(BaseScraper):
    """Javbooks 数据源 - 使用内嵌搜索页面"""

    BASE_URL = "https://jkk044.com"

    def search(self, keyword: str) -> List[Dict]:
        """搜索影片 - Javbooks 使用内嵌搜索"""
        results = []

        # Javbooks 有多个分类，有码和无码
        search_urls = [
            f"{self.BASE_URL}/serchinfo_censored/IamOverEighteenYearsOld/topicsbt_1.htm?keyword={quote(keyword)}",
            f"{self.BASE_URL}/serchinfo_censored/topicsbt/topicsbt_1.htm?keyword={quote(keyword)}",
        ]

        for url in search_urls:
            soup = self._get(url)
            if not soup:
                continue

            # Javbooks 通常使用表格或列表结构
            # 查找包含番号的链接
            links = soup.select('a[href*=".htm"]')
            for link in links:
                href = link.get("href", "")
                text = link.get_text(strip=True)

                # 检查是否包含番号
                code_match = re.search(r"([A-Z]{1,6}-\d{2,5})", text, re.IGNORECASE)
                if code_match and keyword.upper() in text.upper():
                    if not href.startswith("http"):
                        href = urljoin(self.BASE_URL, href)

                    results.append({
                        "code": code_match.group(1).upper(),
                        "title": text,
                        "detail_url": href,
                        "cover_url": "",
                        "source": "javbooks",
                    })
                    break

            if results:
                break

        logger.info(f"Javbooks 找到 {len(results)} 个结果")
        return results

    def get_detail(self, detail_url: str) -> Optional[Dict]:
        """获取影片详情"""
        soup = self._get(detail_url)
        if not soup:
            return None

        data = self._parse_detail_page(soup, detail_url)
        data["source"] = "javbooks"
        return data

    def _parse_detail_page(self, soup: BeautifulSoup, url: str) -> Dict:
        """解析详情页面"""
        data = make_basic_data(url)

        title_tag = soup.select_one("h1, h2, .title, td")
        if title_tag:
            data["title"] = title_tag.get_text(strip=True)

        # 提取番号
        code_match = re.search(r"([A-Z]{1,6}-\d{2,5})", soup.get_text(), re.IGNORECASE)
        if code_match:
            data["code"] = code_match.group(1).upper()

        return data


# ==================== 辅助方法 ====================

def make_basic_data(url: str) -> Dict:
    """生成基础数据结构"""
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


# ==================== 更新后的多源爬虫 ====================

class EnhancedMultiScraper:
    """增强型多数据源爬虫 - 使用配置文件的网站"""

    def __init__(self):
        self.scrapers = []
        self._init_scrapers()

    def _init_scrapers(self):
        """根据配置初始化爬虫"""
        scraper_map = {
            "avdanyuwiki": AvdanyuwikiScraper,
            "av-wiki": AvWikiScraper,
            "javdb": JavDBScraper,
            "avbase": AvbaseScraper,
            "javbus": JavBusScraper,
            "javbooks": JavbooksScraper,
            "javhoo": JavhooScraper,
            "javd": JavdScraper,
            "javinfo": JavInfoScraper,
            "javcup": JavcupScraper,
        }

        # 按优先级排序初始化爬虫
        for source in SCRAPER_SOURCES:
            source_id = source["id"]
            if source_id in scraper_map and source.get("enabled", True):
                scraper_class = scraper_map[source_id]
                delay = DEFAULT_DELAY * (2 if source.get("anti_bot") else 1)
                self.scrapers.append(scraper_class(delay=delay))

    def scrape(self, keyword: str) -> Optional[Dict]:
        """尝试多个数据源刮削"""
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

                    # 如果已获取足够数据，可以提前退出
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


def scrape_movie_enhanced(keyword: str, save_cover: bool = True) -> Optional[Dict]:
    """增强版刮削函数"""
    scraper = EnhancedMultiScraper()
    return scraper.scrape(keyword)


# ==================== 爬虫测试函数 ====================

def test_all_scrapers(keyword: str = "ABC-123") -> Dict:
    """测试所有爬虫的可用性"""
    results = {}
    scrapers = [
        ("Avdanyuwiki", AvdanyuwikiScraper),
        ("AvWiki", AvWikiScraper),
        ("JavDB", JavDBScraper),
        ("JavBus", JavBusScraper),
        ("Avbase", AvbaseScraper),
        ("Javbooks", JavbooksScraper),
        ("Javhoo", JavhooScraper),
        ("Javd", JavdScraper),
        ("JavInfo", JavInfoScraper),
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

