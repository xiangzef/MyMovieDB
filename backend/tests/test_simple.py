"""
简单爬虫测试
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scraper import EnhancedMultiScraper

def test():
    scraper = EnhancedMultiScraper()
    codes = ["SSIS-254", "IPZZ-792"]
    
    for code in codes:
        print(f"\n测试 {code}...")
        result = scraper.scrape(code)
        
        if result:
            print(f"✅ 成功")
            print(f"  标题: {result.get('title_jp', '')[:50]}...")
            print(f"  演员: {result.get('actors', [])}")
            print(f"  发行: {result.get('studio')}")
            print(f"  日期: {result.get('release_date')}")
            print(f"  封面: {'有' if result.get('cover_url') else '无'}")
        else:
            print(f"❌ 失败")

if __name__ == "__main__":
    test()
