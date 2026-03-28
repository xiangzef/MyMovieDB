from scraper import scrape_movie
import json
import sys

# 强制 UTF-8 输出
sys.stdout.reconfigure(encoding='utf-8')

codes = ["SSIS-254", "JUFE-238", "ABP-567"]

for code in codes:
    print(f"\n{'='*60}")
    print(f"Testing: {code}")
    print('='*60)
    result = scrape_movie(code, save_cover=False)
    if result:
        print(f"Title: {result.get('title')}")
        print(f"Cover: {result.get('cover_url')}")
        print(f"Actors: {result.get('actors')}")
        print(f"Release: {result.get('release_date')}")
        print(f"Genres: {result.get('genres')}")
        print(f"Source: {result.get('scrape_source')}")
    else:
        print("No result!")

