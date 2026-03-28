"""
测试各个爬虫数据源的真实可用性
"""
import sys
import time
from scraper import (
    AvdanyuwikiScraper,
    AvWikiScraper,
    AvbaseScraper,
    JavcupScraper,
)
import requests
from bs4 import BeautifulSoup

def test_avdanyuwiki_variants():
    """测试 Avdanyuwiki 多种番号格式"""
    print("\n" + "="*60)
    print("测试 Avdanyuwiki - 多种番号格式变体")
    print("="*60)
    
    # 测试番号
    test_codes = ["SSIS-254", "SSIS00254", "IPZZ-792", "JNT-001"]
    
    scraper = AvdanyuwikiScraper(delay=0.5)
    
    for code in test_codes:
        print(f"\n--- 测试番号: {code} ---")
        result = scraper.search(code)
        if result:
            print(f"✅ 找到结果:")
            print(f"  番号: {result[0].get('code')}")
            print(f"  标题: {result[0].get('title_jp', '')[:50]}...")
            print(f"  演员: {result[0].get('actors')}")
            print(f"  男优: {result[0].get('actors_male')}")
            print(f"  封面: {result[0].get('cover_url', '')[:60]}...")
        else:
            print("❌ 未找到结果")
        
        time.sleep(1)


def test_avdanyuwiki_direct_access():
    """直接访问 Avdanyuwiki 页面，检查真实结构"""
    print("\n" + "="*60)
    print("测试 Avdanyuwiki - 直接页面访问")
    print("="*60)
    
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "ja,en;q=0.7",
    })
    
    test_urls = [
        "https://avdanyuwiki.com/?s=SSIS-254",
        "https://avdanyuwiki.com/?s=SSIS00254",
        "https://avdanyuwiki.com/?s=IPZZ-792",
    ]
    
    for url in test_urls:
        print(f"\n--- 访问: {url} ---")
        try:
            resp = session.get(url, timeout=15)
            print(f"状态码: {resp.status_code}")
            
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.content, "lxml")
                
                # 检查页面关键内容
                page_text = soup.get_text()
                
                # 查找番号
                import re
                codes = re.findall(r'([A-Z]{2,6}-\d{2,5})', page_text, re.IGNORECASE)
                print(f"找到番号: {set(codes[:5])}")
                
                # 查找标题关键词
                if "SSIS" in page_text.upper():
                    print("✅ 页面包含 SSIS 关键词")
                
                # 查找演员信息
                if "出演" in page_text:
                    print("✅ 页面包含演员信息")
                
                # 查找封面图
                imgs = soup.find_all("img")
                dmm_imgs = [img for img in imgs if "dmm" in (img.get("src", "").lower())]
                print(f"DMM 图片数量: {len(dmm_imgs)}")
                
                # 输出部分页面文本（前500字符）
                print(f"\n页面文本片段:\n{page_text[:500]}...")
                
        except Exception as e:
            print(f"❌ 访问失败: {e}")
        
        time.sleep(2)


def test_avbase_search():
    """测试 Avbase 搜索流程"""
    print("\n" + "="*60)
    print("测试 Avbase - 搜索 + 详情页")
    print("="*60)
    
    test_codes = ["BDSR-55301", "SSIS-254", "HMN-803"]
    
    scraper = AvbaseScraper(delay=0.5)
    
    for code in test_codes:
        print(f"\n--- 测试番号: {code} ---")
        result = scraper.search(code)
        if result:
            print(f"✅ 找到结果:")
            print(f"  详情页: {result[0].get('detail_url')}")
            print(f"  标题: {result[0].get('title', '')[:50]}...")
            print(f"  封面: {result[0].get('cover_url', '')[:60]}...")
        else:
            print("❌ 未找到结果")
        
        time.sleep(1)


