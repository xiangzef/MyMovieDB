"""
Fanza 爬虫测试 - 测试 Fanza (DMM) 数据源
合并自: test_fanza_simple.py, test_fanza_full.py, test_fanza_direct.py, test_director.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scraper import FanzaScraper

def test_fanza():
    print("\n" + "="*60)
    print("测试 Fanza (DMM) 爬虫")
    print("="*60)

    scraper = FanzaScraper()
    test_codes = ["SSIS-254", "JUFE-238"]

    for code in test_codes:
        print(f"\n--- {code} ---")
        result = scraper.scrape(code)
        if result:
            print(f"✅ 标题: {result.get('title_jp', '')[:60]}")
            print(f"  演员: {result.get('actors', [])}")
            print(f"  发行: {result.get('studio')}")
            print(f"  制作: {result.get('maker')}")
            print(f"  导演: {result.get('director')}")
            print(f"  日期: {result.get('release_date')}")
            print(f"  时长: {result.get('duration')} 分钟")
            print(f"  封面: {'有' if result.get('cover_url') else '无'}")
        else:
            print("❌ 爬取失败")

if __name__ == "__main__":
    test_fanza()
