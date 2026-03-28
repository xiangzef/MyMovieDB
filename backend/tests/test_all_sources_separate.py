"""
测试多数据源合并效果
"""
import time
from scraper import AvbaseScraper, AvWikiScraper, JavcupScraper, AvdanyuwikiScraper

def test_separate_sources():
    """分别测试各个数据源"""
    print("\n" + "="*60)
    print("分别测试各个数据源")
    print("="*60)
    
    test_code = "SSIS-254"
    
    # 1. Avbase
    print(f"\n--- 1. Avbase ---")
    scraper1 = AvbaseScraper(delay=0.5)
    result1 = scraper1.scrape(test_code)
    if result1:
        print(f"标题: {result1.get('title_jp', '')[:60]}...")
        print(f"演员: {result1.get('actors', [])}")
        print(f"封面: {result1.get('cover_url', '')[:60]}...")
    
    time.sleep(2)
    
    # 2. AV-Wiki
    print(f"\n--- 2. AV-Wiki ---")
    scraper2 = AvWikiScraper(delay=0.5)
    result2 = scraper2.scrape(test_code)
    if result2:
        print(f"标题: {result2.get('title', '')[:60]}...")
        print(f"演员: {result2.get('actors', [])}")
        print(f"封面: {result2.get('cover_url', '')[:60]}...")
    
    time.sleep(2)
    
    # 3. Javcup
    print(f"\n--- 3. Javcup ---")
    scraper3 = JavcupScraper(delay=0.5)
    result3 = scraper3.scrape(test_code)
    if result3:
        print(f"标题: {result3.get('title', '')[:60]}...")
        print(f"演员: {result3.get('actors', [])}")
        print(f"封面: {result3.get('cover_url', '')[:60]}...")
    
    time.sleep(2)
    
    # 4. Avdanyuwiki
    print(f"\n--- 4. Avdanyuwiki ---")
    scraper4 = AvdanyuwikiScraper(delay=0.5)
    result4 = scraper4.scrape(test_code)
    if result4:
        print(f"标题: {result4.get('title_jp', '')[:60]}...")
        print(f"演员: {result4.get('actors', [])}")
        print(f"男优: {result4.get('actors_male', [])}")
        print(f"封面: {result4.get('cover_url', '')[:60]}...")
    
    print("\n" + "="*60)
    print("测试完成")
    print("="*60)


if __name__ == "__main__":
    test_separate_sources()
