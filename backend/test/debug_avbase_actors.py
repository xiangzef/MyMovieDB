"""
调试 Avbase 演员提取逻辑
"""
import requests
from bs4 import BeautifulSoup
import re

def debug_avbase_actors():
    """调试 Avbase 演员信息提取"""
    print("\n" + "="*60)
    print("调试 Avbase 演员信息提取")
    print("="*60)
    
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    })
    
    test_urls = [
        "https://www.avbase.net/works/SSIS-254",
        "https://www.avbase.net/works/HMN-803",
    ]
    
    for url in test_urls:
        print(f"\n{'='*60}")
        print(f"访问: {url}")
        print(f"{'='*60}")
        
        try:
            resp = session.get(url, timeout=15)
            soup = BeautifulSoup(resp.content, "lxml")
            
            # 查找所有可能包含演员信息的元素
            print(f"\n1. 查找所有链接（可能包含演员）：")
            all_links = soup.find_all("a")
            for link in all_links[:10]:
                href = link.get("href", "")
                text = link.get_text(strip=True)
                if text and len(text) > 1 and len(text) < 20:
                    print(f"  - {text}: {href}")
            
            print(f"\n2. 查找所有 span 标签：")
            spans = soup.find_all("span")
            for span in spans[:10]:
                text = span.get_text(strip=True)
                if text and len(text) > 1 and len(text) < 20:
                    print(f"  - span: {text}")
            
            print(f"\n3. 查找所有 div 标签：")
            divs = soup.find_all("div")
            for div in divs[:5]:
                text = div.get_text(strip=True)
                if text and len(text) > 20 and len(text) < 100:
                    print(f"  - div: {text[:80]}...")
            
            print(f"\n4. 页面纯文本（前1000字符）：")
            page_text = soup.get_text()
            print(page_text[:1000])
            
            print(f"\n5. 查找 'actress' 关键词：")
            if "actress" in page_text.lower():
                print("  ✅ 找到 'actress' 关键词")
                # 提取附近文本
                idx = page_text.lower().find("actress")
                print(f"  上下文: {page_text[max(0, idx-50):idx+100]}")
            
            print(f"\n6. 查找 '出演' 关键词：")
            if "出演" in page_text:
                print("  ✅ 找到 '出演' 关键词")
                idx = page_text.find("出演")
                print(f"  上下文: {page_text[max(0, idx-20):idx+100]}")
            
        except Exception as e:
            print(f"❌ 错误: {e}")


if __name__ == "__main__":
    debug_avbase_actors()
