"""
Jellyfin/Kodi 格式 NFO 文件解析模块
功能：扫描已整理的影视目录，解析 NFO 元数据，导入数据库
作者：高级开发者
日期：2026-03-29
"""
import os
import re
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# 尝试导入 chardet，如果没有则使用默认编码
try:
    import chardet
    HAS_CHARDET = True
except ImportError:
    HAS_CHARDET = False

# 番号正则（与 main.py 保持一致）
CODE_PATTERN = re.compile(r'^[A-Z]{2,6}-\d{2,5}$', re.IGNORECASE)
VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.wmv', '.flv', '.mov', '.mpg', '.mpeg', '.m2ts', '.ts'}
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}


def detect_encoding(file_path: str) -> str:
    """检测文件编码"""
    if HAS_CHARDET:
        with open(file_path, 'rb') as f:
            raw = f.read(10000)  # 读取前 10KB 判断编码
            result = chardet.detect(raw)
            return result.get('encoding') or 'utf-8'
    else:
        # 没有 chardet，尝试常见编码
        for encoding in ['utf-8', 'utf-8-sig', 'gbk', 'gb2312', 'big5']:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    f.read(10000)
                return encoding
            except UnicodeDecodeError:
                continue
        return 'utf-8'


def parse_jellyfin_nfo(nfo_path: str) -> Optional[Dict]:
    """
    解析 Jellyfin/Kodi 格式的 NFO 文件
    
    Args:
        nfo_path: NFO 文件路径
    
    Returns:
        影片信息字典，解析失败返回 None
    """
    try:
        encoding = detect_encoding(nfo_path)
        with open(nfo_path, 'r', encoding=encoding, errors='ignore') as f:
            content = f.read()
        
        # 去除 BOM 标记
        if content.startswith('\ufeff'):
            content = content[1:]
        
        # 去除 XML 声明前的空白
        content = content.strip()
        
        root = ET.fromstring(content)
        
        # 提取演员（区分男女）
        actors = []
        actors_male = []
        for actor in root.findall('actor'):
            name = actor.findtext('name', '').strip()
            if not name:
                continue
            role = actor.findtext('role', '').lower()
            actor_type = actor.findtext('type', '').lower()
            is_male = 'male' in role or 'male' in actor_type or '男' in role
            is_not_actress = 'actress' not in actor_type
            if is_male or is_not_actress:
                # 明确标记为男优，或未标记为女演员
                if is_male:
                    actors_male.append(name)
                else:
                    actors.append(name)
            else:
                actors.append(name)
        
        # 提取标签
        genres = [g.text.strip() for g in root.findall('genre') if g.text]
        tags = [t.text.strip() for t in root.findall('tag') if t.text]
        
        # 合并 genres 和 tags
        all_tags = list(set(genres + tags))
        
        # 提取图片路径（thumb 标签）
        poster_path = None
        fanart_path = None
        thumb_path = None
        
        for thumb in root.findall('thumb'):
            aspect = thumb.get('aspect', '').lower()
            text = (thumb.text or '').strip()
            if not text:
                continue
            if 'poster' in aspect or 'poster' in text.lower():
                poster_path = text
            elif 'fanart' in aspect or 'fanart' in text.lower() or 'backdrop' in aspect:
                fanart_path = text
            else:
                thumb_path = text
        
        # 尝试从 fanart 标签获取背景图
        fanart_elem = root.find('fanart')
        if fanart_elem is not None:
            for thumb in fanart_elem.findall('thumb'):
                text = (thumb.text or '').strip()
                if text and not fanart_path:
                    fanart_path = text
        
        # 解析发布日期
        release_date = root.findtext('releasedate', '').strip()
        if not release_date:
            release_date = root.findtext('year', '').strip()
            if release_date and len(release_date) == 4:
                release_date = f"{release_date}-01-01"
        
        result = {
            'title': root.findtext('title', '').strip() or None,
            'title_jp': root.findtext('originaltitle', '').strip() or None,
            'plot': root.findtext('plot', '').strip() or None,
            'release_date': release_date or None,
            'studio': root.findtext('studio', '').strip() or None,
            'maker': root.findtext('maker', '').strip() or None,
            'director': root.findtext('director', '').strip() or None,
            'actors': actors if actors else None,
            'actors_male': actors_male if actors_male else None,
            'genres': all_tags if all_tags else None,
            'poster_path': poster_path,
            'fanart_path': fanart_path,
            'thumb_path': thumb_path,
        }
        
        # 清理空值
        return {k: v for k, v in result.items() if v}
    
    except ET.ParseError as e:
        print(f"[Jellyfin] XML 解析失败: {nfo_path}, 错误: {e}")
        return None
    except Exception as e:
        print(f"[Jellyfin] 解析 NFO 失败: {nfo_path}, 错误: {e}")
        return None


