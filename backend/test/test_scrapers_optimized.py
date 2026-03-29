"""
优化爬虫策略测试 - 提取完整信息
"""
import re
import requests
from bs4 import BeautifulSoup
import time

def test_avdanyuwiki_parsing():
    """优化 Avdanyuwiki 解析逻辑"""
    print("\n" + "="*60)
    print("优化 Avdanyuwiki 解析逻辑")
    print("="*60)
    
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "ja,en;q=0.7",
    })
    
    test_codes = ["SSIS-254", "IPZZ-792"]
    
    for code in test_codes:
        print(f"\n--- 测试番号: {code} ---")
        url = f"https://avdanyuwiki.com/?s={code}"
        
        try:
            resp = session.get(url, timeout=15)
            soup = BeautifulSoup(resp.content, "lxml")
            page_text = soup.get_text()
            
            # 清理换行和多余空格
            lines = [line.strip() for line in page_text.split('\n') if line.strip()]
            
            print(f"\n关键行提取：")
            
            # 查找标题行（番号后的第一行长文本）
            title_found = False
            for i, line in enumerate(lines):
                if code.replace("-", "") in line.replace("-", "").upper():
                    print(f"  找到番号行: {line}")
                    # 后续行找标题
                    for j in range(i+1, min(i+10, len(lines))):
                        next_line = lines[j]
                        # 标题特征：长度>20且包含日文
                        if len(next_line) > 20 and any('\u3040' <= c <= '\u30ff' for c in next_line):
                            # 排除非标题行
                            if not any(keyword in next_line for keyword in ["出演", "ジャンル", "メーカー", "配信開始"]):
                                print(f"  ✅ 标题: {next_line[:80]}...")
                                title_found = True
                                break
                    break
            
            # 查找演员信息
            print(f"\n演员信息：")
            for i, line in enumerate(lines):
                if "出演者：" in line or "出演者:" in line:
                    # 提取演员（冒号后到下一个关键词前）
                    actors_text = line.split("出演者")[-1].replace("：", "").replace(":", "").strip()
                    # 查找下一行继续
                    if i+1 < len(lines) and "出演男優" not in lines[i+1]:
                        actors_text += " " + lines[i+1]
                    print(f"  女优: {actors_text}")
                
                if "出演男優：" in line or "出演男優:" in line:
                    males_text = line.split("出演男優")[-1].replace("：", "").replace(":", "").strip()
                    # 查找下一行继续
                    if i+1 < len(lines) and "監督" not in lines[i+1]:
                        males_text += " " + lines[i+1]
                    print(f"  男优: {males_text}")
            
            # 查找封面
            print(f"\n封面图片：")
            imgs = soup.find_all("img")
            for img in imgs:
                src = img.get("src", "") or img.get("data-src", "")
                if "dmm" in src.lower() and "pl" in src:
                    print(f"  ✅ 封面: {src}")
                    break
            
        except Exception as e:
            print(f"❌ 错误: {e}")
        
        time.sleep(2)


def test_avbase_detail():
    """测试 Avbase 详情页提取更多信息"""
    print("\n" + "="*60)
    print("测试 Avbase 详情页信息提取")
    print("="*60)
    
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    })
    
    test_urls = [
        "https://www.avbase.net/works/SSIS-254",
        "https://www.avbase.net/works/IPZZ-792",
    ]
    
    for url in test_urls:
        print(f"\n--- 访问: {url} ---")
        
        try:
            resp = session.get(url, timeout=15)
            soup = BeautifulSoup(resp.content, "lxml")
            page_text = soup.get_text()
            
            # 查找关键信息
            print(f"\n关键信息：")
            
            # 标题
            title_tag = soup.select_one("h1, .title, .work-title")
            if title_tag:
                print(f"  标题: {title_tag.get_text(strip=True)[:80]}...")
            
            # 番号
            code_match = re.search(r'([A-Z]{2,6}-\d{2,5})', page_text, re.IGNORECASE)
            if code_match:
                print(f"  番号: {code_match.group(1).upper()}")
            
            # 日期
            date_match = re.search(r'(\d{4}[-/]\d{2}[-/]\d{2})', page_text)
            if date_match:
                print(f"  日期: {date_match.group(1)}")
            
            # 演员 - 查找所有可能的演员标签
            actor_tags = soup.select(".actor, .actress, .performer, [class*='actor']")
            if actor_tags:
                actors = [tag.get_text(strip=True) for tag in actor_tags if tag.get_text(strip=True)]
                print(f"  演员: {actors}")
            
            # 标签/类型
            genre_tags = soup.select(".genre, .tag, .category, [class*='genre']")
            if genre_tags:
                genres = [tag.get_text(strip=True) for tag in genre_tags if tag.get_text(strip=True)]
                print(f"  类型: {genres[:5]}")
            
            # 封面
            imgs = soup.find_all("img")
            for img in imgs:
                src = img.get("src", "") or img.get("data-src", "")
                if "dmm" in src.lower() or "avbase" in src.lower():
                    if "favicon" not in src and "logo" not in src:
                        print(f"  封面: {src[:80]}...")
                        break
            
            # 查找表格数据
            tables = soup.find_all("table")
            for table in tables:
                rows = table.find_all("tr")
                for row in rows:
                    cells = row.find_all(["th", "td"])
                    if len(cells) >= 2:
                        key = cells[0].get_text(strip=True)
                        value = cells[1].get_text(strip=True)
                        if key and value and len(key) < 20:
                            print(f"  {key}: {value[:50]}...")
            
        except Exception as e:
            print(f"❌ 错误: {e}")
        
        time.sleep(2)


