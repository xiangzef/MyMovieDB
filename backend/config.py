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


# ============================================================
# 路径翻译：容器内 Linux 路径 <-> Windows 可读形式
# ============================================================
# 用途：浏览器点「播放」时，前端发的是容器里 /media/... 的路径，
# 但 迅雷播放器 / os.startfile 在 Windows 上跑，需要把 /media/...
# 翻译成 \\<NAS_IP>\volume2\home1\jellyfin\... 之类的 Windows 可读形式。
#
# 翻译逻辑（main.py.to_windows_path 用）：
#   1. 优先用 local_sources.windows_path 显式映射（最长前缀匹配）
#   2. 兜底：从 /proc/mounts 找容器挂载点的宿主机路径，
#      拼成 \\<NAS_IP>\<host_path>\...
#   3. 都没有：返回原路径（启动播放器会失败，给出明确错误）

# NAS 内网 IP（SMB 访问的地址）
NAS_IP = get("nas", "ip", "192.168.1.179")


# 缓存：容器内路径 -> 宿主机路径
_MOUNT_CACHE: dict = {}


def _load_mounts() -> dict:
    """从 /proc/mounts 读取挂载点，返回 {容器内路径: 宿主机路径}。

    只关心 bind mount（Source 字段在容器内表现为文件系统挂载）。
    """
    global _MOUNT_CACHE
    if _MOUNT_CACHE:
        return _MOUNT_CACHE
    mounts_file = Path("/proc/mounts")
    if not mounts_file.exists():
        return _MOUNT_CACHE
    out = {}
    try:
        for line in mounts_file.read_text(encoding="utf-8", errors="replace").splitlines():
            parts = line.split()
            if len(parts) < 3:
                continue
            mount_point = parts[1]
            fstype = parts[2]
            # 我们只关心 overlay 之外的真挂载（bind mount 会显示成 ext4/nfs/tfsp 等）
            if mount_point in ("/", "/dev", "/proc", "/sys", "/etc/hosts", "/dev/pts"):
                continue
            # 在容器内看不到宿主机的源路径（bind mount 在容器内 /proc/mounts
            # 显示的是 mount_point，源在容器内不可见）。所以我们靠 docker
            # inspect 拿的 volume 列表来推断，或在 NAS 端用 mount 命令。
            # 这里走「目录存在性 + 已知前缀」匹配：
            if Path(mount_point).is_dir():
                out[mount_point] = mount_point
    except Exception:
        pass
    _MOUNT_CACHE = out
    return _MOUNT_CACHE


def get_host_path_for(container_path: str) -> Optional[str]:
    """把容器内路径换算成 NAS 宿主机上的路径（如果可推断）。

    容器内 /proc/mounts 没有 bind mount 的源信息；这条函数主要靠
    外部注入（NAS_SMB_VOLUMES 配置）来告诉后端「/media/jellyfin
    这个容器挂载，对应 NAS 上的 /volume2/home1/jellyfin」。
    """
    smb_volumes = _parse_smb_volumes()
    norm = container_path.rstrip("/\\")
    for container_prefix, host_prefix in smb_volumes:
        if norm == container_prefix or norm.startswith(container_prefix + "/") or \
           norm.startswith(container_prefix + "\\"):
            return host_prefix + norm[len(container_prefix):]
    return None


def _parse_smb_volumes() -> list:
    """从 [nas] smb_volumes_json 读「容器前缀, NAS 宿主机前缀」对。

    例：
        smb_volumes_json = [
            ["/media/jellyfin/", "/volume2/home1/jellyfin/"],
            ["/media/jellyfin2/", "/volume3/home2/jellyfin/"],
            ["/media/影视库/", "/volume5/home5/影视库/"]
        ]
    """
    raw = get("nas", "smb_volumes_json", "[]")
    try:
        pairs = json.loads(raw)
        if not isinstance(pairs, list):
            return []
        out = []
        for p in pairs:
            if isinstance(p, (list, tuple)) and len(p) == 2:
                out.append((str(p[0]), str(p[1])))
        return out
    except (json.JSONDecodeError, TypeError):
        return []
