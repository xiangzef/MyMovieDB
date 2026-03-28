"""
测试 Fanza 完整爬取
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scraper import FanzaScraper

scraper = FanzaScraper()
result = scraper.scrape("SSIS-254")

if result:
    print("✅ Fanza 爬取成功")
    print(f"标题: {result.get('title_jp', '')[:60]}...")
    print(f"演员: {result.get('actors', [])}")
    print(f"发行: {result.get('studio')}")
    print(f"制作: {result.get('maker')}")
    print(f"导演: {result.get('director')}")
    print(f"日期: {result.get('release_date')}")
    print(f"时长: {result.get('duration')} 分钟")
    print(f"类型: {result.get('genres', [])}")
    print(f"封面: {result.get('cover_url', '')[:60]}...")
else:
    print("❌ Fanza 爬取失败")
