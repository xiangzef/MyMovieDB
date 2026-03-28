"""爬虫测试脚本 - 测试各个数据源对指定番号的爬取效果"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import requests
from bs4 import BeautifulSoup
import re
import time
import json

# 导入爬虫
from scraper import (
    AvdanyuwikiScraper,
    AvWikiScraper,
    JavDBScraper,
    AvbaseScraper,
    JavBusScraper,
    JavbooksScraper,
    JavhooScraper,
    JavdScraper,
    JavInfoScraper,
    JavcupScraper,
)

# 测试番号
TEST_CODES = [
    "IPZZ-792",
    "GQN-011",
    "JUR-664",
    "IPZZ-776",
]

def test_single_scraper(name, scraper, keyword):
    """测试单个爬虫"""
    try:
        print(f"\n{'='*60}")
        print(f"测试: {name}")
        print(f"关键词: {keyword}")
        print(f"{'='*60}")

        start = time.time()
        result = scraper.search(keyword)
        elapsed = time.time() - start

        if result:
            print(f"[OK] 找到 {len(result)} 个结果 ({elapsed:.1f}s)")
            for i, item in enumerate(result[:3], 1):
                print(f"\n  Result {i}:")
                print(f"    Code: {item.get('code', 'N/A')}")
                print(f"    Title: {item.get('title', 'N/A')[:60]}...")
                if item.get('cover_url'):
                    print(f"    Cover: {item.get('cover_url', '')[:80]}...")
                if item.get('detail_url'):
                    print(f"    URL: {item.get('detail_url', '')[:80]}...")
            return {"status": "success", "count": len(result), "results": result}
        else:
            print(f"[EMPTY] 无结果 ({elapsed:.1f}s)")
            return {"status": "empty", "count": 0}
    except Exception as e:
        print(f"[ERROR] {str(e)[:100]}")
        return {"status": "error", "error": str(e)}


def main():
    """主测试函数"""
    print("\n" + "="*70)
    print(" "*20 + "爬虫功能性测试")
    print("="*70)

    # 定义爬虫
    scrapers = [
        ("Avdanyuwiki (avdanyuwiki.com)", AvdanyuwikiScraper(delay=1.0)),
        ("AV-Wiki (av-wiki.net)", AvWikiScraper(delay=1.0)),
        ("JavDB (javdb564.com)", JavDBScraper(delay=1.0)),
        ("Avbase (avbase.net)", AvbaseScraper(delay=1.0)),
        ("Javbooks (jkk044.com)", JavbooksScraper(delay=1.0)),
        ("Javd (cn.javd.me)", JavdScraper(delay=1.0)),
        ("Javcup (javcup.com)", JavcupScraper(delay=1.0)),
    ]

    all_results = {}

    for code in TEST_CODES:
        print(f"\n\n{'#'*70}")
        print(f"# 测试番号: {code}")
        print(f"{'#'*70}")

        all_results[code] = {}

        # 测试原始番号
        print(f"\n>>> 搜索: {code}")
        for name, scraper in scrapers:
            result = test_single_scraper(name, scraper, code)
            all_results[code][name] = result
            time.sleep(0.5)

        # 对于 GQN-011，额外测试 avgqn00011 格式
        if code == "GQN-011":
            print(f"\n\n{'#'*70}")
            print(f"# 额外测试: GQN00011 (无横杠格式)")
            print(f"{'#'*70}")
            for name, scraper in scrapers:
                if "Avdanyuwiki" in name:
                    result = test_single_scraper(name, scraper, "GQN00011")
                    all_results[code][name + " (GQN00011)"] = result
                    time.sleep(0.5)

    # 总结
    print("\n\n" + "="*70)
    print(" "*25 + "测试结果汇总")
    print("="*70)

    for code in TEST_CODES:
        print(f"\n【{code}】")
        success_count = 0
        for name, result in all_results[code].items():
            if result["status"] == "success":
                success_count += 1
                res = result["results"][0] if result["results"] else {}
                print(f"  [OK] {name.split('(')[0].strip()}: {res.get('code', 'N/A')} - {res.get('title', 'N/A')[:40]}...")
            elif result["status"] == "empty":
                print(f"  [--] {name.split('(')[0].strip()}: 无结果")
            else:
                print(f"  [XX] {name.split('(')[0].strip()}: 错误")
        print(f"  -- 可用: {success_count}/{len(all_results[code])}")

    print("\n" + "="*70)
    print("测试完成!")
    print("="*70)


if __name__ == "__main__":
    main()
