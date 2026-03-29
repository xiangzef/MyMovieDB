from scraper import AvdanyuwikiScraper
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

scraper = AvdanyuwikiScraper()
result = scraper.search("SSIS-254")

print("Search result:")
for key, value in result[0].items() if result else {}:
    print(f"  {key}: {value}")
