from scraper import AvbaseScraper
import sys
import json

sys.stdout.reconfigure(encoding='utf-8')

scraper = AvbaseScraper()
results = scraper.search("SSIS-254")

print(f"Found {len(results)} results")
if results:
    for key, value in results[0].items():
        if isinstance(value, list):
            print(f"  {key}: {value}")
        else:
            print(f"  {key}: {value[:100] if isinstance(value, str) and len(value) > 100 else value}")
