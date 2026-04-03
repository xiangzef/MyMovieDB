"""
gfriends 头像引擎
- 从 gfriends 仓库获取女演员头像
- 本地缓存avatar/目录
- 支持按名字查询头像URL
- 支持批量下载头像
"""
import os
import io
import json
import time
import logging
import requests
import threading
from pathlib import Path
from PIL import Image
from hashlib import md5
from urllib.parse import quote

logger = logging.getLogger(__name__)

# ========== 配置 ==========
BASE_DIR = Path(__file__).resolve().parent.parent
AVATAR_DIR = BASE_DIR / "data" / "avatars"
AVATAR_DIR.mkdir(parents=True, exist_ok=True)

# gfriends 仓库地址
GFRIENDS_RAW = "https://raw.githubusercontent.com/gfriends/gfriends/master/"
FILETREE_URL = GFRIENDS_RAW + "Filetree.json"
CONTENT_BASE = GFRIENDS_RAW + "Content"

# 备用镜像（官方）
GFRIENDS_MIRRORS = [
    "https://raw.githubusercontent.com/gfriends/gfriends/master/",
    "https://mirror.ghproxy.com/https://raw.githubusercontent.com/gfriends/gfriends/master/",
]

# 请求会话
_session = None
_session_lock = threading.Lock()

def _get_session():
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({
            "User-Agent": "MyMovieDB/1.0 (gfriends-client)",
            "Accept-Encoding": "gzip, deflate",
        })
        # 适配配置里的代理
        try:
            from config import cfg
            proxy = getattr(cfg, 'PROXY', None)
            if proxy:
                _session.proxies = {"http": proxy, "https": proxy}
        except:
            pass
    return _session


# ========== 头像文件树缓存 ==========
# Filetree.json 在本地缓存，过期时间24小时
_filetree_cache = {"data": None, "mtime": 0}
_CACHE_TTL = 24 * 3600  # 24小时


def get_filetree(force_refresh=False):
    """
    获取 gfriends Filetree.json（演员名→头像URL映射）
    优先使用本地缓存，24小时刷新一次
    """
    global _filetree_cache

    now = time.time()
    if (not force_refresh
            and _filetree_cache["data"] is not None
            and now - _filetree_cache["mtime"] < _CACHE_TTL):
        return _filetree_cache["data"]

    cache_file = AVATAR_DIR / "filetree.json"

    # 尝试读本地缓存
    if not force_refresh and cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            _filetree_cache["data"] = data
            _filetree_cache["mtime"] = os.path.getmtime(cache_file)
            logger.info(f"gfriends 文件树加载成功（本地缓存），共 {data.get('Information', {}).get('TotalNum', 0)} 名演员")
            return data
        except Exception as e:
            logger.warning(f"读取本地缓存失败: {e}")

    # 从网络获取
    for mirror in GFRIENDS_MIRRORS:
        try:
            url = mirror + "Filetree.json"
            session = _get_session()
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
            resp.encoding = "utf-8"

            data = json.loads(resp.text.replace("AI-Fix-", ""))

            # 保存本地缓存
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)

            _filetree_cache["data"] = data
            _filetree_cache["mtime"] = time.time()
            total = data.get("Information", {}).get("TotalNum", 0)
            logger.info(f"gfriends 文件树下载成功，共 {total} 名演员")
            return data
        except Exception as e:
            logger.warning(f"gfriends 镜像 {mirror} 下载失败: {e}")
            continue

    # 兜底：用本地缓存
    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            _filetree_cache["data"] = data
            logger.warning("使用过期的本地文件树缓存")
            return data
        except:
            pass

    logger.error("gfriends 文件树获取全部失败")
    return None


def _name_to_url(name: str, url_base=CONTENT_BASE) -> str:
    """
    将演员名转换为 gfriends 仓库中的目录路径和头像URL
    按姓名字典序确定子目录：あ行→A, か行→K, 等
    """
    # 日文名按读音分组（gfriends 使用罗马字/日文混合目录）
    # 实际 gfriends 按 Unicode 码点分组，我们直接搜索
    # 规则：取名字第一个字符的 Unicode 范围对应目录
    first_char = name[0] if name else ""
    # 日文平假名/片假名/汉字混排，直接用第一个字符
    dir_char = _char_to_dir(first_char)
    return f"{url_base}/{dir_char}/{_escape_name(name)}"


