"""
配置加载模块
从 config.ini 读取所有初始化变量，支持相对路径解析
"""
import configparser
import json
import os
from pathlib import Path

# config.ini 所在目录（即 backend/）
_CONFIG_DIR = Path(__file__).parent
_CONFIG_FILE = _CONFIG_DIR / "config.ini"


def _load() -> configparser.ConfigParser:
    """加载 config.ini，若不存在则返回空配置"""
    cfg = configparser.ConfigParser()
    if _CONFIG_FILE.exists():
        cfg.read(_CONFIG_FILE, encoding="utf-8")
    return cfg


_cfg = _load()


def get(section: str, key: str, fallback=None):
    """读取配置值（字符串），不存在则返回 fallback"""
    try:
        return _cfg.get(section, key)
    except (configparser.NoSectionError, configparser.NoOptionError):
        return fallback


def getint(section: str, key: str, fallback: int = 0) -> int:
    """读取配置值（整数）"""
    try:
        return _cfg.getint(section, key)
    except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
        return fallback


def getfloat(section: str, key: str, fallback: float = 0.0) -> float:
    """读取配置值（浮点数）"""
    try:
        return _cfg.getfloat(section, key)
    except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
        return fallback


def getbool(section: str, key: str, fallback: bool = False) -> bool:
    """读取配置值（布尔）"""
    try:
        return _cfg.getboolean(section, key)
    except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
        return fallback


def resolve_path(relative_path: str) -> Path:
    """将相对于 backend/ 的路径解析为绝对路径"""
    path = _CONFIG_DIR / relative_path
    return path.resolve()


# ============================================================
# 导出常用配置（供 main.py / start-backend.ps1 使用）
# ============================================================

# Server
HOST = get("server", "host", "0.0.0.0")
PORT = getint("server", "port", 8000)

# Paths
DATA_DIR = resolve_path(get("paths", "data_dir", "../data"))
COVERS_DIR = DATA_DIR / "covers"
FRONTEND_DIR = resolve_path(get("paths", "frontend_dir", "../frontend"))
INFO_DIR = resolve_path(get("paths", "info_dir", "../info"))

# CORS
CORS_ORIGINS = get("cors", "allow_origins", "*")
CORS_CREDENTIALS = getbool("cors", "allow_credentials", True)
CORS_METHODS = get("cors", "allow_methods", "*")
CORS_HEADERS = get("cors", "allow_headers", "*")

# Scrape
SAVE_COVER_DEFAULT = getbool("scrape", "save_cover", True)
SCRAPE_TIMEOUT = getint("scrape", "timeout", 30)
DEFAULT_DELAY = getfloat("scrape", "default_delay", 1.0)
DEFAULT_RETRY = getint("scrape", "default_retry", 2)

# Page
DEFAULT_PAGE_SIZE = getint("page", "default_page_size", 20)
MAX_PAGE_SIZE = getint("page", "max_page_size", 100)


# ============================================================
# 爬虫数据源配置
# ============================================================

# HTTP 默认请求头
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def _parse_sources() -> list:
    """从 [sources] 配置节加载爬虫数据源列表"""
    raw = get("sources", "sources_json", "[]")
    try:
        # 尝试解析 JSON（支持单行或多行格式）
        return json.loads(raw)
    except json.JSONDecodeError:
        return []


SCRAPER_SOURCES = _parse_sources()


def get_enabled_sources() -> list:
    """返回所有已启用的数据源，按 priority 升序排列"""
    enabled = [s for s in SCRAPER_SOURCES if s.get("enabled", False)]
    return sorted(enabled, key=lambda x: x.get("priority", 999))


def get_source_by_id(source_id: str) -> dict:
    """根据 id 查找数据源，未找到返回空字典"""
    for s in SCRAPER_SOURCES:
        if s.get("id") == source_id:
            return s
    return {}
