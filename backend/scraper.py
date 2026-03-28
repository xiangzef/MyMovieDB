"""
爬虫模块 - 支持多个数据源，自动翻译标题
1. JavDB (多个域名)
2. Avdanyuwiki (主要数据源)
"""
import requests
from bs4 import BeautifulSoup
import re
import time
from pathlib import Path
from urllib.parse import quote, urljoin
from typing import Optional, Dict, List
import logging

try:
    from googletrans import Translator
    GOOGLE_TRANSLATE_AVAILABLE = True
except ImportError:
    GOOGLE_TRANSLATE_AVAILABLE = False
    print("警告: googletrans 未安装，标题将不会翻译")

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
