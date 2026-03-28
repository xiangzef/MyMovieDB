from scraper import scrape_movie
import sys
import json

sys.stdout.reconfigure(encoding='utf-8')

codes = ["SSIS-254", "JUFE-238"]

for code in codes:
    print(f"\n{'='*60}")
    print(f"Testing: {code}")
    print('='*60)
    result = scrape_movie(code, save_cover=False)
    if result:
        print(f"Code: {result.get('code')}")
        print(f"Title JP: {result.get('title_jp')}")
        print(f"Title CN: {result.get('title_cn')}")
        print(f"Title: {result.get('title')[:100]}...")
        print(f"Cover: {result.get('cover_url')}")
        print(f"Actors: {result.get('actors')}")
        print(f"Release: {result.get('release_date')}")
        print(f"Genres: {result.get('genres')}")
        print(f"Scrape Status: {result.get('scrape_status')}")
    else:
        print("No result!")