def scan_jellyfin_directory(directory: str) -> List[Dict]:
    """
    扫描 Jellyfin 格式目录，返回所有有效影片信息
    
    目录结构期望：
    根目录/
    ├── 女星A/
    │   ├── SSIS-001/
    │   │   ├── SSIS-001.mp4
    │   │   ├── SSIS-001.nfo
    │   │   ├── SSIS-001-poster.jpg
    │   │   └── SSIS-001-fanart.jpg
    │   └── SSIS-002/
    │       └── ...
    └── ...
    
    或者直接：
    根目录/
    ├── SSIS-001/
    │   ├── SSIS-001.mp4
    │   ├── SSIS-001.nfo
    │   └── ...
    └── ...
    
    Args:
        directory: 根目录路径（如 Z:\\影视库）
    
    Returns:
        影片信息列表，每项包含 code, video_path, nfo_path, metadata, 图片路径
    """
    results = []
    root_path = Path(directory)
    
    if not root_path.exists():
        print(f"[Jellyfin] 目录不存在: {directory}")
        return results
    
    print(f"[Jellyfin] 开始扫描目录: {directory}")
    
    # 递归扫描所有子目录
    for dir_path in root_path.rglob('*'):
        if not dir_path.is_dir():
            continue
        
        try:
            # 检查目录名是否为番号格式
            dir_name = dir_path.name
            
            # 标准化番号（大写）
            code_match = CODE_PATTERN.match(dir_name)
            if not code_match:
                continue
            
            code = dir_name.upper()  # 标准化番号
            
            # 查找 NFO 文件（可选，支持 -C/-U/-UC/-4K 等后缀变体）
            try:
                nfo_files = list(dir_path.glob('*.nfo'))
                nfo_path = None
                if nfo_files:
                    # ① 精确匹配：NFO 文件名（去扩展名）= 目录名
                    for nf in nfo_files:
                        stem = os.path.splitext(nf.name)[0]
                        if stem.upper() == dir_name.upper():
                            nfo_path = str(nf)
                            break
                    # ② 基础番号匹配（SSIS-251-C → SSIS-251）
                    if not nfo_path:
                        base_code = re.sub(r'[-_](C|U|UC|4K|HD|KT|TT)$', '',
                                           dir_name, flags=re.IGNORECASE)
                        if base_code.upper() != dir_name.upper():
                            for nf in nfo_files:
                                stem = os.path.splitext(nf.name)[0]
                                if stem.upper() == base_code.upper():
                                    nfo_path = str(nf)
                                    break
                    # ③ 兜底：使用第一个找到的 NFO
                    if not nfo_path:
                        nfo_path = str(nfo_files[0])
            except Exception as e:
                print(f"[Jellyfin] 扫描 NFO 失败 {dir_path}: {e}")
                nfo_path = None
            
            # 查找视频文件
            try:
                video_files = [f for f in dir_path.iterdir() 
                               if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS]
            except Exception as e:
                print(f"[Jellyfin] 扫描视频失败 {dir_path}: {e}")
                continue
            
            if not video_files:
                continue
            
            video_path = str(video_files[0])
            
            # 解析 NFO（如果没有，创建基本元数据）
            if nfo_path:
                metadata = parse_jellyfin_nfo(nfo_path) or {'title': code}
            else:
                # 没有 NFO 文件，创建基本元数据
                print(f"[Jellyfin] 未找到 NFO 文件: {code}，将创建基本元数据")
                metadata = {
                    'title': code,
                    'title_jp': None,
                    'plot': None,
                    'release_date': None,
                    'studio': None,
                    'maker': None,
                    'director': None,
                    'actors': None,
                    'actors_male': None,
                    'genres': None,
                }
        
            # 查找本地图片文件
            poster_file = None
            fanart_file = None
            thumb_file = None
            
            try:
                for img_file in dir_path.iterdir():
                    if not img_file.is_file():
                        continue
                    if img_file.suffix.lower() not in IMAGE_EXTENSIONS:
                        continue
                    
                    img_name = img_file.name.lower()
                    img_name_lower = img_file.stem.lower()  # 不含扩展名
                    
                    # 优先匹配包含关键词的文件
                    if 'poster' in img_name or 'cover' in img_name:
                        poster_file = str(img_file)
                    elif 'fanart' in img_name or 'background' in img_name or 'backdrop' in img_name:
                        fanart_file = str(img_file)
                    elif 'thumb' in img_name:
                        thumb_file = str(img_file)
                    # 其次匹配文件名包含番号的
                    elif code.lower() in img_name_lower:
                        if '-poster' in img_name or '_poster' in img_name:
                            poster_file = str(img_file)
                        elif '-fanart' in img_name or '_fanart' in img_name:
                            fanart_file = str(img_file)
                        elif '-thumb' in img_name or '_thumb' in img_name:
                            thumb_file = str(img_file)
            except Exception as e:
                print(f"[Jellyfin] 扫描图片失败 {dir_path}: {e}")
            
            results.append({
                'code': code,
                'video_path': video_path,
                'nfo_path': nfo_path,
                'poster_file': poster_file,
                'fanart_file': fanart_file,
                'thumb_file': thumb_file,
                'metadata': metadata,
            })
        
        except Exception as e:
            print(f"[Jellyfin] 扫描目录失败 {dir_path}: {e}")
            continue
    
    print(f"[Jellyfin] 扫描完成，找到 {len(results)} 个有效影片目录")
    return results


def get_jellyfin_stats(directory: str) -> Dict:
    """
    获取 Jellyfin 目录统计信息
    
    Args:
        directory: 根目录路径
    
    Returns:
        统计信息字典
    """
    results = scan_jellyfin_directory(directory)
    return {
        'total': len(results),
        'directory': directory,
    }


# 测试函数
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        test_dir = sys.argv[1]
    else:
        test_dir = r"Z:\影视库"
    
    print(f"测试扫描目录: {test_dir}")
    print("-" * 50)
    
    results = scan_jellyfin_directory(test_dir)
    
    print(f"\n找到 {len(results)} 个影片:")
    for i, item in enumerate(results[:10]):  # 只显示前10个
        print(f"{i+1}. {item['code']}")
        print(f"   视频: {os.path.basename(item['video_path'])}")
        print(f"   NFO: {os.path.basename(item['nfo_path']) if item['nfo_path'] else '无'}")
        print(f"   海报: {item['poster_file'] or '无'}")
        print(f"   元数据: {item['metadata'].get('title', 'N/A')}")
        print()
