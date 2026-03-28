"""
================================================================================
爬虫配置文件 - 存储所有数据源网站配置
================================================================================
文件路径: F:\github\MyMovieDB\backend\config.py
功能说明: 定义所有可用的爬虫数据源网站配置
依赖模块: typing (Python内置)
使用语法: from config import SCRAPER_SOURCES, get_enabled_sources
================================================================================
"""

# ===============================================================================
# 类型提示导入 - 用于类型注解
# ===============================================================================
from typing import Dict, List, Optional

# ===============================================================================
# HTTP 请求配置
# ===============================================================================

# 默认 User-Agent - 模拟浏览器访问
# 来源: https://www.whatmyuseragent.com
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# 默认请求头 - 发送给服务器的 HTTP 头信息
# 依赖: DEFAULT_USER_AGENT
DEFAULT_HEADERS = {
    "User-Agent": DEFAULT_USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",  # 接受的响应类型
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,ja;q=0.7",  # 接受的语言优先级
    "Connection": "keep-alive",  # 保持连接
}

# 请求延迟（秒）- 防止请求过快被封禁
# 语法: time.sleep() 在 scraper.py 中使用
DEFAULT_DELAY = 1.0

# 请求超时（秒）- 单次请求最大等待时间
# 语法: requests.Session.get(timeout=30)
DEFAULT_TIMEOUT = 30

# 重试次数 - 请求失败时的重试次数
DEFAULT_RETRY = 2


# ===============================================================================
# 网站配置列表
# ===============================================================================
# 配置说明:
#   - id: 爬虫唯一标识符，用于代码中引用
#   - name: 网站英文名
#   - name_cn: 网站中文名
#   - base_url: 网站基础 URL
#   - search_url: 搜索页面 URL 格式（{code} 会替换为番号）
#   - enabled: 是否启用该爬虫
#   - priority: 优先级，数字越小越优先（按 1,2,3... 顺序尝试）
#   - notes: 备注说明
#   - anti_bot: 是否有反爬虫机制（有则自动增加请求延迟）
#
# 依赖库:
#   - requests: HTTP 请求
#   - bs4.BeautifulSoup: HTML 解析
#   - re: 正则表达式
#   - urllib.parse.quote: URL 编码

SCRAPER_SOURCES: List[Dict] = [
    # --------------------------------------------------------------------------
    # 可用爬虫（保留）
    # --------------------------------------------------------------------------

    {
        # =========================================================================
        # Avdanyuwiki - 主要数据源，测试成功率最高 (4/4)
        # =========================================================================
        "id": "avdanyuwiki",                          # 爬虫标识符
        "name": "Avdanyuwiki",                        # 英文名
        "name_cn": "Av单元Wiki",                      # 中文名
        "base_url": "https://avdanyuwiki.com",       # 基础 URL
        "search_url": "/?s={code}",                  # 搜索 URL（参数: code）
        "enabled": True,                             # 启用状态
        "priority": 1,                                # 优先级（最高）
        "notes": "主要数据源，信息全面，测试成功率 100%",
        "anti_bot": False,                            # 无反爬
    },

    {
        # =========================================================================
        # AV-Wiki - 备用数据源
        # =========================================================================
        "id": "av-wiki",
        "name": "AV-Wiki",
        "name_cn": "AV维基",
        "base_url": "https://av-wiki.net",
        "search_url": "/?s={code}&post_type=product",
        "enabled": True,
        "priority": 2,
        "notes": "使用 WordPress 结构，需要点击阅读全文",
        "anti_bot": False,
    },

    {
        # =========================================================================
        # Avbase - 备用数据源，测试成功率最高 (4/4)
        # =========================================================================
        "id": "avbase",
        "name": "Avbase",
        "name_cn": "Avbase",
        "base_url": "https://www.avbase.net",
        "search_url": "/works?q={code}",              # 注意：使用 ?q= 参数格式
        "enabled": True,
        "priority": 3,
        "notes": "搜索 URL: /works?q=CODE（不是 /works/CODE）",
        "anti_bot": False,
    },

    {
        # =========================================================================
        # Javcup - 备用数据源
        # =========================================================================
        "id": "javcup",
        "name": "Javcup",
        "name_cn": "Javcup",
        "base_url": "https://javcup.com",
        "search_url": "/search?q={code}",
        "enabled": True,
        "priority": 4,
        "notes": "备用数据源，部分番号可用",
        "anti_bot": False,
    },

    # --------------------------------------------------------------------------
    # 已禁用爬虫（暂时屏蔽，等待更好的反反爬虫方案）
    # --------------------------------------------------------------------------

    {
        # =========================================================================
        # JavDB - 已禁用：403 禁止访问
        # =========================================================================
        "id": "javdb",
        "name": "JavDB",
        "name_cn": "JavDB",
        "base_url": "https://javdb564.com",
        "search_url": "/search?q={code}&f=all",
        "enabled": False,                             # 已禁用
        "priority": 5,
        "notes": "[已禁用] 403 禁止访问，需要反反爬虫工具或代理",
        "anti_bot": True,
    },

    {
        # =========================================================================
        # Javbus - 已禁用：域名失效
        # =========================================================================
        "id": "javbus",
        "name": "Javbus",
        "name_cn": "Javbus",
        "base_url": "https://www.javsee.bond",
        "search_url": "/search/{code}",
        "enabled": False,                             # 已禁用
        "priority": 6,
        "notes": "[已禁用] 域名失效或站点关闭",
        "anti_bot": True,
    },

    {
        # =========================================================================
        # Javbooks - 已禁用：站点失效
        # =========================================================================
        "id": "javbooks",
        "name": "Javbooks",
        "name_cn": "Javbooks",
        "base_url": "https://jkk044.com",
        "search_url": "/serchinfo_censored/IamOverEighteenYearsOld/topicsbt_1.htm?keyword={code}",
        "enabled": False,                             # 已禁用
        "priority": 7,
        "notes": "[已禁用] 站点结构变化，搜索无结果",
        "anti_bot": False,
    },

    {
        # =========================================================================
        # Javhoo - 已禁用：404 Not Found
        # =========================================================================
        "id": "javhoo",
        "name": "Javhoo",
        "name_cn": "Javhoo",
        "base_url": "https://www.javhoo.com",
        "search_url": "/search?q={code}",
        "enabled": False,                             # 已禁用
        "priority": 8,
        "notes": "[已禁用] 域名 404，无法访问",
        "anti_bot": False,
    },

    {
        # =========================================================================
        # Javd - 已禁用：404 Not Found
        # =========================================================================
        "id": "javd",
        "name": "Javd",
        "name_cn": "Javd",
        "base_url": "https://cn.javd.me",
        "search_url": "/search?q={code}",
        "enabled": False,                             # 已禁用
        "priority": 9,
        "notes": "[已禁用] 域名 404，需要寻找新域名",
        "anti_bot": False,
    },

    {
        # =========================================================================
        # Jav情报站 - 已禁用：需要复杂 hash 验证
        # =========================================================================
        "id": "javinfo",
        "name": "Jav情报站",
        "name_cn": "Jav情报站",
        "base_url": "https://pc5.top",
        "search_url": "/search?q={code}",
        "enabled": False,                             # 已禁用
        "priority": 10,
        "notes": "[已禁用] 需要先获取 hash 验证，复杂度高",
        "anti_bot": False,
    },
]