def test_av_wiki_detail():
    """测试 AV-Wiki 详情页提取更多信息"""
    print("\n" + "="*60)
    print("测试 AV-Wiki 详情页信息提取")
    print("="*60)
    
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    })
    
    test_urls = [
        "https://av-wiki.net/ssis-254/",
        "https://av-wiki.net/sim-091/",
    ]
    
    for url in test_urls:
        print(f"\n--- 访问: {url} ---")
        
        try:
            resp = session.get(url, timeout=15)
            soup = BeautifulSoup(resp.content, "lxml")
            page_text = soup.get_text()
            
            print(f"\n关键信息：")
            
            # 标题
            title_tag = soup.select_one("h1, .entry-title")
            if title_tag:
                print(f"  标题: {title_tag.get_text(strip=True)[:80]}...")
            
            # 查找文章内容
            article = soup.select_one("article, .entry-content, .post-content")
            if article:
                article_text = article.get_text()
                
                # 演员
                actor_match = re.search(r'出演[：:]\s*([^\n]+)', article_text)
                if actor_match:
                    print(f"  演员: {actor_match.group(1).strip()}")
                
                # 日期
                date_match = re.search(r'(\d{4}[-/]\d{2}[-/]\d{2})', article_text)
                if date_match:
                    print(f"  日期: {date_match.group(1)}")
                
                # 类型
                genre_section = re.search(r'ジャンル[：:]\s*([^\n]+)', article_text)
                if genre_section:
                    print(f"  类型: {genre_section.group(1).strip()}")
            
            # 封面
            imgs = soup.find_all("img")
            for img in imgs:
                src = img.get("src", "") or img.get("data-src", "")
                if src and "favicon" not in src and "logo" not in src:
                    print(f"  封面: {src[:80]}...")
                    break
            
        except Exception as e:
            print(f"❌ 错误: {e}")
        
        time.sleep(2)


def test_javcup_detail():
    """测试 Javcup 详情页提取更多信息"""
    print("\n" + "="*60)
    print("测试 Javcup 详情页信息提取")
    print("="*60)
    
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    })
    
    test_urls = [
        "https://javcup.com/movie/SSIS-254",
        "https://javcup.com/movie/HMN-803",
    ]
    
    for url in test_urls:
        print(f"\n--- 访问: {url} ---")
        
        try:
            resp = session.get(url, timeout=15)
            soup = BeautifulSoup(resp.content, "lxml")
            page_text = soup.get_text()
            
            print(f"\n关键信息：")
            
            # 标题
            title_tag = soup.select_one("h1, .title, .movie-title")
            if title_tag:
                print(f"  标题: {title_tag.get_text(strip=True)[:80]}...")
            
            # 演员
            actor_tags = soup.select(".actress, .actor, .performer")
            if actor_tags:
                actors = [tag.get_text(strip=True) for tag in actor_tags if tag.get_text(strip=True)]
                print(f"  演员: {actors}")
            
            # 封面
            imgs = soup.find_all("img")
            for img in imgs:
                src = img.get("src", "") or img.get("data-src", "")
                if src and "favicon" not in src and "logo" not in src:
                    print(f"  封面: {src[:80]}...")
                    break
            
        except Exception as e:
            print(f"❌ 错误: {e}")
        
        time.sleep(2)


if __name__ == "__main__":
    print("\n" + "="*60)
    print("优化爬虫策略 - 提取完整信息")
    print("="*60)
    
    # 1. 优化 Avdanyuwiki 解析
    test_avdanyuwiki_parsing()
    
    # 2. 测试 Avbase 详情页
    test_avbase_detail()
    
    # 3. 测试 AV-Wiki 详情页
    test_av_wiki_detail()
    
    # 4. 测试 Javcup 详情页
    test_javcup_detail()
    
    print("\n" + "="*60)
    print("测试完成")
    print("="*60)
