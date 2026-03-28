from scraper import AvbaseScraper
import sys

sys.stdout.reconfigure(encoding='utf-8')

scraper = AvbaseScraper()
result = scraper.scrape("SSIS-254")

if result:
    print("AvbaseScraper result:")
    for k, v in result.items():
        print(f"  {k}: {v}")
else:
    print("No result")
