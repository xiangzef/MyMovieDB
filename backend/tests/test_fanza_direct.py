"""
单独测试 Fanza 爬虫
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from bs4 import BeautifulSoup
import re

def test_fanza_direct():
    """直接测试 Fanza 页面"""
    print("\n" + "="*60)
    print("测试 Fanza (DMM) 页面")
    print("="*60)
    
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "ja,en;q=0.7",
    })
    
    # 添加年龄验证 Cookie
    session.cookies.set("age_check_done", "1", domain=".dmm.co.jp")
    session.cookies.set("age_check_done", "1", domain="www.dmm.co.jp")
    
    # 测试 URL
    test_urls = [
        "https://www.dmm.co.jp/mono/dvd/-/detail/=/cid=ssis254/",
        "https://www.dmm.co.jp/mono/dvd/-/detail/=/cid=ssis00254/",
    ]
    
    for url in test_urls:
        print(f"\n--- 访问: {url} ---")
        
        try:
            resp = session.get(url, timeout=15)
            print(f"状态码: {resp.status_code}")
            
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.content, "lxml")
                page_text = soup.get_text()
                
                # 检查是否包含番号
                print(f"\n页面文本片段（前1000字符）:")
                print(page_text[:1000])
                
                if "SSIS" in page_text.upper() or "ssis" in page_text.lower():
                    print("✅ 页面包含 SSIS 关键词")
                    
                    # 提取标题
                    print(f"\n标题:")
                    title_tag = soup.select_one("h1, #title")
                    if title_tag:
                        print(f"  {title_tag.get_text(strip=True)[:100]}...")
                    
                    # 提取演员
                    print(f"\n演员:")
                    actor_links = soup.select('a[href*="article=actress"], a[href*="actress"]')
                    if actor_links:
                        for link in actor_links[:5]:
                            print(f"  - {link.get_text(strip=True)}")
                    else:
                        print("  未找到演员信息")
                    
                    # 提取封面
                    print(f"\n封面:")
                    imgs = soup.find_all("img")
                    for img in imgs:
                        src = img.get("src", "") or img.get("data-src", "")
                        if "pics.dmm" in src or "thumbnail" in src:
                            print(f"  {src[:80]}...")
                            break
                    
                    # 提取日期
                    print(f"\n发布日期:")
                    date_match = re.search(r"(\d{4}年\d{2}月\d{2}日)", page_text)
                    if date_match:
                        print(f"  {date_match.group(1)}")
                    
                    # 提取时长
                    print(f"\n时长:")
                    duration_match = re.search(r"(\d+)\s*分", page_text)
                    if duration_match:
                        print(f"  {duration_match.group(1)} 分钟")
                    
                    # 提取制作商
                    print(f"\n制作商:")
                    maker_link = soup.select_one('a[href*="article=maker"]')
                    if maker_link:
                        print(f"  {maker_link.get_text(strip=True)}")
                    
                    # 提取发行商
                    print(f"\n发行商:")
                    label_link = soup.select_one('a[href*="article=label"]')
                    if label_link:
                        print(f"  {label_link.get_text(strip=True)}")
                    
                    # 提取导演
                    print(f"\n导演:")
                    director_link = soup.select_one('a[href*="article=director"]')
                    if director_link:
                        print(f"  {director_link.get_text(strip=True)}")
                    
                    # 提取类型
                    print(f"\n类型:")
                    genre_links = soup.select('a[href*="article=genre"]')
                    if genre_links:
                        for link in genre_links[:5]:
                            print(f"  - {link.get_text(strip=True)}")
                    
                    # 查找表格
                    print(f"\n表格数据:")
                    tables = soup.find_all("table")
                    for i, table in enumerate(tables[:2]):
                        print(f"  表格 {i+1}:")
                        rows = table.find_all("tr")
                        for row in rows[:5]:
                            cells = row.find_all(["th", "td"])
                            if len(cells) >= 2:
                                key = cells[0].get_text(strip=True)
                                value = cells[1].get_text(strip=True)
                                if key and value and len(key) < 20:
                                    print(f"    {key}: {value[:50]}...")
                    
                    # 输出部分页面文本（调试用）
                    print(f"\n页面文本片段（前500字符）:")
                    print(page_text[:500])
                    
                    return  # 找到一个有效的就退出
                
                else:
                    print("❌ 页面不包含 SSIS 关键词（可能是 404）")
            
        except Exception as e:
            print(f"❌ 错误: {e}")


if __name__ == "__main__":
    test_fanza_direct()
