"""
爬虫配置文件 - 存储所有数据源网站配置
"""
from typing import Dict, List, Optional

# ==================== 网站配置 ====================

# 默认 User-Agent
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# 默认请求头
DEFAULT_HEADERS = {
    "User-Agent": DEFAULT_USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,ja;q=0.7",
    "Connection": "keep-alive",
}

# 请求延迟（秒）- 防止请求过快被封
DEFAULT_DELAY = 1.0

# 请求超时（秒）
DEFAULT_TIMEOUT = 30

# 重试次数
DEFAULT_RETRY = 2


# ==================== 各网站配置 ====================

SCRAPER_SOURCES: List[Dict] = [
    {
        "id": "avdanyuwiki",
        "name": "Avdanyuwiki",
        "name_cn": "Av单元Wiki",
        "base_url": "https://avdanyuwiki.com",
        "search_url": "/cn/search/{code}",
        "enabled": True,
        "priority": 1,  # 优先级，数字越小越优先
        "notes": "主要数据源，信息全面",
        "anti_bot": False,
    },
    {
        "id": "av-wiki",
        "name": "AV-Wiki",
        "name_cn": "AV维基",
        "base_url": "https://av-wiki.net",
        "search_url": "/?s={code}",
        "enabled": True,
        "priority": 2,
        "notes": "",
        "anti_bot": False,
    },
    {
        "id": "javdb",
        "name": "JavDB",
        "name_cn": "JavDB",
        "base_url": "https://javdb564.com",
        "search_url": "/search?q={code}&f=all",
        "enabled": True,
        "priority": 3,
        "notes": "备选域名: javdb565.com, javdb33.com",
        "fallback_domains": [
            "javdb565.com",
            "javdb33.com",
            "javdb3.com",
            "javdb32.com",
        ],
        "anti_bot": True,  # 有反爬
    },
    {
        "id": "avbase",
        "name": "Avbase",
        "name_cn": "Avbase",
        "base_url": "https://www.avbase.net",
        "search_url": "/works?q={code}",
        "enabled": True,
        "priority": 4,
        "notes": "搜索 URL 格式: /works?q=CODE",
        "anti_bot": False,
    },
    {
        "id": "javbus",
        "name": "Javbus",
        "name_cn": "Javbus",
        "base_url": "https://www.javsee.bond",
        "search_url": "/search/{code}",
        "enabled": True,
        "priority": 5,
        "notes": "",
        "anti_bot": True,  # 有反爬
    },
    {
        "id": "javbooks",
        "name": "Javbooks",
        "name_cn": "Javbooks",
        "base_url": "https://jkk044.com",
        "search_url": "/serchinfo_censored/IamOverEighteenYearsOld/topicsbt_1.htm?keyword={code}",
        "enabled": True,
        "priority": 6,
        "notes": "搜索结果在新窗口打开",
        "anti_bot": False,
    },
    {
        "id": "javhoo",
        "name": "Javhoo",
        "name_cn": "Javhoo",
        "base_url": "https://www.javhoo.com",
        "search_url": "/search?q={code}",
        "enabled": True,
        "priority": 7,
        "notes": "",
        "anti_bot": False,
    },
    {
        "id": "javd",
        "name": "Javd",
        "name_cn": "Javd",
        "base_url": "https://cn.javd.me",
        "search_url": "/search?q={code}",
        "enabled": True,
        "priority": 8,
        "notes": "",
        "anti_bot": False,
    },
    {
        "id": "javinfo",
        "name": "Jav情报站",
        "name_cn": "Jav情报站",
        "base_url": "https://pc5.top",
        "search_url": "/search?q={code}",
        "enabled": True,
        "priority": 9,
        "notes": "",
        "anti_bot": False,
    },
    {
        "id": "javcup",
        "name": "Javcup",
        "name_cn": "Javcup",
        "base_url": "https://javcup.com",
        "search_url": "/search?q={code}",
        "enabled": True,
        "priority": 10,
        "notes": "",
        "anti_bot": False,
    },
]


# ==================== 获取启用的数据源 ====================

def get_enabled_sources() -> List[Dict]:
    """获取所有启用的数据源，按优先级排序"""
    enabled = [s for s in SCRAPER_SOURCES if s.get("enabled", True)]
    return sorted(enabled, key=lambda x: x.get("priority", 99))


def get_source_by_id(source_id: str) -> Optional[Dict]:
    """根据ID获取数据源配置"""
    for source in SCRAPER_SOURCES:
        if source["id"] == source_id:
            return source
    return None


def get_source_urls(source_id: str) -> tuple:  # noqa: E501
    """获取数据源的URL列表（包括备选域名）"""
    source = get_source_by_id(source_id)
    if not source:
        return ()

    urls = [source["base_url"]]
    if "fallback_domains" in source:
        urls.extend(source["fallback_domains"])
    return tuple(urls)


# ==================== 通用配置 ====================

# 刮削配置
SCRAPE_CONFIG = {
    "max_results": 10,  # 最多返回结果数
    "require_exact_match": False,  # 是否要求精确匹配
    "fallback_to_first": True,  # 没有精确匹配时是否使用第一个结果
}

# 代理配置（可选）
PROXY_CONFIG = {
    "enabled": False,
    "http": "",
    "https": "",
}

# Cookie配置（用于需要登录的网站）
COOKIE_CONFIG = {
    "enabled": False,
    "cookies": {},
}
