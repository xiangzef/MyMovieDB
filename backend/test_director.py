import requests
from bs4 import BeautifulSoup
import re
from scraper import FanzaScraper

# 测试 Fanza 爬虫
print('=== 测试 Fanza 爬虫 ===')
scraper = FanzaScraper()
result = scraper.scrape('JUFE-238')
if result:
    print(f'director: {result.get("director", "N/A")}')
else:
    print('爬虫返回 None')