def _char_to_dir(char: str) -> str:
    """将日文/罗马字首字符映射到 gfriends 目录字母"""
    c = ord(char)
    # 平假名 range: 12352-12447, 片假名: 12448-12543
    if 12352 <= c <= 12447:  # 平假名
        # 转换为片假名
        c = c + 96
    if 12448 <= c <= 12543:  # 片假名
        pass
    # 取片假名转罗马字
    hira_to_kana = {
        'ア': 'A', 'イ': 'I', 'ウ': 'U', 'エ': 'E', 'オ': 'O',
        'カ': 'K', 'キ': 'K', 'ク': 'K', 'ケ': 'K', 'コ': 'K',
        'サ': 'S', 'シ': 'S', 'ス': 'S', 'セ': 'S', 'ソ': 'S',
        'タ': 'T', 'チ': 'T', 'ツ': 'T', 'テ': 'T', 'ト': 'T',
        'ナ': 'N', 'ニ': 'N', 'ヌ': 'N', 'ネ': 'N', 'ノ': 'N',
        'ハ': 'H', 'ヒ': 'H', 'フ': 'H', 'ヘ': 'H', 'ホ': 'H',
        'マ': 'M', 'ミ': 'M', 'ム': 'M', 'メ': 'M', 'モ': 'M',
        'ヤ': 'Y', 'ユ': 'Y', 'ヨ': 'Y',
        'ラ': 'R', 'リ': 'R', 'ル': 'R', 'レ': 'R', 'ロ': 'R',
        'ワ': 'W', 'ヲ': 'W', 'ン': 'N',
    }
    char_kata = chr(c) if 12352 <= ord(char) <= 12447 else char
    return hira_to_kana.get(char_kata, char_kata.upper()[:1])


def _escape_name(name: str) -> str:
    """URL 编码演员名，保留斜杠（因为目录可能有多层）"""
    # gfriends 仓库中名字不会被 URL 编码，但空格会被替换
    return name.replace("/", "／")  # 全角斜杠


def search_avatar_url(actor_name: str, force_refresh=False) -> list:
    """
    在 gfriends 文件树中搜索演员头像 URL
    返回: [{url, is_aifix}, ...] 列表，或空列表
    """
    filetree = get_filetree(force_refresh=force_refresh)
    if not filetree:
        return []

    content = filetree.get("Content", {})
    results = []

    # 精确匹配（最优先）
    exact = _escape_name(actor_name)
    for sub_dir, files in content.items():
        for filename, url_path in files.items():
            key = filename.replace(".jpg", "").replace(".png", "")
            if key == exact or key == actor_name:
                is_aifix = "AI-Fix" in url_path or "AI-Fix" in filename
                results.insert(0, {
                    "url": CONTENT_BASE + "/" + sub_dir + "/" + filename,
                    "is_aifix": is_aifix,
                    "match": "exact"
                })

    # 去重（可能有多个同名）
    seen_urls = set()
    unique_results = []
    for r in results:
        if r["url"] not in seen_urls:
            seen_urls.add(r["url"])
            unique_results.append(r)

    return unique_results


def lookup_actor(actor_name: str) -> dict:
    """
    查询演员是否存在 gfriends 仓库中
    返回: {"exists": bool, "urls": [...], "cached": bool, "local_path": str}
    """
    urls = search_avatar_url(actor_name)
    exists = len(urls) > 0

    # 检查本地缓存
    local_path = get_local_avatar_path(actor_name)
    cached = local_path is not None and local_path.exists()

    return {
        "exists": exists,
        "urls": urls,
        "cached": cached,
        "local_path": str(local_path) if cached else None,
        "total_in_repo": len(urls),
    }


def _safe_filename(name: str) -> str:
    """
    将演员姓名转换为安全的文件名（直接用真实名字，去除非法字符）。
    Windows 文件名非法字符: \\ / : * ? " < > |
    """
    if not name:
        return None
    # 替换非法字符为全角或下划线
    illegal = r'\/:*?"<>|'
    result = name
    for ch in illegal:
        result = result.replace(ch, '_')
    return result.strip()


def _get_avatar_filename(actor_name: str, for_lookup: bool = False) -> str:
    """
    将演员姓名转换为文件名（使用真实名字，不做 URL 编码）。
    Starlette StaticFiles 会对 URL 做 decode，所以文件名必须是真实字符。
    """
    if not actor_name or actor_name == "佚名":
        return None
    return _safe_filename(actor_name)


def _safe_exists(path):
    """安全检查文件是否存在（处理非法路径名/超长路径错误）"""
    try:
        return path.exists()
    except OSError:
        return False


def get_local_avatar_path(actor_name: str) -> Path:
    """
    获取本地缓存的头像路径。
    查找顺序：
      1. 真实名字格式（当前格式，如 三上悠亜.jpg）
      2. MD5 兜底格式（最早期文件）
    """
    if not actor_name or actor_name == "佚名":
        return None

    safe_name = _safe_filename(actor_name)
    if not safe_name:
        return None

    # 1) 真实名字格式（当前逻辑）
    path = AVATAR_DIR / f"{safe_name}.jpg"
    if _safe_exists(path):
        return path
    path_png = AVATAR_DIR / f"{safe_name}.png"
    if _safe_exists(path_png):
        return path_png

    # 2) MD5 兜底（早期文件）
    hash_name = md5(actor_name.encode("utf-8")).hexdigest()[12:-12]
    path = AVATAR_DIR / f"{hash_name}.jpg"
    if _safe_exists(path):
        return path
    path_png = AVATAR_DIR / f"{hash_name}.png"
    if _safe_exists(path_png):
        return path_png

    return None


