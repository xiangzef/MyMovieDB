"""
各数据源独立测试 - 分别测试每个爬虫的搜索/刮削能力
合并自: test_all_sources_separate.py, test_avbase.py, test_avbase2.py, test_avdanyu.py
"""
import time
from scraper import AvbaseScraper, AvWikiScraper, JavcupScraper, AvdanyuwikiScraper
import sys

sys.stdout.reconfigure(encoding='utf-8')

TEST_CODE = "SSIS-254"

def test_all_sources():
    sources = [
        ("Avbase", AvbaseScraper(delay=0.5)),
        ("AV-Wiki", AvWikiScraper(delay=0.5)),
        ("Javcup", JavcupScraper(delay=0.5)),
        ("Avdanyuwiki", AvdanyuwikiScraper(delay=0.5)),
    ]

    for name, scraper in sources:
        print(f"\n{'='*60}")
        print(f"测试: {name}")
        print(f"{'='*60}")
        result = scraper.scrape(TEST_CODE)
        if result:
            print(f"✅ 标题: {result.get('title', result.get('title_jp', ''))[:60]}")
            print(f"  演员: {result.get('actors', [])}")
            print(f"  封面: {'有' if result.get('cover_url') else '无'}")
        else:
            print("❌ 未找到结果")
        time.sleep(1)

if __name__ == "__main__":
    test_all_sources()
