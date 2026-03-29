"""
爬虫测试工具 - 统一测试各个数据源
合并自: test_scrapers_optimized.py, test_scrapers_real.py, test_sources.py
"""
import sys
import time
from argparse import ArgumentParser

sys.stdout.reconfigure(encoding='utf-8')

# 添加 backend 到 path
sys.path.insert(0, str(__file__).replace("\\test\\test_scrapers.py", "\\backend"))

from scraper import (
    AvbaseScraper,
    AvWikiScraper,
    JavcupScraper,
    AvdanyuwikiScraper,
    FanzaScraper,
)


def test_single_source(source_name, code="SSIS-254"):
    """测试单个数据源"""
    scrapers = {
        'fanza': FanzaScraper,
        'avbase': AvbaseScraper,
        'av-wiki': AvWikiScraper,
        'javcup': JavcupScraper,
        'avdanyuwiki': AvdanyuwikiScraper,
    }
    
    if source_name not in scrapers:
        print(f"❌ 未知数据源: {source_name}")
        print(f"可用数据源: {', '.join(scrapers.keys())}")
        return
    
    print(f"\n{'='*60}")
    print(f"测试数据源: {source_name.upper()}")
    print(f"测试番号: {code}")
    print(f"{'='*60}\n")
    
    scraper = scrapers[source_name](delay=0.5)
    result = scraper.scrape(code)
    
    if result:
        print(f"✅ 标题: {result.get('title', result.get('title_jp', ''))}")
        print(f"📅 日期: {result.get('release_date')}")
        print(f"🏭 制作商: {result.get('maker')}")
        print(f"🎭 演员: {result.get('actors', [])}")
        print(f"🖼️  封面: {'有' if result.get('cover_url') else '无'}")
        print(f"\n📋 完整结果:")
        for key, value in result.items():
            if value:
                print(f"  {key}: {str(value)[:100]}")
    else:
        print(f"❌ 未找到结果")


def test_all_sources(code="SSIS-254"):
    """测试所有数据源"""
    print(f"\n{'='*60}")
    print(f"测试所有数据源 - 番号: {code}")
    print(f"{'='*60}\n")
    
    sources = [
        ("Fanza", FanzaScraper(delay=0.5)),
        ("Avbase", AvbaseScraper(delay=0.5)),
        ("AV-Wiki", AvWikiScraper(delay=0.5)),
        ("Javcup", JavcupScraper(delay=0.5)),
        ("Avdanyuwiki", AvdanyuwikiScraper(delay=0.5)),
    ]
    
    for name, scraper in sources:
        print(f"\n--- {name} ---")
        start_time = time.time()
        result = scraper.scrape(code)
        elapsed = time.time() - start_time
        
        if result:
            title = result.get('title', result.get('title_jp', ''))[:50]
            actors = result.get('actors', [])
            cover = '有' if result.get('cover_url') else '无'
            print(f"✅ {title}")
            print(f"   演员: {actors[:3] if actors else []} | 封面: {cover} | 耗时: {elapsed:.1f}s")
        else:
            print(f"❌ 未找到 | 耗时: {elapsed:.1f}s")


def test_batch_codes(codes):
    """批量测试多个番号"""
    print(f"\n{'='*60}")
    print(f"批量测试 - {len(codes)} 个番号")
    print(f"{'='*60}\n")
    
    sources = [
        ("Fanza", FanzaScraper(delay=0.5)),
        ("Avbase", AvbaseScraper(delay=0.5)),
        ("AV-Wiki", AvWikiScraper(delay=0.5)),
    ]
    
    for code in codes:
        print(f"\n🎬 番号: {code}")
        found = False
        
        for name, scraper in sources:
            result = scraper.scrape(code)
            if result:
                title = result.get('title', result.get('title_jp', ''))[:40]
                print(f"  ✅ {name}: {title}")
                found = True
                break
        
        if not found:
            print(f"  ❌ 所有数据源均未找到")


if __name__ == "__main__":
    parser = ArgumentParser(description="爬虫测试工具")
    parser.add_argument('command', choices=['single', 'all', 'batch'],
                       help='测试命令: single(单数据源), all(所有数据源), batch(批量番号)')
    parser.add_argument('--source', type=str, help='数据源名称 (fanza/avbase/av-wiki/javcup/avdanyuwiki)')
    parser.add_argument('--code', type=str, default='SSIS-254', help='测试番号')
    parser.add_argument('--codes', type=str, help='批量测试番号（逗号分隔）')
    
    args = parser.parse_args()
    
    if args.command == 'single':
        if not args.source:
            print("❌ 请使用 --source 参数指定数据源")
            sys.exit(1)
        test_single_source(args.source, args.code)
    elif args.command == 'all':
        test_all_sources(args.code)
    elif args.command == 'batch':
        if not args.codes:
            print("❌ 请使用 --codes 参数指定番号列表（逗号分隔）")
            sys.exit(1)
        codes = [c.strip() for c in args.codes.split(',')]
        test_batch_codes(codes)