# ===============================================================================
# 配置获取函数
# ===============================================================================

def get_enabled_sources() -> List[Dict]:
    """
    功能: 获取所有启用的数据源，按优先级排序
    文件: config.py
    返回: List[Dict] - 启用的数据源列表
    依赖: SCRAPER_SOURCES
    使用语法:
        from config import get_enabled_sources
        sources = get_enabled_sources()
    """
    # 过滤出 enabled=True 的数据源
    # 语法: 列表推导式 + sorted 排序
    enabled = [s for s in SCRAPER_SOURCES if s.get("enabled", True)]
    return sorted(enabled, key=lambda x: x.get("priority", 99))


def get_source_by_id(source_id: str) -> Optional[Dict]:
    """
    功能: 根据 ID 获取单个数据源配置
    文件: config.py
    参数:
        source_id: 数据源 ID (如 "avdanyuwiki")
    返回: Optional[Dict] - 数据源配置或 None
    依赖: SCRAPER_SOURCES
    使用语法:
        source = get_source_by_id("avdanyuwiki")
    """
    # 遍历查找匹配的 ID
    # 语法: next() + 生成器表达式
    for source in SCRAPER_SOURCES:
        if source["id"] == source_id:
            return source
    return None


def get_source_urls(source_id: str) -> tuple:
    """
    功能: 获取数据源的 URL 列表（包括备选域名）
    文件: config.py
    参数:
        source_id: 数据源 ID
    返回: tuple - URL 元组
    依赖: get_source_by_id
    使用语法:
        urls = get_source_urls("javdb")
        # 返回: ("https://javdb564.com", "https://javdb565.com", ...)
    """
    source = get_source_by_id(source_id)
    if not source:
        return ()

    urls = [source["base_url"]]
    # 检查是否有备选域名
    if "fallback_domains" in source:
        urls.extend(source["fallback_domains"])
    return tuple(urls)


# ===============================================================================
# 通用配置
# ===============================================================================

# 刮削配置 - 控制爬虫行为
SCRAPE_CONFIG = {
    "max_results": 10,                    # 最多返回结果数
    "require_exact_match": False,         # 是否要求精确匹配番号
    "fallback_to_first": True,            # 没有精确匹配时使用第一个结果
}

# 代理配置 - 可选，用于绕过 IP 限制
# 使用方法: 设置 enabled=True 并填入代理地址
PROXY_CONFIG = {
    "enabled": False,                     # 是否启用代理
    "http": "",                          # HTTP 代理地址
    "https": "",                         # HTTPS 代理地址
}

# Cookie 配置 - 可选，用于需要登录的网站
COOKIE_CONFIG = {
    "enabled": False,                    # 是否启用 Cookie
    "cookies": {},                       # Cookie 字典
}
