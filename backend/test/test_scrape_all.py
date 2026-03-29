"""
综合刮削测试 - 调用 scrape_movie 验证多番号刮削效果
合并自: test_scraper.py, final_test.py, test_simple.py, test_final_scrapers.py
"""
from scraper import scrape_movie
import sys

sys.stdout.reconfigure(encoding='utf-8')

CODES = ["SSIS-254", "JUFE-238", "ABP-567", "JERA-16", "MIDA-599"]

def test_scrape_all():
    for code in CODES:
        print(f"\n{'='*60}")
        print(f"测试: {code}")
        print('='*60)
        result = scrape_movie(code, save_cover=False)
        if result:
            print(f"标题: {result.get('title', '')[:80]}")
            print(f"封面: {'有' if result.get('cover_url') else '无'}")
            print(f"演员: {result.get('actors', [])}")
            print(f"日期: {result.get('release_date')}")
            print(f"制作: {result.get('maker')}")
            print(f"发行: {result.get('studio')}")
            print(f"时长: {result.get('duration')} 分钟")
            print(f"类型: {result.get('genres', [])[:3]}")
            print(f"状态: {result.get('scrape_status', '')}")
            fields = ['code', 'title', 'release_date', 'duration', 'actors', 'cover_url', 'maker', 'studio']
            filled = sum(1 for f in fields if result.get(f))
            print(f"完整度: {filled}/{len(fields)} ({filled*100//len(fields)}%)")
        else:
            print("❌ 未找到结果")

if __name__ == "__main__":
    test_scrape_all()