def test_av_wiki_search():
    """测试 AV-Wiki 搜索流程"""
    print("\n" + "="*60)
    print("测试 AV-Wiki - 搜索 + 详情页")
    print("="*60)
    
    test_codes = ["SIM-091", "SSIS-254"]
    
    scraper = AvWikiScraper(delay=0.5)
    
    for code in test_codes:
        print(f"\n--- 测试番号: {code} ---")
        result = scraper.search(code)
        if result:
            print(f"✅ 找到结果:")
            print(f"  详情页: {result[0].get('detail_url')}")
            print(f"  标题: {result[0].get('title', '')[:50]}...")
        else:
            print("❌ 未找到结果")
        
        time.sleep(1)


def test_javcup_search():
    """测试 Javcup 搜索流程"""
    print("\n" + "="*60)
    print("测试 Javcup - 搜索")
    print("="*60)
    
    test_codes = ["HMN-803", "SSIS-254"]
    
    scraper = JavcupScraper(delay=0.5)
    
    for code in test_codes:
        print(f"\n--- 测试番号: {code} ---")
        result = scraper.search(code)
        if result:
            print(f"✅ 找到结果:")
            print(f"  详情页: {result[0].get('detail_url')}")
            print(f"  标题: {result[0].get('title', '')[:50]}...")
        else:
            print("❌ 未找到结果")
        
        time.sleep(1)


def test_javbooks_structure():
    """测试 Javbooks 搜索结构"""
    print("\n" + "="*60)
    print("测试 Javbooks - 搜索结构分析")
    print("="*60)
    
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    })
    
    # Javbooks 搜索页
    search_url = "https://jkk044.com/serch_censored.htm"
    
    try:
        print(f"访问搜索页: {search_url}")
        resp = session.get(search_url, timeout=15)
        print(f"状态码: {resp.status_code}")
        
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.content, "lxml")
            
            # 查找搜索表单
            forms = soup.find_all("form")
            print(f"表单数量: {len(forms)}")
            
            for i, form in enumerate(forms):
                action = form.get("action", "")
                method = form.get("method", "GET")
                inputs = form.find_all("input")
                print(f"表单 {i+1}: action={action}, method={method}")
                for inp in inputs:
                    print(f"  - input: name={inp.get('name')}, type={inp.get('type')}")
            
            # 查找 iframe
            iframes = soup.find_all("iframe")
            print(f"iframe 数量: {len(iframes)}")
            for iframe in iframes:
                print(f"  iframe src: {iframe.get('src')}")
        
    except Exception as e:
        print(f"❌ 访问失败: {e}")


def test_javd_structure():
    """测试 Javd 搜索结构"""
    print("\n" + "="*60)
    print("测试 Javd - 搜索结构分析")
    print("="*60)
    
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    })
    
    # Javd 搜索
    search_url = "https://javd.me/search?q=HUBLK-068"
    
    try:
        print(f"访问搜索页: {search_url}")
        resp = session.get(search_url, timeout=15)
        print(f"状态码: {resp.status_code}")
        
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.content, "lxml")
            
            # 检查重定向
            print(f"最终 URL: {resp.url}")
            
            # 查找电影链接
            movie_links = soup.find_all("a", href=lambda x: x and "/movie/" in x)
            print(f"电影链接数量: {len(movie_links)}")
            
            for link in movie_links[:3]:
                print(f"  - {link.get('href')}: {link.get_text(strip=True)[:50]}")
        
    except Exception as e:
        print(f"❌ 访问失败: {e}")


if __name__ == "__main__":
    # 运行所有测试
    print("\n" + "="*60)
    print("爬虫数据源真实可用性测试")
    print("="*60)
    
    # 1. 测试 Avdanyuwiki 多种格式
    test_avdanyuwiki_variants()
    
    # 2. 测试 Avdanyuwiki 直接访问
    test_avdanyuwiki_direct_access()
    
    # 3. 测试 Avbase
    test_avbase_search()
    
    # 4. 测试 AV-Wiki
    test_av_wiki_search()
    
    # 5. 测试 Javcup
    test_javcup_search()
    
    # 6. 测试 Javbooks 结构
    test_javbooks_structure()
    
    # 7. 测试 Javd 结构
    test_javd_structure()
    
    print("\n" + "="*60)
    print("测试完成")
    print("="*60)