def get_local_avatar_url(actor_name: str) -> str:
    """
    获取本地头像的 HTTP URL 路径（供前端使用）。
    返回: /avatars/{URL编码名字}.jpg 或 None
    注意：URL 中用 quote 编码，文件系统中用真实名字，Starlette 自动 decode 匹配。
    """
    if not actor_name or actor_name == "佚名":
        return None

    safe_name = _safe_filename(actor_name)
    if not safe_name:
        return None

    # 1) 真实名字格式（当前逻辑）
    path_jpg = AVATAR_DIR / f"{safe_name}.jpg"
    if _safe_exists(path_jpg):
        # URL 中对名字做编码，Starlette decode 后找到真实文件
        return f"/avatars/{quote(safe_name, safe='')}.jpg"
    path_png = AVATAR_DIR / f"{safe_name}.png"
    if _safe_exists(path_png):
        return f"/avatars/{quote(safe_name, safe='')}.png"

    # 2) MD5 兜底（早期文件）
    hash_name = md5(actor_name.encode("utf-8")).hexdigest()[12:-12]
    path_jpg = AVATAR_DIR / f"{hash_name}.jpg"
    if _safe_exists(path_jpg):
        return f"/avatars/{hash_name}.jpg"
    path_png = AVATAR_DIR / f"{hash_name}.png"
    if _safe_exists(path_png):
        return f"/avatars/{hash_name}.png"

    return None


def download_avatar(actor_name: str, url: str, prefer_aifix=True) -> bool:
    """
    下载单个头像到本地缓存（用真实名字存储，如 三上悠亜.jpg）。
    prefer_aifix: 优先选择 AI-Fix 版本（更高质量）
    """
    if not actor_name or actor_name == "佚名":
        return False

    safe_name = _safe_filename(actor_name)
    if not safe_name:
        return False

    local_path = AVATAR_DIR / f"{safe_name}.jpg"
    # 已存在则跳过（除非文件损坏）
    if local_path.exists():
        try:
            Image.open(local_path).verify()
            return True  # 已缓存
        except:
            pass  # 文件损坏，重新下载

    # 备查：MD5 格式（早期文件）
    hash_name = md5(actor_name.encode("utf-8")).hexdigest()[12:-12]
    old_path = AVATAR_DIR / f"{hash_name}.jpg"
    if old_path.exists():
        try:
            Image.open(old_path).verify()
            return True  # 旧文件已存在（不迁移，保留兼容）
        except:
            pass

    try:
        session = _get_session()
        resp = session.get(url, timeout=15)
        resp.raise_for_status()

        # 校验图片
        try:
            Image.open(io.BytesIO(resp.content)).verify()
        except:
            logger.warning(f"头像校验失败: {actor_name} <- {url}")
            return False

        # 保存
        with open(local_path, "wb") as f:
            f.write(resp.content)

        logger.debug(f"头像下载成功: {actor_name} → {filename}.jpg")
        return True
    except Exception as e:
        logger.warning(f"头像下载失败: {actor_name} <- {url}: {e}")
        return False


def batch_download_avatars(actor_names: list, max_workers=5, delay=0.3) -> dict:
    """
    批量下载演员头像（多线程）
    actor_names: 演员名列表
    返回: {"success": [...], "fail": [...], "skipped": [...], "total": int}
    """
    results = {"success": [], "fail": [], "skipped": [], "total": len(actor_names)}

    # 过滤掉佚名和已缓存的
    to_download = []
    for name in actor_names:
        if not name or name == "佚名":
            results["skipped"].append(name)
            continue
        local = get_local_avatar_path(name)
        if local and local.exists():
            results["success"].append(name)  # 已缓存，算成功
        else:
            to_download.append(name)

    if not to_download:
        return results

    def download_one(name):
        urls = search_avatar_url(name)
        if not urls:
            return ("fail", name)
        # 优先 AI-Fix
        url = None
        for u in urls:
            if u["is_aifix"] and prefer_aifix:
                url = u["url"]
                break
        if url is None:
            url = urls[0]["url"]
        ok = download_avatar(name, url)
        return ("success" if ok else "fail", name)

    # 简单多线程
    threads = []
    for name in to_download:
        t = threading.Thread(target=lambda n=name: results[download_one(n)[0]].append(n))
        threads.append(t)
        t.start()
        time.sleep(delay / max_workers)  # 限速
        if len([t for t in threads if t.is_alive()]) >= max_workers:
            for tt in threads:
                tt.join()

    for t in threads:
        t.join()

    return results


def is_real_actress(actor_name: str) -> bool:
    """
    判断演员是否为 gfriends 仓库收录的真实 AV 女优
    收录 → 真实女优（知名艺名）
    未收录 → 可能是素人/临时艺名/马甲
    """
    if not actor_name or actor_name == "佚名":
        return False
    result = lookup_actor(actor_name)
    return result["exists"]


# ========== 供 FastAPI 静态文件服务 ==========
def get_avatar_dir() -> Path:
    return AVATAR_DIR
