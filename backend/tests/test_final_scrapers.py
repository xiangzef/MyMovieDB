"""
最终爬虫效果测试 - 验证优化后的数据质量
"""
import time
from scraper import EnhancedMultiScraper

def test_final_scrapers():
    """测试优化后的爬虫效果"""
    print("\n" + "="*60)
    print("最终爬虫效果测试")
    print("="*60)
    
    test_codes = [
        "SSIS-254",
        "IPZZ-792",
        "HMN-803",
        "BDSR-55301",
        "SIM-091",
    ]
    
    scraper = EnhancedMultiScraper()
    
    for code in test_codes:
        print(f"\n{'='*60}")
        print(f"测试番号: {code}")
        print(f"{'='*60}")
        
        result = scraper.scrape(code)
        
        if result:
            print(f"✅ 刮削成功")
            print(f"  番号: {result.get('code')}")
            print(f"  标题: {result.get('title_jp', '')[:60]}...")
            print(f"  中文: {result.get('title_cn', '')[:40] if result.get('title_cn') else '未翻译'}")
            print(f"  日期: {result.get('release_date')}")
            print(f"  时长: {result.get('duration')} 分钟")
            print(f"  演员: {result.get('actors', [])}")
            print(f"  男优: {result.get('actors_male', [])}")
            print(f"  导演: {result.get('director')}")
            print(f"  制作: {result.get('maker')}")
            print(f"  发行: {result.get('studio')}")
            print(f"  类型: {result.get('genres', [])[:3]}")
            print(f"  封面: {result.get('cover_url', '')[:60]}...")
            print(f"  来源: {result.get('source', 'unknown')}")
            
            # 计算完整度
            fields = ['code', 'title', 'release_date', 'duration', 'actors', 'cover_url', 'maker', 'studio']
            filled = sum(1 for f in fields if result.get(f))
            print(f"  完整度: {filled}/{len(fields)} ({filled*100//len(fields)}%)")
        else:
            print(f"❌ 刮削失败")
        
        time.sleep(2)
    
    print("\n" + "="*60)
    print("测试完成")
    print("="*60)


if __name__ == "__main__":
    test_final_scrapers()
