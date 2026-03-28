"""快速测试 Avbase"""
from scraper import AvbaseScraper

scraper = AvbaseScraper()
test_codes = ['IPZZ-792', 'GQN-011', 'JUR-664', 'IPZZ-776']

print("\nAvbase 测试结果:")
print("-" * 50)
for code in test_codes:
    result = scraper.search(code)
    if result:
        title = result[0]['title'][:40]
        print(f"OK   {code}: {title}...")
    else:
        print(f"EMPTY {code}")
