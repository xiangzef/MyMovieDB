from scraper import AvdanyuwikiScraper
import sys

sys.stdout.reconfigure(encoding='utf-8')

scraper = AvdanyuwikiScraper()

# 测试番号格式转换
print("Search variants:")
variants = scraper._generate_search_variants("SSIS-254")
for v in variants:
    print(f"  - {v}")

print("\nTesting search...")
result = scraper.search("SSIS-254")

if result:
    print(f"\nFound {len(result)} results:")
    for key, value in result[0].items():
        if isinstance(value, list):
            print(f"  {key}: {value}")
        elif isinstance(value, str) and len(value) > 100:
            print(f"  {key}: {value[:100]}...")
        else:
            print(f"  {key}: {value}")
else:
    print("No results found")
